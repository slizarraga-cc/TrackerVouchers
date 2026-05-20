"""
Flujo: Seguimiento de pagos masivos
Banco: BBVA Net Cash (bbvanetcash.pe)

Referencias de selectores: documentacion tecnica del flujo (manual del usuario)

Estructura de iframes:
  Documento principal
    └── iframe[src*="menurization-landing"]   (menu de sub-opciones)
    └── iframe[src*="SPEKYOP"]                (contenido legacy — IFRAME_LEGACY)
          └── #kyop-central-load-area          (contenido activo — IFRAME_CENTRAL)
"""

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
    nro_orden: str
    planilla: str = ""
    estado: str = ""
    descripcion: str = ""
    moneda: str = ""
    procesado: str = ""
    fecha_envio: str = ""


class SeguimientoPagosMasivos(BaseFlow):

    def __init__(self, driver: WebDriver, timeout: int = 15):
        super().__init__(driver, timeout)
        self._fecha = ""
        self._ventana_principal = ""

    def ejecutar(self, fecha: str, max_pdfs: Optional[int] = None) -> int:
        """
        Ejecuta el flujo completo de descarga de PDFs de pagos masivos.

        Args:
            fecha:    Fecha de busqueda en formato DD/MM/YYYY
            max_pdfs: Limite de PDFs. None = sin limite (descarga todos).

        Returns:
            Cantidad de PDFs descargados exitosamente
        """
        self._fecha = fecha
        self._ventana_principal = self.driver.current_window_handle
        limite_str = str(max_pdfs) if max_pdfs is not None else "sin limite"
        logger.info(f"Iniciando SeguimientoPagosMasivos | fecha={fecha} | max={limite_str}")

        self._navegar_a_seguimiento()
        self._ingresar_fecha_y_buscar(fecha)
        return self._procesar_todas_las_operaciones(max_pdfs)

    # ------------------------------------------------------------------
    # Navegacion al modulo
    # ------------------------------------------------------------------

    def _navegar_a_seguimiento(self) -> None:
        """
        Paso 1: Clic en "Pagos" del menu lateral.
        Paso 2: Clic en "Seguimiento de pagos masivos" dentro del iframe de menu.

        El menu usa bbva-web-navigation-menu-item (Web Component).
        El sub-menu usa bbva-web-link dentro de iframe[src*="menurization-landing"].
        """
        self.driver.switch_to.default_content()

        # Paso 1: Click en el item de menu "Pagos"
        # El elemento host es accesible en DOM plano via CSS aunque tenga shadow DOM interno.
        logger.debug(f"Haciendo clic en menu Pagos: {S.MENU_PAGOS}")
        if not self.click_js_css(S.MENU_PAGOS):
            raise RuntimeError(f"No se encontro el menu Pagos. Selector: {S.MENU_PAGOS}")
        self.esperar(2)

        # Paso 2: Click en "Seguimiento de pagos masivos" (dentro del iframe del menu)
        logger.debug(f"Buscando sub-menu '{S.SUBMENU_SEGUIMIENTO_TEXTO}' en iframe menurization")
        try:
            iframe_menu = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, S.IFRAME_MENURIZATION))
            )
            self.driver.switch_to.frame(iframe_menu)

            # Intento 1: shadow DOM traversal por texto (si bbva-web-link usa shadow DOM)
            if self.click_js_shadow(S.SUBMENU_SEGUIMIENTO_TEXTO):
                logger.info("Sub-menu clickeado via shadow DOM traversal")
            else:
                # Intento 2: XPath directo (si el texto es accesible en light DOM)
                xpath = f'//bbva-web-link[normalize-space(.)="{S.SUBMENU_SEGUIMIENTO_TEXTO}"]'
                if self.elemento_presente(xpath, timeout=5):
                    self.click_xpath(xpath)
                    logger.info("Sub-menu clickeado via XPath")
                else:
                    raise RuntimeError(
                        f"No se encontro '{S.SUBMENU_SEGUIMIENTO_TEXTO}' en el sub-menu. "
                        "Verifica que el menu Pagos este expandido."
                    )
        finally:
            self.driver.switch_to.default_content()

        self.esperar(3)
        logger.info("Navegado a Seguimiento de pagos masivos")

    # ------------------------------------------------------------------
    # Formulario de busqueda
    # ------------------------------------------------------------------

    def _ingresar_fecha_y_buscar(self, fecha: str) -> None:
        """
        Paso 3: Ingresa la fecha en #fechaEspecifica (input con jQuery datepicker).
        Paso 4: Hace clic en el boton "Aceptar".

        Ambos elementos estan dentro de IFRAME_LEGACY > IFRAME_CENTRAL.
        """
        self._switch_to_iframe_central()

        # Campo fecha (input type=text con clase hasDatepicker)
        input_fecha = WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, S.INPUT_FECHA))
        )
        input_fecha.clear()
        input_fecha.send_keys(fecha)
        self.esperar(0.5)

        # Boton Aceptar
        btn_aceptar = WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, S.BTN_ACEPTAR))
        )
        self.click_js(btn_aceptar)
        self.esperar(4)

        self.driver.switch_to.default_content()
        logger.info(f"Busqueda ejecutada para fecha: {fecha}")

    # ------------------------------------------------------------------
    # Lectura de tabla de operaciones
    # ------------------------------------------------------------------

    def _leer_operaciones(self) -> List[Operacion]:
        """
        Lee todas las filas de la tabla de resultados dentro del IFRAME_CENTRAL.

        Estructura de la tabla:
          | N° Orden | Planilla | Estado | Descripcion | Moneda | Procesado | Fecha Envio |

        Solo se incluyen filas donde la columna N° Orden contiene un valor numerico.
        Los datos se capturan antes de entrar al detalle de cada operacion (req. de negocio).
        """
        self._switch_to_iframe_central()

        operaciones: List[Operacion] = []
        filas = self.driver.find_elements(By.CSS_SELECTOR, S.TABLE_ROWS)

        for fila in filas:
            celdas = fila.find_elements(By.TAG_NAME, 'td')
            if len(celdas) < 7:
                continue
            nro = celdas[S.COL_NRO_ORDEN].text.strip()
            if not nro.isdigit():
                continue  # Saltamos header y filas no-dato
            operaciones.append(Operacion(
                nro_orden=nro,
                planilla=celdas[S.COL_PLANILLA].text.strip(),
                estado=celdas[S.COL_ESTADO].text.strip(),
                descripcion=celdas[S.COL_DESCRIPCION].text.strip(),
                moneda=celdas[S.COL_MONEDA].text.strip(),
                procesado=celdas[S.COL_PROCESADO].text.strip(),
                fecha_envio=celdas[S.COL_FECHA_ENVIO].text.strip(),
            ))

        self.driver.switch_to.default_content()

        logger.info(f"Operaciones encontradas: {len(operaciones)}")
        for op in operaciones:
            logger.info(f"  [{op.nro_orden}] {op.moneda} | Procesado: {op.procesado}")

        return operaciones

    # ------------------------------------------------------------------
    # Loop principal de procesamiento
    # ------------------------------------------------------------------

    def _procesar_todas_las_operaciones(self, max_pdfs: Optional[int]) -> int:
        operaciones = self._leer_operaciones()
        if not operaciones:
            logger.warning("No se encontraron operaciones en la tabla")
            return 0

        total = min(len(operaciones), max_pdfs) if max_pdfs is not None else len(operaciones)
        descargados = 0

        for i, op in enumerate(operaciones[:total]):
            logger.info(
                f"[{i + 1}/{total}] Orden {op.nro_orden} | {op.moneda} {op.procesado} | Estado: {op.estado}"
            )
            try:
                self._descargar_pdf_operacion(op)
                descargados += 1
                self._volver_a_lista()
            except Exception as e:
                logger.error(f"Error en orden {op.nro_orden}: {e}")
                self._recuperar_lista()

        logger.success(f"Proceso completado: {descargados}/{total} PDFs descargados")
        return descargados

    # ------------------------------------------------------------------
    # Descarga de un PDF
    # ------------------------------------------------------------------

    def _descargar_pdf_operacion(self, op: Operacion) -> None:
        """
        Secuencia completa para descargar el PDF de una operacion:

        1. Clic en "Ver Detalle" (identificado por nro_orden en el onclick)
           Selector: a[onclick*="'{nro_orden}','D'"]
           Estabilidad: ALTA (nro_orden es ID de negocio)

        2. Clic en "Ver contenido de la planilla"
           Selector: a.ic.enlace_ico
           Estabilidad: ALTA (clase funcional)

        3. Clic en "Exportar PDF" (abre ventana nueva con target="_new")
           Selector: a[title="Descargar Pdf"]
           Estabilidad: ALTA (title attribute)

        4. Cierra la ventana extra si se abrio y vuelve a la ventana principal.
        """
        # 1. Click en Ver Detalle (usando nro_orden para identificar la fila exacta)
        self._switch_to_iframe_central()
        selector_detalle = S.btn_ver_detalle_por_orden(op.nro_orden)
        btn_detalle = WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector_detalle))
        )
        self.click_js(btn_detalle)
        self.esperar(4)
        logger.debug(f"Ver Detalle abierto para orden {op.nro_orden}")

        # 2. Click en Ver contenido de planilla
        # Re-switch porque la navegacion dentro del iframe invalida la referencia anterior
        self._switch_to_iframe_central()
        link_planilla = WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, S.LINK_VER_PLANILLA))
        )
        self.click_js(link_planilla)
        self.esperar(4)
        logger.debug(f"Ver contenido de planilla abierto para orden {op.nro_orden}")

        # 3. Click en Exportar PDF (puede abrir nueva ventana)
        self._switch_to_iframe_central()
        ventanas_antes = set(self.driver.window_handles)
        btn_pdf = WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, S.BTN_EXPORTAR_PDF))
        )
        self.click_js(btn_pdf)
        self.esperar(6)

        # 4. Cerrar ventanas extra que se hayan abierto
        ventanas_nuevas = set(self.driver.window_handles) - ventanas_antes
        for handle in ventanas_nuevas:
            self.driver.switch_to.window(handle)
            self.driver.close()
            logger.debug("Ventana de PDF cerrada")

        self.driver.switch_to.window(self._ventana_principal)
        logger.success(f"PDF descargado | orden={op.nro_orden} | {op.moneda} {op.procesado}")

    # ------------------------------------------------------------------
    # Retorno al listado
    # ------------------------------------------------------------------

    def _volver_a_lista(self) -> None:
        """
        Regresa al listado ejecutando history.go(-5) en el IFRAME_CENTRAL
        desde el contexto del IFRAME_LEGACY (fuera del central).

        Ref: documentacion flujo B4 — centralFrame.contentWindow.history.go(-5)

        Fallback: re-ejecuta la busqueda con la misma fecha si el listado
        no aparece tras la navegacion por historial.
        """
        self.driver.switch_to.default_content()
        try:
            legacy = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, S.IFRAME_LEGACY))
            )
            self.driver.switch_to.frame(legacy)

            self.driver.execute_script("""
                const central = document.getElementById('kyop-central-load-area');
                if (central && central.contentWindow) {
                    central.contentWindow.history.go(-5);
                }
            """)
            self.esperar(3)
        finally:
            self.driver.switch_to.default_content()

        if not self._lista_presente():
            logger.warning("history.go(-5) no retorno la lista. Re-ejecutando busqueda.")
            self._ingresar_fecha_y_buscar(self._fecha)

    def _lista_presente(self) -> bool:
        """Verifica que el listado de operaciones este visible en el IFRAME_CENTRAL."""
        try:
            self._switch_to_iframe_central()
            botones_detalle = self.driver.find_elements(By.CSS_SELECTOR, S.BTN_VER_DETALLE)
            self.driver.switch_to.default_content()
            return len(botones_detalle) > 0
        except Exception:
            self.driver.switch_to.default_content()
            return False

    def _recuperar_lista(self) -> None:
        """Recuperacion de error: re-ejecuta la busqueda desde el estado actual."""
        self.driver.switch_to.default_content()
        try:
            self._ingresar_fecha_y_buscar(self._fecha)
        except Exception as e:
            logger.error(f"No se pudo recuperar el listado: {e}")

    # ------------------------------------------------------------------
    # Utilitario: cambio de iframe
    # ------------------------------------------------------------------

    def _switch_to_iframe_central(self) -> None:
        """
        Navega al iframe anidado IFRAME_LEGACY > IFRAME_CENTRAL.
        Siempre parte desde default_content para evitar referencias obsoletas
        tras navegaciones internas del iframe.

        Jerarquia:
          default_content
            └── iframe[src*="SPEKYOP"]      (IFRAME_LEGACY)
                  └── #kyop-central-load-area (IFRAME_CENTRAL)
        """
        self.driver.switch_to.default_content()
        legacy = WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, S.IFRAME_LEGACY))
        )
        self.driver.switch_to.frame(legacy)
        central = WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, S.IFRAME_CENTRAL))
        )
        self.driver.switch_to.frame(central)
