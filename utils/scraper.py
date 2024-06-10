import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor, as_completed
from .api import rate_limited_process_image_with_plate_recognizer
from .image import download_image, crop_license_plate
import json

def get_chrome_options():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920x1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--proxy-server='direct://'")
    chrome_options.add_argument("--proxy-bypass-list=*")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-browser-side-navigation")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    return chrome_options

def get_image_urls(driver):
    try:
        parent_div = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'photodiv')))
        image_elements = parent_div.find_elements(By.XPATH, './img')
        if not image_elements:
            logging.warning("No image elements found in 'photodiv'")
        return [
            img.get_attribute('src') for img in image_elements 
            if img.is_displayed() and img.get_attribute('src') and not img.get_attribute('src').endswith('p1.jpg')
        ]
    except Exception as e:
        logging.error(f"Error finding images: {e}")
        return []

def scrape_car_images(api_config, image_config, car_url, car_number, page_number, skip_api):
    options = get_chrome_options()
    service = Service(ChromeDriverManager().install())

    with webdriver.Chrome(service=service, options=options) as driver:
        try:
            logging.info(f"Scraping page {page_number}, car {car_number}")
            driver.get(car_url)
            WebDriverWait(driver, 20).until(EC.presence_of_all_elements_located((By.ID, 'photodiv')))
            image_urls = get_image_urls(driver)
            if not image_urls:
                logging.info(f"No images found on {car_url}")
                return
            for index, img_url in enumerate(image_urls, start=1):
                if not img_url.startswith("http"):
                    img_url = api_config['base_url'] + img_url
                extension = img_url.split('.')[-1]
                filename = f"web1_{page_number}_{car_number}_{index}.{extension}"
                image_path = download_image(img_url, image_config['web_images_folder'], filename)
                if image_path:
                    result = rate_limited_process_image_with_plate_recognizer(
                        api_config['url'], api_config['key'], api_config['config_payload'],
                        api_config['mmc'], api_config['regions'], image_path, skip_api
                    )
                    if 'skip_api' in result and result['skip_api']:
                        skip_api = True
                        logging.info("Continuing without API calls due to user configuration.")
                    else:
                        crop_license_plate(image_path, result.get('results', []), image_config['cropped_images_folder'], image_config['pattern'])
        except Exception as e:
            logging.error(f"Error processing car {car_number} on page {page_number}: {e}")

def get_car_links(driver, base_url):
    try:
        car_links = WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div#dync > a'))
        )
        return [
            link.get_attribute('href') if link.get_attribute('href').startswith("http") else base_url + link.get_attribute('href')
        for link in car_links]
    except Exception as e:
        logging.error(f"Error finding car links: {e}")
        return []

def scrape_page_images(api_config, image_config, page_number, start_car_number, skip_api):
    options = get_chrome_options()
    service = Service(ChromeDriverManager().install())

    with webdriver.Chrome(service=service, options=options) as driver:
        page_url = f"{api_config['main_url']}?PN={page_number}"
        driver.get(page_url)
        car_links = get_car_links(driver, api_config['base_url'])
        logging.info(f"Scraping page {page_number} with {len(car_links)} cars")

        car_links = car_links[start_car_number - 1:] if page_number == api_config['start_page'] else car_links

        with ThreadPoolExecutor(max_workers=api_config['max_workers']) as executor:
            futures = [executor.submit(scrape_car_images, api_config, image_config, car_url, car_number + start_car_number, page_number, skip_api) for car_number, car_url in enumerate(car_links, start=start_car_number)]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"Error processing a car on page {page_number}: {e}")

def scrape_main_page_images(config):
    api_config = {
        'url': config.get('API', 'PLATE_RECOGNIZER_API_URL'),
        'key': config.get('API', 'PLATE_RECOGNIZER_API_KEY'),
        'skip_api_on_403': config.getboolean('API', 'SKIP_API_ON_403', fallback=False),
        'base_url': config.get('URL', 'BASE_URL'),
        'main_url': config.get('URL', 'MAIN_URL'),
        'end_page': config.getint('SETTINGS', 'END_PAGE'),
        'max_workers': config.getint('SETTINGS', 'MAX_WORKERS'),
        'start_page': config.getint('SETTINGS', 'START_PAGE', fallback=1),
        'config_payload': json.dumps({
            "region": "strict",
            "threshold_d": 0.1,
            "threshold_o": 0.3,
            "mode": "redaction"
        }),
        'mmc': "true",
        'regions': ["fr"]
    }

    image_config = {
        'web_images_folder': 'web_images',
        'cropped_images_folder': 'cropped_images',
        'pattern': r".*(\d{4}[a-zA-Z]{2}\d{2}|\d{3}[a-zA-Z]{3}\d{2}).*"
    }

    skip_api = api_config['key'] in [None, '', 'your_api_key_here']
    
    for page in range(api_config['start_page'], api_config['end_page'] + 1):
        start_car_number = config.getint('SETTINGS', 'START_CAR_NUMBER', fallback=1) if page == api_config['start_page'] else 1
        scrape_page_images(api_config, image_config, page, start_car_number, skip_api)
