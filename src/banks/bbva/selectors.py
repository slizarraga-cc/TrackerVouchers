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
    # Menu principal (Web Component en DOM plano)
    # El host element es accesible por CSS aunque su interior tenga shadow DOM.
    # Estabilidad: ALTA (event-name es identificador de negocio)
    # Ref: PASO 1 — HTML: bbva-web-navigation-menu-item[event-name="event-111V00039"]
    # -------------------------------------------------------------------------
    MENU_PAGOS = 'bbva-web-navigation-menu-item[event-name="event-111V00039"]'

    # -------------------------------------------------------------------------
    # Sub-menu dentro de iframe menurization-landing
    # Estabilidad: ALTA (texto visible)
    # Ref: PASO 2 — bbva-web-link con texto "Seguimiento de pagos masivos"
    # -------------------------------------------------------------------------
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

    @staticmethod
    def btn_ver_detalle_por_orden(nro_orden: str) -> str:
        """
        CSS selector para el boton Ver Detalle de una orden especifica.
        Usa el atributo onclick que contiene el nro_orden como identificador de negocio.
        Ref: PASO 5 — onclick="marca('M','T','0511003','D')"
        Estabilidad: ALTA (nro_orden es ID de negocio)
        """
        return f"a[onclick*=\"'{nro_orden}','D'\"]"
