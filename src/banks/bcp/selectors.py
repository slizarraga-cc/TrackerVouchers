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
    # Filtro Estado de operacion
    # Estabilidad: MEDIA (Web Component custom; el tag puede cambiar entre versiones)
    # -------------------------------------------------------------------------
    # Tag CSS del componente custom que envuelve el select de estado
    DROPDOWN_ESTADO_TAG = "bcp-select-consult-tray"
    # CSS del indicador visual de la opcion "Procesada" (span.processed dentro de bcp-select-option-consult-tray)
    # Confirmado en dom_error_bcp.html: cada opcion tiene un span con clase de estado (.processed, .pending, .rejected)
    OPCION_PROCESADA_CSS = "bcp-select-option-consult-tray .processed"
    # XPath de la opcion "Procesada" una vez que el dropdown esta abierto
    OPCION_PROCESADA = '//span[contains(@class,"processed")]'

    # -------------------------------------------------------------------------
    # Detalle de operacion — tipo y monto
    # Estabilidad: ALTA (basado en texto visible del label)
    # Patron: //div[normalize-space()="<label>"]/following-sibling::div[1]
    # -------------------------------------------------------------------------
    TIPO_OPERACION_VALOR = (
        '//div[normalize-space()="Tipo de operación"]/following-sibling::div[1]'
    )

    # Mapa: fragmento del tipo de operacion (lowercase) -> XPath del valor del monto.
    #
    # Cada tipo puede tener una estructura DOM diferente segun el componente usado.
    # Los XPaths fueron derivados de inspeccion directa del page_source de cada pagina:
    #
    #   - Tipos con estructura div.col-static / div.col.pl-0 (ntlc-commons-widgets):
    #     El label esta en <p> dentro de div.col-static y el valor en div.col.pl-0.
    #     Confirmado en: dom_monto_local.html
    #
    #   - Tipos con estructura ldd-container (y0daaa / cheques):
    #     El label esta en ldd-title > p y el valor en ldd-subtitle-container > h3.
    #     Confirmado en: dom_monto_checke.html
    #
    #   - Tipos con estructura div label / div value (transferencias diferidas):
    #     El label y valor estan en divs hermanos directos.
    #     Confirmado en: flujos previos funcionales.
    MONTO_POR_TIPO: dict = {
        'tipo de cambio': (
            '//div[normalize-space()="Monto cambiado"]/following-sibling::div[1]'
        ),
        'transferencias a cuentas de terceros bcp local': (
            # Label " Monto " en div.col-static > p; valor en sibling div.col.pl-0 > ... > h3
            '//div[contains(@class,"col-static")][.//p[normalize-space()="Monto"]]'
            '/following-sibling::div[contains(@class,"col")]'
        ),
        'transferencia a otros bancos locales - diferida': (
            '//div[normalize-space()="Monto transferido"]/following-sibling::div[1]'
        ),
        'pago de servicios': (
            '//div[normalize-space()="Monto a pagar"]/following-sibling::div[1]'
        ),
        'pago masivo a proveedores': (
            # "Monto" puede existir en multiples secciones; acotado al que sigue a "Datos de la planilla"
            '//div[normalize-space()="Datos de la planilla"]'
            '/following::div[normalize-space()="Monto"][1]/following-sibling::div[1]'
        ),
        'transferencia a otros bancos del exterior': (
            '//div[normalize-space()="Monto total"]/following-sibling::div[1]'
        ),
        'cheques': (
            # Label "Monto" en ldd-title > p; valor en ldd-subtitle-container > h3
            '//p[normalize-space()="Monto"]'
            '/ancestor::div[contains(@class,"ldd-container")]'
            '/div[contains(@class,"ldd-subtitle-container")]'
        ),
    }

    # -------------------------------------------------------------------------
    # Detalle de operacion — fecha
    # Se prueban en orden hasta encontrar el primero que exista en el DOM.
    # Patron: //div[normalize-space()="<label>"]/following-sibling::div[1]
    # -------------------------------------------------------------------------
    FECHA_LABELS = [
        "Fecha de operación",
        "Fecha operación",
        "Fecha",
        "Fecha de solicitud",
        "Fecha de pago",
        "Fecha valor",
        "Fecha de acreditamiento",
        "Fecha de ejecución",
        "Fecha de proceso",
    ]

    # -------------------------------------------------------------------------
    # Paginacion
    # Ref: documentacion de flujo — PASO 4
    # Estabilidad: ALTA (aria-label es semantico, no de estilo)
    # -------------------------------------------------------------------------
    # CSS selector del nav de paginacion
    PAGINACION_NAV = 'nav[aria-label="Page navigation"]'
    # Todos los li de paginas dentro del nav
    PAGINACION_LI_ITEMS = 'nav[aria-label="Page navigation"] ul li.page'
