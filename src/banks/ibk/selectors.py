"""
Selectores centralizados para Interbank Empresas (empresas.interbank.pe).
Fuente: documentacion tecnica del flujo — Descarga de comprobantes masivos.

Estabilidad documentada:
  ALTA  -> basados en data-test, name, aria-label o texto visible semantico
  MEDIA -> basados en clase CSS funcional o estructura de tabla Angular Material
  BAJA  -> basados en indice posicional o ID dinamico
"""


class IBKSelectors:
    # -------------------------------------------------------------------------
    # URLs
    # -------------------------------------------------------------------------
    HISTORIAL_URL = "https://empresas.interbank.pe/pagos-transferencias/masivos/historial/"
    REPORTES_URL  = "https://empresas.interbank.pe/reportes"

    # -------------------------------------------------------------------------
    # Servicios a procesar (en orden: soles primero, dolares segundo)
    # -------------------------------------------------------------------------
    SERVICIO_SOLES   = "AHTC-01 - PROVEEDORES"
    SERVICIO_DOLARES = "AHTC-02 - PROVEEDORES"
    SERVICIOS = [
        (SERVICIO_SOLES,   "soles"),
        (SERVICIO_DOLARES, "dolares"),
    ]

    # -------------------------------------------------------------------------
    # Formulario de busqueda — Angular Material (mat-select)
    #
    # SELECT_SERVICIO / SELECT_CANAL usan data-test: estabilidad ALTA.
    # SELECT_TIPO_PAGO no tiene data-test; se localiza por el label visible
    # dentro del mismo mat-form-field: estabilidad MEDIA.
    # -------------------------------------------------------------------------
    SELECT_TIPO_PAGO = 'mat-select[data-test="cmbTypePayment"]'      # ALTA
    SELECT_SERVICIO  = 'mat-select[data-test="cmbService"]'          # ALTA
    SELECT_CANAL     = 'mat-select[data-test="cmbShippingChannel"]'  # ALTA

    # Opciones de los selects (aparecen en el CDK overlay al abrir el mat-select)
    OPCION_PAGO_PROVEEDORES = '//mat-option[contains(normalize-space(.), "Pago a proveedores")]'
    OPCION_CANAL_TODOS      = '//mat-option[normalize-space()="Todos"]'

    @staticmethod
    def opcion_servicio(nombre: str) -> str:
        """XPath para la mat-option del servicio por nombre exacto."""
        return f'//mat-option[normalize-space()="{nombre}"]'

    # -------------------------------------------------------------------------
    # Campos de fecha (Angular Material datepicker)
    # Los inputs viven dentro de ibk-datepicker-v2. No tienen placeholder;
    # se identifican por el atributo data-mat-calendar que enlaza al calendario.
    # Estabilidad: ALTA (atributo funcional de Angular Material datepicker)
    # -------------------------------------------------------------------------
    INPUT_FECHA_INICIO = '(//ibk-datepicker-v2//input[@data-mat-calendar])[1]'
    INPUT_FECHA_FIN    = '(//ibk-datepicker-v2//input[@data-mat-calendar])[2]'

    # -------------------------------------------------------------------------
    # Boton Buscar
    # Estabilidad: ALTA (type="submit" es semantico)
    # -------------------------------------------------------------------------
    BOTON_BUSCAR = '//button[@type="submit"]'

    # -------------------------------------------------------------------------
    # Tabla de resultados — IBK usa ibk-table > ibk-table-body > ibk-table-row
    # Dentro de un virtual-scroller: solo filas visibles en DOM en cada momento.
    # Estabilidad: ALTA (componente custom ibk-table)
    # -------------------------------------------------------------------------
    TABLA_FILAS = '//ibk-table//ibk-table-body//ibk-table-row'

    # Texto que indica estado "Procesado" dentro de una fila
    ESTADO_PROCESADO = "Procesado"

    # Boton lupa (ver detalle) — celda 9 de la fila segun documentacion exploratorias
    # Estabilidad: MEDIA (posicion de columna puede cambiar si el portal agrega columnas)
    BTN_LUPA          = './ibk-table-cell[9]/ibk-button-icon[1]/button[1]'
    BTN_LUPA_FALLBACK = './/ibk-button-icon[1]//button[1]'

    # -------------------------------------------------------------------------
    # Pantalla de detalle — Informacion del lote
    # ibk-card-section[3] > div > div > ibk-card-label[N] / ibk-card-description[N]
    # Indices documentados:
    #   [4] = Total soles    [5] = Total dolares
    # Estabilidad: MEDIA (posicion dentro del card-section puede variar)
    # -------------------------------------------------------------------------
    CAMPO_TOTAL_SOLES = (
        '//ibk-card-label[normalize-space()="Total soles"]'
        '/following-sibling::ibk-card-description[1]'
    )
    CAMPO_TOTAL_DOLARES = (
        '//ibk-card-label[normalize-space()="Total dólares"]'
        '/following-sibling::ibk-card-description[1]'
    )
    # Fallback posicional
    CAMPO_TOTAL_SOLES_POS   = '//ibk-processed-detail//ibk-card-section[3]//ibk-card-description[4]'
    CAMPO_TOTAL_DOLARES_POS = '//ibk-processed-detail//ibk-card-section[3]//ibk-card-description[5]'

    # Selector de monto segun tipo de moneda
    CAMPO_MONTO: dict = {
        "soles":   CAMPO_TOTAL_SOLES,
        "dolares": CAMPO_TOTAL_DOLARES,
    }
    CAMPO_MONTO_POS: dict = {
        "soles":   CAMPO_TOTAL_SOLES_POS,
        "dolares": CAMPO_TOTAL_DOLARES_POS,
    }

    # -------------------------------------------------------------------------
    # Boton imprimir en la barra "Detalle completo"
    # Abre window.print() — interceptado via CDP Page.printToPDF para guardar PDF
    # Estabilidad: ALTA (testid semantico documentado)
    # -------------------------------------------------------------------------
    BTN_IMPRIMIR = '//*[@testid="lnkPrintConstancy"]'

    # -------------------------------------------------------------------------
    # Paginacion de la tabla (Angular Material paginator)
    # El boton "siguiente pagina" se deshabilita cuando no hay mas paginas.
    # Estabilidad: MEDIA (aria-label puede estar en espanol o ingles segun locale)
    # -------------------------------------------------------------------------
    # Angular Material deshabilita via clase CSS (mat-mdc-button-disabled), NO via
    # atributo HTML disabled. El atributo disabledinteractive="" permite que el boton
    # reciba eventos (para tooltips) aunque este deshabilitado — por eso not(@disabled)
    # no es suficiente. Hay que excluir tambien la clase mat-mdc-button-disabled.
    BTN_SIGUIENTE_PAGINA = (
        '//button[contains(@class,"paginator-navigation-next") '
        'and not(contains(@class,"mat-mdc-button-disabled")) '
        'and not(@disabled)] | '
        '//button[@aria-label="Next page" '
        'and not(contains(@class,"mat-mdc-button-disabled")) '
        'and not(@disabled)] | '
        '//button[@aria-label="Siguiente página" '
        'and not(contains(@class,"mat-mdc-button-disabled")) '
        'and not(@disabled)] | '
        '//button[@aria-label="Siguiente pagina" '
        'and not(contains(@class,"mat-mdc-button-disabled")) '
        'and not(@disabled)]'
    )
    # Selector para verificar si existe paginador (no importa si habilitado)
    PAGINATOR = 'mat-paginator, ibk-paginator'

    # -------------------------------------------------------------------------
    # Boton Regresar (volver al historial desde el detalle)
    # Estabilidad: ALTA (texto visible semantico)
    # -------------------------------------------------------------------------
    BTN_REGRESAR = (
        '//a[contains(normalize-space(),"Regresar")] | '
        '//button[contains(normalize-space(),"Regresar")] | '
        '//*[@testid="lnkBack"] | '
        '//*[contains(@class,"back") and contains(normalize-space(),"Regresar")]'
    )
