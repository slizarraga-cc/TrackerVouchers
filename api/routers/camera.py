"""
WebSocket relay: recibe frames JPEG del navegador del usuario y los pipa a ffmpeg,
que los escribe en /dev/video0 (v4l2loopback) para que Chrome-IBK los lea como cámara.

Flujo:
  Browser (getUserMedia → canvas.toBlob JPEG) → WS /ws/camera → ffmpeg → /dev/video0 → Chrome IBK
"""

import subprocess

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

router = APIRouter()

VIRTUAL_DEVICE = "/dev/video0"
FFMPEG_FPS = "15"


@router.websocket("/ws/camera")
async def camera_relay(websocket: WebSocket):
    await websocket.accept()
    logger.info("Camera relay: cliente conectado")

    proc = subprocess.Popen(
        [
            "ffmpeg",
            "-f", "image2pipe",
            "-vcodec", "mjpeg",
            "-framerate", FFMPEG_FPS,
            "-i", "pipe:0",
            "-f", "v4l2",
            "-pix_fmt", "yuv420p",
            VIRTUAL_DEVICE,
            "-y",
            "-loglevel", "error",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        while True:
            frame = await websocket.receive_bytes()
            try:
                proc.stdin.write(frame)
                proc.stdin.flush()
            except (BrokenPipeError, OSError):
                logger.warning("Camera relay: ffmpeg pipe cerrado inesperadamente")
                break
    except WebSocketDisconnect:
        logger.info("Camera relay: cliente desconectado")
    except Exception as e:
        logger.error(f"Camera relay error: {e}")
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        logger.info("Camera relay: ffmpeg detenido")
