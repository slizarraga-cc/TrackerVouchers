import asyncio
import os
import threading
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from api.session_manager import session_manager, SessionStatus, Session

DOWNLOADS_PATH               = os.getenv('DOWNLOADS_PATH', '/app/downloads')
DOWNLOADS_PATH_SCOTIABANK    = os.path.join(DOWNLOADS_PATH, 'scotiabank')
SELENIUM_GRID_URL_SCOTIABANK = os.getenv('SELENIUM_GRID_URL_SCOTIABANK', 'http://selenium-scotiabank:4444')
LOGS_PATH                    = os.getenv('LOGS_PATH', '/app/logs')
DEBUG_MODE                 = os.getenv('DEBUG', 'false').lower() == 'true'

router = APIRouter()

_thread_sessions: dict[int, Session] = {}
_ts_lock = threading.Lock()


def _session_sink(message):
    tid = message.record["thread"].id
    with _ts_lock:
        session = _thread_sessions.get(tid)
    if session:
        session.logs.append(message.record["message"])


logger.add(_session_sink, format="{message}", level="DEBUG")


def _capturar_dom_en_error(session: Session) -> None:
    if not session.driver:
        return
    try:
        url  = session.driver.current_url
        info = session.driver.execute_script("""
        return {
            url:       document.location.href,
            title:     document.title,
            body_head: document.body ? document.body.outerHTML.slice(0, 500) : null,
        };
        """)
        logger.debug(f"[DOM-ERROR] URL: {info.get('url')} | Title: {info.get('title')}")
        logger.debug(f"[DOM-ERROR] body head:\n{info.get('body_head')}")
        try:
            os.makedirs(LOGS_PATH, exist_ok=True)
            ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(LOGS_PATH, f"dom_error_SCOTIABANK_{ts}.html")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"<!-- URL: {url} -->\n")
                f.write(session.driver.page_source)
            logger.debug(f"[DOM-ERROR] Source guardado en: {filepath}")
        except Exception as save_err:
            logger.debug(f"[DOM-ERROR] No se pudo guardar el archivo: {save_err}")
    except Exception as dom_err:
        logger.debug(f"[DOM-ERROR] No se pudo capturar el DOM: {dom_err}")


def _run_libre(session: Session):
    thread_id = threading.current_thread().ident
    with _ts_lock:
        _thread_sessions[thread_id] = session

    try:
        from src.core.driver import get_driver
        from src.banks.scotiabank.selectors import ScotiabankSelectors as S

        logger.info("Conectando al Selenium Grid Scotiabank (modo libre)...")
        driver = get_driver(remote=True, grid_url=SELENIUM_GRID_URL_SCOTIABANK, download_subdir='scotiabank')
        session.driver = driver

        logger.info("Navegando al portal Scotiabank Empresas...")
        driver.get(S.PORTAL_URL)

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


def _run_flow(session: Session, fecha_desde: str, fecha_hasta: str, max_pdfs: int | None = None):
    thread_id = threading.current_thread().ident
    with _ts_lock:
        _thread_sessions[thread_id] = session

    try:
        from src.core.driver import get_driver
        from src.banks.scotiabank.flows.descarga_comprobantes import DescargaComprobantes
        from src.banks.scotiabank.selectors import ScotiabankSelectors as S

        logger.info("Conectando al Selenium Grid Scotiabank...")
        driver = get_driver(remote=True, grid_url=SELENIUM_GRID_URL_SCOTIABANK, download_subdir='scotiabank')
        session.driver = driver

        logger.info("Navegando al portal Scotiabank Empresas...")
        driver.get(S.PORTAL_URL)

        session.status = SessionStatus.ESPERANDO_LOGIN
        logger.info(
            "Portal abierto. "
            "Completa el ingreso en el visor y luego haz clic en 'Confirmar login'."
        )

        while not session.login_event.wait(timeout=30):
            if session.cancel_event.is_set():
                session.status = SessionStatus.CANCELADO
                logger.info("Sesion cancelada por el usuario.")
                return
            try:
                driver.execute_script("return document.readyState;")
                logger.debug("[keep-alive] Sesion activa en Selenium Grid")
            except Exception:
                session.status = SessionStatus.ERROR
                session.error  = "Conexion con el navegador perdida durante la espera del login."
                logger.error(session.error)
                return

        if session.cancel_event.is_set():
            session.status = SessionStatus.CANCELADO
            logger.info("Sesion cancelada por el usuario.")
            return

        session.status = SessionStatus.EJECUTANDO
        logger.info(f"Login confirmado. Iniciando descarga de comprobantes Scotiabank ({fecha_desde} → {fecha_hasta})...")

        flow = DescargaComprobantes(driver, downloads_path=DOWNLOADS_PATH_SCOTIABANK)
        descargados = flow.ejecutar(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, max_pdfs=max_pdfs)

        session.resultado = descargados
        session.status    = SessionStatus.COMPLETADO
        logger.success(f"Completado: {descargados} archivo(s) descargados.")

    except Exception as e:
        session.status = SessionStatus.LIBRE
        session.error  = str(e)
        logger.error(f"Error inesperado: {e}")
        logger.warning(
            "Flujo detenido con error. Navegador en MODO LIBRE — "
            "puedes navegar e inspeccionar el DOM. Usa 'Capturar DOM' para guardar el estado actual."
        )
        _capturar_dom_en_error(session)
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
    session = session_manager.get_activa("scotiabank")
    if not session:
        return {"session_id": None, "status": None, "resultado": None, "error": None}
    return {
        "session_id": session.id,
        "status":     session.status.value,
        "resultado":  session.resultado,
        "error":      session.error,
    }


class IniciarRequest(BaseModel):
    fechaDesde: str       # DD/MM/YYYY
    fechaHasta: str       # DD/MM/YYYY
    max_pdfs: int | None = None


@router.post("/iniciar-libre")
def iniciar_libre():
    """Abre el navegador directamente en modo libre sin ejecutar ningún flujo."""
    activa = session_manager.get_activa("scotiabank")
    if activa:
        raise HTTPException(
            400,
            f"Ya hay una sesion de Scotiabank en curso ({activa.status}). "
            "Cancelala antes de iniciar una nueva.",
        )
    session = session_manager.crear("scotiabank")
    t = threading.Thread(target=_run_libre, args=(session,), daemon=True)
    t.start()
    return {"session_id": session.id, "status": session.status.value}


@router.post("/iniciar")
def iniciar(req: IniciarRequest):
    activa = session_manager.get_activa("scotiabank")
    if activa:
        raise HTTPException(
            400,
            f"Ya hay una sesion de Scotiabank en curso ({activa.status}). "
            "Cancelala antes de iniciar una nueva.",
        )

    session = session_manager.crear("scotiabank")
    t = threading.Thread(
        target=_run_flow,
        args=(session, req.fechaDesde, req.fechaHasta, req.max_pdfs),
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
    session.login_event.set()
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
    """Captura el DOM de la página actual del navegador y lo guarda en logs/."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(404, "Sesion no encontrada")
    if not session.driver:
        raise HTTPException(400, "No hay navegador activo para capturar DOM")
    try:
        os.makedirs(LOGS_PATH, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dom_captura_SCOTIABANK_{ts}.html"
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
        "status":     session.status.value,
        "resultado":  session.resultado,
        "error":      session.error,
        "log_count":  len(session.logs),
    }


@router.get("/{session_id}/logs")
async def logs_sse(session_id: str):
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(404, "Sesion no encontrada")

    _TERMINAL = {SessionStatus.COMPLETADO, SessionStatus.ERROR, SessionStatus.CANCELADO}

    async def event_generator():
        sent = 0
        while True:
            while sent < len(session.logs):
                yield f"data: {session.logs[sent]}\n\n"
                sent += 1
            yield f"event: status\ndata: {session.status.value}\n\n"
            if session.status in _TERMINAL:
                while sent < len(session.logs):
                    yield f"data: {session.logs[sent]}\n\n"
                    sent += 1
                yield f"event: status\ndata: {session.status.value}\n\n"
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
