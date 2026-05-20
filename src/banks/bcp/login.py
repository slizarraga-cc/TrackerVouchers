import threading

from loguru import logger
from selenium.common.exceptions import NoSuchWindowException
from selenium.webdriver.remote.webdriver import WebDriver

from src.banks.bcp.selectors import BCPSelectors as S


class BCPLogin:
    """
    Maneja el login en BCP ViaBCP.

    Estrategia: login supervisado via noVNC.
      1. Navega a la URL de login.
      2. Pausa y espera que el usuario complete el login manualmente.
      3. Verifica que la sesion este activa en el portal Telecredito.

    El auto-login no esta habilitado por politicas de seguridad del banco.
    """

    LOGIN_URL = S.LOGIN_URL
    PORTAL_URL = S.PORTAL_URL

    def __init__(self, driver: WebDriver):
        self.driver = driver

    def ejecutar(self) -> None:
        logger.info("Iniciando flujo de login BCP")
        self.driver.get(self.LOGIN_URL)
        self._esperar_confirmacion_usuario()
        self._verificar_sesion()

    def _esperar_confirmacion_usuario(self) -> None:
        print("\n" + "=" * 60)
        print("  ACCION REQUERIDA")
        print("=" * 60)
        print(f"  1. Abre el visor en tu browser:")
        print(f"     http://localhost:7900  (contrasena: rpa123)")
        print(f"  2. Completa el login en la ventana del browser.")
        print(f"  3. Asegurate de estar dentro del portal Telecredito.")
        print(f"  4. Presiona ENTER aqui cuando estes listo.")
        print("=" * 60 + "\n")

        # Keep-alive: evita que Selenium Grid cierre la sesion por inactividad
        stop_event = threading.Event()
        hilo = threading.Thread(target=self._keep_alive, args=(stop_event,), daemon=True)
        hilo.start()

        input("  >> Presiona ENTER para continuar...")

        stop_event.set()

    def _keep_alive(self, stop_event: threading.Event) -> None:
        """Ejecuta JS cada 30 segundos para mantener la sesion activa en Selenium Grid."""
        while not stop_event.wait(timeout=30):
            try:
                self.driver.execute_script("return document.readyState;")
                logger.debug("Keep-alive enviado al Grid")
            except Exception:
                break

    def _verificar_sesion(self) -> None:
        try:
            url_actual = self.driver.current_url
        except NoSuchWindowException:
            handles = self.driver.window_handles
            if not handles:
                raise RuntimeError(
                    "La ventana del navegador se cerro y no hay pestanas disponibles. "
                    "No abras ni cierres ventanas del navegador manualmente durante el login."
                )
            logger.warning(
                f"La ventana original se cerro. Cambiando a otra pestana disponible ({len(handles)} encontradas)."
            )
            self.driver.switch_to.window(handles[-1])
            url_actual = self.driver.current_url

        if "tlcbcp.com" in url_actual or "viabcp.com" in url_actual:
            logger.success(f"Sesion activa detectada: {url_actual}")
        else:
            logger.warning(
                f"URL actual inesperada: {url_actual}. "
                "Verifica que el login haya sido exitoso antes de continuar."
            )
