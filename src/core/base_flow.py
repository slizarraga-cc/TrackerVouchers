import time
from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
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
    # Formularios
    # ------------------------------------------------------------------

    def rellenar_fecha(self, name: str, valor: str) -> bool:
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

    def volver_atras(self) -> None:
        self.driver.execute_script("window.history.back();")
        self.esperar(2)
