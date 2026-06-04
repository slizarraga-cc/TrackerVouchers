"""
Selectores centralizados para Scotiabank Peru — Portal Empresas.
Fuente: documentacion tecnica del flujo exploratorio — Descarga de comprobantes.

Estabilidad:
  ALTA  -> ID unico, data-attr semantico, clase funcional documentada
  MEDIA -> placeholder, clase CSS que puede cambiar entre versiones
  BAJA  -> indice posicional
"""


class ScotiabankSelectors:
    # -------------------------------------------------------------------------
    # URL de entrada (pagina de login del portal empresas)
    # Confirmar con el equipo antes de desplegar en produccion.
    # -------------------------------------------------------------------------
    PORTAL_URL = "https://bancainternetempresas.scotiabank.com.pe/main/loginPage"

    # -------------------------------------------------------------------------
    # Cuentas a procesar (en orden: soles primero, dolares segundo)
    # -------------------------------------------------------------------------
    CUENTAS = [
        {"numero": "000-3991288", "moneda": "soles"},
        {"numero": "000-4728397", "moneda": "dolares"},
    ]

    # -------------------------------------------------------------------------
    # Conceptos validos para filtrar movimientos
    # -------------------------------------------------------------------------
    CONCEPTOS_VALIDOS = frozenset([
        "TBK-PAGO PROVEEDORES",
        "TBK-TRF. CTAS 3ROS",
        "TRANSF.CTAS PROPIAS/CCE",
    ])

    # -------------------------------------------------------------------------
    # Navegacion — menu superior
    #
    # El menu usa enlaces <a> tradicionales, no SPA.
    # MEDIA: el texto "Consulta" puede variar en mayusculas/minusculas.
    # -------------------------------------------------------------------------
    MENU_CONSULTAS = (
        '//a[normalize-space()="Consultas" or normalize-space()="Consulta"]'
    )
    # Estabilidad ALTA — href es un ancla fija del sistema
    LINK_GENERAL_SALDOS = 'a[href="#C1000-consultas"]'

    # -------------------------------------------------------------------------
    # Tabla de cuentas — General de Saldos
    # -------------------------------------------------------------------------
    # Link "Ver" dentro del contenedor de una cuenta especifica.
    # data-account es un atributo semantico: estabilidad ALTA.
    @staticmethod
    def link_ver_cuenta(numero: str) -> str:
        return f'//div[@data-account="{numero}"]//a[contains(@class,"viewMovements")]'

    # Fallback: primer a.viewMovements de la pagina (si no hay data-account)
    BTN_VER_PRIMERO  = '(//a[contains(@class,"viewMovements")])[1]'
    BTN_VER_SEGUNDO  = '(//a[contains(@class,"viewMovements")])[2]'

    # -------------------------------------------------------------------------
    # Filtro de movimientos
    # -------------------------------------------------------------------------
    # Estabilidad ALTA — clases funcionales documentadas
    BTN_FILTRAR        = '//a[contains(@class,"butt-filtro") and contains(@class,"filtrar-active")]'
    BTN_APLICAR_FILTRO = '//input[contains(@class,"btn-aplicar-filtros")]'

    # Inputs de fecha — estabilidad MEDIA (placeholder puede cambiar)
    INPUT_FECHA_DESDE = '(//input[@placeholder="dd/mm/aaaa"])[1]'
    INPUT_FECHA_HASTA = '(//input[@placeholder="dd/mm/aaaa"])[2]'

    # -------------------------------------------------------------------------
    # Tabla de movimientos
    # -------------------------------------------------------------------------
    # Estabilidad ALTA — clase funcional documentada en exploracion
    FILA_MOVIMIENTO     = "div.list-tabl-row.column-payment-tbk-body"

    # Atributos de datos en cada fila (data-* attributes)
    ATTR_CONCEPTO       = "data-transaction"       # "TBK-PAGO PROVEEDORES"
    ATTR_IMPORTE_FMT    = "data-amountformatted"   # "S/ -5,831.02"
    ATTR_MONTO_NUM      = "data-amount"            # "00000000583102" (sin signo)

    # -------------------------------------------------------------------------
    # Modal de detalle del movimiento
    # -------------------------------------------------------------------------
    # Estabilidad ALTA — ID de modal Bootstrap documentado
    MODAL_DETALLE         = "#modalDetalleMovimiento"
    MODAL_DETALLE_VISIBLE = (
        '//*[@id="modalDetalleMovimiento" and contains(@class,"in")]'
        ' | //*[@id="modalDetalleMovimiento"][contains(@style,"display: block")]'
        ' | //*[@id="modalDetalleMovimiento"][contains(@style,"display:block")]'
    )

    # Boton imprimir dentro del modal — estabilidad ALTA (ID unico)
    BTN_IMPRIMIR      = "a#print-movement-details"
    BTN_IMPRIMIR_XPATH = '//*[@id="print-movement-details"]'

    # Boton cerrar modal — estabilidad ALTA (Bootstrap .close + data-dismiss)
    BTN_CERRAR_MODAL  = 'button.close[data-dismiss="modal"]'
    BTN_CERRAR_XPATH  = '//button[@data-dismiss="modal" and contains(@class,"close")]'

    # -------------------------------------------------------------------------
    # Indicadores de carga / espera
    # -------------------------------------------------------------------------
    # Spinner o overlay que aparece mientras se cargan los movimientos.
    # Clases tipicas de jQuery/Bootstrap loading overlays.
    SPINNER = '.loading, .spinner, [class*="loading"], [class*="spinner"]'
