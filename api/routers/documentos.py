import io
import os
import zipfile
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

router = APIRouter()

DOWNLOADS_PATH = os.getenv('DOWNLOADS_PATH', '/app/downloads')

BANK_SUFFIXES = ['BCP', 'BBVA', 'SCOTIABANK', 'INTERBANK', 'IBK']

_LIMA = timezone(timedelta(hours=-5))


def _detectar_banco(filename: str) -> str:
    upper = filename.upper()
    for banco in BANK_SUFFIXES:
        if f' {banco}.' in upper or f'-{banco}.' in upper or f' {banco} ' in upper:
            return banco
    return 'OTRO'


def _mtime_a_fecha(mtime: float) -> str:
    """Convierte mtime Unix a fecha YYYY-MM-DD en hora Lima (UTC-5)."""
    return datetime.fromtimestamp(mtime, tz=_LIMA).strftime('%Y-%m-%d')


def _listar_pdfs() -> list[dict]:
    archivos = []
    try:
        for nombre in sorted(os.listdir(DOWNLOADS_PATH)):
            if not nombre.lower().endswith('.pdf'):
                continue
            path = os.path.join(DOWNLOADS_PATH, nombre)
            stat = os.stat(path)
            archivos.append({
                'nombre':     nombre,
                'banco':      _detectar_banco(nombre),
                'size':       stat.st_size,
                'modificado': stat.st_mtime,
                'fecha':      _mtime_a_fecha(stat.st_mtime),
            })
    except FileNotFoundError:
        pass
    return archivos


@router.get('')
def listar():
    return _listar_pdfs()


@router.get('/descargar-todos')
def descargar_todos(fecha: Optional[str] = Query(None, description='Filtrar por fecha YYYY-MM-DD')):
    """Empaqueta los PDFs en un ZIP. Si se indica fecha, solo incluye los de ese dia."""
    docs = _listar_pdfs()
    if fecha:
        docs = [d for d in docs if d['fecha'] == fecha]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for doc in docs:
            path = os.path.join(DOWNLOADS_PATH, doc['nombre'])
            try:
                zf.write(path, doc['nombre'])
            except Exception:
                pass
    buf.seek(0)
    nombre_zip = f'comprobantes_{fecha}.zip' if fecha else 'comprobantes.zip'
    return StreamingResponse(
        buf,
        media_type='application/zip',
        headers={'Content-Disposition': f'attachment; filename="{nombre_zip}"'},
    )


@router.delete('')
def eliminar_todos():
    """Elimina todos los PDFs del directorio de descargas."""
    eliminados = 0
    try:
        for nombre in os.listdir(DOWNLOADS_PATH):
            if nombre.lower().endswith('.pdf'):
                os.remove(os.path.join(DOWNLOADS_PATH, nombre))
                eliminados += 1
    except FileNotFoundError:
        pass
    return {'eliminados': eliminados}


@router.get('/{filename}')
def descargar_archivo(filename: str):
    """Descarga un PDF individual."""
    # Sanitizar para evitar path traversal
    filename = os.path.basename(filename)
    path = os.path.join(DOWNLOADS_PATH, filename)
    if not os.path.isfile(path):
        raise HTTPException(404, 'Archivo no encontrado')
    return FileResponse(path, media_type='application/pdf', filename=filename)
