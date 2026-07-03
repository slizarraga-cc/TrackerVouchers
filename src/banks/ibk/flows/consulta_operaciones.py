"""
Flujo 2: Historial de Pago de Servicios
Banco: Interbank Empresas (empresas.interbank.pe)

Logica general:
  - Navegar a /pagos-transferencias/servicios/historial
  - Obtener todas las cuentas de cargo disponibles en mat-select[data-test="cmbAccount"]
  - Para cada cuenta:
      * Seleccionar la cuenta en el dropdown
      * Ingresar rango de fechas
      * Ejecutar busqueda
      * Por cada fila con estado "Procesada":
          - Click en la lupa (ibk-icon[icon="search"]) para abrir el detalle
          - Extraer fecha del ultimo autorizador (ul[data-test="txtAutoriza"] > li[last()] > span)
          - Extraer monto (ibk-card-description[data-test="lblAmountValue"])
          - Descargar constancia (a[data-test="lnkDownloadConstancy"])
          - Renombrar PDF como "<monto_limpio> IBK.pdf" en subcarpeta YYYY-MM-DD/
          - Click en Regresar
      * Continuar con la siguiente cuenta

Referencias de selectores: src/banks/ibk/selectors.py (seccion FLUJO 2)
Fuente DOM: doms/pagos_servicios.html
            doms/historial_pagos_servicios.html
            doms/busqueda_historial_pago_servicios.html
            doms/historial_pago_detallado.html
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

from src.banks.ibk.selectors import IBKSelectors as S
from src.core.base_flow import BaseFlow

LOGS_PATH = os.getenv("LOGS_PATH", "/app/logs")


class ConsultaOperaciones(BaseFlow):

    def __init__(self, driver: WebDriver, timeout: int = 15, downloads_path: str = "/home/seluser/Downloads"):
        super().__init__(driver, timeout)
        self._downloads_path = downloads_path

    # ------------------------------------------------------------------
    # Diagnostico DOM
    # ------------------------------------------------------------------

    def _guardar_dom(self, nombre: str) -> None:
        try:
            os.makedirs(LOGS_PATH, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            slug = nombre.replace(" ", "_").replace("/", "-")
            html_path = os.path.join(LOGS_PATH, f"dom_IBK_F2_{slug}_{ts}.html")
            png_path  = os.path.join(LOGS_PATH, f"dom_IBK_F2_{slug}_{ts}.png")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(f"<!-- URL: {self.driver.current_url} | {nombre} -->\n")
                f.write(self.driver.page_source)
            self.driver.save_screenshot(png_path)
            logger.info(f"[DOM] '{nombre}' guardado -> {html_path}")
        except Exception as e:
            logger.warning(f"[DOM] No se pudo guardar '{nombre}': {e}")

    # ------------------------------------------------------------------
    # Punto de entrada
    # ------------------------------------------------------------------

    def ejecutar(self, fecha_inicio: str, fecha_fin: str, max_pdfs: Optional[int] = None) -> int:
        """
        Ejecuta el flujo completo de historial de pago de servicios.

        Args:
            fecha_inicio: Fecha inicio en formato DD/MM/YYYY.
            fecha_fin:    Fecha fin en formato DD/MM/YYYY.
            max_pdfs:     Limite total de PDFs. None = sin limite.

        Returns:
            Cantidad de PDFs descargados.
        """
        logger.info(
            f"Iniciando ConsultaOperaciones IBK F2 | "
            f"desde: {fecha_inicio} hasta: {fecha_fin} | max: {max_pdfs or 'sin limite'}"
        )

        self._navegar_a_historial()
        self._guardar_dom("historial_cargado")

        cuentas = self._obtener_cuentas()
        if not cuentas:
            logger.warning("No se encontraron cuentas de cargo disponibles. Abortando.")
            return 0

        logger.info(f"{len(cuentas)} cuenta(s) de cargo encontradas")

        descargados = 0
        for idx, nombre_cuenta in enumerate(cuentas):
            if max_pdfs is not None and descargados >= max_pdfs:
                break

            logger.info(f"--- Cuenta {idx + 1}/{len(cuentas)}: {nombre_cuenta} ---")
            restante = (max_pdfs - descargados) if max_pdfs is not None else None

            try:
                n = self._procesar_cuenta(idx, nombre_cuenta, fecha_inicio, fecha_fin, restante)
                descargados += n
                logger.info(f"Cuenta '{nombre_cuenta}': {n} PDF(s) descargados")
            except Exception as e:
                logger.error(f"Error procesando cuenta '{nombre_cuenta}': {e}")
                self._guardar_dom(f"error_cuenta_{idx + 1}")
                self._navegar_a_historial()

        logger.success(f"Flujo IBK F2 finalizado: {descargados} PDF(s) descargados")
        return descargados

    # ------------------------------------------------------------------
    # Navegacion
    # ------------------------------------------------------------------

    def _navegar_a_historial(self) -> None:
        """Navega directamente a la URL del historial de pago de servicios."""
        self.driver.get(S.SERVICIOS_HISTORIAL_URL)
        self.esperar(3)
        logger.debug(f"Navegado a: {S.SERVICIOS_HISTORIAL_URL}")

    # ------------------------------------------------------------------
    # Cuentas de cargo
    # ------------------------------------------------------------------

    def _obtener_cuentas(self) -> list[str]:
        """
        Abre el mat-select[data-test="cmbAccount"] y obtiene los textos
        de todas las mat-option disponibles. Cierra el dropdown sin seleccionar.

        Returns:
            Lista de nombres de cuenta en el orden en que aparecen.
        """
        try:
            select_el = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, S.SELECT_CUENTA))
            )
            trigger = select_el.find_element(By.CSS_SELECTOR, ".mat-mdc-select-trigger")
            self.click_js(trigger)
            self.esperar(1)
            self._guardar_dom("cuentas_dropdown_abierto")

            opciones = self.driver.find_elements(By.CSS_SELECTOR, "mat-option")
            nombres = [op.text.strip() for op in opciones if op.text.strip()]

            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            self.esperar(0.5)

            logger.debug(f"Cuentas disponibles: {nombres}")
            return nombres
        except Exception as e:
            logger.error(f"No se pudo obtener la lista de cuentas: {e}")
            self._guardar_dom("cuentas_error")
            return []

    def _seleccionar_cuenta(self, indice: int, nombre: str) -> bool:
        """
        Selecciona la cuenta en la posicion `indice` del dropdown cmbAccount.

        Returns:
            True si la seleccion fue exitosa.
        """
        try:
            select_el = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, S.SELECT_CUENTA))
            )
            trigger = select_el.find_element(By.CSS_SELECTOR, ".mat-mdc-select-trigger")
            self.click_js(trigger)
            self.esperar(1)

            opciones = self.driver.find_elements(By.CSS_SELECTOR, "mat-option")
            if indice >= len(opciones):
                logger.warning(f"Indice {indice} fuera de rango ({len(opciones)} opciones)")
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                return False

            self.click_js(opciones[indice])
            self.esperar(1)
            logger.info(f"Cuenta seleccionada [{indice}]: '{nombre}'")
            return True
        except Exception as e:
            logger.error(f"Error seleccionando cuenta '{nombre}': {e}")
            return False

    # ------------------------------------------------------------------
    # Filtros y busqueda
    # ------------------------------------------------------------------

    def _ingresar_fechas(self, fecha_inicio: str, fecha_fin: str) -> None:
        """
        Ingresa el rango de fechas en ibk-datepicker-range-v2.
        Mismo patron que flujo 1: ibk-datepicker-v2//input[@data-mat-calendar].

        NO usar click(): abre el calendario y ESCAPE descarta el valor.
        focus() via JS activa el input sin abrir el calendario.
        TAB confirma (dispara blur → Angular parsea y acepta la fecha).
        """
        for xpath, etiqueta, valor in [
            (S.INPUT_FECHA_INICIO, "inicio", fecha_inicio),
            (S.INPUT_FECHA_FIN,    "fin",    fecha_fin),
        ]:
            try:
                inp = self.esperar_elemento(xpath, timeout=8)
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", inp)
                self.liberar_modificadores()
                # ESCAPE cierra cualquier calendario que haya abierto el TAB anterior
                inp.send_keys(Keys.ESCAPE)
                self.esperar(0.2)
                self.driver.execute_script("arguments[0].focus();", inp)
                self.esperar(0.3)
                inp.send_keys(Keys.CONTROL + "a")
                inp.send_keys(Keys.DELETE)   # limpia el valor default que Angular pone
                inp.send_keys(valor)
                inp.send_keys(Keys.TAB)      # TAB confirma; ESCAPE cancelaria
                self.esperar(0.3)
                logger.debug(f"Fecha {etiqueta}: '{valor}' ingresada (focus+TAB)")
            except Exception:
                ok = self._rellenar_fecha_xpath(xpath, valor)
                logger.debug(f"Fecha {etiqueta}: '{valor}' ingresada (JS fallback, ok={ok})")
        self.esperar(0.5)

    def _rellenar_fecha_xpath(self, xpath: str, valor: str) -> bool:
        """
        Fallback JS: nativeInputValueSetter + input + blur.
        'blur' es necesario para que Angular Material parsee y confirme la fecha.
        """
        script = """
        const inputs = document.evaluate(
            arguments[0], document, null,
            XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null
        );
        const input = inputs.snapshotItem(0);
        if (!input) return false;
        const setter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value').set;
        setter.call(input, arguments[1]);
        input.dispatchEvent(new Event('input',  { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        input.dispatchEvent(new Event('blur',   { bubbles: true }));
        return true;
        """
        return bool(self.driver.execute_script(script, xpath, valor))

    def _ejecutar_busqueda(self) -> None:
        """Click en el boton Buscar (data-test="btnSearch" / type="submit")."""
        xpath_btn = '//*[@data-test="btnSearch"] | //button[@type="submit" and contains(.,"Buscar")]'
        if self.elemento_presente(xpath_btn, timeout=8):
            el = self.esperar_clickeable(xpath_btn)
            self.click_js(el)
            self.esperar(4)
            logger.info("Busqueda ejecutada")
            return

        if self.click_js_shadow("Buscar"):
            self.esperar(4)
            logger.info("Busqueda ejecutada (shadow DOM)")
            return

        raise RuntimeError("No se encontro el boton Buscar en el historial de servicios.")

    # ------------------------------------------------------------------
    # Procesamiento por cuenta
    # ------------------------------------------------------------------

    def _procesar_cuenta(
        self,
        indice: int,
        nombre_cuenta: str,
        fecha_inicio: str,
        fecha_fin: str,
        max_pdfs: Optional[int],
    ) -> int:
        """
        Selecciona la cuenta, aplica filtros, busca y procesa las filas Procesada.
        Al terminar queda posicionado en el historial listo para la siguiente cuenta.
        """
        if indice > 0:
            self._navegar_a_historial()

        if not self._seleccionar_cuenta(indice, nombre_cuenta):
            return 0

        self._ingresar_fechas(fecha_inicio, fecha_fin)
        self._ejecutar_busqueda()
        self._guardar_dom(f"post_busqueda_cuenta_{indice + 1}")

        return self._procesar_filas(nombre_cuenta, max_pdfs)

    # ------------------------------------------------------------------
    # Iteracion de filas
    # ------------------------------------------------------------------

    def _procesar_filas(self, nombre_cuenta: str, max_pdfs: Optional[int]) -> int:
        """
        Itera las ibk-table-row de la tabla de resultados en todas las paginas.
        Solo procesa las filas con estado "Procesada".
        Retorna la cantidad de PDFs descargados.
        """
        descargados = 0
        pagina = 1

        while True:
            filas = self._obtener_filas()

            if not filas:
                logger.info(f"Sin filas en pagina {pagina} para cuenta '{nombre_cuenta}'")
                break

            logger.info(f"[p{pagina}] {len(filas)} fila(s) en tabla")
            indice_fila = 0

            while indice_fila < len(filas):
                if max_pdfs is not None and descargados >= max_pdfs:
                    logger.info(f"Limite de {max_pdfs} PDFs alcanzado")
                    return descargados

                filas = self._obtener_filas()
                if indice_fila >= len(filas):
                    break

                fila = filas[indice_fila]
                estado = self._leer_estado_fila(fila)
                logger.debug(f"[p{pagina}] Fila {indice_fila + 1}/{len(filas)} | Estado: '{estado}'")

                if estado != S.ESTADO_PROCESADA:
                    indice_fila += 1
                    continue

                logger.info(f"[p{pagina}] Procesando fila {indice_fila + 1}")
                try:
                    self._abrir_detalle(fila)
                    self._guardar_dom(f"detalle_p{pagina}_f{indice_fila + 1}")

                    fecha_raw  = self._extraer_fecha_autorizacion()
                    fecha_dir  = self._fecha_a_directorio(fecha_raw)
                    monto      = self._extraer_monto()

                    logger.info(f"Fecha: '{fecha_raw}' | Monto: '{monto}'")

                    pdfs_antes = self._pdfs_actuales()
                    ok = self._descargar_constancia()
                    if ok:
                        self._renombrar_pdf_nuevo(pdfs_antes, monto, descargados + 1, fecha_dir)
                        descargados += 1
                except Exception as e:
                    logger.error(f"Error en fila {indice_fila + 1}: {e}")
                    self._guardar_dom(f"error_p{pagina}_f{indice_fila + 1}")
                finally:
                    self._regresar_historial()
                    self.esperar(2)

                indice_fila += 1

            if self._ir_siguiente_pagina():
                pagina += 1
                self.esperar(3)
                logger.info(f"Avanzando a pagina {pagina}")
            else:
                logger.info("No hay mas paginas.")
                break

        return descargados

    def _obtener_filas(self) -> list:
        """Retorna las ibk-table-row del cuerpo de la tabla de resultados."""
        try:
            tabla = self.driver.find_element(By.CSS_SELECTOR, S.TABLA_SERVICIOS)
            return tabla.find_elements(By.CSS_SELECTOR, "ibk-table-body ibk-table-row")
        except Exception:
            return []

    def _leer_estado_fila(self, fila) -> str:
        """
        Lee el estado desde la celda col[7] (0-based) = ibk-table-cell[8] (1-based).
        Fallback: busca texto conocido en cualquier celda.
        """
        try:
            celdas = fila.find_elements(By.CSS_SELECTOR, "ibk-table-cell")
            if len(celdas) >= 8:
                return celdas[7].text.strip()
            for celda in celdas:
                texto = celda.text.strip()
                if texto in ("Procesada", "Rechazada", "Pendiente", "En proceso", "Anulada"):
                    return texto
        except Exception:
            pass
        return ""

    def _abrir_detalle(self, fila) -> None:
        """
        Click en la lupa (ibk-icon[icon="search"]) de la fila para abrir el detalle.

        Estrategia 1 — ibk-table-cell[9] > ibk-icon[icon="search"] (col 8, 0-based)
        Estrategia 2 — primer ibk-icon[icon="search"] con cursor-pointer en la fila
        Estrategia 3 — click directo en la fila
        """
        try:
            lupa = fila.find_element(By.XPATH, S.BTN_LUPA_SERVICIOS)
            self.click_js(lupa)
            self.esperar(3)
            logger.debug("Detalle abierto (ibk-table-cell[9] lupa)")
            return
        except Exception:
            pass

        try:
            lupa = fila.find_element(By.XPATH, S.BTN_LUPA_SERVICIOS_FALLBACK)
            self.click_js(lupa)
            self.esperar(3)
            logger.debug("Detalle abierto (ibk-icon[search] fallback)")
            return
        except Exception:
            pass

        self.click_js(fila)
        self.esperar(3)
        logger.debug("Detalle abierto (click en fila)")

    # ------------------------------------------------------------------
    # Extraccion de datos del detalle
    # ------------------------------------------------------------------

    def _extraer_fecha_autorizacion(self) -> str:
        """
        Extrae la fecha del ultimo autorizador.

        Estructura DOM (historial_pago_detallado.html):
          ul[data-test="txtAutoriza"] > li* > span " - DD/MM/YYYY | HH:MM:SS P. M. "

        Se toma el ULTIMO li (quien autorizo al final, ej: MATIAS GRUNWALD).
        Retorna el texto raw del span (ej: "- 02/06/2026 | 07:40:20 P. M.").
        Retorna "" si no se encuentra.
        """
        try:
            el = self.esperar_elemento(S.DETALLE_ULTIMO_AUTORIZADOR_FECHA, timeout=8)
            fecha_raw = el.text.strip()
            logger.debug(f"Fecha autorizacion raw: '{fecha_raw}'")
            return fecha_raw
        except Exception as e:
            logger.warning(f"No se pudo extraer fecha del autorizador: {e}")
            return ""

    def _fecha_a_directorio(self, fecha_raw: str) -> str:
        """
        Convierte el texto raw de fecha a formato YYYY-MM-DD para el nombre de carpeta.

        Ejemplos de entrada:
          "- 02/06/2026 | 07:40:20 P. M."  -> "2026-06-02"
          "02/06/2026"                       -> "2026-06-02"

        Retorna "" si no se puede parsear (usara carpeta 'sin-fecha').
        """
        m = re.search(r'(\d{2})/(\d{2})/(\d{4})', fecha_raw)
        if not m:
            return ""
        dia, mes, anio = m.group(1), m.group(2), m.group(3)
        return f"{anio}-{mes}-{dia}"

    def _extraer_monto(self) -> str:
        """
        Extrae el monto del detalle del pago.

        Confirmado en historial_pago_detallado.html:
          ibk-card-description[data-test="lblAmountValue"] -> " S/ 12,642.06 "

        Retorna el texto limpio (ej: "S/ 12,642.06") o "" si no se encuentra.
        """
        try:
            el = self.esperar_elemento(S.DETALLE_MONTO, timeout=8)
            monto = el.text.strip()
            logger.debug(f"Monto extraido: '{monto}'")
            return monto
        except Exception as e:
            logger.warning(f"No se pudo extraer el monto: {e}")
            return ""

    # ------------------------------------------------------------------
    # Descarga del PDF
    # ------------------------------------------------------------------

    def _pdfs_actuales(self) -> set:
        try:
            return {f for f in os.listdir(self._downloads_path) if f.lower().endswith('.pdf')}
        except Exception:
            return set()

    def _descargar_constancia(self) -> bool:
        """
        Descarga la constancia del detalle.

        IBK Angular: click → fetch PDF → Blob → URL.createObjectURL → iframe.src → iframe.contentWindow.print()
        El print() falla con SecurityError cuando el iframe queda cross-origin (chrome bloquea el acceso).

        Estrategia principal (blob_intercept):
          1. Antes del click, sobrescribir URL.createObjectURL para capturar el blob PDF en window.__ibkPdfUrl.
          2. También interceptar HTMLIFrameElement.src por si IBK asigna el blob directamente al iframe.
          3. Suprimir window.print para evitar el dialogo nativo.
          4. Click en el boton.
          5. Esperar hasta 15s que window.__ibkPdfUrl sea asignado.
          6. Disparar descarga via <a href=blob download>.
          7. Esperar el archivo en disco.

        Fallback: CDP Page.printToPDF sobre la pagina de detalle actual.
        """
        # ── Inyectar interceptores ANTES del click ────────────────────────────
        self.driver.execute_script("""
            window.__ibkPdfUrl  = null;
            window.__ibkDiag    = [];   // log de eventos para depuracion

            function _ibkLog(msg) { window.__ibkDiag.push(msg); }

            // Suprimir dialogo de impresion nativo
            window.print = function() { _ibkLog('window.print() llamado'); };

            // Capturar blob PDF al crearse
            const _origCreate = URL.createObjectURL.bind(URL);
            URL.createObjectURL = function(blob) {
                const url = _origCreate(blob);
                const t = ((blob && blob.type) || '').toLowerCase();
                _ibkLog('URL.createObjectURL type=' + t + ' url=' + url.slice(0,60));
                if (t.includes('pdf') || t.includes('octet-stream') || t.includes('application')) {
                    window.__ibkPdfUrl = url;
                }
                return url;
            };

            // Capturar iframe.src
            const _d = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'src');
            if (_d && _d.set) {
                Object.defineProperty(HTMLIFrameElement.prototype, 'src', {
                    set: function(v) {
                        _ibkLog('iframe.src asignado: ' + String(v).slice(0,80));
                        _d.set.call(this, v);
                        if (v && v.startsWith('blob:')) window.__ibkPdfUrl = v;
                    },
                    get: _d.get,
                    configurable: true,
                });
            }

            // Capturar window.open (IBK podria abrir nueva ventana con el PDF)
            const _origOpen = window.open.bind(window);
            window.open = function(url, target, features) {
                _ibkLog('window.open url=' + String(url).slice(0,80) + ' target=' + target);
                if (url && (String(url).includes('pdf') || String(url).startsWith('blob:'))) {
                    window.__ibkPdfUrl = url;
                }
                return _origOpen(url, target, features);
            };

            // Interceptar fetch para loguear respuestas PDF
            const _origFetch = window.fetch.bind(window);
            window.fetch = async function(...args) {
                const url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url) || '';
                _ibkLog('fetch iniciado: ' + String(url).slice(0,80));
                const resp = await _origFetch.apply(this, args);
                const ct = (resp.headers.get('content-type') || '').toLowerCase();
                _ibkLog('fetch respuesta ct=' + ct + ' status=' + resp.status + ' url=' + String(url).slice(0,60));
                if (ct.includes('pdf') || ct.includes('octet-stream')) {
                    const clone = resp.clone();
                    const buf = await clone.arrayBuffer();
                    const blob = new Blob([buf], {type: 'application/pdf'});
                    const blobUrl = _origCreate(blob);
                    _ibkLog('fetch PDF capturado como blob: ' + blobUrl.slice(0,60));
                    window.__ibkPdfUrl = blobUrl;
                }
                return resp;
            };

            // Interceptar XHR para loguear respuestas PDF
            const _origXhrOpen = XMLHttpRequest.prototype.open;
            XMLHttpRequest.prototype.open = function(method, url) {
                this.__ibkUrl = url;
                return _origXhrOpen.apply(this, arguments);
            };
            const _origXhrSend = XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.send = function() {
                this.addEventListener('load', function() {
                    const ct = (this.getResponseHeader('content-type') || '').toLowerCase();
                    _ibkLog('XHR load url=' + String(this.__ibkUrl).slice(0,60) + ' ct=' + ct + ' status=' + this.status);
                    if (ct.includes('pdf') || ct.includes('octet-stream')) {
                        const blob = new Blob([this.response], {type: 'application/pdf'});
                        const blobUrl = _origCreate(blob);
                        _ibkLog('XHR PDF capturado como blob: ' + blobUrl.slice(0,60));
                        window.__ibkPdfUrl = blobUrl;
                    }
                });
                return _origXhrSend.apply(this, arguments);
            };
        """)

        # ── Click en el boton ─────────────────────────────────────────────────
        # IBK usa Angular Zone.js: el handler puede estar en el <a>, en el hijo
        # <ibk-icon> o en un ancestor. click_js() despacha un click sintetico JS
        # que a veces no propaga correctamente. Intentamos 3 estrategias:
        #   1. Click nativo Selenium sobre el <a> (genera mousedown+mouseup+click reales)
        #   2. click_js sobre el <ibk-icon> hijo
        #   3. click_js sobre el <a>
        url_antes = self.driver.current_url
        clicked = False
        try:
            el = self.esperar_elemento(S.BTN_DESCARGAR_CONSTANCIA, timeout=8)
            try:
                el.click()   # click nativo Selenium
                clicked = True
                logger.debug("Click nativo en Descargar constancia")
            except Exception as e_native:
                logger.debug(f"Click nativo fallo ({e_native}), probando hijo ibk-icon...")
                try:
                    icon = el.find_element(By.CSS_SELECTOR, "ibk-icon")
                    self.click_js(icon)
                    clicked = True
                    logger.debug("click_js en ibk-icon hijo")
                except Exception:
                    self.click_js(el)
                    clicked = True
                    logger.debug("click_js fallback en <a>")
        except Exception as e:
            logger.warning(f"No se encontro el boton Descargar constancia: {e}")
            self._guardar_dom("constancia_btn_no_encontrado")
            return False

        url_despues = self.driver.current_url
        logger.debug(f"URL antes={url_antes[-60:]} | despues={url_despues[-60:]}")

        # ── Esperar blob URL o descarga HTTP directa (hasta 15s) ────────────────
        # IBK puede usar blob (URL.createObjectURL) o descarga HTTP directa
        # (Content-Disposition: attachment). Chrome maneja la segunda sin pasar
        # por JS, por lo que __ibkPdfUrl queda null aunque el archivo ya este en disco.
        pdfs_pre = {
            f for f in os.listdir(self._downloads_path)
            if f.lower().endswith('.pdf') and not f.endswith('.crdownload')
        }
        pdf_url = None
        for _ in range(30):
            pdf_url = self.driver.execute_script("return window.__ibkPdfUrl;")
            if pdf_url:
                break
            # Detectar descarga HTTP directa
            pdfs_ahora = {
                f for f in os.listdir(self._downloads_path)
                if f.lower().endswith('.pdf') and not f.endswith('.crdownload')
            }
            if pdfs_ahora - pdfs_pre:
                logger.debug(f"Descarga HTTP directa detectada: {pdfs_ahora - pdfs_pre}")
                return True
            self.esperar(0.5)

        # Volcar log de diagnostico JS al logger de Python
        try:
            diag = self.driver.execute_script("return window.__ibkDiag || [];")
            if diag:
                logger.debug(f"[IBK-DIAG] {len(diag)} evento(s) capturados:")
                for entry in diag:
                    logger.debug(f"  [IBK-DIAG] {entry}")
            else:
                logger.debug("[IBK-DIAG] Sin eventos JS registrados tras el click")
        except Exception as e:
            logger.debug(f"[IBK-DIAG] No se pudo leer diagnostico: {e}")

        if pdf_url:
            logger.debug(f"Blob URL capturada: {pdf_url[:80]}...")
            # Disparar descarga via <a href=blob download>
            self.driver.execute_script("""
                const a = document.createElement('a');
                a.href = arguments[0];
                a.download = '_constancia_ibk_temp.pdf';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            """, pdf_url)

            # Esperar hasta 30s que aparezca el archivo en disco
            deadline = time.time() + 30
            while time.time() < deadline:
                pdfs = {
                    f for f in os.listdir(self._downloads_path)
                    if f.lower().endswith('.pdf') and not f.endswith('.crdownload')
                }
                if pdfs:
                    logger.debug(f"PDF detectado en downloads: {pdfs}")
                    return True
                time.sleep(0.5)

            logger.warning("Timeout esperando descarga (blob URL capturada pero sin archivo en disco)")
            return False

        # ── Fallback: CDP Page.printToPDF ─────────────────────────────────────
        logger.warning("Sin blob URL — fallback CDP Page.printToPDF sobre pagina de detalle")
        try:
            self.driver.execute_cdp_cmd("Emulation.setEmulatedMedia", {"media": "print"})
            self.esperar(1)
            result = self.driver.execute_cdp_cmd("Page.printToPDF", {
                "printBackground": True,
                "paperWidth":  8.27,
                "paperHeight": 11.69,
                "marginTop":    0.4,
                "marginBottom": 0.4,
                "marginLeft":   0.4,
                "marginRight":  0.4,
                "scale": 0.9,
            })
            pdf_bytes = base64.b64decode(result["data"])
            ruta = os.path.join(self._downloads_path, "_constancia_ibk_cdp.pdf")
            os.makedirs(self._downloads_path, exist_ok=True)
            with open(ruta, "wb") as f:
                f.write(pdf_bytes)
            logger.info(f"PDF guardado via CDP fallback: {len(pdf_bytes):,} bytes → {ruta}")
            return True
        except Exception as e:
            logger.error(f"CDP Page.printToPDF fallo: {e}")
            self._guardar_dom("constancia_cdp_error")
            return False
        finally:
            try:
                self.driver.execute_cdp_cmd("Emulation.setEmulatedMedia", {"media": ""})
            except Exception:
                pass

    def _carpeta_fecha(self, fecha: str) -> str:
        """Retorna (y crea) el subdirectorio downloads_path/YYYY-MM-DD/."""
        nombre = fecha if fecha else "sin-fecha"
        ruta = os.path.join(self._downloads_path, nombre)
        os.makedirs(ruta, exist_ok=True)
        return ruta

    def _renombrar_pdf_nuevo(self, pdfs_antes: set, monto: str, indice: int, fecha: str) -> None:
        """
        Espera hasta 30s a que aparezca un PDF nuevo, lo renombra y lo mueve
        al subdirectorio de fecha.

        Nombre del archivo: "<monto_limpio> IBK.pdf"
        Fallback si monto vacio: "<indice> IBK.pdf"
        Colisiones: agrega sufijo numerico.

        Estructura resultante:
          downloads_path/
            YYYY-MM-DD/
              12,642.06 IBK.pdf
        """
        deadline = time.time() + 30
        nuevo_archivo = None
        while time.time() < deadline:
            nuevos = self._pdfs_actuales() - pdfs_antes
            completos = {f for f in nuevos if not f.endswith('.crdownload')}
            if completos:
                nuevo_archivo = next(iter(completos))
                break
            time.sleep(0.5)

        if not nuevo_archivo:
            logger.warning(f"No se detecto PDF nuevo para indice #{indice}")
            return

        monto_parte = ''.join(c for c in monto if c.isdigit() or c in '.,') if monto else str(indice)
        nombre_base = f"{monto_parte} IBK" if monto_parte else f"{indice} IBK"

        carpeta = self._carpeta_fecha(fecha)

        nombre_destino = f"{nombre_base}.pdf"
        if os.path.exists(os.path.join(carpeta, nombre_destino)):
            contador = 2
            while os.path.exists(os.path.join(carpeta, f"{nombre_base} {contador}.pdf")):
                contador += 1
            nombre_destino = f"{nombre_base} {contador}.pdf"

        ruta_origen  = os.path.join(self._downloads_path, nuevo_archivo)
        ruta_destino = os.path.join(carpeta, nombre_destino)
        try:
            os.rename(ruta_origen, ruta_destino)
            logger.info(f"PDF movido: {nuevo_archivo} → {fecha or 'sin-fecha'}/{nombre_destino}")
        except Exception as e:
            logger.warning(f"No se pudo mover {nuevo_archivo}: {e}")

    # ------------------------------------------------------------------
    # Paginacion
    # ------------------------------------------------------------------

    def _ir_siguiente_pagina(self) -> bool:
        try:
            btn = self.esperar_elemento(S.BTN_SIGUIENTE_PAGINA, timeout=3)
            self.click_js(btn)
            return True
        except Exception:
            pass

        try:
            paginadores = self.driver.find_elements(By.CSS_SELECTOR, S.PAGINATOR)
            for p in paginadores:
                btns = p.find_elements(
                    By.CSS_SELECTOR,
                    "button:not([disabled]):not(.mat-mdc-button-disabled)"
                )
                for b in btns:
                    aria = (b.get_attribute("aria-label") or "").lower()
                    cls  = (b.get_attribute("class") or "").lower()
                    if "next" in aria or "siguiente" in aria or "navigation-next" in cls:
                        self.click_js(b)
                        return True
        except Exception as e:
            logger.debug(f"_ir_siguiente_pagina fallback fallo: {e}")

        return False

    # ------------------------------------------------------------------
    # Regresar al historial
    # ------------------------------------------------------------------

    def _regresar_historial(self) -> None:
        """
        Vuelve al historial de pagos de servicios desde el detalle.
        Estrategia 1 — boton Regresar
        Estrategia 2 — browser back
        Estrategia 3 — URL directa
        """
        if self.elemento_presente(S.BTN_REGRESAR, timeout=5):
            self.click_xpath(S.BTN_REGRESAR)
            self.esperar(2)
            logger.debug("Regresado al historial (boton Regresar)")
            return

        self.volver_atras()
        self.esperar(2)
        if "servicios/historial" in self.driver.current_url:
            logger.debug("Regresado al historial (browser back)")
            return

        logger.info("Navegando directamente a URL del historial de servicios")
        self.driver.get(S.SERVICIOS_HISTORIAL_URL)
        self.esperar(3)
