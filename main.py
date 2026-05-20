#!/usr/bin/env python3
"""
RPA Bancos - Punto de entrada CLI

BCP:
    python main.py ejecutar --banco bcp --fecha-desde 22/04/2026
    python main.py ejecutar --banco bcp --fecha-desde 01/04/2026 --fecha-hasta 30/04/2026
    python main.py ejecutar --banco bcp --fecha-desde 22/04/2026 --max-pdfs 5

BBVA:
    python main.py ejecutar --banco bbva --fecha-desde 11/05/2026
    python main.py ejecutar --banco bbva --fecha-desde 11/05/2026 --max-pdfs 2
"""

import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# Configurar logger
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")
logger.add("logs/rpa_{time:YYYY-MM-DD}.log", level="DEBUG", rotation="1 day", retention="7 days")

import click
from src.core.driver import get_driver


BANCOS_DISPONIBLES = ["bcp", "bbva"]


@click.group()
def cli():
    """RPA para descarga automatizada de comprobantes bancarios."""
    pass


@cli.command()
@click.option("--banco", default="bcp", type=click.Choice(BANCOS_DISPONIBLES), show_default=True,
              help="Banco a procesar")
@click.option("--fecha-desde", required=True, metavar="DD/MM/YYYY",
              help="Fecha inicio del rango de busqueda")
@click.option("--fecha-hasta", default=None, metavar="DD/MM/YYYY",
              help="Fecha fin del rango (default: igual a --fecha-desde)")
@click.option("--max-pdfs", default=None, type=int,
              help="[Avanzado] Limitar a N PDFs. Sin este parametro descarga todos.")
@click.option("--local", "modo", flag_value="local", default=False,
              help="Usar Chrome local en vez de Selenium Grid")
@click.option("--remoto", "modo", flag_value="remoto",
              help="Usar Selenium Grid remoto via Docker (default)")
def ejecutar(banco: str, fecha_desde: str, fecha_hasta: str, max_pdfs: int, modo: str):
    """Descarga comprobantes del banco indicado para el rango de fechas dado."""

    if not fecha_hasta:
        fecha_hasta = fecha_desde

    usar_remoto = (modo != "local")
    limite_str = str(max_pdfs) if max_pdfs is not None else "todos"

    logger.info(f"Banco: {banco} | {fecha_desde} -> {fecha_hasta} | max={limite_str}")
    logger.info(f"Modo: {'Selenium Grid remoto' if usar_remoto else 'Chrome local'}")

    Path("downloads").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)

    driver = get_driver(remote=usar_remoto)

    try:
        if banco == "bcp":
            _ejecutar_bcp(driver, fecha_desde, fecha_hasta, max_pdfs)
        elif banco == "bbva":
            _ejecutar_bbva(driver, fecha_desde, max_pdfs)
    except KeyboardInterrupt:
        logger.warning("Ejecucion interrumpida por el usuario")
    except Exception as e:
        logger.exception(f"Error no controlado: {e}")
        sys.exit(1)
    finally:
        driver.quit()
        logger.info("Driver cerrado")


def _ejecutar_bcp(driver, fecha_desde: str, fecha_hasta: str, max_pdfs: int):
    from src.banks.bcp.login import BCPLogin
    from src.banks.bcp.flows.descarga_comprobantes import DescargaComprobantes

    BCPLogin(driver).ejecutar()
    DescargaComprobantes(driver).ejecutar(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        max_pdfs=max_pdfs,
    )


def _ejecutar_bbva(driver, fecha: str, max_pdfs: int):
    from src.banks.bbva.login import BBVALogin
    from src.banks.bbva.flows.seguimiento_pagos import SeguimientoPagosMasivos

    BBVALogin(driver).ejecutar()
    SeguimientoPagosMasivos(driver).ejecutar(
        fecha=fecha,
        max_pdfs=max_pdfs,
    )


if __name__ == "__main__":
    cli()
