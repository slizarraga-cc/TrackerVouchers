"""
WebSocket relay de cámara para el flujo IBK.

El navegador del usuario captura su cámara con getUserMedia, envía frames JPEG
vía WebSocket, y el servidor los almacena en la sesión activa de IBK.

Un hilo en ibk.py lee esos frames y los pushea al Chrome remoto via CDP
(Runtime.evaluate), dibujándolos en un canvas cuyo MediaStream es devuelto
por la override de getUserMedia inyectada antes de cargar la página.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from api.session_manager import session_manager

router = APIRouter()


@router.websocket("/ws/camera")
async def camera_relay(websocket: WebSocket):
    await websocket.accept()
    logger.info("Camera relay: cliente conectado")
    try:
        while True:
            frame = await websocket.receive_bytes()
            for banco in ("ibk", "ibk_test"):
                session = session_manager.get_activa(banco)
                if session:
                    session.current_frame = frame
    except WebSocketDisconnect:
        logger.info("Camera relay: cliente desconectado")
    except Exception as e:
        logger.error(f"Camera relay error: {e}")
