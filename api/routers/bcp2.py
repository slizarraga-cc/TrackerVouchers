import asyncio
import os
import threading
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

DOWNLOADS_PATH = os.getenv('DOWNLOADS_PATH', '/app/downloads')
SELENIUM_GRID_URL_BCP2 = os.getenv('SELENIUM_GRID_URL_BCP2', 'http://selenium-bcp2:4444')
LOGS_PATH = os.getenv('LOGS_PATH', '/app/logs')

from api.session_manager import session_manager, SessionStatus, Session

router = APIRouter()

# Maps thread_id → active Session to route loguru output per session
_thread_sessions: dict[int, Session] = {}
_ts_lock = threading.Lock()


def _session_sink(message):
    """Global loguru sink: routes log records to the session running on that thread."""
    tid = message.record["thread"].id
    with _ts_lock:
        session = _thread_sessions.get(tid)
    if session:
        session.logs.append(message.record["message"])


# Register the sink once at import time
logger.add(_session_sink, format="{message}", level="DEBUG")


# ---------------------------------------------------------------------------
# Diagnostico de DOM en error
# ---------------------------------------------------------------------------

def _capturar_dom_en_error(session: Session, banco: str = 'BCP2') -> None:
    if not session.driver:
        return
    try:
        url = session.driver.current_url
        try:
            os.makedirs(LOGS_PATH, exist_ok=True)
            ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(LOGS_PATH, f"dom_error_{banco}_{ts}.html")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"<!-- URL: {url} -->\n")
                f.write(session.driver.page_source)
            logger.debug(f"[DOM-ERROR] Source completo guardado en: {filepath}")
        except Exception as save_err:
            logger.debug(f"[DOM-ERROR] No se pudo guardar el archivo: {save_err}")
    except Exception as dom_err:
        logger.debug(f"[DOM-ERROR] No se pudo capturar el DOM: {dom_err}")


# ---------------------------------------------------------------------------
# Background flow — modo libre directo
# ---------------------------------------------------------------------------

def _run_libre(session: Session):
    thread_id = threading.current_thread().ident
    with _ts_lock:
        _thread_sessions[thread_id] = session

    try:
        from src.core.driver import get_driver
        from src.banks.bcp.selectors import BCPSelectors as S

        logger.info("Conectando al Selenium Grid BCP2 (modo libre)...")
        driver = get_driver(remote=True, grid_url=SELENIUM_GRID_URL_BCP2)
        session.driver = driver

        logger.info("Navegando al portal BCP2...")
        driver.get(S.LOGIN_URL)

        session.status = SessionStatus.LIBRE
        logger.info("Modo libre activo. Navega libremente e inspecciona el DOM cuando quieras.")

    except Exception as e:
        session.status = SessionStatus.ERROR
        session.error = str(e)
        logger.error(f"Error al iniciar modo libre: {e}")
    finally:
        with _ts_lock:
            _thread_sessions.pop(thread_id, None)
        if session.driver and session.status != SessionStatus.LIBRE:
            try:
                session.driver.quit()
            except Exception:
                pass
            session.driver = None


# ---------------------------------------------------------------------------
# Background flow
# ---------------------------------------------------------------------------

def _run_flow(session: Session, fecha: str, max_pdfs: int):
    thread_id = threading.current_thread().ident
    with _ts_lock:
        _thread_sessions[thread_id] = session

    try:
        from src.core.driver import get_driver
        from src.banks.bcp.selectors import BCPSelectors as S
        from src.banks.bcp.flows.descarga_comprobantes import DescargaComprobantes

        logger.info("Conectando al Selenium Grid BCP2...")
        driver = get_driver(remote=True, grid_url=SELENIUM_GRID_URL_BCP2)
        session.driver = driver

        logger.info("Navegando a la pagina de login BCP2...")
        driver.get(S.LOGIN_URL)

        session.status = SessionStatus.ESPERANDO_LOGIN
        logger.info(
            "Pagina de login abierta. "
            "Completa el ingreso en el visor y luego haz clic en 'Confirmar login'."
        )

        # Keep-alive loop while waiting for manual login
        while not session.login_event.wait(timeout=30):
            if session.cancel_event.is_set():
                session.status = SessionStatus.CANCELADO
                logger.info("Sesion cancelada por el usuario.")
                return
            try:
                driver.execute_script("return document.readyState;")
                logger.debug("[keep-alive] Sesion activa en Selenium Grid BCP2")
            except Exception:
                session.status = SessionStatus.ERROR
                session.error = "Conexion con el navegador perdida durante la espera del login."
                logger.error(session.error)
                return

        if session.cancel_event.is_set():
            session.status = SessionStatus.CANCELADO
            logger.info("Sesion cancelada por el usuario.")
            return

        session.status = SessionStatus.EJECUTANDO
        logger.info("Login confirmado. Iniciando descarga de comprobantes BCP2...")

        flow = DescargaComprobantes(driver, downloads_path=DOWNLOADS_PATH, logs_path=LOGS_PATH)
        descargados = flow.ejecutar(fecha=fecha, max_pdfs=max_pdfs)

        session.resultado = descargados
        session.status = SessionStatus.COMPLETADO
        logger.success(f"Completado: {descargados} PDF(s) descargados.")

    except Exception as e:
        session.status = SessionStatus.LIBRE
        session.error = str(e)
        logger.error(f"Error inesperado: {e}")
        logger.warning(
            "Flujo detenido con error. Navegador en MODO LIBRE — "
            "puedes navegar e inspeccionar el DOM. Usa 'Capturar DOM' para guardar el estado actual."
        )
        _capturar_dom_en_error(session, banco='BCP2')
    finally:
        with _ts_lock:
            _thread_sessions.pop(thread_id, None)
        if session.driver and session.status != SessionStatus.LIBRE:
            try:
                session.driver.quit()
            except Exception:
                pass
            session.driver = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get('/sesion-activa')
def sesion_activa():
    session = session_manager.get_activa("bcp2")
    if not session:
        return {"session_id": None, "status": None, "resultado": None, "error": None}
    return {
        "session_id": session.id,
        "status":     session.status.value,
        "resultado":  session.resultado,
        "error":      session.error,
    }


class IniciarRequest(BaseModel):
    fecha: str  # DD/MM/YYYY
    max_pdfs: int | None = None


@router.post("/iniciar-libre")
def iniciar_libre():
    activa = session_manager.get_activa("bcp2")
    if activa:
        raise HTTPException(
            400,
            f"Ya hay una sesion de BCP2 en curso ({activa.status}). "
            "Cancelala antes de iniciar una nueva.",
        )
    session = session_manager.crear("bcp2")
    t = threading.Thread(target=_run_libre, args=(session,), daemon=True)
    t.start()
    return {"session_id": session.id, "status": session.status.value}


@router.post("/iniciar")
def iniciar(req: IniciarRequest):
    activa = session_manager.get_activa("bcp2")
    if activa:
        raise HTTPException(
            400,
            f"Ya hay una sesion de BCP2 en curso ({activa.status}). "
            "Cancelala antes de iniciar una nueva.",
        )

    session = session_manager.crear("bcp2")
    t = threading.Thread(
        target=_run_flow,
        args=(session, req.fecha, req.max_pdfs),
        daemon=True,
    )
    t.start()
    return {"session_id": session.id, "status": session.status.value}


@router.post("/{session_id}/confirmar-login")
def confirmar_login(session_id: str):
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(404, "Sesion no encontrada")
    if session.status != SessionStatus.ESPERANDO_LOGIN:
        raise HTTPException(400, f"Estado actual no permite confirmar login: {session.status}")
    session.login_event.set()
    return {"ok": True}


@router.post("/{session_id}/cancelar")
def cancelar(session_id: str):
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(404, "Sesion no encontrada")
    session.cancel_event.set()
    session.login_event.set()  # desbloquea si estaba esperando
    if session.status == SessionStatus.LIBRE and session.driver:
        try:
            session.driver.quit()
        except Exception:
            pass
        session.driver = None
    session.status = SessionStatus.CANCELADO
    return {"ok": True}


@router.post("/{session_id}/capturar-dom")
def capturar_dom(session_id: str):
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(404, "Sesion no encontrada")
    if not session.driver:
        raise HTTPException(400, "No hay navegador activo para capturar DOM")
    try:
        os.makedirs(LOGS_PATH, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dom_captura_BCP2_{ts}.html"
        filepath = os.path.join(LOGS_PATH, filename)
        url = session.driver.current_url
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"<!-- URL: {url} -->\n")
            f.write(session.driver.page_source)
        logger.info(f"DOM capturado manualmente: {filename}")
        return {"ok": True, "filename": filename, "url": url}
    except Exception as e:
        raise HTTPException(500, f"Error capturando DOM: {e}")


@router.get("/{session_id}/status")
def get_status(session_id: str):
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(404, "Sesion no encontrada")
    return {
        "session_id": session.id,
        "status": session.status.value,
        "resultado": session.resultado,
        "error": session.error,
        "log_count": len(session.logs),
    }


@router.get("/{session_id}/logs")
async def logs_sse(session_id: str):
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(404, "Sesion no encontrada")

    _TERMINAL_STATUSES = {SessionStatus.COMPLETADO, SessionStatus.ERROR, SessionStatus.CANCELADO}

    async def event_generator():
        sent = 0
        while True:
            while sent < len(session.logs):
                yield f"data: {session.logs[sent]}\n\n"
                sent += 1

            yield f"event: status\ndata: {session.status.value}\n\n"

            if session.status in _TERMINAL_STATUSES:
                while sent < len(session.logs):
                    yield f"data: {session.logs[sent]}\n\n"
                    sent += 1
                yield f"event: status\ndata: {session.status.value}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
