import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import bcp, bcp2, bbva, ibk, scotiabank, documentos, camera

app = FastAPI(title="Tesoreria RPA", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bcp.router,        prefix="/api/bcp",        tags=["BCP"])
app.include_router(bcp2.router,       prefix="/api/bcp2",       tags=["BCP2"])
app.include_router(bbva.router,       prefix="/api/bbva",       tags=["BBVA"])
app.include_router(ibk.router,        prefix="/api/ibk",        tags=["IBK"])
app.include_router(scotiabank.router, prefix="/api/scotiabank", tags=["Scotiabank"])
app.include_router(documentos.router, prefix="/api/documentos", tags=["Documentos"])
app.include_router(camera.router,    tags=["Camera"])


@app.get("/api/config")
def config():
    """Expone configuracion publica para el frontend."""
    return {
        "vnc_password": os.getenv("VNC_PASSWORD", "rpa123"),
        "vnc_ports": {
            "bcp":        int(os.getenv("VNC_PORT_BCP",        "7901")),
            "bcp2":       int(os.getenv("VNC_PORT_BCP2",       "7905")),
            "bbva":       int(os.getenv("VNC_PORT_BBVA",       "7902")),
            "ibk":        int(os.getenv("VNC_PORT_IBK",        "7903")),
            "scotiabank": int(os.getenv("VNC_PORT_SCOTIABANK", "7904")),
        },
    }


@app.get("/api/health")
def health():
    return {"ok": True}
