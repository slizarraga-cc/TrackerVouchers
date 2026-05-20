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
    nro_orden: str
    planilla: str = ""
    estado: str = ""
    descripcion: str = ""
    moneda: str = ""
    procesado: str = ""
    fecha_envio: str = ""


class SeguimientoPagosMasivos(BaseFlow):

    def __init__(self, driver: WebDriver, timeout: int = 15, downloads_path: str = "/home/seluser/Downloads"):
        super().__init__(driver, timeout)
        self._fecha = ""
        self._ventana_principal = ""
        self._downloads_path = downloads_path

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
        Paso 1: Clic en "Pagos" del menu.
        Paso 2: Clic en "Seguimiento de pagos masivos".

        Detecta automaticamente el modo de pantalla via JS (no XPath,
        que falla con shadow DOM de Web Components):
        - Desktop (sidebar visible): bbva-btge-sidebar-menu presente en DOM.
        - Responsive (sidebar oculto): sidebar no encontrado.
        """
        self.driver.switch_to.default_content()
        self._log_estado_dom()

        sidebar_en_dom = self.elemento_presente_js('bbva-btge-sidebar-menu')

        if sidebar_en_dom:
            logger.info("Modo desktop detectado — bbva-btge-sidebar-menu presente en DOM")
            self._navegar_menu_sidebar()
        else:
            logger.info("Modo responsive detectado — bbva-btge-sidebar-menu no encontrado")
            self._navegar_menu_responsive()

        self.esperar(3)
        logger.info("Navegado a Seguimiento de pagos masivos")

    def _log_estado_dom(self) -> None:
        """Registra informacion diagnostica del estado del DOM para debug."""
        try:
            url    = self.driver.current_url
            width  = self.driver.execute_script("return window.innerWidth")
            height = self.driver.execute_script("return window.innerHeight")
            sidebar_host   = self.driver.execute_script("return !!document.querySelector('bbva-btge-sidebar-menu')")
            menu_event     = self.driver.execute_script(
                "return !!document.querySelector('bbva-web-navigation-menu-item[event-name=\"event-111V00039\"]')"
            )
            menu_any_item  = self.driver.execute_script(
                "return !!document.querySelector('bbva-web-navigation-menu-item')"
            )
            nav_menu       = self.driver.execute_script(
                "return !!document.querySelector('bbva-web-navigation-menu')"
            )
            iframe_menu    = self.driver.execute_script(
                "return !!document.querySelector('iframe[src*=\"menurization-landing\"]')"
            )
            logger.debug(f"[DOM] URL: {url}")
            logger.debug(f"[DOM] Ventana: {width}x{height}px")
            logger.debug(f"[DOM] bbva-btge-sidebar-menu: {sidebar_host}")
            logger.debug(f"[DOM] bbva-web-navigation-menu: {nav_menu}")
            logger.debug(f"[DOM] bbva-web-navigation-menu-item (cualquiera): {menu_any_item}")
            logger.debug(f"[DOM] bbva-web-navigation-menu-item[event-name='event-111V00039']: {menu_event}")
            logger.debug(f"[DOM] iframe menurization-landing: {iframe_menu}")
        except Exception as e:
            logger.warning(f"[DOM] Error al leer estado diagnostico: {e}")

    def _navegar_menu_sidebar(self) -> None:
        """
        Menu lateral visible (resolucion desktop).
        Los elementos estan dentro del shadow DOM del sidebar —
        XPath no funciona; se usa JS traversal recursivo.

        El sub-menu se expande dentro del shadow DOM del sidebar (NO en iframe).
        En responsive el sub-menu aparece en iframe menurization-landing.
        """
        # Click en "Pagos": traversal profundo hasta bbva-web-navigation-menu-item-action > div
        resultado_click = self.click_js_shadow_menu_item("event-111V00039")
        logger.info(f"Click en menu Pagos resultado: {resultado_click}")
        if resultado_click == 'not-found':
            # Fallback: XPath posicional (puede funcionar si shadow root es abierto)
            logger.debug("event-name no hallado en shadow DOM, intentando XPath posicional")
            if self.elemento_presente(S.MENU_PAGOS_SIDEBAR, timeout=3):
                self.click_xpath(S.MENU_PAGOS_SIDEBAR)
                logger.info("Menu Pagos clickeado via XPath posicional — modo desktop")
            else:
                raise RuntimeError(
                    "No se pudo hacer click en menu Pagos (desktop). "
                    "Ni shadow DOM traversal ni XPath posicional encontraron el elemento."
                )

        # Esperar a que la seccion de sub-menu cargue en el DOM.
        # BBVA carga cells-template-bbva-btge-menurization-landing-solution
        # de forma asincrona tras el click en Pagos — puede tardar mas de 3 segundos.
        SECTION_CSS = '#cells-template-bbva-btge-menurization-landing-solution'
        logger.debug(f"Esperando que aparezca '{SECTION_CSS}' en DOM...")
        seccion_presente = False
        for _ in range(20):          # hasta 10 segundos (20 x 0.5s)
            self.esperar(0.5)
            if self.elemento_presente_js(SECTION_CSS):
                seccion_presente = True
                break
        logger.debug(f"Seccion menurization en DOM: {seccion_presente}")

        # El componente carga su contenido desde origin= URL de forma asincrona.
        # bbva-web-link vive en el shadow DOM del componente — hay que buscar desde
        # document (no desde sec, que tiene cero hijos en light DOM) y esperar
        # hasta que los links aparezcan (show-spinner puede seguir activo un tiempo).
        # Esperar a que el contenido de la seccion menurization cargue.
        # IMPORTANTE: contar desde `sec` (no desde `document`) para no confundir
        # los bbva-web-link del sidebar con los del sub-menu de Pagos.
        SECTION_CSS = '#cells-template-bbva-btge-menurization-landing-solution'
        logger.debug("Esperando que bbva-web-link aparezca dentro de la seccion menurization (hasta 20s)...")
        links_encontrados = 0
        for _ in range(40):   # 40 x 0.5s = 20 segundos max
            self.esperar(0.5)
            links_encontrados = self.driver.execute_script("""
                const SECTION_CSS = arguments[0];
                const sec = document.querySelector(SECTION_CSS);
                if (!sec) return -1;  // -1 = seccion no presente aun

                function findAll(root, tag) {
                    let items = Array.from(root.querySelectorAll ? root.querySelectorAll(tag) : []);
                    const all = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
                    for (const el of all) {
                        if (el.shadowRoot) items = items.concat(findAll(el.shadowRoot, tag));
                    }
                    if (root.shadowRoot) items = items.concat(findAll(root.shadowRoot, tag));
                    return items;
                }

                return findAll(sec, 'bbva-web-link').length;
            """, SECTION_CSS)
            if links_encontrados > 0:
                break
        logger.debug(f"bbva-web-link en seccion menurization: {links_encontrados}")

        # Diagnostico completo una vez que tenemos links (o agotamos el tiempo)
        self._log_seccion_menurization()

        # Intento 1: XPath en DOM principal (funciona si contenido esta en light DOM)
        if self.elemento_presente(S.SUBMENU_SEGUIMIENTO_SIDEBAR, timeout=3):
            self.click_xpath(S.SUBMENU_SEGUIMIENTO_SIDEBAR)
            logger.info("Sub-menu clickeado via XPath DOM principal")
            return

        # Intento 2: JS — busca por texto en shadow DOM desde document root
        if self.click_js_shadow_link(S.SUBMENU_SEGUIMIENTO_TEXTO):
            logger.info("Sub-menu clickeado via shadow DOM link traversal (texto)")
            return

        # Intento 3: window.frames — el iframe del menu esta dentro del shadow DOM
        # del componente bbva-btge-menurization-landing-solution-page, por lo que
        # querySelector no lo ve, pero window.frames si lo expone.
        if self._click_submenu_en_window_frames():
            logger.info("Sub-menu clickeado via window.frames (iframe en shadow DOM)")
            return

        # Intento 4: JS — busca bbva-web-link[5] (6to) desde document root
        if self._click_bbva_web_link_nth(5):
            logger.info("Sub-menu clickeado via JS bbva-web-link[5] desde document")
            return

        # Intento 5: fallback al iframe por CSS selector (responsive)
        logger.debug("Sub-menu no encontrado, intentando iframe menurization como ultimo recurso")
        self._click_submenu_en_iframe()

    def _log_seccion_menurization(self) -> None:
        """Diagnostico de que hay dentro de la seccion menurization tras el click en Pagos."""
        try:
            info = self.driver.execute_script("""
                const SECTION = '#cells-template-bbva-btge-menurization-landing-solution';
                const sec = document.querySelector(SECTION);
                if (!sec) return {presente: false};

                function findAll(root, tag) {
                    let items = Array.from(root.querySelectorAll ? root.querySelectorAll(tag) : []);
                    const all = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
                    for (const el of all) {
                        if (el.shadowRoot) items = items.concat(findAll(el.shadowRoot, tag));
                    }
                    if (root.shadowRoot) items = items.concat(findAll(root.shadowRoot, tag));
                    return items;
                }

                function iframesIn(root) {
                    // Retorna solo elementos iframe, sin mezclar con strings
                    let result = [];
                    const list = root.querySelectorAll ? Array.from(root.querySelectorAll('iframe')) : [];
                    result.push(...list);
                    const all = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
                    for (const el of all) {
                        if (el.shadowRoot) result.push(...iframesIn(el.shadowRoot));
                    }
                    if (root.shadowRoot) result.push(...iframesIn(root.shadowRoot));
                    return result;
                }

                const sr = sec.shadowRoot;
                const links = findAll(sec, 'bbva-web-link');
                const allLinks = findAll(sec, 'a');
                const iframeEls = iframesIn(sec);

                // window.frames info
                const framesInfo = [];
                for (let i = 0; i < window.frames.length; i++) {
                    try {
                        framesInfo.push({i, href: window.frames[i].location.href});
                    } catch(e) {
                        framesInfo.push({i, href: '(cross-origin or error)'});
                    }
                }

                return {
                    presente: true,
                    hasShadowRoot: !!sr,
                    shadowChildCount: sr ? sr.childElementCount : null,
                    shadowHTML: sr ? sr.innerHTML.slice(0, 400) : null,
                    spinner: sec.hasAttribute('show-spinner'),
                    isPageReady: sec.hasAttribute('is-page-ready'),
                    bbvaWebLinks: links.length,
                    aLinks: allLinks.length,
                    aTextos: allLinks.slice(0, 10).map(l => l.textContent.trim().slice(0, 60)),
                    iframesEnSec: iframeEls.map(f => f.src || f.getAttribute('src') || '(no-src)'),
                    windowFrames: framesInfo,
                };
            """)
            logger.debug(f"[Menurization] presente={info.get('presente')}")
            logger.debug(f"[Menurization] shadowRoot={info.get('hasShadowRoot')} | childCount={info.get('shadowChildCount')}")
            logger.debug(f"[Menurization] show-spinner={info.get('spinner')} | is-page-ready={info.get('isPageReady')}")
            logger.debug(f"[Menurization] shadowHTML (400 chars): {info.get('shadowHTML')}")
            logger.debug(f"[Menurization] iframes dentro de sec: {info.get('iframesEnSec')}")
            logger.debug(f"[Menurization] bbva-web-link count={info.get('bbvaWebLinks')} | <a> count={info.get('aLinks')}")
            for i, txt in enumerate(info.get('aTextos', [])):
                logger.debug(f"[Menurization] <a>[{i}]: '{txt}'")
            logger.debug(f"[Menurization] window.frames total={len(info.get('windowFrames', []))}")
            for f in info.get('windowFrames', []):
                logger.debug(f"[Menurization] frame[{f['i']}]: {f['href']}")
        except Exception as e:
            logger.warning(f"[Menurization] Error en diagnostico: {e}")

    def _click_submenu_en_window_frames(self) -> bool:
        """
        El iframe del menu de Pagos esta dentro del shadow DOM del componente
        bbva-btge-menurization-landing-solution-page.
        window.frames no lo expone (iframes en shadow DOM no aparecen ahi),
        pero JS puede retornar el elemento iframe como WebElement de Selenium,
        y driver.switch_to.frame(webElement) si funciona.

        Estrategia:
        1. JS recorre el shadow DOM de sec y retorna el primer <iframe> que encuentra.
        2. Selenium hace switch_to.frame con ese WebElement.
        3. Busca el link por texto dentro del documento del frame.
        """
        try:
            iframe_el = self.driver.execute_script("""
                function findIframe(root) {
                    if (root.querySelectorAll) {
                        const frames = root.querySelectorAll('iframe');
                        if (frames.length) return frames[0];
                        for (const el of root.querySelectorAll('*')) {
                            if (el.shadowRoot) {
                                const f = findIframe(el.shadowRoot);
                                if (f) return f;
                            }
                        }
                    }
                    if (root.shadowRoot) {
                        const f = findIframe(root.shadowRoot);
                        if (f) return f;
                    }
                    return null;
                }
                const sec = document.querySelector('#cells-template-bbva-btge-menurization-landing-solution');
                return sec ? findIframe(sec) : null;
            """)

            if not iframe_el:
                logger.debug("[ShadowFrame] No se encontro iframe dentro del shadow DOM de sec")
                return False

            logger.debug("[ShadowFrame] iframe encontrado via JS — haciendo switch_to.frame")
            self.driver.switch_to.frame(iframe_el)

            # Esperar a que el contenido del iframe cargue
            self.esperar(2)

            # Buscar el link por texto (puede estar en shadow DOM dentro del frame tambien)
            resultado = self.driver.execute_script("""
                const texto = arguments[0];
                function buscar(root) {
                    for (const tag of ['a', 'bbva-web-link', 'li', 'span']) {
                        for (const el of (root.querySelectorAll ? root.querySelectorAll(tag) : [])) {
                            if (el.textContent.trim().includes(texto)) {
                                el.click();
                                return 'clicked:' + el.tagName + ' | text=' + el.textContent.trim().slice(0, 60);
                            }
                        }
                    }
                    for (const el of (root.querySelectorAll ? root.querySelectorAll('*') : [])) {
                        if (el.shadowRoot) {
                            const r = buscar(el.shadowRoot);
                            if (r) return r;
                        }
                    }
                    return null;
                }
                return buscar(document);
            """, S.SUBMENU_SEGUIMIENTO_TEXTO)

            logger.debug(f"[ShadowFrame] Resultado click: {resultado}")

            if resultado:
                return True

            # Si no encontro, loguear todos los links para diagnostico
            links_en_frame = self.driver.execute_script("""
                return Array.from(document.querySelectorAll('a, bbva-web-link'))
                    .map(el => el.textContent.trim().slice(0, 80))
                    .filter(t => t.length > 0)
                    .slice(0, 20);
            """)
            logger.debug(f"[ShadowFrame] Links en iframe: {links_en_frame}")
            return False

        except Exception as e:
            logger.warning(f"[ShadowFrame] Error: {e}")
            return False
        finally:
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass

    def _click_bbva_web_link_nth(self, index: int) -> bool:
        """
        Hace click en el Nth bbva-web-link (0-indexed) dentro de
        #cells-template-bbva-btge-menurization-landing-solution,
        atravesando shadow DOM si es necesario.
        """
        script = """
        const SECTION = '#cells-template-bbva-btge-menurization-landing-solution';
        const sec = document.querySelector(SECTION);
        if (!sec) return false;

        function findAll(root, tag) {
            let items = Array.from(root.querySelectorAll ? root.querySelectorAll(tag) : []);
            const all = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
            for (const el of all) {
                if (el.shadowRoot) items = items.concat(findAll(el.shadowRoot, tag));
            }
            if (root.shadowRoot) items = items.concat(findAll(root.shadowRoot, tag));
            return items;
        }

        const links = findAll(sec, 'bbva-web-link');
        if (links.length <= arguments[0]) return false;
        links[arguments[0]].click();
        return true;
        """
        return bool(self.driver.execute_script(script, index))

    def _navegar_menu_responsive(self) -> None:
        """
        Menu lateral oculto (resolucion responsive).
        Intento 1: CSS directo (light DOM).
        Intento 2: shadow DOM traversal.
        """
        # Intento 1: CSS directo
        if self.click_js_css(S.MENU_PAGOS):
            logger.info("Menu Pagos clickeado via CSS directo — modo responsive")
        else:
            # Intento 2: shadow DOM traversal
            logger.debug("CSS directo fallido, intentando shadow DOM traversal")
            if self.click_js_shadow_css(S.MENU_PAGOS):
                logger.info("Menu Pagos clickeado via shadow DOM traversal — modo responsive")
            else:
                raise RuntimeError(
                    f"No se encontro el menu Pagos en ningun modo. "
                    f"Selector: {S.MENU_PAGOS}"
                )
        self.esperar(2)
        self._click_submenu_en_iframe()

    def _click_submenu_en_iframe(self) -> None:
        """Busca y hace click en 'Seguimiento de pagos masivos' dentro del iframe menurization."""
        iframe_presente = self.driver.execute_script(
            "return !!document.querySelector(arguments[0])", S.IFRAME_MENURIZATION
        )
        logger.debug(f"iframe menurization presente en DOM antes de esperar: {iframe_presente}")
        try:
            iframe_menu = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, S.IFRAME_MENURIZATION))
            )
            self.driver.switch_to.frame(iframe_menu)

            # Intento 1: shadow DOM traversal por texto
            if self.click_js_shadow(S.SUBMENU_SEGUIMIENTO_TEXTO):
                logger.info("Sub-menu clickeado via shadow DOM traversal (texto) en iframe")
                return

            # Intento 2: XPath directo en iframe
            xpath = f'//bbva-web-link[normalize-space(.)="{S.SUBMENU_SEGUIMIENTO_TEXTO}"]'
            if self.elemento_presente(xpath, timeout=5):
                self.click_xpath(xpath)
                logger.info("Sub-menu clickeado via XPath en iframe")
            else:
                raise RuntimeError(
                    f"No se encontro '{S.SUBMENU_SEGUIMIENTO_TEXTO}' en iframe menurization. "
                    "Verifica que el menu Pagos este expandido."
                )
        finally:
            self.driver.switch_to.default_content()

    # ------------------------------------------------------------------
    # Formulario de busqueda
    # ------------------------------------------------------------------

    def _ingresar_fecha_y_buscar(self, fecha: str) -> None:
        """
        Paso 3: Ingresa la fecha en #fechaEspecifica (input con jQuery datepicker).
        Paso 4: Hace clic en el boton "Aceptar".

        Ambos elementos estan dentro del shadow DOM de la SPA > iframe SPEKYOP > iframe central.
        Se usa JS para setear el valor (evita problemas de interactabilidad con el datepicker)
        y click_js para el boton (evita problemas de elemento no interactable).
        """
        self._switch_to_iframe_central()

        # Esperar a que la pagina cargue completamente (onload dispara mostrarEspecifica)
        WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, S.INPUT_FECHA))
        )
        self.esperar(1)  # dar tiempo al onload para mostrar el input

        # Setear fecha via JS (datepicker puede bloquear send_keys)
        ok = self.driver.execute_script("""
            var input = document.getElementById('fechaEspecifica');
            if (!input) return false;
            input.value = arguments[0];
            // Disparar change para que jQuery datepicker registre el valor
            if (window.$ && $(input).data('datepicker')) {
                $(input).datepicker('setDate', arguments[0]);
            }
            return true;
        """, fecha)
        logger.debug(f"Fecha seteada via JS: {ok} | valor={fecha}")

        self.esperar(0.5)

        # Boton Aceptar — click via JS para evitar element not interactable
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

    def _pdfs_actuales(self) -> set:
        try:
            return {f for f in os.listdir(self._downloads_path) if f.lower().endswith('.pdf')}
        except Exception:
            return set()

    def _renombrar_pdf_nuevo(self, pdfs_antes: set, op: 'Operacion') -> None:
        """
        Espera hasta 30s a que aparezca un PDF nuevo en downloads_path y lo
        renombra a '<monto> BBVA.pdf'. Si ya existe un archivo con ese nombre
        agrega el nro_orden para evitar colision.
        """
        deadline = time.time() + 30
        nuevo_archivo = None
        while time.time() < deadline:
            nuevos = self._pdfs_actuales() - pdfs_antes
            # Ignorar archivos temporales de Chrome (.crdownload)
            completos = {f for f in nuevos if not f.endswith('.crdownload')}
            if completos:
                nuevo_archivo = next(iter(completos))
                break
            time.sleep(0.5)

        if not nuevo_archivo:
            logger.warning(f"No se detecto PDF nuevo para orden {op.nro_orden}")
            return

        monto_safe = re.sub(r'[<>:"/\\|?*\n\r\t]', '', op.procesado).strip()
        if not monto_safe:
            monto_safe = op.nro_orden

        nombre_destino = f"{monto_safe} BBVA.pdf"
        ruta_origen  = os.path.join(self._downloads_path, nuevo_archivo)
        ruta_destino = os.path.join(self._downloads_path, nombre_destino)

        # Evitar colision si ya existe un archivo con ese monto
        if os.path.exists(ruta_destino):
            nombre_destino = f"{monto_safe} {op.nro_orden} BBVA.pdf"
            ruta_destino = os.path.join(self._downloads_path, nombre_destino)

        try:
            os.rename(ruta_origen, ruta_destino)
            logger.info(f"PDF renombrado: {nuevo_archivo} → {nombre_destino}")
        except Exception as e:
            logger.warning(f"No se pudo renombrar {nuevo_archivo}: {e}")

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
            pdfs_antes = self._pdfs_actuales()
            try:
                self._descargar_pdf_operacion(op)
                self._renombrar_pdf_nuevo(pdfs_antes, op)
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
            legacy_el = self._find_iframe_in_shadow('SPEKYOP')
            if not legacy_el:
                logger.warning("_volver_a_lista: iframe SPEKYOP no encontrado en shadow DOM")
                return
            self.driver.switch_to.frame(legacy_el)

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

    def _find_iframe_in_shadow(self, src_pattern: str, timeout: int = None):
        """
        Busca un <iframe> cuyo src contiene `src_pattern` atravesando el shadow DOM.
        Retorna el WebElement del iframe (para usar en switch_to.frame) o None.
        Necesario porque en BBVA todos los iframes estan dentro de shadow DOM
        y document.querySelector no los encuentra.
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
        import time
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
        Siempre parte desde default_content para evitar referencias obsoletas.

        En BBVA ambos iframes estan dentro de shadow DOM de componentes Web,
        por lo que no son accesibles via document.querySelector ni WebDriverWait
        con CSS selector. Se usa JS shadow DOM traversal para obtener el
        WebElement y luego switch_to.frame(element).

        Jerarquia:
          default_content
            └── (shadow DOM) iframe[src*="SPEKYOP"]   (IFRAME_LEGACY)
                  └── #kyop-central-load-area          (IFRAME_CENTRAL, en light DOM del legacy)
        """
        self.driver.switch_to.default_content()

        legacy_el = self._find_iframe_in_shadow('SPEKYOP')
        if not legacy_el:
            raise RuntimeError(
                "No se encontro el iframe SPEKYOP en shadow DOM. "
                "Verifica que el modulo Seguimiento de pagos masivos este cargado."
            )
        self.driver.switch_to.frame(legacy_el)
        logger.debug("Cambiado a iframe SPEKYOP (legacy)")

        # #kyop-central-load-area esta en el light DOM del documento SPEKYOP
        central = WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, S.IFRAME_CENTRAL))
        )
        self.driver.switch_to.frame(central)
        logger.debug("Cambiado a iframe #kyop-central-load-area")
