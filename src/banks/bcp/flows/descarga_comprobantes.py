"""
Flujo: Descarga de comprobantes (Estado de operaciones)
Banco: BCP Telecredito (tlcbcp.com)

Referencias de selectores: manual_componentes.md + Prueba1.md
"""

from typing import Optional

from loguru import logger
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from src.banks.bcp.selectors import BCPSelectors as S
from src.core.base_flow import BaseFlow


class DescargaComprobantes(BaseFlow):

    def __init__(self, driver: WebDriver, timeout: int = 15):
        super().__init__(driver, timeout)

    def ejecutar(self, fecha_desde: str, fecha_hasta: str, max_pdfs: Optional[int] = None) -> int:
        """
        Ejecuta el flujo completo de descarga de PDFs.

        Args:
            fecha_desde: Fecha inicio en formato DD/MM/YYYY
            fecha_hasta:  Fecha fin en formato DD/MM/YYYY
            max_pdfs:     Limite de PDFs a descargar. None = sin limite (descarga todos).

        Returns:
            Cantidad de PDFs descargados exitosamente
        """
        limite_str = str(max_pdfs) if max_pdfs is not None else "sin limite"
        logger.info(
            f"Iniciando DescargaComprobantes | rango: {fecha_desde} -> {fecha_hasta} | max: {limite_str}"
        )

        # Guardamos las fechas para poder re-buscar si los resultados se pierden al volver
        self._fecha_desde = fecha_desde
        self._fecha_hasta = fecha_hasta

        self._navegar_a_bandeja()
        self._cerrar_modal_fraude()
        self._ingresar_fechas(fecha_desde, fecha_hasta)
        self._ejecutar_busqueda()

        descargados = self._procesar_operaciones(max_pdfs)

        logger.success(f"Flujo finalizado: {descargados} PDF(s) descargados")
        return descargados

    # ------------------------------------------------------------------
    # Pasos del flujo
    # ------------------------------------------------------------------

    def _navegar_a_bandeja(self) -> None:
        """
        Navega directamente a la bandeja de consulta por URL hash.
        Evita tener que interactuar con el menu lateral.

        Selector documentado: URL directa '#/h/bandeja-consulta'
        """
        self.driver.get(S.PORTAL_URL)
        self.esperar(3)
        logger.debug(f"Navegado a: {S.PORTAL_URL}")

    def _cerrar_modal_fraude(self) -> None:
        """
        Cierra el modal de alerta de fraude si aparece.

        Selector: //dialog//button[normalize-space(.)="Entendido"]
        Estabilidad: ALTA | Aparicion: condicional (primera carga de sesion)
        """
        if self.elemento_presente(S.MODAL_ENTENDIDO, timeout=5):
            self.click_xpath(S.MODAL_ENTENDIDO)
            logger.info("Modal de fraude cerrado")
            self.esperar(1)
        else:
            logger.debug("Modal de fraude no presente")

    def _ingresar_fechas(self, fecha_desde: str, fecha_hasta: str) -> None:
        """
        Ingresa el rango de fechas en los campos del formulario.

        Selectores (name, estabilidad ALTA):
          - inputDateFrom  -> campo "Desde"
          - inputDateTo    -> campo "Hasta"

        Usa JS nativo porque los Web Components no responden a .send_keys() directamente.
        Tras rellenar se hace click en el body para cerrar el datepicker que se
        abre automaticamente (de lo contrario puede tapar el boton "Buscar").
        """
        self.esperar(1)
        ok_desde = self.rellenar_fecha(S.INPUT_FECHA_DESDE, fecha_desde)
        self.esperar(1)
        ok_hasta = self.rellenar_fecha(S.INPUT_FECHA_HASTA, fecha_hasta)
        self.esperar(1)

        # Cerrar el datepicker enviando Escape al ultimo campo de fecha
        # (evita click en body que puede activar elementos de navegacion)
        try:
            inp = self.driver.find_element(By.CSS_SELECTOR, f'input[name="{S.INPUT_FECHA_HASTA}"]')
            inp.send_keys(Keys.ESCAPE)
        except Exception:
            pass
        self.esperar(1)

        if not ok_desde or not ok_hasta:
            logger.warning(
                "Uno o ambos campos de fecha no fueron encontrados. "
                "Verifica que la pagina de busqueda este cargada."
            )

    def _ejecutar_busqueda(self) -> None:
        """
        Hace clic en el boton "Buscar". Cascada de estrategias porque el
        boton puede estar en DOM plano, dentro de bcp-button-consult-tray
        o dentro de un shadow DOM segun la version del sitio.

        Estrategia 1 — CSS selector directo (ref: Prueba1.md)
          button.bcp-ffw-btn-primary
        Estrategia 2 — XPath al parent Web Component (ref: manual_componentes.md)
          //bcp-button-consult-tray//button
        Estrategia 3 — XPath texto exacto (ref: manual_componentes.md)
          //button[normalize-space(.)="Buscar"]
        Estrategia 4 — shadow DOM JS traversal
          Busca button con texto "Buscar" dentro de shadow roots abiertos
        """
        # Estrategia 1: CSS plano (funciona si el WC no usa shadow DOM real)
        if self.click_js_css("button.bcp-ffw-btn-primary"):
            self.esperar(3)
            logger.info("Busqueda ejecutada (CSS bcp-ffw-btn-primary)")
            return

        # Estrategia 2: XPath via parent bcp-button-consult-tray
        if self.elemento_presente("//bcp-button-consult-tray//button", timeout=5):
            self.click_xpath("//bcp-button-consult-tray//button")
            self.esperar(3)
            logger.info("Busqueda ejecutada (bcp-button-consult-tray)")
            return

        # Estrategia 3: XPath texto exacto
        if self.elemento_presente(S.BOTON_BUSCAR, timeout=5):
            el = self.esperar_elemento(S.BOTON_BUSCAR)
            self.click_js(el)
            self.esperar(3)
            logger.info("Busqueda ejecutada (XPath texto)")
            return

        # Estrategia 4: shadow DOM traversal JS
        if self.click_js_shadow("Buscar"):
            self.esperar(3)
            logger.info("Busqueda ejecutada (shadow DOM traversal)")
            return

        raise RuntimeError(
            "No se encontro el boton 'Buscar' con ninguna estrategia. "
            "Verifica que la pagina de bandeja-consulta este completamente cargada."
        )

    def _procesar_operaciones(self, max_pdfs: Optional[int]) -> int:
        """
        Itera sobre todas las paginas de la tabla descargando el PDF de cada operacion.

        Logica de paginacion (ref: documentacion flujo PASO 4):
          - Procesar todas las filas de la pagina actual.
          - Buscar el siguiente li.page sin clase .active en el nav de paginacion.
          - Hacer click y continuar hasta no encontrar pagina siguiente.

        Si max_pdfs esta definido, se detiene al alcanzar ese numero (uso avanzado).
        """
        descargados = 0
        self._pagina_actual = 1

        while True:
            filas = self._filas_pagina_actual()

            if not filas:
                logger.warning(f"Pagina {self._pagina_actual}: sin operaciones, terminando")
                break

            logger.info(f"--- Pagina {self._pagina_actual}: {len(filas)} operaciones ---")

            for i in range(len(filas)):
                if max_pdfs is not None and descargados >= max_pdfs:
                    logger.info(f"Limite de {max_pdfs} PDFs alcanzado")
                    return descargados

                # Re-fetch para evitar referencias obsoletas tras cada navegacion
                filas = self._filas_pagina_actual()
                if i >= len(filas):
                    logger.warning(f"Fila {i + 1} desaparecio del DOM")
                    break

                fila = filas[i]
                codigo = fila.get_attribute("index") or f"p{self._pagina_actual}f{i + 1}"
                logger.info(f"[pag={self._pagina_actual} | fila={i + 1}/{len(filas)}] Operacion {codigo}")

                try:
                    self._abrir_operacion(fila)
                    if self._descargar_pdf(codigo):
                        descargados += 1
                    self._volver_a_lista()
                    self._restaurar_resultados_y_pagina()
                except Exception as e:
                    logger.error(f"Error en operacion {codigo}: {e}")
                    self._intentar_recuperacion()

            if not self._ir_siguiente_pagina():
                logger.info("Ultima pagina procesada")
                break
            self._pagina_actual += 1

        return descargados

    def _filas_pagina_actual(self) -> list:
        """
        Retorna las filas de datos de la pagina actual.
        El primer elemento del querySelectorAll es el header del Web Component; se omite.
        """
        todas = self.driver.find_elements(By.CSS_SELECTOR, S.TABLE_ROW_TAG)
        return todas[1:] if len(todas) > 1 else []

    def _ir_siguiente_pagina(self) -> bool:
        """
        Hace click en el numero de pagina siguiente al activo.

        Logica JS (ref: documentacion flujo PASO 4):
          - Obtiene todos los li.page del nav de paginacion.
          - Encuentra el indice del li que contiene el elemento .active.
          - Si existe un li siguiente, lo retorna para hacer click.

        Returns:
            True si navego a la siguiente pagina, False si ya estamos en la ultima.
        """
        siguiente = self.driver.execute_script("""
            const items = Array.from(
                document.querySelectorAll('nav[aria-label="Page navigation"] ul li.page')
            );
            if (!items.length) return null;
            const activeIdx = items.findIndex(li => li.querySelector('.active'));
            if (activeIdx === -1 || activeIdx + 1 >= items.length) return null;
            return items[activeIdx + 1];
        """)

        if siguiente is None:
            return False

        self.click_js(siguiente)
        self.esperar(2)
        logger.info(f"Navegado a pagina {self._pagina_actual + 1}")
        return True

    def _ir_a_pagina(self, numero: int) -> bool:
        """
        Navega directamente al numero de pagina indicado haciendo click en su li.page.
        Usado para restaurar la pagina actual tras re-ejecutar la busqueda.

        Returns:
            True si el li de la pagina existe y se hizo click.
        """
        if numero <= 1:
            return True

        ok = self.driver.execute_script("""
            const items = Array.from(
                document.querySelectorAll('nav[aria-label="Page navigation"] ul li.page')
            );
            if (items.length < arguments[0]) return false;
            items[arguments[0] - 1].click();
            return true;
        """, numero)

        if ok:
            self.esperar(2)
            logger.info(f"Restaurada pagina {numero}")
        else:
            logger.warning(f"No se pudo restaurar la pagina {numero} (no existe en el nav)")
        return bool(ok)

    def _abrir_operacion(self, fila) -> None:
        """
        Abre el detalle de una operacion.

        Metodo: click() programatico via JavaScript (obligatorio).
        El clic nativo de Selenium NO funciona en bcp-table-row-consult-tray.

        Selector: bcp-table-row-consult-tray (tag CSS)
        Estabilidad: ALTA cuando se usa el atributo [index] de negocio
        """
        self.click_js(fila)
        self.esperar(2)
        logger.debug("Detalle de operacion abierto")

    def _descargar_pdf(self, codigo: str) -> bool:
        """
        Detecta el tipo de operacion y hace clic en "Descargar PDF".

        Estrategias en orden:
          1. XPath por tipo conocido (Transfer / FEC / Generico)
          2. Shadow DOM JS traversal por texto "Descargar PDF"

        NO se usa CSS por clase (ej: bcp-ffw-btn-outline-primary) porque esa
        clase es compartida por otros botones de la pagina y puede disparar
        acciones incorrectas (ej: cerrar sesion).

        Tras cada click se verifica que seguimos en tlcbcp.com antes de
        declarar exito.

        Selectores documentados (manual_componentes.md):
          - Transferencias: //bcp-button-ntlc-commons-widgets//button[contains(., "Descargar PDF")]
          - FEC:            //fec-button-export-pdf//button[contains(., "Descargar PDF")]
        """
        candidatos = [
            ("Transferencia", S.BTN_DESCARGAR_PDF_TRANSFER),
            ("FEC/Autodesembolso", S.BTN_DESCARGAR_PDF_FEC),
            ("Generico", S.BTN_DESCARGAR_PDF_GENERIC),
        ]

        for tipo, xpath in candidatos:
            presente = self.elemento_presente(xpath, timeout=3)
            logger.debug(f"  [Descargar PDF | {tipo}] presente={presente} | xpath={xpath}")
            if not presente:
                continue

            url_antes = self.driver.current_url
            logger.info(f"Haciendo click en Descargar PDF via {tipo}")
            self.click_xpath(xpath)
            self.esperar(3)
            url_despues = self.driver.current_url
            logger.debug(f"  URL tras click descarga: {url_despues}")

            if "tlcbcp.com" not in url_despues:
                logger.warning(
                    f"Click en {tipo} navego fuera del portal ({url_despues}). "
                    "Abortando descarga para esta operacion."
                )
                return False

            logger.success(f"PDF descargado | operacion={codigo} | tipo={tipo}")
            return True

        # Fallback: shadow DOM traversal por texto (NO por clase CSS, que es demasiado generica)
        url_antes = self.driver.current_url
        logger.debug("  [Descargar PDF | shadow DOM] intentando traversal por texto")
        if self.click_js_shadow("Descargar PDF"):
            self.esperar(3)
            url_despues = self.driver.current_url
            logger.debug(f"  URL tras click shadow DOM: {url_despues}")
            if "tlcbcp.com" not in url_despues:
                logger.warning(
                    f"Shadow DOM click navego fuera del portal ({url_despues}). "
                    "Abortando descarga para esta operacion."
                )
                return False
            logger.success(f"PDF descargado | operacion={codigo} | tipo=shadow DOM")
            return True

        logger.warning(f"Boton 'Descargar PDF' no encontrado para operacion {codigo}")
        return False

    def _volver_a_lista(self) -> None:
        """
        Vuelve a la lista de operaciones.

        Selectores:
          - Transferencias: //ntlc-button-return//a     (estabilidad ALTA)
          - FEC:            //app-return-button//a      (estabilidad ALTA)
          - Fallback:       //a[contains(., "Volver")]  (estabilidad MEDIA)
          - Ultimo recurso: navegar directamente a PORTAL_URL

        Tras el click se verifica que seguimos en tlcbcp.com. Si el boton
        Volver navego fuera del portal (viabcp.com), se navega directamente
        a PORTAL_URL para no perder la sesion.
        """
        candidatos = [
            ("BTN_VOLVER_TRANSFER",  S.BTN_VOLVER_TRANSFER),
            ("BTN_VOLVER_FEC",       S.BTN_VOLVER_FEC),
            ("BTN_VOLVER_FEC_FB",    S.BTN_VOLVER_FEC_FALLBACK),
            ("BTN_VOLVER_GENERIC",   S.BTN_VOLVER_GENERIC),
        ]

        logger.debug(f"Buscando boton Volver | URL actual: {self.driver.current_url}")

        for nombre, xpath in candidatos:
            presente = self.elemento_presente(xpath, timeout=3)
            logger.debug(f"  [{nombre}] presente={presente} | xpath={xpath}")
            if not presente:
                continue

            logger.info(f"Haciendo click en Volver via {nombre}")
            self.click_xpath(xpath)
            self.esperar(2)
            url_post = self.driver.current_url
            logger.debug(f"  URL tras click: {url_post}")

            if "tlcbcp.com" in url_post:
                logger.debug("Vuelto a la lista de operaciones")
                return

            logger.warning(
                f"Boton {nombre} navego fuera del portal ({url_post}). "
                "Navegando directamente a la bandeja."
            )
            break

        logger.info("Navegando a bandeja via URL directa")
        self.driver.get(S.PORTAL_URL)
        self.esperar(3)

    def _restaurar_resultados_y_pagina(self) -> None:
        """
        Al volver a la bandeja los resultados pueden perderse si la pagina cargo
        en estado limpio (ej: se navego a PORTAL_URL como fallback).
        En ese caso re-ejecuta la busqueda y vuelve a la pagina que estabamos procesando.
        """
        if self._filas_pagina_actual():
            return  # resultados siguen presentes
        logger.warning("Resultados perdidos al volver. Re-ejecutando busqueda.")
        self._ingresar_fechas(self._fecha_desde, self._fecha_hasta)
        self._ejecutar_busqueda()
        if self._pagina_actual > 1:
            self._ir_a_pagina(self._pagina_actual)

    def _intentar_recuperacion(self) -> None:
        """Intenta volver a la bandeja en caso de error inesperado."""
        try:
            self.volver_atras()
        except Exception:
            self.driver.get(S.PORTAL_URL)
            self.esperar(3)
