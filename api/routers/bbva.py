import asyncio
import os
import threading
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from api.session_manager import session_manager, SessionStatus, Session

DOWNLOADS_PATH = os.getenv('DOWNLOADS_PATH', '/app/downloads')
SELENIUM_GRID_URL_BBVA = os.getenv('SELENIUM_GRID_URL_BBVA', 'http://selenium-bbva:4444')
DEBUG_MODE = os.getenv('DEBUG', 'false').lower() == 'true'

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


def _renombrar_pdfs_nuevos(pdfs_previos: set) -> None:
    try:
        pdfs_actuales = {f for f in os.listdir(DOWNLOADS_PATH) if f.lower().endswith('.pdf')}
        nuevos = pdfs_actuales - pdfs_previos
        sufijo = '-BBVA.pdf'
        for nombre in nuevos:
            if '-BBVA.' not in nombre.upper():
                base = nombre[:-4]
                nuevo = f"{base}{sufijo}"
                os.rename(
                    os.path.join(DOWNLOADS_PATH, nombre),
                    os.path.join(DOWNLOADS_PATH, nuevo),
                )
                logger.info(f"Renombrado: {nombre} -> {nuevo}")
    except Exception as e:
        logger.warning(f"No se pudo renombrar PDFs: {e}")


LOGS_PATH = os.getenv('LOGS_PATH', '/app/logs')


def _capturar_dom_en_error(session: Session) -> None:
    """
    Captura el estado del DOM cuando ocurre un error:
    - Loguea un resumen de los elementos clave en la sesion (visible en el frontend).
    - Guarda el page source completo en logs/dom_error_BBVA_<timestamp>.html
      para inspeccion manual.
    """
    if not session.driver:
        return
    try:
        url     = session.driver.current_url
        script  = """
        function outerOrEmpty(sel) {
            const el = document.querySelector(sel);
            return el ? el.outerHTML.slice(0, 2000) : null;
        }
        return {
            url:        document.location.href,
            title:      document.title,
            section:    outerOrEmpty('#cells-template-bbva-btge-menurization-landing-solution'),
            sidebar:    outerOrEmpty('bbva-btge-sidebar-menu'),
            body_head:  document.body ? document.body.outerHTML.slice(0, 500) : null,
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
            filepath = os.path.join(LOGS_PATH, f"dom_error_BBVA_{ts}.html")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"<!-- URL: {url} -->\n")
                f.write(session.driver.page_source)
            logger.debug(f"[DOM-ERROR] Source completo guardado en: {filepath}")
        except Exception as save_err:
            logger.debug(f"[DOM-ERROR] No se pudo guardar el archivo: {save_err}")

    except Exception as dom_err:
        logger.debug(f"[DOM-ERROR] No se pudo capturar el DOM: {dom_err}")


def _run_flow(session: Session, fecha: str, max_pdfs):
    thread_id = threading.current_thread().ident
    with _ts_lock:
        _thread_sessions[thread_id] = session

    try:
        from src.core.driver import get_driver
        from src.banks.bbva.selectors import BBVASelectors as S
        from src.banks.bbva.flows.seguimiento_pagos import SeguimientoPagosMasivos

        logger.info("Conectando al Selenium Grid...")
        driver = get_driver(remote=True, grid_url=SELENIUM_GRID_URL_BBVA)
        session.driver = driver

        # BBVA Net Cash usa Polymer/Web Components con shadow DOM cerrado por defecto.
        # Parcheamos attachShadow para forzar mode:'open' en cada nuevo documento,
        # incluyendo las rutas SPA que instancian bbva-btge-menurization-landing-solution-page.
        # Sin este parche, el.shadowRoot == null y el traversal JS no puede acceder al menu.
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': """
                (function() {
                    const _orig = Element.prototype.attachShadow;
                    Element.prototype.attachShadow = function(init) {
                        return _orig.call(this, Object.assign({}, init, {mode: 'open'}));
                    };
                })();
            """
        })
        logger.debug("Shadow DOM patch inyectado via CDP (attachShadow -> mode:open)")

        logger.info("Navegando a la pagina de login BBVA...")
        driver.get(S.LOGIN_URL)

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
        logger.info("Login confirmado. Iniciando seguimiento de pagos masivos...")

        flow = SeguimientoPagosMasivos(driver, downloads_path=DOWNLOADS_PATH)
        descargados = flow.ejecutar(fecha=fecha, max_pdfs=max_pdfs)

        session.resultado = descargados
        session.status = SessionStatus.COMPLETADO
        logger.success(f"Completado: {descargados} PDF(s) descargados.")

    except Exception as e:
        session.status = SessionStatus.ERROR
        session.error = str(e)
        logger.error(f"Error inesperado: {e}")
        _capturar_dom_en_error(session)
    finally:
        with _ts_lock:
            _thread_sessions.pop(thread_id, None)
        if session.driver:
            if DEBUG_MODE and session.status == SessionStatus.ERROR:
                logger.warning(
                    "DEBUG=true — navegador BBVA mantenido abierto para inspeccion. "
                    "Cerralo manualmente o reinicia el contenedor."
                )
            else:
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
    session = session_manager.get_activa("bbva")
    if not session:
        return {"session_id": None, "status": None, "resultado": None, "error": None}
    return {
        "session_id": session.id,
        "status":     session.status.value,
        "resultado":  session.resultado,
        "error":      session.error,
    }


class IniciarRequest(BaseModel):
    fecha: str              # DD/MM/YYYY
    max_pdfs: int | None = None


@router.post("/iniciar")
def iniciar(req: IniciarRequest):
    activa = session_manager.get_activa("bbva")
    if activa:
        raise HTTPException(
            400,
            f"Ya hay una sesion de BBVA en curso ({activa.status}). "
            "Cancelala antes de iniciar una nueva.",
        )

    session = session_manager.crear("bbva")
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
    session.login_event.set()
    session.status = SessionStatus.CANCELADO
    return {"ok": True}


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
