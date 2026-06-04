import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from loguru import logger

SELENIUM_GRID_URL = os.getenv("SELENIUM_GRID_URL", "http://localhost:4444")
DOWNLOAD_DIR_CONTAINER = "/home/seluser/Downloads"
DOWNLOAD_DIR_LOCAL = os.path.abspath("downloads")


def get_driver(remote: bool = True, grid_url: str = None, use_camera: bool = False) -> webdriver.Remote:
    options = Options()

    prefs = {
        "download.default_directory": DOWNLOAD_DIR_CONTAINER if remote else DOWNLOAD_DIR_LOCAL,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
        "safebrowsing.enabled": True,
    }

    if use_camera:
        # Pre-concede permisos de cámara para el origen IBK sin mostrar diálogo.
        # setting 1 = ALLOW
        prefs["profile.content_settings.exceptions.media_stream_camera"] = {
            "https://empresas.interbank.pe,*": {"setting": 1}
        }
        prefs["profile.content_settings.exceptions.media_stream_mic"] = {
            "https://empresas.interbank.pe,*": {"setting": 1}
        }

    options.add_experimental_option("prefs", prefs)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    if use_camera:
        # Auto-aprueba solicitudes de cámara/micrófono sin diálogo del navegador.
        options.add_argument("--use-fake-ui-for-media-stream")

    if remote:
        url = grid_url or SELENIUM_GRID_URL
        driver = webdriver.Remote(
            command_executor=f"{url}/wd/hub",
            options=options,
        )
        logger.info(f"Driver remoto conectado a {url}")
        download_dir = DOWNLOAD_DIR_CONTAINER
    else:
        driver = webdriver.Chrome(options=options)
        logger.info("Driver local iniciado")
        download_dir = DOWNLOAD_DIR_LOCAL

    # CDP garantiza la descarga automatica sin dialogo incluso en Grid remoto
    driver.execute_cdp_cmd("Page.setDownloadBehavior", {
        "behavior": "allow",
        "downloadPath": download_dir,
    })
    logger.debug(f"Download dir configurado via CDP: {download_dir}")

    if use_camera:
        # Concede el permiso de cámara vía CDP para el origen IBK.
        # Cubre el caso donde el perfil Chrome no persiste los prefs entre sesiones.
        try:
            driver.execute_cdp_cmd("Browser.grantPermissions", {
                "permissions": ["videoCapture", "audioCapture"],
                "origin": "https://empresas.interbank.pe",
            })
            logger.debug("Permisos de cámara concedidos via CDP para empresas.interbank.pe")
        except Exception as e:
            logger.warning(f"No se pudo conceder permisos de cámara via CDP: {e}")

    driver.set_window_size(1920, 1080)
    driver.implicitly_wait(0)  # Usamos waits explicitos en BaseFlow
    return driver
