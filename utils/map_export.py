import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def export_map_to_jpg(html_file, output_file="map.jpg"):

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--window-size=1400,1000")

    service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=options)

    # convertir a ruta absoluta
    html_path = os.path.abspath(html_file)

    driver.get("file:///" + html_path.replace("\\", "/"))

    # esperar que cargue el mapa
    time.sleep(4)

    driver.save_screenshot(output_file)

    driver.quit()

    return output_file