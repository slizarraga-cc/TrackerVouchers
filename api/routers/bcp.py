import asyncio
import os
import threading
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

DOWNLOADS_PATH = os.getenv('DOWNLOADS_PATH', '/app/downloads')
SELENIUM_GRID_URL_BCP = os.getenv('SELENIUM_GRID_URL_BCP', 'http://selenium-bcp:4444')
LOGS_PATH = os.getenv('LOGS_PATH', '/app/logs')


def _renombrar_pdfs_nuevos(pdfs_previos: set, banco: str) -> None:
    """Renombra los PDFs nuevos agregando indice y sufijo del banco.
    Resultado: '1.nombre BCP.pdf', '2.nombre BCP.pdf', ...
    El orden del indice sigue el orden de descarga (fecha de modificacion).
    """
    try:
        pdfs_actuales = {f for f in os.listdir(DOWNLOADS_PATH) if f.lower().endswith('.pdf')}
        nuevos = pdfs_actuales - pdfs_previos
        sufijo = f' {banco}.pdf'
        # Ordenar por fecha de modificacion para respetar el orden de descarga
        nuevos_ordenados = sorted(
            nuevos,
            key=lambda f: os.path.getmtime(os.path.join(DOWNLOADS_PATH, f))
        )
        for i, nombre in enumerate(nuevos_ordenados, start=1):
            if not nombre.upper().endswith(f' {banco.upper()}.PDF') and not nombre.endswith(sufijo):
                base = nombre[:-4]  # quitar .pdf
                nuevo = f"{i}.{base}{sufijo}"
                os.rename(
                    os.path.join(DOWNLOADS_PATH, nombre),
                    os.path.join(DOWNLOADS_PATH, nuevo),
                )
                logger.info(f"Renombrado: {nombre} -> {nuevo}")
    except Exception as e:
        logger.warning(f"No se pudo renombrar PDFs: {e}")

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

def _capturar_dom_en_error(session: Session, banco: str = 'BCP') -> None:
    """
    Captura el estado del DOM cuando ocurre un error:
    - Loguea un resumen de los elementos clave (visible en el frontend).
    - Guarda el page source completo en logs/dom_error_<banco>_<timestamp>.html
      para inspeccion manual.
    """
    if not session.driver:
        return
    try:
        url = session.driver.current_url
        script = """
        function outerOrEmpty(sel) {
            const el = document.querySelector(sel);
            return el ? el.outerHTML.slice(0, 2000) : null;
        }
        return {
            url:     document.location.href,
            title:   document.title,
            section: outerOrEmpty('#cells-template-bbva-btge-menurization-landing-solution'),
            sidebar: outerOrEmpty('bbva-btge-sidebar-menu'),
            body_head: document.body ? document.body.outerHTML.slice(0, 500) : null,
        };
        """
        info = session.driver.execute_script(script)
        logger.debug(f"[DOM-ERROR] URL: {info.get('url')} | Title: {info.get('title')}")

        if info.get('section'):
            logger.debug(f"[DOM-ERROR] seccion menurization (primeros 2000 chars):\n{info['section']}")
        elif info.get('sidebar'):
            logger.debug(f"[DOM-ERROR] sidebar (primeros 2000 chars):\n{info['sidebar']}")
        else:
            logger.debug(f"[DOM-ERROR] body head:\n{info.get('body_head')}")

        # Guardar source completo en archivo para inspeccion
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
# Background flow
# ---------------------------------------------------------------------------

def _run_flow(session: Session, fecha_desde: str, fecha_hasta: str, max_pdfs: int):
    thread_id = threading.current_thread().ident
    with _ts_lock:
        _thread_sessions[thread_id] = session

    try:
        from src.core.driver import get_driver
        from src.banks.bcp.selectors import BCPSelectors as S
        from src.banks.bcp.flows.descarga_comprobantes import DescargaComprobantes

        logger.info("Conectando al Selenium Grid...")
        driver = get_driver(remote=True, grid_url=SELENIUM_GRID_URL_BCP)
        session.driver = driver

        logger.info("Navegando a la pagina de login BCP...")
        driver.get(S.LOGIN_URL)

        # Registrar PDFs existentes antes del flujo para detectar los nuevos al final
        pdfs_previos: set = set()
        try:
            pdfs_previos = {f for f in os.listdir(DOWNLOADS_PATH) if f.lower().endswith('.pdf')}
        except Exception:
            pass

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
                logger.debug("[keep-alive] Sesion activa en Selenium Grid")
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
        logger.info("Login confirmado. Iniciando descarga de comprobantes...")

        flow = DescargaComprobantes(driver, downloads_path=DOWNLOADS_PATH)
        descargados = flow.ejecutar(
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            max_pdfs=max_pdfs,
        )

        session.resultado = descargados
        session.status = SessionStatus.COMPLETADO
        logger.success(f"Completado: {descargados} PDF(s) descargados.")

    except Exception as e:
        session.status = SessionStatus.ERROR
        session.error = str(e)
        logger.error(f"Error inesperado: {e}")
        _capturar_dom_en_error(session, banco='BCP')
    finally:
        with _ts_lock:
            _thread_sessions.pop(thread_id, None)
        if session.driver:
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
    """Devuelve la sesion activa de BCP (no terminal), o nulls si no existe."""
    session = session_manager.get_activa("bcp")
    if not session:
        return {"session_id": None, "status": None, "resultado": None, "error": None}
    return {
        "session_id": session.id,
        "status":     session.status.value,
        "resultado":  session.resultado,
        "error":      session.error,
    }


class IniciarRequest(BaseModel):
    fecha_desde: str  # DD/MM/YYYY
    fecha_hasta: str  # DD/MM/YYYY
    max_pdfs: int | None = None


@router.post("/iniciar")
def iniciar(req: IniciarRequest):
    activa = session_manager.get_activa("bcp")
    if activa:
        raise HTTPException(
            400,
            f"Ya hay una sesion de BCP en curso ({activa.status}). "
            "Cancelala antes de iniciar una nueva.",
        )

    session = session_manager.crear("bcp")
    t = threading.Thread(
        target=_run_flow,
        args=(session, req.fecha_desde, req.fecha_hasta, req.max_pdfs),
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
    session.status = SessionStatus.CANCELADO
    return {"ok": True}


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
            # Flush any new log lines
            while sent < len(session.logs):
                yield f"data: {session.logs[sent]}\n\n"
                sent += 1

            # Send current status
            yield f"event: status\ndata: {session.status.value}\n\n"

            if session.status in _TERMINAL_STATUSES:
                # Drain any remaining logs before closing
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
