import time
from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class BaseFlow(ABC):
    def __init__(self, driver: WebDriver, timeout: int = 15):
        self.driver = driver
        self.timeout = timeout

    @abstractmethod
    def ejecutar(self, **kwargs):
        pass

    # ------------------------------------------------------------------
    # Esperas
    # ------------------------------------------------------------------

    def esperar(self, segundos: float) -> None:
        time.sleep(segundos)

    def esperar_elemento(self, xpath: str, timeout: Optional[int] = None) -> WebElement:
        t = timeout or self.timeout
        return WebDriverWait(self.driver, t).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )

    def esperar_clickeable(self, xpath: str, timeout: Optional[int] = None) -> WebElement:
        t = timeout or self.timeout
        return WebDriverWait(self.driver, t).until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )

    def elemento_presente(self, xpath: str, timeout: int = 3) -> bool:
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            return True
        except TimeoutException:
            return False

    # ------------------------------------------------------------------
    # Interaccion
    # ------------------------------------------------------------------

    def click_js(self, element: WebElement) -> None:
        self.driver.execute_script("arguments[0].click();", element)

    def click_xpath(self, xpath: str, timeout: Optional[int] = None) -> None:
        el = self.esperar_clickeable(xpath, timeout)
        self.click_js(el)

    def scroll_a_elemento(self, element: WebElement) -> None:
        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)

    def ejecutar_js(self, script: str, *args):
        return self.driver.execute_script(script, *args)

    # ------------------------------------------------------------------
    # Teclado — gestion de modificadores
    # ------------------------------------------------------------------

    def liberar_modificadores(self) -> None:
        """
        Libera explicitamente Shift, Ctrl y Alt via ActionChains.

        Selenium puede dejar un modificador en estado "presionado" despues de
        operaciones fallidas o interrumpidas (send_keys con Keys.SHIFT, etc.).
        Esto provoca que los siguientes send_keys escriban en mayusculas o
        activen atajos de teclado de forma involuntaria.

        Llamar a este metodo antes de cualquier send_keys critico garantiza
        un estado limpio del teclado en el WebDriver.
        """
        try:
            ActionChains(self.driver) \
                .key_up(Keys.SHIFT) \
                .key_up(Keys.CONTROL) \
                .key_up(Keys.ALT) \
                .perform()
        except Exception as e:
            logger.debug(f"liberar_modificadores: {e}")

    # ------------------------------------------------------------------
    # Formularios
    # ------------------------------------------------------------------

    def rellenar_fecha(self, name: str, valor: str) -> bool:
        self.liberar_modificadores()
        script = """
        const input = document.querySelector(`input[name="${arguments[0]}"]`);
        if (!input) return false;
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value').set;
        nativeInputValueSetter.call(input, arguments[1]);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
        """
        ok = self.driver.execute_script(script, name, valor)
        logger.debug(f"Fecha '{valor}' en [{name}]: {'ok' if ok else 'campo no encontrado'}")
        return bool(ok)

    # ------------------------------------------------------------------
    # Navegacion
    # ------------------------------------------------------------------

    def click_js_css(self, css: str) -> bool:
        """Busca por CSS selector en el DOM plano y hace JS click. Retorna True si lo encontro."""
        return bool(self.driver.execute_script(
            "const el = document.querySelector(arguments[0]); if(el){el.click(); return true;} return false;",
            css,
        ))

    def elemento_presente_js(self, css: str) -> bool:
        """
        Verifica si un elemento existe en el DOM usando JS querySelector.
        A diferencia de elemento_presente (XPath), NO falla con shadow DOM hosts.
        Util para detectar la presencia de Web Components como contenedores.
        """
        return bool(self.driver.execute_script(
            "return !!document.querySelector(arguments[0]);", css
        ))

    def click_js_shadow_css(self, css: str) -> bool:
        """
        Busca un elemento por CSS selector atravesando shadow DOMs abiertos
        recursivamente y hace click. Retorna True si lo encontro.
        Necesario cuando el elemento esta dentro del shadow root de un Web Component.
        """
        script = """
        function buscar(root, selector) {
            const el = root.querySelector(selector);
            if (el) { el.click(); return true; }
            for (const node of root.querySelectorAll('*')) {
                if (node.shadowRoot && buscar(node.shadowRoot, selector)) return true;
            }
            return false;
        }
        return buscar(document, arguments[0]);
        """
        return bool(self.driver.execute_script(script, css))

    def click_js_shadow(self, texto: str) -> bool:
        """
        Busca un <button> cuyo textContent contenga `texto` atravesando
        shadow DOMs abiertos recursivamente. Retorna True si lo encontro.
        Necesario cuando el boton vive dentro del shadow root de un Web Component.
        """
        script = """
        function buscar(root, texto) {
            for (const btn of root.querySelectorAll('button')) {
                if (btn.textContent.includes(texto)) { btn.click(); return true; }
            }
            for (const el of root.querySelectorAll('*')) {
                if (el.shadowRoot && buscar(el.shadowRoot, texto)) return true;
            }
            return false;
        }
        return buscar(document, arguments[0]);
        """
        return bool(self.driver.execute_script(script, texto))

    def click_js_shadow_link(self, texto: str) -> bool:
        """
        Busca cualquier elemento interactivo (bbva-web-link, a, li)
        cuyo textContent contenga `texto` (includes, no exact match),
        atravesando shadow DOMs recursivamente.
        Mas general que click_js_shadow (que solo busca buttons).
        Necesario para sub-menus de BBVA que usan bbva-web-link dentro del sidebar.
        """
        script = """
        const TAGS = ['bbva-web-link', 'a', 'li'];
        function buscar(root, texto) {
            for (const tag of TAGS) {
                for (const el of root.querySelectorAll(tag)) {
                    if (el.textContent.trim().includes(texto)) {
                        el.click(); return true;
                    }
                }
            }
            for (const el of root.querySelectorAll('*')) {
                if (el.shadowRoot && buscar(el.shadowRoot, texto)) return true;
            }
            return false;
        }
        return buscar(document, arguments[0]);
        """
        return bool(self.driver.execute_script(script, texto))

    def click_js_shadow_menu_item(self, event_name: str) -> str:
        """
        Hace click en un bbva-web-navigation-menu-item buscando por event-name,
        atravesando shadow DOMs. Intenta llegar al div interno de
        bbva-web-navigation-menu-item-action (nivel mas profundo clickeable).

        Retorna una cadena indicando que se clickeo, o 'not-found' si no lo encontro.
        Util para diagnosticar exactamente donde llego el click.
        """
        script = """
        function findInShadow(root, selector) {
            const el = root.querySelector(selector);
            if (el) return el;
            for (const node of root.querySelectorAll('*')) {
                if (node.shadowRoot) {
                    const found = findInShadow(node.shadowRoot, selector);
                    if (found) return found;
                }
            }
            return null;
        }

        const sel = 'bbva-web-navigation-menu-item[event-name="' + arguments[0] + '"]';
        const item = findInShadow(document, sel);
        if (!item) return 'not-found';

        if (item.shadowRoot) {
            const action = item.shadowRoot.querySelector('bbva-web-navigation-menu-item-action');
            if (action) {
                if (action.shadowRoot) {
                    const div = action.shadowRoot.querySelector('div');
                    if (div) { div.click(); return 'clicked-action-div'; }
                }
                action.click();
                return 'clicked-action';
            }
        }
        item.click();
        return 'clicked-item-host';
        """
        return str(self.driver.execute_script(script, event_name))

    def volver_atras(self) -> None:
        self.driver.execute_script("window.history.back();")
        self.esperar(2)
