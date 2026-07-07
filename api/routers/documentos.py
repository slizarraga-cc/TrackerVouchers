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

_LIMA = timezone(timedelta(hours=-5))
_DATE_FOLDER_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

# Mapeo de subdirectorio → etiqueta de banco
_BANK_DIR_MAP = {
    'bcp1':       'BCP1',
    'bcp2':       'BCP2',
    'bbva':       'BBVA',
    'ibk':        'IBK',
    'scotiabank': 'SCOTIABANK',
}

# Fallback: detectar banco por sufijo en el nombre del archivo (archivos legacy en raíz)
_BANK_SUFFIXES = ['BCP', 'BBVA', 'SCOTIABANK', 'INTERBANK', 'IBK']


def _detectar_banco(filename: str) -> str:
    upper = filename.upper()
    for banco in _BANK_SUFFIXES:
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
    """Lista todos los PDFs recursivamente, incluyendo subcarpetas de banco y fecha.

    Estructura esperada:
      downloads/
        bcp1/YYYY-MM-DD/archivo.pdf   → banco=BCP1, fecha=YYYY-MM-DD
        bcp2/YYYY-MM-DD/archivo.pdf   → banco=BCP2, fecha=YYYY-MM-DD
        bbva/YYYY-MM-DD/archivo.pdf   → banco=BBVA, fecha=YYYY-MM-DD
        ibk/archivo.pdf               → banco=IBK,  fecha=mtime
        scotiabank/archivo.pdf        → banco=SCOTIABANK, fecha=mtime
        archivo_legacy.pdf            → banco=detectado por sufijo, fecha=mtime
    """
    archivos = []
    try:
        for dirpath, dirnames, filenames in os.walk(DOWNLOADS_PATH):
            dirnames.sort()
            rel_dir = os.path.relpath(dirpath, DOWNLOADS_PATH)
            parts = rel_dir.split(os.sep) if rel_dir != '.' else []

            # Banco: primer componente del path si está en el mapa de subdirectorios
            banco_dir = _BANK_DIR_MAP.get(parts[0]) if parts else None

            # Fecha: último componente del path si tiene formato YYYY-MM-DD
            folder_fecha = parts[-1] if parts and _DATE_FOLDER_RE.match(parts[-1]) else None

            for nombre in sorted(filenames):
                if not nombre.lower().endswith('.pdf'):
                    continue
                full_path = os.path.join(dirpath, nombre)
                stat = os.stat(full_path)
                ruta = nombre if rel_dir == '.' else f'{rel_dir}/{nombre}'
                fecha = folder_fecha if folder_fecha else _mtime_a_fecha(stat.st_mtime)
                banco = banco_dir if banco_dir else _detectar_banco(nombre)
                archivos.append({
                    'nombre':     nombre,
                    'ruta':       ruta,
                    'banco':      banco,
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
