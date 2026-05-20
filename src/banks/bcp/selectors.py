"""
Selectores centralizados para BCP Telecrédito (tlcbcp.com).
Fuente: manual_componentes.md + Prueba1.md

Estabilidad documentada:
  ALTA  -> basados en atributo name, texto visible, o atributo index de negocio
  MEDIA -> basados en clase CSS funcional (no de estilo)
  BAJA  -> basados en indice posicional o ID dinamico
"""


class BCPSelectors:
    # -------------------------------------------------------------------------
    # URLs
    # -------------------------------------------------------------------------
    LOGIN_URL = "https://www.viabcp.com/empresas/cobranzas-y-pagos/telecredito/telecredito-web"
    PORTAL_URL = "https://www.tlcbcp.com/#/h/bandeja-consulta"

    # -------------------------------------------------------------------------
    # Modal alerta de fraude (condicional, no siempre aparece)
    # Estabilidad: ALTA
    # -------------------------------------------------------------------------
    MODAL_ENTENDIDO = '//dialog//button[normalize-space(.)="Entendido"]'

    # -------------------------------------------------------------------------
    # Menu lateral
    # Estabilidad: ALTA (basado en texto visible)
    # -------------------------------------------------------------------------
    MENU_CONSULTA_OPERACIONES = (
        '//bcp-menu-option-sidebar[.//p[normalize-space(text())="Consulta de operaciones"]]'
    )
    SUBMENU_ESTADO_OPERACIONES = '//p[normalize-space(text())="Estado de operaciones"]'

    # -------------------------------------------------------------------------
    # Formulario de busqueda
    # Estabilidad: ALTA (name no cambia entre sesiones)
    # -------------------------------------------------------------------------
    INPUT_FECHA_DESDE = "inputDateFrom"   # Usar con rellenar_fecha(name, valor)
    INPUT_FECHA_HASTA = "inputDateTo"

    BOTON_BUSCAR = '//button[normalize-space(.)="Buscar"]'

    # -------------------------------------------------------------------------
    # Tabla de resultados
    # Estabilidad: ALTA (selector de tag CSS)
    # El atributo [index] de cada fila = codigo de solicitud (identificador de negocio)
    # -------------------------------------------------------------------------
    TABLE_ROW_TAG = "bcp-table-row-consult-tray"

    @staticmethod
    def fila_por_codigo(codigo: str) -> str:
        """XPath para una fila especifica por su codigo de solicitud."""
        return f'//bcp-table-row-consult-tray[@index="{codigo}"]'

    # -------------------------------------------------------------------------
    # Detalle: Transferencias
    # Estabilidad: ALTA
    # -------------------------------------------------------------------------
    BTN_DESCARGAR_PDF_TRANSFER = (
        '//bcp-button-ntlc-commons-widgets//button[contains(., "Descargar PDF")]'
    )
    BTN_VOLVER_TRANSFER = "//ntlc-button-return//a"

    # -------------------------------------------------------------------------
    # Detalle: FEC / Autodesembolso
    # Estabilidad: ALTA
    # -------------------------------------------------------------------------
    BTN_DESCARGAR_PDF_FEC = (
        '//fec-button-export-pdf//button[contains(., "Descargar PDF")]'
    )
    # XPath verificado en sitio:
    # app-go-back > bcp-button-fiec-payment-detail > a
    BTN_VOLVER_FEC = "//app-go-back//bcp-button-fiec-payment-detail//a"
    BTN_VOLVER_FEC_FALLBACK = "//app-go-back//a"

    # -------------------------------------------------------------------------
    # Fallback generico (aplica a ambos tipos)
    # Estabilidad: MEDIA
    # -------------------------------------------------------------------------
    BTN_DESCARGAR_PDF_GENERIC = '//button[contains(normalize-space(.), "Descargar PDF")]'
    BTN_VOLVER_GENERIC = '//a[contains(normalize-space(.), "Volver")]'

    # -------------------------------------------------------------------------
    # Paginacion
    # Ref: documentacion de flujo — PASO 4
    # Estabilidad: ALTA (aria-label es semantico, no de estilo)
    # -------------------------------------------------------------------------
    # CSS selector del nav de paginacion
    PAGINACION_NAV = 'nav[aria-label="Page navigation"]'
    # Todos los li de paginas dentro del nav
    PAGINACION_LI_ITEMS = 'nav[aria-label="Page navigation"] ul li.page'
