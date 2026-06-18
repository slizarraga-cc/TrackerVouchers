import io
import os
import re
import zipfile
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

router = APIRouter()

DOWNLOADS_PATH = os.getenv('DOWNLOADS_PATH', '/app/downloads')

BANK_SUFFIXES = ['BCP', 'BBVA', 'SCOTIABANK', 'INTERBANK', 'IBK']

_LIMA = timezone(timedelta(hours=-5))
_DATE_FOLDER_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _detectar_banco(filename: str) -> str:
    upper = filename.upper()
    for banco in BANK_SUFFIXES:
        if f' {banco}.' in upper or f'-{banco}.' in upper or f' {banco} ' in upper:
            return banco
    return 'OTRO'


def _mtime_a_fecha(mtime: float) -> str:
    """Convierte mtime Unix a fecha YYYY-MM-DD en hora Lima (UTC-5)."""
    return datetime.fromtimestamp(mtime, tz=_LIMA).strftime('%Y-%m-%d')


def _safe_path(ruta: str) -> str:
    """Convierte ruta relativa a path absoluto seguro dentro de DOWNLOADS_PATH."""
    parts = [p for p in ruta.replace('\\', '/').split('/') if p and p != '..']
    return os.path.join(DOWNLOADS_PATH, *parts)


def _listar_pdfs() -> list[dict]:
    """Lista todos los PDFs recursivamente, incluyendo subcarpetas de fecha."""
    archivos = []
    try:
        for dirpath, dirnames, filenames in os.walk(DOWNLOADS_PATH):
            dirnames.sort()
            rel_dir = os.path.relpath(dirpath, DOWNLOADS_PATH)
            # Usar el nombre de la carpeta como fecha si coincide con YYYY-MM-DD
            folder_fecha = rel_dir if _DATE_FOLDER_RE.match(rel_dir) else None

            for nombre in sorted(filenames):
                if not nombre.lower().endswith('.pdf'):
                    continue
                full_path = os.path.join(dirpath, nombre)
                stat = os.stat(full_path)
                ruta = nombre if rel_dir == '.' else f'{rel_dir}/{nombre}'
                fecha = folder_fecha if folder_fecha else _mtime_a_fecha(stat.st_mtime)
                archivos.append({
                    'nombre':     nombre,
                    'ruta':       ruta,
                    'banco':      _detectar_banco(nombre),
                    'size':       stat.st_size,
                    'modificado': stat.st_mtime,
                    'fecha':      fecha,
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
            path = _safe_path(doc['ruta'])
            try:
                zf.write(path, doc['ruta'])
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
    """Elimina todos los PDFs del directorio de descargas (incluye subcarpetas)."""
    eliminados = 0
    try:
        for dirpath, _, filenames in os.walk(DOWNLOADS_PATH):
            for nombre in filenames:
                if nombre.lower().endswith('.pdf'):
                    os.remove(os.path.join(dirpath, nombre))
                    eliminados += 1
    except FileNotFoundError:
        pass
    return {'eliminados': eliminados}


@router.get('/{ruta:path}')
def descargar_archivo(ruta: str):
    """Descarga un PDF individual. Acepta rutas con subcarpeta (ej: 2026-06-15/archivo.pdf)."""
    path = _safe_path(ruta)
    # Verificar que el path resuelto sigue dentro de DOWNLOADS_PATH
    if not os.path.realpath(path).startswith(os.path.realpath(DOWNLOADS_PATH)):
        raise HTTPException(400, 'Ruta inválida')
    if not os.path.isfile(path):
        raise HTTPException(404, 'Archivo no encontrado')
    nombre = os.path.basename(path)
    return FileResponse(path, media_type='application/pdf', filename=nombre)
