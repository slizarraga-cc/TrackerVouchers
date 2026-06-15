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

    def ejecutar(self, fecha_desde: str, fecha_hasta: str, max_pdfs: Optional[int] = None) -> int:
        """
        Ejecuta el flujo completo.

        Args:
            fecha_desde: Fecha inicio en formato DD/MM/YYYY.
            fecha_hasta: Fecha fin en formato DD/MM/YYYY.
            max_pdfs:    Limite total de PDFs. None = sin limite.

        Returns:
            Cantidad de PDFs guardados exitosamente.
        """
        logger.info(
            f"Iniciando DescargaComprobantes Scotiabank | "
            f"desde: {fecha_desde} hasta: {fecha_hasta} | max: {max_pdfs or 'sin limite'}"
        )

        self._navegar_a_general_saldos()

        total_guardados = 0
        for cuenta in S.CUENTAS:
            if max_pdfs is not None and total_guardados >= max_pdfs:
                break
            restante = (max_pdfs - total_guardados) if max_pdfs is not None else None
            guardados = self._procesar_cuenta(cuenta["numero"], cuenta["moneda"], fecha_desde, fecha_hasta, restante)
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

    def _abrir_movimientos_cuenta(self, numero: str) -> None:
        """
        Hace clic en el numero de cuenta para abrir su listado de movimientos.

        DOM: <div class="col-sm-12 col-md-5 btn-detail" data-column="2">000-3991288</div>
        Estabilidad ALTA — se busca por texto exacto del numero de cuenta.
        """
        xpath = S.click_numero_cuenta(numero)
        if self.elemento_presente(xpath, timeout=10):
            self.click_xpath(xpath)
            self.esperar(3)
            logger.info(f"Cuenta {numero}: movimientos abiertos (click en numero de cuenta)")
            self._guardar_dom(f"movimientos_{numero}")
            return

        self._guardar_dom(f"movimientos_{numero}_fallido")
        raise RuntimeError(f"No se pudo encontrar el numero de cuenta {numero} en la tabla")

    def _aplicar_filtro_fecha(self, fecha_desde: str, fecha_hasta: str) -> None:
        """
        Abre el panel de filtro, ingresa fecha inicio y fin, y aplica.

        Los inputs usan jQuery UI Datepicker → send_keys funciona directamente.
        Si send_keys falla, se usa JS como fallback.
        """
        # Abrir panel de filtros
        if not self.elemento_presente(S.BTN_FILTRAR, timeout=8):
            raise RuntimeError("No se encontro el boton 'FILTRAR Y MOSTRAR'")
        self.click_xpath(S.BTN_FILTRAR)
        self.esperar(1.5)
        logger.debug("Panel de filtros abierto")

        # Ingresar fecha inicio y fin
        self._ingresar_fecha_input(S.INPUT_FECHA_DESDE, fecha_desde, "desde")
        self._ingresar_fecha_input(S.INPUT_FECHA_HASTA, fecha_hasta, "hasta")
        self.esperar(0.5)

        self._guardar_dom("antes_filtro")

        # Aplicar filtro
        if not self.elemento_presente(S.BTN_APLICAR_FILTRO, timeout=5):
            self._guardar_dom("filtro_boton_aplicar_no_encontrado")
            raise RuntimeError("No se encontro el boton 'APLICAR'")
        self.click_xpath(S.BTN_APLICAR_FILTRO)
        self.esperar(4)
        logger.info(f"Filtro aplicado: {fecha_desde} → {fecha_hasta}")
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
        Regresa a la pantalla de General de Saldos desde la vista de movimientos.

        Estrategia 1 — breadcrumb visible en la pagina de movimientos:
          <ol class="breadcrumb"> ... <a href="#C1000-consultas">General de Saldos</a>
        Estrategia 2 — item del menu Consultas (ID unico navigation-menu-C1000):
          requiere que el menu Consultas este abierto o sea clickeable.
        Estrategia 3 — abrir menu Consultas y luego hacer click en el item.
        """
        # Estrategia 1: breadcrumb directo (disponible en la pagina de movimientos)
        if self.elemento_presente(S.BREADCRUMB_GENERAL_SALDOS, timeout=5):
            self.click_xpath(S.BREADCRUMB_GENERAL_SALDOS)
            self.esperar(2)
            logger.info("Regresado a General de Saldos (breadcrumb)")
            self._guardar_dom("general_saldos_vuelto")
            return

        # Estrategia 2: item del menu si ya esta visible
        if self.elemento_presente(S.MENU_ITEM_GENERAL_SALDOS, timeout=3):
            self.click_xpath(S.MENU_ITEM_GENERAL_SALDOS)
            self.esperar(2)
            logger.info("Regresado a General de Saldos (menu item directo)")
            self._guardar_dom("general_saldos_vuelto")
            return

        # Estrategia 3: abrir menu Consultas y luego click en General de Saldos
        if self.elemento_presente(S.MENU_CONSULTAS, timeout=5):
            self.click_xpath(S.MENU_CONSULTAS)
            self.esperar(1)
            if self.elemento_presente(S.MENU_ITEM_GENERAL_SALDOS, timeout=5):
                self.click_xpath(S.MENU_ITEM_GENERAL_SALDOS)
                self.esperar(2)
                logger.info("Regresado a General de Saldos (menu Consultas → General de Saldos)")
                self._guardar_dom("general_saldos_vuelto")
                return

        self._guardar_dom("volver_general_saldos_fallido")
        raise RuntimeError("No se pudo volver a General de Saldos")

    # ------------------------------------------------------------------
    # Procesamiento de filas
    # ------------------------------------------------------------------

    def _procesar_cuenta(self, numero: str, moneda: str, fecha_desde: str, fecha_hasta: str, max_pdfs: Optional[int] = None) -> int:
        """Procesa todas las filas validas de una cuenta. Retorna PDFs guardados."""
        logger.info(f"--- Procesando cuenta {numero} ({moneda}) ---")

        self._abrir_movimientos_cuenta(numero)
        self._aplicar_filtro_fecha(fecha_desde, fecha_hasta)

        guardados = self._guardar_comprobantes_filas_validas(numero, fecha_desde, max_pdfs)

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
    # PDF via CDP — popup window
    # ------------------------------------------------------------------

    def _guardar_pdf(self, nombre_archivo: str) -> bool:
        """
        Guarda el comprobante como PDF usando CDP Page.printToPDF sobre la
        ventana popup que abre el boton imprimir del portal Scotiabank.

        Flujo:
          1. Registrar ventanas abiertas antes del click.
          2. Bloquear window.print en la ventana popup para que no abra
             el dialogo nativo del sistema operativo.
          3. Hacer click en el boton imprimir (a#print-movement-details).
             El portal abre un popup about:blank con el contenido del
             comprobante ya formateado y llama a window.print() en el.
          4. Esperar a que aparezca la nueva ventana.
          5. Cambiar el foco del driver a la popup.
          6. Ejecutar CDP Page.printToPDF sobre la popup y guardar el archivo.
          7. Cerrar la popup y volver a la ventana principal.

        Retorna True si el archivo fue guardado exitosamente.
        """
        ventana_principal = self.driver.current_window_handle
        ventanas_antes = set(self.driver.window_handles)
        popup_handle = None

        try:
            # Interceptar window.open en la ventana principal ANTES del click.
            # El portal abre el popup via window.open() y llama popup.print()
            # de forma sincrona (o casi). Al sobreescribir window.open aqui,
            # bloqueamos popup.print en el instante de creacion, antes de que
            # cualquier script del popup pueda invocarlo y abrir el dialogo nativo.
            self.driver.execute_script("""
                if (!window._scot_print_intercepted) {
                    window._scot_print_intercepted = true;
                    const _origOpen = window.open.bind(window);
                    window.open = function() {
                        const w = _origOpen.apply(window, arguments);
                        if (w) {
                            try {
                                w.print = function(){};
                                w.close = function(){};
                            } catch(e) {}
                            setTimeout(function(){
                                try {
                                    w.print = function(){};
                                    w.close = function(){};
                                } catch(e) {}
                            }, 0);
                        }
                        return w;
                    };
                }
            """)

            # Click en el boton imprimir — abre popup
            if not self.elemento_presente_js(S.BTN_IMPRIMIR):
                raise RuntimeError("Boton imprimir no encontrado en el modal")
            self.click_js_css(S.BTN_IMPRIMIR)

            # Esperar a que aparezca la nueva ventana (max 10 s)
            for _ in range(20):
                nuevas = set(self.driver.window_handles) - ventanas_antes
                if nuevas:
                    popup_handle = nuevas.pop()
                    break
                time.sleep(0.5)

            if not popup_handle:
                raise RuntimeError("La popup de impresion no se abrio tras el click")

            # Cambiar a la popup
            self.driver.switch_to.window(popup_handle)
            self.esperar(1)

            # Doble seguridad: bloquear window.print dentro de la popup
            self.driver.execute_script("window.print = function(){};")

            # CDP sobre la popup
            result = self.driver.execute_cdp_cmd("Page.printToPDF", {
                "landscape":         False,
                "printBackground":   True,
                "preferCSSPageSize": True,
                "paperWidth":        8.27,   # A4 en pulgadas
                "paperHeight":       11.69,
                "marginTop":         0.4,
                "marginBottom":      0.4,
                "marginLeft":        0.4,
                "marginRight":       0.4,
            })

            pdf_bytes = base64.b64decode(result["data"])
            os.makedirs(self._downloads_path, exist_ok=True)

            # Evitar sobreescribir archivos con el mismo nombre (ej: dos pagos de igual importe).
            # Si "18.30 Scotiabank.pdf" ya existe → usar "18.30 Scotiabank (2).pdf", etc.
            nombre_final = self._nombre_sin_colision(nombre_archivo)
            ruta = os.path.join(self._downloads_path, nombre_final)
            with open(ruta, "wb") as f:
                f.write(pdf_bytes)

            logger.info(f"PDF guardado: {nombre_final} ({len(pdf_bytes):,} bytes)")
            return True

        except Exception as e:
            logger.warning(
                f"CDP Page.printToPDF fallo para '{nombre_archivo}': {e}. "
                "El movimiento se registrara como pendiente manual."
            )
            self._guardar_dom(f"pdf_cdp_error_{nombre_archivo[:30]}")
            return False

        finally:
            # Cerrar la popup si sigue abierta y volver a la ventana principal
            try:
                if popup_handle and popup_handle in self.driver.window_handles:
                    self.driver.close()
            except Exception:
                pass
            try:
                self.driver.switch_to.window(ventana_principal)
            except Exception as e:
                logger.warning(f"No se pudo volver a la ventana principal: {e}")

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def _nombre_sin_colision(self, nombre_archivo: str) -> str:
        """
        Si 'nombre_archivo' ya existe en downloads_path, agrega sufijo numerico
        separado por espacio hasta encontrar un nombre libre.
        Mismo patron que BCP e IBK: "{nombre_base} {contador}.pdf"

        Ejemplos:
          "18.30 Scotiabank.pdf"      → existe → "18.30 Scotiabank 2.pdf"
          "18.30 Scotiabank 2.pdf"    → existe → "18.30 Scotiabank 3.pdf"
        """
        if not os.path.exists(os.path.join(self._downloads_path, nombre_archivo)):
            return nombre_archivo

        base, ext = os.path.splitext(nombre_archivo)
        contador = 2
        while True:
            candidato = f"{base} {contador}{ext}"
            if not os.path.exists(os.path.join(self._downloads_path, candidato)):
                logger.debug(f"Colision de nombre: '{nombre_archivo}' → '{candidato}'")
                return candidato
            contador += 1

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
