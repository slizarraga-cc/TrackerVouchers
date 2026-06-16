"""
Flujo: Consulta de Operaciones
Banco: BBVA Net Cash (bbvanetcash.pe)

Modulo: Cuentas > Movimientos de cuentas > Consulta de operaciones
Pantalla destino: "Relacion de Operaciones Realizadas"

Estructura de iframes (identica al Flujo 1):
  Documento principal
    └── (shadow DOM) legacy-page > bbva-core-iframe
          └── iframe#bbvaIframe [src*="SPEKYOP"]   (IFRAME_LEGACY)
                └── #kyop-central-load-area         (IFRAME_CENTRAL)
                      └── table.tb_data             (tabla de operaciones)

Selectores documentados: src/banks/bbva/selectors.py — seccion FLUJO 2
Ref: Informe de ejecucion 03/06/2026
"""

import os
import re
import time
from dataclasses import dataclass
from typing import List, Optional

from loguru import logger
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.banks.bbva.selectors import BBVASelectors as S
from src.core.base_flow import BaseFlow


@dataclass
class Operacion:
    tipo_operacion: str
    beneficiario: str = ""
    fecha_hora: str = ""
    importe: str = ""
    moneda: str = ""
    nro_operacion: str = ""
    nro_referencia: str = ""


class ConsultaOperaciones(BaseFlow):

    def __init__(self, driver: WebDriver, timeout: int = 15, downloads_path: str = "/home/seluser/Downloads"):
        super().__init__(driver, timeout)
        self._fecha = ""
        self._ventana_principal = ""
        self._downloads_path = downloads_path

    def ejecutar(self, fecha: str, max_pdfs: Optional[int] = None) -> int:
        """
        Ejecuta el flujo completo de descarga de PDFs de consulta de operaciones.

        Args:
            fecha:    Fecha a filtrar en formato DD/MM/YYYY
            max_pdfs: Limite de PDFs. None = sin limite (descarga todos).

        Returns:
            Cantidad de PDFs descargados exitosamente
        """
        self._fecha = fecha
        self._ventana_principal = self.driver.current_window_handle
        limite_str = str(max_pdfs) if max_pdfs is not None else "sin limite"
        logger.info(f"Iniciando ConsultaOperaciones | fecha={fecha} | max={limite_str}")

        self._navegar_a_consulta()
        return self._procesar_todas_las_operaciones(max_pdfs)

    # ------------------------------------------------------------------
    # Navegacion al modulo
    # ------------------------------------------------------------------

    def _navegar_a_consulta(self) -> None:
        """
        Navega a Consulta de Operaciones usando navegacion directa por URL (metodo primario)
        o via clicks en el menu como fallback.

        Metodo primario — URL directa:
          Navega a S.CONSULTA_OP_URL (hash-based SPA route) y espera
          que legacy-page#cells-template-legacy tenga el atributo is-page-ready.
          Confirmado en doms/consulta_operaciones.html:
            URL: .../index.html#!/legacy/000000314E
            DOM: <legacy-page id="cells-template-legacy" is-page-ready="" ...>

        Fallback — click en menu:
          1. Click en item Cuentas: event-name="event-111V00002"
             (confirmado por URL doms/cuentas.html: ?id=111V00002)
          2. Click en "Consulta de operaciones" en la seccion menurization.
        """
        self.driver.switch_to.default_content()
        logger.info("Navegando a Consulta de operaciones via URL directa...")
        self.driver.get(S.CONSULTA_OP_URL)

        # Esperar hasta 20s a que legacy-page este listo
        if self._esperar_legacy_page_lista(timeout=20):
            logger.info("Consulta de operaciones cargada via URL directa")
            return

        # Fallback: menu click si la URL directa no cargo el modulo
        logger.warning(
            "URL directa no cargo legacy-page. "
            "Intentando navegacion via menu (Cuentas > Consulta de operaciones)..."
        )
        self._navegar_via_menu()

    def _esperar_legacy_page_lista(self, timeout: int = 20) -> bool:
        """
        Espera a que legacy-page#cells-template-legacy tenga el atributo is-page-ready
        y que el iframe SPEKYOP este disponible en su shadow DOM.
        Retorna True si quedo lista dentro del timeout, False si no.

        Confirmado en DOMs:
          <legacy-page id="cells-template-legacy" is-page-ready="" show-spinner="">
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            lista = self.driver.execute_script("""
                const lp = document.querySelector(arguments[0]);
                return lp && lp.hasAttribute('is-page-ready');
            """, S.LEGACY_PAGE)
            if lista:
                return True
            time.sleep(0.5)
        return False

    def _navegar_via_menu(self) -> None:
        """
        Fallback: navega a Consulta de Operaciones via clicks en el menu lateral.

        Paso 1 — Click en "Cuentas":
          Selector: bbva-web-navigation-menu-item[event-name="event-111V00002"]
          event-name confirmado por URL doms/cuentas.html (?id=111V00002).
          Usa click_js_shadow_menu_item (mismo patron que Flujo 1 con "event-111V00039").

        Paso 2 — Click en "Consulta de operaciones":
          Texto visible en el sub-menu de Cuentas tras expandir la seccion.
        """
        self.driver.switch_to.default_content()

        # --- Paso 1: Click en Cuentas ---
        resultado = self.click_js_shadow_menu_item("event-111V00002")
        logger.info(f"Click menu Cuentas resultado: {resultado}")

        if resultado == 'not-found':
            # Fallback CSS directo (modo responsive o shadow abierto)
            if not self.click_js_css(S.MENU_CUENTAS):
                if not self.click_js_shadow_css(S.MENU_CUENTAS):
                    raise RuntimeError(
                        "No se pudo hacer click en menu Cuentas. "
                        f"Selector: {S.MENU_CUENTAS}"
                    )
            logger.info("Menu Cuentas clickeado via CSS (fallback)")

        # Esperar que la seccion menurization cargue el sub-menu de Cuentas
        SECTION_CSS = '#cells-template-bbva-btge-menurization-landing-solution'
        for _ in range(20):
            self.esperar(0.5)
            if self.elemento_presente_js(SECTION_CSS):
                break

        # Esperar a que los bbva-web-link del sub-menu aparezcan
        for _ in range(40):
            self.esperar(0.5)
            links = self.driver.execute_script("""
                const sec = document.querySelector(arguments[0]);
                if (!sec) return -1;
                function findAll(root, tag) {
                    let items = Array.from(root.querySelectorAll ? root.querySelectorAll(tag) : []);
                    for (const el of (root.querySelectorAll ? root.querySelectorAll('*') : [])) {
                        if (el.shadowRoot) items = items.concat(findAll(el.shadowRoot, tag));
                    }
                    if (root.shadowRoot) items = items.concat(findAll(root.shadowRoot, tag));
                    return items;
                }
                return findAll(sec, 'bbva-web-link').length;
            """, SECTION_CSS)
            if links and links > 0:
                break

        # --- Paso 2: Click en "Consulta de operaciones" ---
        # Intento 1: shadow DOM traversal desde document root
        if self.click_js_shadow_link(S.SUBMENU_CONSULTA_OP_TEXTO):
            logger.info("'Consulta de operaciones' clickeado via shadow DOM traversal")
        else:
            # Intento 2: dentro del iframe menurization
            self._click_en_iframe_menurization(S.SUBMENU_CONSULTA_OP_TEXTO)

        if not self._esperar_legacy_page_lista(timeout=15):
            raise RuntimeError(
                "legacy-page no cargo tras click en 'Consulta de operaciones'. "
                "Verifica que el sub-menu de Cuentas este visible."
            )
        logger.info("Consulta de operaciones cargada via menu")

    def _click_en_iframe_menurization(self, texto: str) -> None:
        """Busca y hace click en un item de sub-menu dentro del iframe menurization."""
        try:
            iframe_menu = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, S.IFRAME_MENURIZATION))
            )
            self.driver.switch_to.frame(iframe_menu)

            if self.click_js_shadow_link(texto):
                logger.info(f"'{texto}' clickeado via shadow DOM en iframe menurization")
                return

            xpath = (
                f'//bbva-web-link[normalize-space(.)="{texto}"]'
                f' | //a[normalize-space(.)="{texto}"]'
            )
            if self.elemento_presente(xpath, timeout=5):
                self.click_xpath(xpath)
                logger.info(f"'{texto}' clickeado via XPath en iframe menurization")
            else:
                raise RuntimeError(
                    f"No se encontro '{texto}' en iframe menurization."
                )
        finally:
            self.driver.switch_to.default_content()

    # ------------------------------------------------------------------
    # Lectura de tabla de operaciones
    # ------------------------------------------------------------------

    def _leer_operaciones(self, fecha_filtro: str) -> List[Operacion]:
        """
        Escanea table.tb_data en orden y extrae el bloque de operaciones
        cuya columna 'Fecha y Hora' comienza con fecha_filtro.

        Logica de escaneo secuencial:
          - Recorre filas de arriba a abajo.
          - Cuando encuentra la primera fila con fecha_filtro, activa el bloque.
          - Sigue acumulando filas mientras la fecha coincida.
          - Para en cuanto la fecha cambia (bloque contiguo completado).
          Esto es mas eficiente que filtrar toda la tabla y refleja que
          las operaciones del mismo dia estan agrupadas consecutivamente.

        Estructura de columnas (0-based, confirmado en informe 03/06/2026):
          | Tipo Operacion | Beneficiario | Fecha y Hora | Importe | Moneda | N° Op | N° Ref |
          |      0         |      1       |      2       |    3    |   4    |   5   |   6    |
        """
        self._switch_to_iframe_central()

        WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, S.TABLE_DATA))
        )

        filas = self.driver.find_elements(By.CSS_SELECTOR, S.TABLE_ROW_DATA)
        operaciones: List[Operacion] = []
        bloque_activo = False

        for fila in filas:
            celdas = fila.find_elements(By.TAG_NAME, 'td')
            if len(celdas) < 4:
                continue

            fecha_hora = celdas[S.COL2_FECHA_HORA].text.strip()

            if fecha_hora.startswith(fecha_filtro):
                bloque_activo = True

                def celda(idx: int) -> str:
                    return celdas[idx].text.strip() if len(celdas) > idx else ""

                operaciones.append(Operacion(
                    tipo_operacion=celda(S.COL2_TIPO_OP),
                    beneficiario=celda(S.COL2_BENEFIC),
                    fecha_hora=fecha_hora,
                    importe=celda(S.COL2_IMPORTE),
                    moneda=celda(S.COL2_MONEDA),
                    nro_operacion=celda(S.COL2_NRO_OP),
                    nro_referencia=celda(S.COL2_NRO_REF),
                ))
            elif bloque_activo:
                # Fecha distinta despues del bloque — no hay mas operaciones del dia
                logger.debug(
                    f"Cambio de fecha detectado ({fecha_hora}) — "
                    f"bloque {fecha_filtro} completo con {len(operaciones)} operaciones"
                )
                break

        self.driver.switch_to.default_content()

        logger.info(f"Operaciones para {fecha_filtro}: {len(operaciones)}")
        for op in operaciones:
            logger.info(f"  [{op.fecha_hora}] {op.tipo_operacion} | {op.moneda} {op.importe}")

        return operaciones

    # ------------------------------------------------------------------
    # Loop principal de procesamiento
    # ------------------------------------------------------------------

    def _pdfs_actuales(self) -> set:
        try:
            return {f for f in os.listdir(self._downloads_path) if f.lower().endswith('.pdf')}
        except Exception:
            return set()

    def _renombrar_pdf_nuevo(self, pdfs_antes: set, op: Operacion) -> None:
        """
        Espera hasta 30s a que aparezca un PDF nuevo y lo renombra
        a '<importe> BBVA.pdf'. Si ya existe, agrega nro_operacion.
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
            logger.warning(
                f"No se detecto PDF nuevo para: {op.tipo_operacion} | {op.importe}"
            )
            return

        importe_safe = re.sub(r'[<>:"/\\|?*\n\r\t]', '', op.importe).strip()
        if not importe_safe:
            importe_safe = op.nro_operacion or op.tipo_operacion[:20]

        nombre_destino = f"{importe_safe} BBVA.pdf"
        ruta_origen  = os.path.join(self._downloads_path, nuevo_archivo)
        ruta_destino = os.path.join(self._downloads_path, nombre_destino)

        if os.path.exists(ruta_destino):
            nombre_destino = f"{importe_safe} {op.nro_operacion} BBVA.pdf"
            ruta_destino = os.path.join(self._downloads_path, nombre_destino)

        try:
            os.rename(ruta_origen, ruta_destino)
            logger.info(f"PDF renombrado: {nuevo_archivo} → {nombre_destino}")
        except Exception as e:
            logger.warning(f"No se pudo renombrar {nuevo_archivo}: {e}")

    def _procesar_todas_las_operaciones(self, max_pdfs: Optional[int]) -> int:
        operaciones = self._leer_operaciones(self._fecha)
        if not operaciones:
            logger.warning(f"No se encontraron operaciones para la fecha {self._fecha}")
            return 0

        total = min(len(operaciones), max_pdfs) if max_pdfs is not None else len(operaciones)
        descargados = 0

        for i, op in enumerate(operaciones[:total]):
            logger.info(
                f"[{i + 1}/{total}] {op.fecha_hora} | {op.tipo_operacion} "
                f"| {op.moneda} {op.importe}"
            )
            pdfs_antes = self._pdfs_actuales()
            try:
                self._descargar_pdf_operacion(op)
                self._renombrar_pdf_nuevo(pdfs_antes, op)
                descargados += 1
                self._volver_a_lista()
            except Exception as e:
                logger.error(
                    f"Error en operacion {op.nro_operacion or op.tipo_operacion}: {e}"
                )
                self._recuperar_lista()

        logger.success(f"Proceso completado: {descargados}/{total} PDFs descargados")
        return descargados

    # ------------------------------------------------------------------
    # Descarga de un PDF
    # ------------------------------------------------------------------

    def _descargar_pdf_operacion(self, op: Operacion) -> None:
        """
        Secuencia para descargar el PDF de una operacion:

        Paso 1 — Click en columna Tipo de Operacion (a.enlace):
          Identifica la fila exacta por (fecha_hora + importe).
          Selector: a.enlace dentro de td[0] de la fila coincidente.
          Ref: informe 03/06/2026 — class="enlace"

        Paso 2 — Esperar carga de consulta_especifica (detalle de la operacion).

        Paso 3 — Click en boton Exportar PDF:
          Selector: a[title="Descargar Pdf"]  (hover visible: "Descargar Pdf")
          Ref: informe 03/06/2026 — class="bt_m bt_azul bt_m_ic_r"
          Si el servidor devuelve 503, la descarga falla silenciosamente
          y _renombrar_pdf_nuevo lo detecta por ausencia de archivo nuevo.

        Paso 4 — Cerrar ventanas extra (el boton usa target="_new").
        """
        # Paso 1: click en el enlace de Tipo de Operacion en la tabla
        self._switch_to_iframe_central()
        enlace = self._buscar_enlace_operacion(op)
        if not enlace:
            raise RuntimeError(
                f"No se encontro el enlace para: {op.tipo_operacion} | "
                f"{op.fecha_hora} | {op.importe}"
            )
        self.click_js(enlace)
        logger.debug(f"Click en Tipo de Operacion: {op.tipo_operacion} | {op.fecha_hora}")

        # Paso 2: esperar carga del detalle
        self.esperar(4)

        # Paso 3: click en boton Exportar PDF (hover: "Descargar Pdf")
        self._switch_to_iframe_central()
        ventanas_antes = set(self.driver.window_handles)
        btn_pdf = WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, S.BTN_EXPORTAR_PDF))
        )
        self.click_js(btn_pdf)
        logger.debug("Click en Exportar PDF (a[title='Descargar Pdf'])")
        self.esperar(6)

        # Paso 4: cerrar ventanas extra que se hayan abierto
        ventanas_nuevas = set(self.driver.window_handles) - ventanas_antes
        for handle in ventanas_nuevas:
            self.driver.switch_to.window(handle)
            self.driver.close()
            logger.debug("Ventana PDF extra cerrada")
        self.driver.switch_to.window(self._ventana_principal)
        logger.success(f"PDF descargado | {op.moneda} {op.importe} | {op.tipo_operacion}")

    def _buscar_enlace_operacion(self, op: Operacion):
        """
        Busca el <a class='enlace'> de la fila que coincide con fecha_hora e importe.
        Identifica la fila por dos campos de negocio para evitar confusiones en caso
        de importes repetidos.
        Retorna el WebElement del enlace o None si no se encuentra.
        """
        filas = self.driver.find_elements(By.CSS_SELECTOR, S.TABLE_ROW_DATA)
        for fila in filas:
            celdas = fila.find_elements(By.TAG_NAME, 'td')
            if len(celdas) < 4:
                continue
            fecha = celdas[S.COL2_FECHA_HORA].text.strip()
            importe = celdas[S.COL2_IMPORTE].text.strip()
            if fecha == op.fecha_hora and importe == op.importe:
                enlaces = fila.find_elements(By.CSS_SELECTOR, S.ENLACE_TIPO_OP)
                if enlaces:
                    return enlaces[0]
        return None

    # ------------------------------------------------------------------
    # Retorno al listado
    # ------------------------------------------------------------------

    def _volver_a_lista(self) -> None:
        """
        Click en a.bt_previous para volver al listado de operaciones y espera
        a que la tabla (table.tb_data) vuelva a estar presente en el iframe.

        Ref: <a class="bt_previous">Volver</a> — parte inferior izquierda del detalle.
        Estabilidad: ALTA (class funcional, confirmado en informe 03/06/2026)
        """
        try:
            self._switch_to_iframe_central()
            btn_volver = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, S.BTN_VOLVER))
            )
            self.click_js(btn_volver)
            logger.debug("Click en Volver (a.bt_previous)")

            # Esperar a que la tabla de operaciones vuelva a aparecer
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, S.TABLE_DATA))
            )
            self.driver.switch_to.default_content()
            logger.debug("Tabla de operaciones visible — listado restaurado")
        except Exception as e:
            self.driver.switch_to.default_content()
            logger.warning(f"Error al volver al listado: {e}")

    def _lista_presente(self) -> bool:
        """Verifica que la tabla de operaciones este visible en el IFRAME_CENTRAL."""
        try:
            self._switch_to_iframe_central()
            tabla = self.driver.find_elements(By.CSS_SELECTOR, S.TABLE_DATA)
            self.driver.switch_to.default_content()
            return len(tabla) > 0
        except Exception:
            self.driver.switch_to.default_content()
            return False

    def _recuperar_lista(self) -> None:
        """
        Recuperacion de error: si la tabla no esta visible, re-navega al modulo.
        """
        self.driver.switch_to.default_content()
        try:
            if not self._lista_presente():
                logger.warning("Tabla no visible tras error — re-navegando al modulo")
                self._navegar_a_consulta()
        except Exception as e:
            logger.error(f"No se pudo recuperar el listado: {e}")

    # ------------------------------------------------------------------
    # Utilitario: cambio de iframe
    # Logica identica al Flujo 1 (SeguimientoPagosMasivos._switch_to_iframe_central)
    # TODO: extraer a BBVABaseFlow cuando se consoliden ambos flujos
    # ------------------------------------------------------------------

    def _find_iframe_in_shadow(self, src_pattern: str, timeout: int = None):
        """
        Busca un <iframe> cuyo src contiene src_pattern atravesando shadow DOM
        recursivamente. Retorna el WebElement o None si supera el timeout.
        Necesario porque en BBVA los iframes estan dentro de shadow DOM y
        document.querySelector no los encuentra directamente.
        """
        t = timeout or self.timeout
        deadline = self.driver.execute_script("return Date.now()") + t * 1000
        script = """
            const pattern = arguments[0];
            function find(root) {
                if (root.querySelectorAll) {
                    for (const f of root.querySelectorAll('iframe')) {
                        if (!pattern || (f.src && f.src.includes(pattern))) return f;
                    }
                    for (const el of root.querySelectorAll('*')) {
                        if (el.shadowRoot) {
                            const r = find(el.shadowRoot);
                            if (r) return r;
                        }
                    }
                }
                if (root.shadowRoot) {
                    const r = find(root.shadowRoot);
                    if (r) return r;
                }
                return null;
            }
            return find(document);
        """
        while True:
            el = self.driver.execute_script(script, src_pattern)
            if el:
                return el
            now = self.driver.execute_script("return Date.now()")
            if now >= deadline:
                return None
            time.sleep(0.5)

    def _switch_to_iframe_central(self) -> None:
        """
        Navega al iframe anidado IFRAME_LEGACY > IFRAME_CENTRAL.
        Siempre parte desde default_content.

        Jerarquia:
          default_content
            └── (shadow DOM) iframe[src*="SPEKYOP"] / iframe#bbvaIframe  (IFRAME_LEGACY)
                  └── #kyop-central-load-area                            (IFRAME_CENTRAL)
        """
        self.driver.switch_to.default_content()

        legacy_el = self._find_iframe_in_shadow('SPEKYOP')
        if not legacy_el:
            raise RuntimeError(
                "No se encontro el iframe SPEKYOP en shadow DOM. "
                "Verifica que el modulo Consulta de operaciones este cargado."
            )
        self.driver.switch_to.frame(legacy_el)
        logger.debug("Cambiado a iframe SPEKYOP (legacy)")

        central = WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, S.IFRAME_CENTRAL))
        )
        self.driver.switch_to.frame(central)
        logger.debug("Cambiado a iframe #kyop-central-load-area")
