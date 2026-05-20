import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from loguru import logger

SELENIUM_GRID_URL = os.getenv("SELENIUM_GRID_URL", "http://localhost:4444")
DOWNLOAD_DIR_CONTAINER = "/home/seluser/Downloads"
DOWNLOAD_DIR_LOCAL = os.path.abspath("downloads")


def get_driver(remote: bool = True, grid_url: str = None) -> webdriver.Remote:
    options = Options()

    prefs = {
        "download.default_directory": DOWNLOAD_DIR_CONTAINER if remote else DOWNLOAD_DIR_LOCAL,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
        "safebrowsing.enabled": True,
    }
    options.add_experimental_option("prefs", prefs)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

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

    driver.set_window_size(1920, 1080)
    driver.implicitly_wait(0)  # Usamos waits explicitos en BaseFlow
    return driver
