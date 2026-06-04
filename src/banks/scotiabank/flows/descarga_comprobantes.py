"""
Flujo: Descarga de comprobantes — Scotiabank Peru Empresas
Portal: bancainternetempresas.scotiabank.com.pe

Logica general:
  1. Navegar a Consultas → General de Saldos (via menu superior).
  2. Para cada cuenta (000-3991288 soles, 000-4728397 dolares):
     a. Abrir lista de movimientos de la cuenta.
     b. Aplicar filtro de fecha.
     c. Para cada fila que cumpla (concepto valido + importe negativo):
        - Leer monto desde data-amountformatted antes de hacer click.
        - Click en la fila → abre modal de detalle.
        - Guardar PDF via CDP Page.printToPDF (sin dialogo nativo).
        - Cerrar modal.
  3. Retornar total de PDFs guardados.

Convencion de nombre de archivo:
  {monto_sin_signo_ni_moneda} Scotiabank.pdf
  Ej: "S/ -5,831.02" → "5,831.02 Scotiabank.pdf"

PDF via CDP:
  Se usa driver.execute_cdp_cmd("Page.printToPDF", ...) que aplica los estilos
  @media print de la pagina (el modal suele ser el unico contenido visible al imprimir)
  y guarda el resultado directamente sin abrir ningun dialogo del sistema operativo.
  Si CDP falla (Grid sin soporte de CDP tunneling), el movimiento se registra como
  pendiente manual y la ejecucion continua con el siguiente.

Referencias de selectores: src/banks/scotiabank/selectors.py
"""

import base64
import os
import re
import time
from datetime import datetime
from typing import Optional

from loguru import logger
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.banks.scotiabank.selectors import ScotiabankSelectors as S
from src.core.base_flow import BaseFlow

LOGS_PATH = os.getenv("LOGS_PATH", "/app/logs")


class DescargaComprobantes(BaseFlow):

    def __init__(self, driver: WebDriver, timeout: int = 15, downloads_path: str = "/home/seluser/Downloads"):
        super().__init__(driver, timeout)
        self._downloads_path = downloads_path
        self._pendientes_manual: list[dict] = []  # movimientos que no se pudieron guardar via CDP

    # ------------------------------------------------------------------
    # Diagnostico DOM
    # ------------------------------------------------------------------

    def _guardar_dom(self, nombre: str) -> None:
        """Guarda page_source + screenshot en LOGS_PATH para inspeccion de selectores."""
        try:
            os.makedirs(LOGS_PATH, exist_ok=True)
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            slug = nombre.replace(" ", "_").replace("/", "-")
            html_path = os.path.join(LOGS_PATH, f"dom_SCOT_{slug}_{ts}.html")
            png_path  = os.path.join(LOGS_PATH, f"dom_SCOT_{slug}_{ts}.png")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(f"<!-- URL: {self.driver.current_url} | {nombre} -->\n")
                f.write(self.driver.page_source)
            self.driver.save_screenshot(png_path)
            logger.info(f"[DOM] '{nombre}' guardado -> {html_path} | {png_path}")
        except Exception as e:
            logger.warning(f"[DOM] No se pudo guardar '{nombre}': {e}")

    def ejecutar(self, fecha: str, max_pdfs: Optional[int] = None) -> int:
        """
        Ejecuta el flujo completo.

        Args:
            fecha:    Fecha en formato DD/MM/YYYY.
            max_pdfs: Limite total de PDFs. None = sin limite.

        Returns:
            Cantidad de PDFs guardados exitosamente.
        """
        logger.info(f"Iniciando DescargaComprobantes Scotiabank | fecha: {fecha} | max: {max_pdfs or 'sin limite'}")

        self._navegar_a_general_saldos()

        total_guardados = 0
        for cuenta in S.CUENTAS:
            if max_pdfs is not None and total_guardados >= max_pdfs:
                break
            restante = (max_pdfs - total_guardados) if max_pdfs is not None else None
            guardados = self._procesar_cuenta(cuenta["numero"], cuenta["moneda"], fecha, restante)
            total_guardados += guardados
            logger.info(f"Cuenta {cuenta['numero']} ({cuenta['moneda']}): {guardados} PDF(s) guardados")

        if self._pendientes_manual:
            logger.warning(
                f"{len(self._pendientes_manual)} movimiento(s) requieren guardado manual "
                "(CDP no disponible). Ver logs para detalles."
            )
            for p in self._pendientes_manual:
                logger.info(
                    f"[MANUAL] Cuenta {p['cuenta']} | {p['fecha']} | {p['concepto']} | "
                    f"Importe: {p['importe']} | Nombre sugerido: {p['nombre_archivo']}"
                )

        logger.success(f"Flujo Scotiabank finalizado: {total_guardados} PDF(s) guardados")
        return total_guardados

    # ------------------------------------------------------------------
    # Navegacion
    # ------------------------------------------------------------------

    def _navegar_a_general_saldos(self) -> None:
        """
        Abre el menu Consultas y hace clic en General de Saldos.

        Estrategia 1 — CSS directo al enlace por href="#C1000-consultas" (ALTA).
        Estrategia 2 — click en menu Consultas (texto) + submenu por CSS.
        Estrategia 3 — click_js_shadow por texto (fallback shadow DOM).
        """
        self._guardar_dom("post_login")

        # Estrategia 1: link directo si ya esta visible
        if self.elemento_presente_js(S.LINK_GENERAL_SALDOS):
            if self.click_js_css(S.LINK_GENERAL_SALDOS):
                self.esperar(2)
                logger.info("Navegado a General de Saldos (link directo)")
                self._guardar_dom("general_saldos")
                return

        # Estrategia 2: abrir menu primero
        if self.elemento_presente(S.MENU_CONSULTAS, timeout=8):
            self.click_xpath(S.MENU_CONSULTAS)
            self.esperar(1)
            self._guardar_dom("menu_consultas_abierto")
            if self.elemento_presente_js(S.LINK_GENERAL_SALDOS):
                self.click_js_css(S.LINK_GENERAL_SALDOS)
                self.esperar(2)
                logger.info("Navegado a General de Saldos (menu → submenu)")
                self._guardar_dom("general_saldos")
                return

        # Estrategia 3: shadow DOM
        if self.click_js_shadow("General de Saldos"):
            self.esperar(2)
            logger.info("Navegado a General de Saldos (shadow DOM)")
            self._guardar_dom("general_saldos")
            return

        self._guardar_dom("general_saldos_fallido")
        raise RuntimeError(
            "No se pudo navegar a General de Saldos. "
            "Verifica que el login fue exitoso y el menu esta disponible."
        )

    def _abrir_movimientos_cuenta(self, numero: str, indice: int) -> None:
        """
        Hace clic en el boton 'Ver' de la cuenta indicada.

        Estrategia 1 — XPath por data-account + a.viewMovements (ALTA).
        Estrategia 2 — XPath posicional por indice de aparicion (1 o 2).
        """
        xpath_especifico = S.link_ver_cuenta(numero)
        if self.elemento_presente(xpath_especifico, timeout=10):
            self.click_xpath(xpath_especifico)
            self.esperar(3)
            logger.info(f"Cuenta {numero}: movimientos abiertos (data-account)")
            self._guardar_dom(f"movimientos_{numero}")
            return

        # Fallback posicional
        xpath_pos = S.BTN_VER_PRIMERO if indice == 0 else S.BTN_VER_SEGUNDO
        if self.elemento_presente(xpath_pos, timeout=5):
            self.click_xpath(xpath_pos)
            self.esperar(3)
            logger.info(f"Cuenta {numero}: movimientos abiertos (posicion {indice + 1})")
            self._guardar_dom(f"movimientos_{numero}")
            return

        self._guardar_dom(f"movimientos_{numero}_fallido")
        raise RuntimeError(f"No se pudo abrir los movimientos de la cuenta {numero}")

    def _aplicar_filtro_fecha(self, fecha: str) -> None:
        """
        Abre el panel de filtro, ingresa la fecha inicio y fin, y aplica.

        Los inputs usan jQuery UI Datepicker → send_keys funciona directamente.
        Si send_keys falla, se usa JS como fallback.
        """
        # Abrir panel de filtros
        if not self.elemento_presente(S.BTN_FILTRAR, timeout=8):
            raise RuntimeError("No se encontro el boton 'FILTRAR Y MOSTRAR'")
        self.click_xpath(S.BTN_FILTRAR)
        self.esperar(1.5)
        logger.debug("Panel de filtros abierto")

        # Ingresar fecha inicio y fin (misma fecha)
        for xpath, etiqueta in [(S.INPUT_FECHA_DESDE, "desde"), (S.INPUT_FECHA_HASTA, "hasta")]:
            self._ingresar_fecha_input(xpath, fecha, etiqueta)
        self.esperar(0.5)

        self._guardar_dom("antes_filtro")

        # Aplicar filtro
        if not self.elemento_presente(S.BTN_APLICAR_FILTRO, timeout=5):
            self._guardar_dom("filtro_boton_aplicar_no_encontrado")
            raise RuntimeError("No se encontro el boton 'APLICAR'")
        self.click_xpath(S.BTN_APLICAR_FILTRO)
        self.esperar(4)
        logger.info(f"Filtro aplicado: {fecha}")
        self._guardar_dom("post_filtro")

    def _ingresar_fecha_input(self, xpath: str, fecha: str, etiqueta: str) -> None:
        """Ingresa fecha en un input de datepicker jQuery UI."""
        try:
            inp = self.esperar_elemento(xpath, timeout=8)
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", inp)
            self.liberar_modificadores()
            inp.click()
            inp.send_keys(Keys.CONTROL + "a")
            inp.send_keys(Keys.DELETE)
            inp.send_keys(fecha)
            inp.send_keys(Keys.ESCAPE)
            logger.debug(f"Fecha {etiqueta}: '{fecha}' ingresada (send_keys)")
        except Exception:
            # Fallback JS nativeInputValueSetter
            script = """
            const inputs = document.evaluate(
                arguments[0], document, null,
                XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
            const input = inputs.snapshotItem(0);
            if (!input) return false;
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            setter.call(input, arguments[1]);
            input.dispatchEvent(new Event('input',  { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
            """
            ok = self.driver.execute_script(script, xpath, fecha)
            logger.debug(f"Fecha {etiqueta}: '{fecha}' ingresada (JS, ok={ok})")

    def _volver_a_general_saldos(self) -> None:
        """
        Regresa a la pantalla principal de cuentas (General de Saldos).
        Intenta el boton Regresar; fallback: browser back; fallback: menu.
        """
        btn_regresar = '//a[normalize-space()="Regresar"] | //button[normalize-space()="Regresar"]'
        if self.elemento_presente(btn_regresar, timeout=4):
            self.click_xpath(btn_regresar)
            self.esperar(2)
            logger.debug("Regresado a General de Saldos (boton Regresar)")
            return

        self.volver_atras()
        self.esperar(2)
        logger.debug("Regresado a General de Saldos (browser back)")

    # ------------------------------------------------------------------
    # Procesamiento de filas
    # ------------------------------------------------------------------

    def _procesar_cuenta(self, numero: str, moneda: str, fecha: str, max_pdfs: Optional[int] = None) -> int:
        """Procesa todas las filas validas de una cuenta. Retorna PDFs guardados."""
        logger.info(f"--- Procesando cuenta {numero} ({moneda}) ---")

        cuentas_lista = S.CUENTAS
        indice = next((i for i, c in enumerate(cuentas_lista) if c["numero"] == numero), 0)
        self._abrir_movimientos_cuenta(numero, indice)
        self._aplicar_filtro_fecha(fecha)

        guardados = self._guardar_comprobantes_filas_validas(numero, fecha, max_pdfs)

        self._volver_a_general_saldos()
        return guardados

    def _obtener_filas(self) -> list:
        """Retorna todas las filas de movimiento del DOM actual."""
        return self.driver.find_elements(By.CSS_SELECTOR, S.FILA_MOVIMIENTO)

    def _fila_es_valida(self, fila) -> bool:
        """
        Retorna True si la fila cumple ambas condiciones:
          1. Concepto en CONCEPTOS_VALIDOS
          2. Importe negativo (contiene '-')
        """
        concepto = (fila.get_attribute(S.ATTR_CONCEPTO) or "").strip()
        importe  = (fila.get_attribute(S.ATTR_IMPORTE_FMT) or "").strip()
        es_valido = concepto in S.CONCEPTOS_VALIDOS and "-" in importe
        if not es_valido:
            logger.debug(f"Fila omitida: concepto='{concepto}' importe='{importe}'")
        return es_valido

    def _guardar_comprobantes_filas_validas(self, numero_cuenta: str, fecha: str, max_pdfs: Optional[int] = None) -> int:
        """
        Itera sobre las filas validas y guarda el PDF de cada una.
        Re-fetch de filas tras cada modal para evitar referencias stale.
        """
        guardados = 0
        indice = 0

        while True:
            filas = self._obtener_filas()
            if not filas:
                logger.info("Sin filas en la tabla")
                break

            # Recolectar datos de filas validas en esta pasada (para evitar stale refs)
            filas_validas = []
            for fila in filas:
                if self._fila_es_valida(fila):
                    filas_validas.append({
                        "concepto": (fila.get_attribute(S.ATTR_CONCEPTO) or "").strip(),
                        "importe":  (fila.get_attribute(S.ATTR_IMPORTE_FMT) or "").strip(),
                        # Guardamos referencia al elemento para el click posterior
                        "_el": fila,
                    })

            if indice >= len(filas_validas):
                logger.info(f"Todas las filas validas procesadas ({len(filas_validas)} total)")
                break

            datos = filas_validas[indice]
            nombre = self._monto_a_nombre(datos["importe"])
            logger.info(
                f"Procesando fila {indice + 1}/{len(filas_validas)} | "
                f"{datos['concepto']} | {datos['importe']} → {nombre}.pdf"
            )

            try:
                self._abrir_modal(datos["_el"])
                self._guardar_dom(f"modal_detalle_{indice + 1}")
                guardado = self._guardar_pdf(nombre + ".pdf")
                if guardado:
                    guardados += 1
                else:
                    self._pendientes_manual.append({
                        "cuenta":      numero_cuenta,
                        "fecha":       fecha,
                        "concepto":    datos["concepto"],
                        "importe":     datos["importe"],
                        "nombre_archivo": nombre + ".pdf",
                    })
            except Exception as e:
                logger.error(f"Error en fila {indice + 1}: {e}")
                self._pendientes_manual.append({
                    "cuenta":      numero_cuenta,
                    "fecha":       fecha,
                    "concepto":    datos["concepto"],
                    "importe":     datos["importe"],
                    "nombre_archivo": nombre + ".pdf",
                })
            finally:
                self._cerrar_modal()
                self.esperar(1)

            indice += 1

            if max_pdfs is not None and guardados >= max_pdfs:
                logger.info(f"Limite de {max_pdfs} PDFs alcanzado")
                break

        return guardados

    # ------------------------------------------------------------------
    # Modal de detalle
    # ------------------------------------------------------------------

    def _abrir_modal(self, fila) -> None:
        """
        Hace click en la fila para abrir el modal de detalle.
        Espera hasta que el modal sea visible en el DOM.
        """
        self.click_js(fila)
        self.esperar(2)

        # Esperar visibilidad del modal
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, S.MODAL_DETALLE))
            )
            logger.debug("Modal de detalle abierto")
        except Exception:
            # Puede que el modal no tenga clase "in" estrictamente; verificar presencia
            if not self.elemento_presente_js(S.MODAL_DETALLE):
                raise RuntimeError("Modal de detalle no se abrio tras click en la fila")
            logger.debug("Modal presente (sin clase 'in')")

    def _cerrar_modal(self) -> None:
        """
        Cierra el modal con el boton X (Bootstrap .close).
        Fallback: tecla Escape.
        """
        if self.elemento_presente_js(S.BTN_CERRAR_MODAL):
            self.click_js_css(S.BTN_CERRAR_MODAL)
            self.esperar(1)
            logger.debug("Modal cerrado (boton X)")
            return

        if self.elemento_presente(S.BTN_CERRAR_XPATH, timeout=3):
            self.click_xpath(S.BTN_CERRAR_XPATH)
            self.esperar(1)
            logger.debug("Modal cerrado (XPath boton close)")
            return

        # Fallback Escape
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            self.esperar(1)
            logger.debug("Modal cerrado (Escape)")
        except Exception as e:
            logger.warning(f"No se pudo cerrar el modal: {e}")

    # ------------------------------------------------------------------
    # PDF via CDP
    # ------------------------------------------------------------------

    def _guardar_pdf(self, nombre_archivo: str) -> bool:
        """
        Guarda la pagina actual (con modal visible) como PDF usando CDP Page.printToPDF.
        Los estilos @media print de Scotiabank focalizan el contenido del modal.

        Retorna True si el archivo fue guardado exitosamente.
        """
        try:
            # Bloquear window.print nativo para evitar dialogo si el boton lo dispara
            self.driver.execute_script("window.print = function(){};")

            result = self.driver.execute_cdp_cmd("Page.printToPDF", {
                "landscape":        False,
                "printBackground":  True,
                "preferCSSPageSize": True,
                "paperWidth":       8.27,    # A4 en pulgadas
                "paperHeight":      11.69,
                "marginTop":        0.4,
                "marginBottom":     0.4,
                "marginLeft":       0.4,
                "marginRight":      0.4,
            })

            pdf_bytes = base64.b64decode(result["data"])
            ruta = os.path.join(self._downloads_path, nombre_archivo)
            os.makedirs(self._downloads_path, exist_ok=True)
            with open(ruta, "wb") as f:
                f.write(pdf_bytes)

            logger.info(f"PDF guardado: {nombre_archivo} ({len(pdf_bytes):,} bytes)")
            return True

        except Exception as e:
            logger.warning(
                f"CDP Page.printToPDF fallo para '{nombre_archivo}': {e}. "
                "El movimiento se registrara como pendiente manual."
            )
            self._guardar_dom(f"pdf_cdp_error_{nombre_archivo[:30]}")
            return False

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def _monto_a_nombre(self, importe_formateado: str) -> str:
        """
        Convierte el importe formateado al nombre base del archivo.

        Ejemplos:
          "S/ -5,831.02" → "5,831.02 Scotiabank"
          "$ -37.82"     → "37.82 Scotiabank"
          ""             → "sin_monto Scotiabank"
        """
        if not importe_formateado:
            return "sin_monto Scotiabank"

        # Eliminar simbolos de moneda, espacios, signo negativo
        limpio = importe_formateado
        for token in ["S/", "$", " "]:
            limpio = limpio.replace(token, "")
        limpio = limpio.replace("-", "").strip()

        # Eliminar caracteres no validos en nombres de archivo
        limpio = re.sub(r'[<>:"/\\|?*]', "_", limpio)

        return f"{limpio} Scotiabank"
