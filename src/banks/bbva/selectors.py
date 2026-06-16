"""
Selectores centralizados para BBVA Net Cash (bbvanetcash.pe).
Fuente: documentacion tecnica del flujo — Seguimiento de pagos masivos.

Estabilidad documentada:
  ALTA  -> basados en ID, name, event-name, title o texto visible
  MEDIA -> basados en clase CSS funcional o estructura de tabla
  BAJA  -> basados en indice posicional
"""


class BBVASelectors:
    # -------------------------------------------------------------------------
    # URLs
    # -------------------------------------------------------------------------
    LOGIN_URL = "https://www.bbvanetcash.pe/DFAUTH85/mult/KDPOSolicitarCredenciales_es.html"

    # -------------------------------------------------------------------------
    # Menu principal — dos variantes segun dimension de pantalla
    #
    # Modo desktop (sidebar visible):
    #   El item "Pagos" es el 3er elemento de bbva-web-navigation-menu en el sidebar.
    #   Estabilidad: MEDIA (posicional, pero unico en el sidebar)
    #   Ref: PASO 1 desktop — sidebar > bbva-web-navigation-menu-item[3]
    #
    # Modo responsive (sidebar oculto):
    #   El item "Pagos" se identifica por event-name en el DOM plano.
    #   Estabilidad: ALTA (event-name es identificador de negocio)
    #   Ref: PASO 1 responsive — bbva-web-navigation-menu-item[event-name="event-111V00039"]
    # -------------------------------------------------------------------------
    MENU_PAGOS_SIDEBAR = (
        '//*[@id="app__content"]/bbva-btge-sidebar-menu'
        '//div/bbva-web-navigation-menu'
        '/bbva-web-navigation-menu-item[3]'
        '//bbva-web-navigation-menu-item-action//div'
    )
    MENU_PAGOS = 'bbva-web-navigation-menu-item[event-name="event-111V00039"]'

    # -------------------------------------------------------------------------
    # Sub-menu — dos variantes segun el modo de menu
    #
    # Modo desktop: el link "Seguimiento de pagos masivos" esta en el DOM principal
    #   dentro del panel de navegacion lateral expandido.
    #   Estabilidad: BAJA (posicional bbva-web-link[6]), usar como fallback.
    #   Ref: PASO 2 desktop — cells-template-bbva-btge-menurization-landing > bbva-web-link[6]
    #
    # Modo responsive: el sub-menu esta dentro de iframe[src*="menurization-landing"]
    #   Estabilidad: ALTA (texto visible)
    #   Ref: PASO 2 responsive — bbva-web-link con texto "Seguimiento de pagos masivos"
    # -------------------------------------------------------------------------
    # ID corregido: el DOM muestra "cells-template-bbva-btge-menurization-landing-solution"
    # (sin -home; ese valor esta en el atributo current-isolated-page, no en el id).
    # cells-template-paper-drawer-panel esta en shadow DOM del componente, por lo que
    # el XPath no puede alcanzarlo — se usa JS traversal en su lugar.
    SUBMENU_SEGUIMIENTO_SIDEBAR = (
        '//*[@id="cells-template-bbva-btge-menurization-landing-solution"]'
        '//cells-template-paper-drawer-panel'
        '/div/div/bbva-foundations-grid-default-layout[2]'
        '/div[5]/div/div/bbva-web-link[6]'
    )
    IFRAME_MENURIZATION = 'iframe[src*="menurization-landing"]'
    SUBMENU_SEGUIMIENTO_TEXTO = "Seguimiento de pagos masivos"

    # -------------------------------------------------------------------------
    # Iframes del contenido principal
    # Jerarquia: iframe[src*="SPEKYOP"] (legacy) > #kyop-central-load-area (central)
    # Estabilidad: ALTA (src pattern e ID respectivamente)
    # Ref: PASO 3 — Contexto: iframe[src*="SPEKYOP"] > iframe#kyop-central-load-area
    # -------------------------------------------------------------------------
    IFRAME_LEGACY = 'iframe[src*="SPEKYOP"]'
    IFRAME_CENTRAL = '#kyop-central-load-area'

    # -------------------------------------------------------------------------
    # Formulario de busqueda (dentro de IFRAME_LEGACY > IFRAME_CENTRAL)
    # Estabilidad: ALTA (ID y name documentados)
    # Ref: PASO 3 y PASO 4
    # -------------------------------------------------------------------------
    INPUT_FECHA = '#fechaEspecifica'            # <input id="fechaEspecifica" name="fechaEspecifica">
    BTN_ACEPTAR = 'input[name="AceptarAvan"]'  # <input type="button" name="AceptarAvan" value="Aceptar">

    # -------------------------------------------------------------------------
    # Tabla de resultados (dentro de IFRAME_CENTRAL)
    # Estabilidad: MEDIA (HTML clasico de tabla)
    # Ref: PASO 5 — bcp-table-row-consult-tray equivalente en BBVA es un <tr> normal
    # -------------------------------------------------------------------------
    TABLE_ROWS = 'table tr'
    BTN_VER_DETALLE = 'a[title="Ver Detalle"]'

    # Columnas de la tabla (0-based)
    # | N° Orden | Planilla | Estado | Descripcion | Moneda | Procesado | Fecha Envio |
    COL_NRO_ORDEN  = 0
    COL_PLANILLA   = 1
    COL_ESTADO     = 2
    COL_DESCRIPCION = 3
    COL_MONEDA     = 4
    COL_PROCESADO  = 5
    COL_FECHA_ENVIO = 6

    # -------------------------------------------------------------------------
    # Detalle de operacion
    # Estabilidad: ALTA (clase funcional + texto visible)
    # Ref: PASO 6 — <a class="ic enlace_ico">Ver contenido de la planilla</a>
    # -------------------------------------------------------------------------
    LINK_VER_PLANILLA = 'a.ic.enlace_ico'

    # -------------------------------------------------------------------------
    # Exportar PDF
    # Estabilidad: ALTA (title attribute)
    # Ref: PASO 7 — <a title="Descargar Pdf" target="_new" ...>
    # -------------------------------------------------------------------------
    BTN_EXPORTAR_PDF = 'a[title="Descargar Pdf"]'

    # -------------------------------------------------------------------------
    # FLUJO 2: Consulta de Operaciones
    # Modulo: Cuentas > Movimientos de cuentas > Consulta de operaciones
    # Ref: Informe de ejecucion 03/06/2026 — Relacion de Operaciones Realizadas
    # Ref DOM: doms/cuentas.html | doms/consulta_operaciones.html
    # -------------------------------------------------------------------------

    # URL directa al modulo (SPA hash-based routing).
    # Confirmada en doms/consulta_operaciones.html:
    #   <!-- URL: .../index.html#!/legacy/000000314E -->
    # Estrategia principal: navegar directo tras login para evitar shadow DOM del menu.
    # Estabilidad: ALTA (ID de ruta legacy en el portal)
    CONSULTA_OP_URL = (
        'https://www.bbvanetcash.pe/nextgenempresas/portal/index.html'
        '#!/legacy/000000314E'
    )

    # Senial de carga: legacy-page esta listo cuando tiene el atributo is-page-ready.
    # Confirmado en DOM: <legacy-page id="cells-template-legacy" is-page-ready="" ...>
    # Estabilidad: ALTA (patron identico a otros modulos legacy de BBVA)
    LEGACY_PAGE = 'legacy-page#cells-template-legacy'

    # Menu principal — "Cuentas" (fallback si URL directa no funciona).
    # event-name confirmado: doms/cuentas.html URL contiene ?id=111V00002.
    # Patron identico a MENU_PAGOS = event-111V00039 para "Pagos".
    # Estabilidad: ALTA (event-name es identificador de negocio)
    MENU_CUENTAS = 'bbva-web-navigation-menu-item[event-name="event-111V00002"]'
    MENU_CUENTAS_TEXTO = "Cuentas"

    # Sub-menu — "Consulta de operaciones" (fallback via menu)
    # Ref: Cuentas > Movimientos de cuentas > Consulta de operaciones
    # Estabilidad: ALTA (texto visible estable)
    SUBMENU_CONSULTA_OP_TEXTO = "Consulta de operaciones"

    # Tabla de Relacion de Operaciones (dentro de IFRAME_CENTRAL)
    # Estructura HTML clasica — sin Web Components
    # Estabilidad: ALTA (class funcional documentado)
    TABLE_DATA     = 'table.tb_data'
    TABLE_ROW_DATA = 'tr.even, tr.odd'   # filas alternas de datos

    # Columnas de la tabla (0-based)
    # | Tipo Operacion | Beneficiario | Fecha y Hora | Importe | Moneda | N° Op | N° Ref |
    COL2_TIPO_OP    = 0
    COL2_BENEFIC    = 1
    COL2_FECHA_HORA = 2
    COL2_IMPORTE    = 3
    COL2_MONEDA     = 4
    COL2_NRO_OP     = 5
    COL2_NRO_REF    = 6

    # Enlace en columna Tipo de Operacion
    # Ref: <a class="enlace">TRANSF A CTAS DE TERCEROS</a>
    # Estabilidad: ALTA (class funcional)
    ENLACE_TIPO_OP = 'a.enlace'

    # Boton Volver (parte inferior izquierda del detalle)
    # Ref: <a class="bt_previous">Volver</a>
    # Estabilidad: ALTA (class funcional)
    BTN_VOLVER = 'a.bt_previous'

    # BTN_EXPORTAR_PDF = 'a[title="Descargar Pdf"]'  — compartido con Flujo 1

    @staticmethod
    def btn_ver_detalle_por_orden(nro_orden: str) -> str:
        """
        CSS selector para el boton Ver Detalle de una orden especifica.
        Usa el atributo onclick que contiene el nro_orden como identificador de negocio.
        Ref: PASO 5 — onclick="marca('M','T','0511003','D')"
        Estabilidad: ALTA (nro_orden es ID de negocio)
        """
        return f"a[onclick*=\"'{nro_orden}','D'\"]"
