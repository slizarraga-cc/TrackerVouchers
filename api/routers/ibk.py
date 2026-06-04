import asyncio
import base64
import os
import threading
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from api.session_manager import session_manager, SessionStatus, Session

DOWNLOADS_PATH        = os.getenv('DOWNLOADS_PATH', '/app/downloads')
SELENIUM_GRID_URL_IBK = os.getenv('SELENIUM_GRID_URL_IBK', 'http://selenium-ibk:4444')
LOGS_PATH             = os.getenv('LOGS_PATH', '/app/logs')
DEBUG_MODE            = os.getenv('DEBUG', 'false').lower() == 'true'

router = APIRouter()

# JS inyectado en cada nuevo documento del Chrome IBK.
# Crea un canvas cuyo MediaStream se devuelve en cada llamada a getUserMedia,
# permitiendo que el Python relay dibuje frames reales del usuario sobre él.
_CAMERA_INJECT_JS = """
(function() {
    const canvas = document.createElement('canvas');
    canvas.width = 640;
    canvas.height = 480;
    const ctx = canvas.getContext('2d');
    // Pre-llenar con negro para que el stream no sea "vacío"
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, 640, 480);
    window.__cameraCtx = ctx;
    const stream = canvas.captureStream(15);

    // Parchear track para que parezca cámara real
    const track = stream.getVideoTracks()[0];
    if (track) {
        track.getCapabilities = () => ({
            aspectRatio: { max: 300, min: 0.005 },
            deviceId: 'virtual-cam',
            facingMode: ['user'],
            frameRate: { max: 60, min: 1 },
            groupId: 'virtual-group',
            height: { max: 1080, min: 1 },
            width: { max: 1920, min: 1 },
            resizeMode: ['none', 'crop-and-scale'],
        });
        track.getSettings = () => ({
            aspectRatio: 1.333,
            deviceId: 'virtual-cam',
            facingMode: 'user',
            frameRate: 15,
            groupId: 'virtual-group',
            height: 480,
            width: 640,
            resizeMode: 'none',
        });
    }

    if (navigator.mediaDevices) {
        navigator.mediaDevices.getUserMedia = async function(constraints) {
            if (constraints && constraints.video) return stream;
            throw Object.assign(new Error('No camera'), { name: 'NotFoundError' });
        };
        const origEnum = navigator.mediaDevices.enumerateDevices.bind(navigator.mediaDevices);
        navigator.mediaDevices.enumerateDevices = async function() {
            const devs = await origEnum();
            if (!devs.some(d => d.kind === 'videoinput')) {
                devs.push({ deviceId: 'virtual-cam', kind: 'videoinput', label: 'Virtual Camera', groupId: 'virtual-group' });
            }
            return devs;
        };
    }

    // API legacy por si IBK usa navigator.getUserMedia
    if (!navigator.getUserMedia && navigator.mediaDevices) {
        navigator.getUserMedia = (constraints, success, error) => {
            navigator.mediaDevices.getUserMedia(constraints).then(success).catch(error);
        };
    }
})();
"""

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
        url = session.driver.current_url
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
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(LOGS_PATH, f"dom_error_IBK_{ts}.html")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"<!-- URL: {url} -->\n")
                f.write(session.driver.page_source)
            logger.debug(f"[DOM-ERROR] Source guardado en: {filepath}")
        except Exception as save_err:
            logger.debug(f"[DOM-ERROR] No se pudo guardar el archivo: {save_err}")
    except Exception as dom_err:
        logger.debug(f"[DOM-ERROR] No se pudo capturar el DOM: {dom_err}")


def _relay_camera_frames(session: Session, driver, stop_event: threading.Event) -> None:
    """Hilo que pushea frames del usuario al canvas inyectado en Chrome-IBK via CDP."""
    while not stop_event.is_set():
        frame = session.current_frame
        if frame is not None:
            frame_b64 = base64.b64encode(frame).decode("ascii")
            try:
                driver.execute_cdp_cmd("Runtime.evaluate", {
                    "expression": (
                        "if(window.__cameraCtx){"
                        "const i=new Image();"
                        "i.onload=()=>window.__cameraCtx.drawImage(i,0,0,640,480);"
                        f"i.src='data:image/jpeg;base64,{frame_b64}';"
                        "}"
                    ),
                    "awaitPromise": False,
                })
            except Exception:
                pass
        time.sleep(0.1)  # 10 fps es suficiente para validación biométrica


def _run_flow(session: Session, fecha_inicio: str, fecha_fin: str, max_pdfs):
    thread_id = threading.current_thread().ident
    with _ts_lock:
        _thread_sessions[thread_id] = session

    stop_relay = threading.Event()

    try:
        from src.core.driver import get_driver
        from src.banks.ibk.flows.descarga_comprobantes import DescargaComprobantes

        logger.info("Conectando al Selenium Grid IBK...")
        driver = get_driver(remote=True, grid_url=SELENIUM_GRID_URL_IBK, use_camera=True)
        session.driver = driver

        # Inyectar override de getUserMedia en cada nueva página que cargue Chrome
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": _CAMERA_INJECT_JS,
        })
        logger.debug("JS de override de cámara inyectado via CDP")

        # Iniciar hilo que pushea frames del usuario al canvas del Chrome remoto
        relay_thread = threading.Thread(
            target=_relay_camera_frames,
            args=(session, driver, stop_relay),
            daemon=True,
        )
        relay_thread.start()

        logger.info("Navegando al portal Interbank Empresas...")
        driver.get("https://empresas.interbank.pe")

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
                session.error = "Conexion con el navegador perdida durante la espera del login."
                logger.error(session.error)
                return

        if session.cancel_event.is_set():
            session.status = SessionStatus.CANCELADO
            logger.info("Sesion cancelada por el usuario.")
            return

        stop_relay.set()  # La cámara solo se necesita durante el login
        session.current_frame = None

        session.status = SessionStatus.EJECUTANDO
        logger.info("Login confirmado. Iniciando descarga de comprobantes IBK...")

        flow = DescargaComprobantes(driver, downloads_path=DOWNLOADS_PATH)
        descargados = flow.ejecutar(fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, max_pdfs=max_pdfs)

        session.resultado = descargados
        session.status = SessionStatus.COMPLETADO
        logger.success(f"Completado: {descargados} archivo(s) descargados.")

    except Exception as e:
        session.status = SessionStatus.ERROR
        session.error = str(e)
        logger.error(f"Error inesperado: {e}")
        _capturar_dom_en_error(session)
    finally:
        stop_relay.set()
        with _ts_lock:
            _thread_sessions.pop(thread_id, None)
        if session.driver:
            if DEBUG_MODE and session.status == SessionStatus.ERROR:
                logger.warning(
                    "DEBUG=true — navegador IBK mantenido abierto para inspeccion. "
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
    session = session_manager.get_activa("ibk")
    if not session:
        return {"session_id": None, "status": None, "resultado": None, "error": None}
    return {
        "session_id": session.id,
        "status":     session.status.value,
        "resultado":  session.resultado,
        "error":      session.error,
    }


class IniciarRequest(BaseModel):
    fecha_inicio: str        # DD/MM/YYYY
    fecha_fin:    str        # DD/MM/YYYY
    max_pdfs:     int | None = None


@router.post("/iniciar")
def iniciar(req: IniciarRequest):
    activa = session_manager.get_activa("ibk")
    if activa:
        raise HTTPException(
            400,
            f"Ya hay una sesion de IBK en curso ({activa.status}). "
            "Cancelala antes de iniciar una nueva.",
        )

    session = session_manager.crear("ibk")
    t = threading.Thread(
        target=_run_flow,
        args=(session, req.fecha_inicio, req.fecha_fin, req.max_pdfs),
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
