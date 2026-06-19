"""
Flujo: Descarga de comprobantes (Pagos masivos — Historial)
Banco: Interbank Empresas (empresas.interbank.pe)

Logica general:
  Para cada servicio (AHTC-01 soles, AHTC-02 dolares):
    - Navegar a /pagos-transferencias/masivos/historial/
    - Configurar filtros (tipo pago, servicio, canal, fechas)
    - Por cada fila "Procesado":
        * Abrir detalle (clic en lupa — ibk-table-cell[9])
        * Extraer monto (ibk-card-description segun moneda)
        * Interceptar window.print + clic en BTN_IMPRIMIR
        * Guardar PDF via CDP Page.printToPDF como <monto>_IBK.pdf
        * Regresar al historial

Referencias de selectores: src/banks/ibk/selectors.py
"""

import base64
import os
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


class DescargaComprobantes(BaseFlow):

    def __init__(self, driver: WebDriver, timeout: int = 15, downloads_path: str = "/home/seluser/Downloads"):
        super().__init__(driver, timeout)
        self._downloads_path = downloads_path

    # ------------------------------------------------------------------
    # Diagnostico DOM
    # ------------------------------------------------------------------

    def _guardar_dom(self, nombre: str) -> None:
        """Guarda page_source + screenshot en LOGS_PATH para inspeccion de selectores."""
        try:
            os.makedirs(LOGS_PATH, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            slug = nombre.replace(" ", "_").replace("/", "-")
            html_path = os.path.join(LOGS_PATH, f"dom_IBK_{slug}_{ts}.html")
            png_path  = os.path.join(LOGS_PATH, f"dom_IBK_{slug}_{ts}.png")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(f"<!-- URL: {self.driver.current_url} | {nombre} -->\n")
                f.write(self.driver.page_source)
            self.driver.save_screenshot(png_path)
            logger.info(f"[DOM] '{nombre}' guardado -> {html_path} | {png_path}")
        except Exception as e:
            logger.warning(f"[DOM] No se pudo guardar '{nombre}': {e}")

    # ------------------------------------------------------------------
    # Punto de entrada
    # ------------------------------------------------------------------

    def ejecutar(self, fecha_inicio: str, fecha_fin: str, max_pdfs: Optional[int] = None) -> int:
        """
        Ejecuta el flujo completo.

        Args:
            fecha_inicio: Fecha inicio en formato DD/MM/YYYY.
            fecha_fin:    Fecha fin en formato DD/MM/YYYY.
            max_pdfs:     Limite total de PDFs. None = sin limite.

        Returns:
            Cantidad de archivos PDF guardados.
        """
        logger.info(f"Iniciando DescargaComprobantes IBK | desde: {fecha_inicio} hasta: {fecha_fin} | max: {max_pdfs or 'sin limite'}")

        descargados = 0
        for servicio_nombre, tipo_moneda in S.SERVICIOS:
            if max_pdfs is not None and descargados >= max_pdfs:
                break
            restante = (max_pdfs - descargados) if max_pdfs is not None else None
            n = self._procesar_servicio(fecha_inicio, fecha_fin, servicio_nombre, tipo_moneda, restante)
            descargados += n
            logger.info(f"Servicio '{servicio_nombre}': {n} PDF(s) guardados")

        logger.success(f"Flujo IBK finalizado: {descargados} archivo(s) descargados")
        return descargados

    # ------------------------------------------------------------------
    # Procesamiento por servicio
    # ------------------------------------------------------------------

    def _procesar_servicio(self, fecha_inicio: str, fecha_fin: str, servicio: str, tipo_moneda: str, max_pdfs: Optional[int]) -> int:
        """Navega al historial, aplica filtros y descarga PDFs de cada fila Procesado."""
        logger.info(f"--- Procesando servicio: {servicio} ({tipo_moneda}) ---")
        # Guardar contexto para poder restaurar la busqueda tras paginacion
        self._ctx_servicio    = servicio
        self._ctx_fecha_inicio = fecha_inicio
        self._ctx_fecha_fin    = fecha_fin
        self._navegar_a_historial()
        self._configurar_filtros(servicio, fecha_inicio, fecha_fin)
        self._ejecutar_busqueda()
        self._guardar_dom(f"post_busqueda_{servicio[:10]}")
        return self._procesar_filas(tipo_moneda, max_pdfs)

    def _navegar_a_historial(self) -> None:
        self.driver.get(S.HISTORIAL_URL)
        self.esperar(3)
        logger.debug(f"Navegado a: {S.HISTORIAL_URL}")
        self._guardar_dom("historial_cargado")

    def _configurar_filtros(self, servicio: str, fecha_inicio: str, fecha_fin: str) -> None:
        self._seleccionar_tipo_pago()
        self.esperar(1)
        self._seleccionar_opcion_css(S.SELECT_SERVICIO, S.opcion_servicio(servicio), servicio)
        self.esperar(1)
        self._seleccionar_opcion_css(S.SELECT_CANAL, S.OPCION_CANAL_TODOS, "Todos")
        self.esperar(1)
        self._ingresar_fechas(fecha_inicio, fecha_fin)

    def _seleccionar_tipo_pago(self) -> None:
        """
        Selecciona "Pago a proveedores" en mat-select[data-test="cmbTypePayment"].
        Requiere click en .mat-mdc-select-trigger para que Angular CDK abra el overlay.
        """
        try:
            select_el = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, S.SELECT_TIPO_PAGO))
            )
            trigger = select_el.find_element(By.CSS_SELECTOR, ".mat-mdc-select-trigger")
            self.click_js(trigger)
            self.esperar(1)
            self._guardar_dom("tipo_pago_dropdown_abierto")
            if self.elemento_presente(S.OPCION_PAGO_PROVEEDORES, timeout=5):
                self.click_xpath(S.OPCION_PAGO_PROVEEDORES)
                logger.info("Tipo de pago: 'Pago a proveedores' seleccionado")
                return
        except Exception as e:
            logger.debug(f"_seleccionar_tipo_pago fallo: {e}")
            self._guardar_dom("tipo_pago_fallido")

        logger.warning("No se pudo seleccionar 'Pago a proveedores'. Continuando con valor por defecto.")

    def _seleccionar_opcion_css(self, select_css: str, opcion_xpath: str, nombre: str) -> None:
        """
        Abre un mat-select por CSS y elige la opcion por XPath.
        Click en .mat-mdc-select-trigger para abrir el overlay CDK.
        """
        try:
            select_el = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, select_css))
            )
            trigger = select_el.find_element(By.CSS_SELECTOR, ".mat-mdc-select-trigger")
            self.click_js(trigger)
            self.esperar(1)
            self._guardar_dom(f"select_{nombre[:20]}_dropdown_abierto")

            if self.elemento_presente(opcion_xpath, timeout=5):
                self.click_xpath(opcion_xpath)
                logger.info(f"Seleccionado: '{nombre}'")
                self.esperar(0.5)
                return
        except Exception as e:
            logger.debug(f"Estrategia CSS/XPath fallo para '{nombre}': {e}")
            self._guardar_dom(f"select_{nombre[:20]}_css_fallido")

        if self.click_js_shadow(nombre):
            logger.info(f"Seleccionado (shadow DOM): '{nombre}'")
            self.esperar(0.5)
        else:
            logger.warning(f"No se pudo seleccionar '{nombre}' en {select_css}")

    def _ingresar_fechas(self, fecha_inicio: str, fecha_fin: str) -> None:
        """
        Ingresa fecha inicio y fin en los ibk-datepicker-v2.
        Los inputs se identifican por data-mat-calendar (sin name ni placeholder).

        NO usar inp.click(): abre el calendario dialog de Angular Material y
        Keys.ESCAPE lo cierra descartando el valor escrito.
        Estrategia correcta:
          1. focus() via JS — activa el input sin abrir el calendario
          2. CTRL+A para seleccionar todo
          3. Escribir la fecha
          4. TAB — mueve el foco, dispara blur, Angular parsea y acepta la fecha
        """
        self._guardar_dom("antes_ingresar_fechas")
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
                ok = self.rellenar_fecha_xpath(xpath, valor)
                logger.debug(f"Fecha {etiqueta}: '{valor}' ingresada (JS fallback, ok={ok})")
        self.esperar(0.5)

    def rellenar_fecha_xpath(self, xpath: str, valor: str) -> bool:
        """
        Rellena un input localizado por XPath usando nativeInputValueSetter.
        Dispara input + blur: Angular Material parsea la fecha en 'input'
        y valida/confirma en 'blur'. Sin 'blur' el valor queda pendiente.
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
        """Clic en el boton Buscar (type=submit) y espera la tabla."""
        if self.elemento_presente(S.BOTON_BUSCAR, timeout=8):
            el = self.esperar_clickeable(S.BOTON_BUSCAR)
            self.click_js(el)
            self.esperar(4)
            logger.info("Busqueda ejecutada (type=submit)")
            return

        if self.click_js_shadow("Buscar"):
            self.esperar(4)
            logger.info("Busqueda ejecutada (shadow DOM traversal)")
            return

        raise RuntimeError("No se encontro el boton 'Buscar'. Verifica que el formulario este cargado.")

    # ------------------------------------------------------------------
    # Iteracion de filas
    # ------------------------------------------------------------------

    def _procesar_filas(self, tipo_moneda: str, max_pdfs: Optional[int]) -> int:
        """
        Itera ibk-table-row en todas las paginas, procesa las filas "Procesado"
        y guarda PDF via CDP. Retorna cantidad de PDFs guardados.
        """
        guardados = 0
        indice_fila = 0
        pagina = 1

        while True:
            filas = self._obtener_filas()

            if not filas:
                if pagina > 1:
                    # La navegacion de vuelta puede haber perdido el estado paginado.
                    # Restaurar: re-ejecutar busqueda y re-paginar a la pagina actual.
                    logger.debug(f"Tabla vacia en pagina {pagina}, restaurando busqueda...")
                    if self._restaurar_busqueda(pagina):
                        filas = self._obtener_filas()

                if not filas:
                    logger.info(f"Sin filas en pagina {pagina}, finalizando")
                    break

            if indice_fila >= len(filas):
                # Todas las filas de esta pagina procesadas — intentar siguiente pagina
                if self._ir_siguiente_pagina():
                    pagina += 1
                    indice_fila = 0
                    self.esperar(3)
                    logger.info(f"Avanzando a pagina {pagina}")
                    continue
                else:
                    logger.info("No hay mas paginas. Procesamiento completado.")
                    break

            fila = filas[indice_fila]
            estado = self._leer_estado_fila(fila)
            logger.debug(f"[p{pagina}] Fila {indice_fila + 1}/{len(filas)} | Estado: '{estado}'")

            if estado != S.ESTADO_PROCESADO:
                logger.debug(f"[p{pagina}] Fila {indice_fila + 1} omitida (estado='{estado}')")
                indice_fila += 1
                continue

            logger.info(f"[p{pagina}] Procesando fila {indice_fila + 1}/{len(filas)}")
            try:
                self._abrir_detalle(fila)
                self._guardar_dom(f"detalle_fila_{indice_fila + 1}")
                monto = self._extraer_monto(tipo_moneda)
                logger.info(f"Monto extraido: '{monto}'")
                ok = self._imprimir_como_pdf(monto, guardados + 1)
                if ok:
                    guardados += 1
            except Exception as e:
                logger.error(f"Error en fila {indice_fila + 1}: {e}")
            finally:
                self._regresar_historial()
                self.esperar(2)
                if pagina > 1:
                    # Angular SPA pierde el estado de paginacion tras browser back:
                    # la tabla vuelve a pagina 1 aunque estabamos en pagina N.
                    # Re-navegar a la pagina correcta antes de continuar.
                    self._restaurar_busqueda(pagina)

            indice_fila += 1

            if max_pdfs is not None and guardados >= max_pdfs:
                logger.info(f"Limite de {max_pdfs} PDFs alcanzado")
                break

        return guardados

    def _restaurar_busqueda(self, pagina: int) -> bool:
        """
        Vuelve a ejecutar la busqueda con los mismos filtros y avanza hasta la pagina
        indicada. Usado cuando la tabla queda vacia tras regresar del detalle en pagina > 1.
        Retorna True si se pudo restaurar y hay filas disponibles.
        """
        try:
            logger.info(f"Restaurando busqueda para pagina {pagina}...")
            self._navegar_a_historial()
            self._configurar_filtros(
                getattr(self, "_ctx_servicio", ""),
                getattr(self, "_ctx_fecha_inicio", ""),
                getattr(self, "_ctx_fecha_fin", ""),
            )
            self._ejecutar_busqueda()

            # Avanzar hasta la pagina deseada
            for n in range(1, pagina):
                if not self._ir_siguiente_pagina():
                    logger.warning(f"No se pudo avanzar a pagina {n + 1} al restaurar")
                    return False
                self.esperar(2)

            filas = self._obtener_filas()
            logger.info(f"Busqueda restaurada en pagina {pagina}: {len(filas)} fila(s)")
            return bool(filas)
        except Exception as e:
            logger.error(f"_restaurar_busqueda fallo: {e}")
            return False

    def _ir_siguiente_pagina(self) -> bool:
        """
        Intenta clic en el boton de siguiente pagina del paginador.
        Retorna True si encontro y clickeo el boton, False si no hay mas paginas.
        """
        try:
            btn = self.esperar_elemento(S.BTN_SIGUIENTE_PAGINA, timeout=3)
            self.click_js(btn)
            logger.debug("Clic en boton siguiente pagina")
            return True
        except Exception:
            pass

        # Fallback: buscar por CSS si existe paginador con boton no deshabilitado
        try:
            paginadores = self.driver.find_elements(By.CSS_SELECTOR, S.PAGINATOR)
            if not paginadores:
                return False
            for p in paginadores:
                # Angular Material deshabilita via clase CSS mat-mdc-button-disabled,
                # NO via atributo HTML disabled. Excluir ambos.
                btns = p.find_elements(
                    By.CSS_SELECTOR,
                    "button:not([disabled]):not(.mat-mdc-button-disabled)"
                )
                for b in btns:
                    aria = (b.get_attribute("aria-label") or "").lower()
                    cls  = (b.get_attribute("class") or "").lower()
                    if ("next" in aria or "siguiente" in aria or "navigation-next" in cls):
                        self.click_js(b)
                        logger.debug("Clic en siguiente pagina (fallback CSS)")
                        return True
        except Exception as e:
            logger.debug(f"_ir_siguiente_pagina fallback fallo: {e}")

        return False

    def _obtener_filas(self) -> list:
        """Retorna las ibk-table-row de la tabla actual."""
        filas = self.driver.find_elements(By.CSS_SELECTOR, "ibk-table-row")
        if filas:
            return filas
        return self.driver.find_elements(By.CSS_SELECTOR, "mat-row, table tbody tr")

    def _leer_estado_fila(self, fila) -> str:
        """Lee el estado de la fila buscando texto conocido en ibk-table-cell."""
        try:
            celdas = fila.find_elements(By.CSS_SELECTOR, "ibk-table-cell, mat-cell, td")
            for celda in celdas:
                texto = celda.text.strip()
                if texto in ("Procesado", "Rechazado", "Pendiente", "En proceso", "Anulado"):
                    return texto
            return fila.text.strip()
        except Exception:
            return ""

    def _abrir_detalle(self, fila) -> None:
        """
        Clic en la lupa de la fila.
        Estrategia 1 — ibk-table-cell[9] > ibk-button-icon > button (documentado).
        Estrategia 2 — primer ibk-button-icon de la fila.
        Estrategia 3 — clic directo en la fila.
        """
        try:
            btn = fila.find_element(By.XPATH, S.BTN_LUPA)
            self.click_js(btn)
            self.esperar(3)
            logger.debug("Detalle abierto (ibk-table-cell[9])")
            return
        except Exception:
            pass

        try:
            btn = fila.find_element(By.XPATH, S.BTN_LUPA_FALLBACK)
            self.click_js(btn)
            self.esperar(3)
            logger.debug("Detalle abierto (ibk-button-icon fallback)")
            return
        except Exception:
            pass

        self.click_js(fila)
        self.esperar(3)
        logger.debug("Detalle abierto (click en fila)")

    def _extraer_monto(self, tipo_moneda: str) -> str:
        """
        Extrae el monto del detalle.
        Estrategia 1 — ibk-card-label por texto + sibling ibk-card-description.
        Estrategia 2 — posicional ibk-card-description[4/5].
        """
        campo_xpath = S.CAMPO_MONTO.get(tipo_moneda)
        if not campo_xpath:
            logger.warning(f"Tipo de moneda desconocido: '{tipo_moneda}'")
            return ""

        try:
            el = self.esperar_elemento(campo_xpath, timeout=8)
            monto = el.text.strip()
            if monto:
                logger.debug(f"Monto '{tipo_moneda}': '{monto}'")
                return monto
        except Exception as e:
            logger.warning(f"No se pudo leer monto '{tipo_moneda}' (semantico): {e}")

        campo_pos = S.CAMPO_MONTO_POS.get(tipo_moneda)
        try:
            el = self.esperar_elemento(campo_pos, timeout=5)
            monto = el.text.strip()
            if monto:
                logger.debug(f"Monto '{tipo_moneda}' (posicional): '{monto}'")
                return monto
        except Exception as e2:
            logger.warning(f"Fallback posicional tambien fallo: {e2}")

        return ""

    def _imprimir_como_pdf(self, monto: str, indice: int) -> bool:
        """
        Descarga el comprobante IBK como PDF.

        IBK genera un blob PDF real via:
          Angular → Blob(pdfBytes, {type:'application/pdf'}) → iframe#printFrame → window.print()

        El blob es un PDF real (~39 KB). Chrome lo auto-descarga via Page.setDownloadBehavior.
        Usamos <a href=blob download=nombre.pdf> para que Chrome lo guarde con el nombre
        correcto en el volumen compartido (montado en /home/seluser/Downloads en el
        container de Chrome y en /app/downloads en el container de la API).

        No usamos Page.printToPDF porque ese comando captura la pagina Angular (SPA),
        no el PDF del blob.
        """
        # Interceptar window.print para evitar el dialogo nativo del OS
        self.driver.execute_script("window.print = function() {};")

        # Clic en el boton imprimir
        try:
            el = self.esperar_elemento(S.BTN_IMPRIMIR, timeout=8)
            self.click_js(el)
            self.esperar(2)
            logger.debug("Clic en boton imprimir ejecutado")
        except Exception as e:
            logger.warning(f"No se encontro el boton imprimir ({S.BTN_IMPRIMIR}): {e}")
            self._guardar_dom(f"imprimir_btn_no_encontrado_{indice}")
            return False

        # Detectar blob URL del #printFrame
        blob_url = self.driver.execute_script(
            "const f = document.getElementById('printFrame');"
            "return (f && f.src && f.src.startsWith('blob:')) ? f.src : null;"
        )

        if blob_url:
            logger.debug(f"printFrame blob URL detectada: {blob_url[:70]}...")
            try:
                nombre_base = self._monto_a_nombre(monto, indice)
                filename = f"{nombre_base}.pdf"

                # Simular <a href=blob download=nombre.pdf> click.
                # Chrome respeta el atributo download para blob URLs del mismo origen
                # y guarda el archivo en el path configurado por Page.setDownloadBehavior
                # (/home/seluser/Downloads → mapeado al volumen 'downloads').
                self.driver.execute_script(
                    """
                    const a = document.createElement('a');
                    a.href = arguments[0];
                    a.download = arguments[1];
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    """,
                    blob_url, filename,
                )

                # Esperar a que el archivo aparezca en el volumen compartido
                ruta = os.path.join(self._downloads_path, filename)
                for _ in range(24):   # hasta 12 segundos
                    if os.path.exists(ruta) and os.path.getsize(ruta) > 0:
                        logger.info(
                            f"PDF descargado [blob_anchor]: {filename} "
                            f"({os.path.getsize(ruta):,} bytes)"
                        )
                        return True
                    self.esperar(0.5)

                logger.warning(f"Timeout esperando descarga en {ruta}")
                return False

            except Exception as e:
                logger.warning(f"Estrategia blob_anchor fallo: {e}")
                self._guardar_dom(f"imprimir_blob_anchor_error_{indice}")
                return False

        # Fallback: @media print sobre la pagina actual (sin blob detectado)
        logger.debug("Fallback: @media print en pagina actual (sin printFrame)")
        try:
            self.driver.execute_cdp_cmd("Emulation.setEmulatedMedia", {"media": "print"})
            self.esperar(1)
            return self._guardar_pdf_cdp(monto, indice, "mediaprint")
        finally:
            try:
                self.driver.execute_cdp_cmd("Emulation.setEmulatedMedia", {"media": ""})
            except Exception:
                pass

    def _guardar_pdf_cdp(self, monto: str, indice: int, origen: str) -> bool:
        """Genera y guarda el PDF de la pagina/pestana actual via CDP Page.printToPDF."""
        try:
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
            nombre_base = self._monto_a_nombre(monto, indice)
            os.makedirs(self._downloads_path, exist_ok=True)
            ruta = os.path.join(self._downloads_path, f"{nombre_base}.pdf")
            with open(ruta, "wb") as f:
                f.write(pdf_bytes)
            logger.info(f"PDF guardado [{origen}]: {nombre_base}.pdf ({len(pdf_bytes):,} bytes)")
            return True
        except Exception as e:
            logger.error(f"CDP Page.printToPDF fallo [{origen}]: {e}")
            self._guardar_dom(f"imprimir_cdp_error_{indice}")
            return False

    def _regresar_historial(self) -> None:
        """
        Vuelve al listado de historial.
        Estrategia 1 — boton/link "Regresar".
        Estrategia 2 — browser back.
        Estrategia 3 — navegar directo a HISTORIAL_URL.
        """
        if self.elemento_presente(S.BTN_REGRESAR, timeout=5):
            self.click_xpath(S.BTN_REGRESAR)
            self.esperar(2)
            logger.debug("Regresado al historial (boton Regresar)")
            return

        self.volver_atras()
        self.esperar(2)
        if "historial" in self.driver.current_url:
            logger.debug("Regresado al historial (browser back)")
            return

        logger.info("Navegando directamente a historial URL")
        self.driver.get(S.HISTORIAL_URL)
        self.esperar(3)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def _monto_a_nombre(self, monto: str, indice: int) -> str:
        """
        Convierte un monto (ej: 'S/ 4,255.32') al nombre base del archivo
        (ej: '4,255.32 IBK'). Fallback: '<indice> IBK'.

        Se preservan comas y puntos para que el nombre sea legible y consistente
        con el formato usado por BCP/Scotiabank. El banco se detecto via
        BANK_SUFFIXES = [..., 'IBK'] en documentos.py.
        """
        if not monto:
            nombre_base = f"{indice} IBK"
        else:
            # Conservar solo digitos, comas y puntos (igual que BCP)
            limpio = ''.join(c for c in monto if c.isdigit() or c in '.,')
            limpio = limpio.strip()
            nombre_base = f"{limpio} IBK" if limpio else f"{indice} IBK"

        # Evitar sobreescribir si ya existe un archivo con el mismo monto
        ruta_base = os.path.join(self._downloads_path, f"{nombre_base}.pdf")
        if not os.path.exists(ruta_base):
            return nombre_base

        contador = 2
        while os.path.exists(os.path.join(self._downloads_path, f"{nombre_base} {contador}.pdf")):
            contador += 1
        return f"{nombre_base} {contador}"
