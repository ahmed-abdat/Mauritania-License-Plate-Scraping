import os
import time
import requests
import json
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from configparser import ConfigParser
from ratelimit import limits, sleep_and_retry
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('WDM').setLevel(logging.ERROR)

# Load configuration settings
config = ConfigParser()
config.read('config.ini')

PLATE_RECOGNIZER_API_URL = config.get('API', 'PLATE_RECOGNIZER_API_URL', fallback=None)
PLATE_RECOGNIZER_API_KEY = config.get('API', 'PLATE_RECOGNIZER_API_KEY', fallback=None)
BASE_URL = config.get('URL', 'BASE_URL')
MAIN_URL = config.get('URL', 'MAIN_URL')
START_PAGE = config.getint('SETTINGS', 'START_PAGE')
END_PAGE = config.getint('SETTINGS', 'END_PAGE')
MAX_WORKERS = config.getint('SETTINGS', 'MAX_WORKERS')
START_CAR_NUMBER = config.getint('SETTINGS', 'START_CAR_NUMBER')

# Rate limiting configuration
CALLS = 1
RATE_LIMIT_PERIOD = 2  # in seconds

# Image folders
WEB_IMAGES_FOLDER = 'web_images'
CROPPED_IMAGES_FOLDER = 'cropped_images'
os.makedirs(WEB_IMAGES_FOLDER, exist_ok=True)
os.makedirs(CROPPED_IMAGES_FOLDER, exist_ok=True)

# License plate detection and OCR settings
regions = ["fr"]
plate_pattern = r".*(\d{4}[a-zA-Z]{2}\d{2}|\d{3}[a-zA-Z]{3}\d{2}).*"

config_payload = json.dumps({
    "region": "strict",
    "threshold_d": 0.1,
    "threshold_o": 0.3,
    "mode": "redaction"
})
mmc = "true"

api_error_occurred = False  # Global flag to track API errors
api_key_invalid = not PLATE_RECOGNIZER_API_KEY or PLATE_RECOGNIZER_API_KEY in ['your_api_key_here', '']

@sleep_and_retry
@limits(calls=CALLS, period=RATE_LIMIT_PERIOD)
def process_image_with_plate_recognizer(image_path):
    """
    Process an image with Plate Recognizer API to detect license plates.
    """
    global api_error_occurred
    if api_error_occurred or api_key_invalid:
        api_error_occurred = True  # Ensure flag is set to true
        return {}

    try:
        with open(image_path, 'rb') as fp:
            response = requests.post(
                PLATE_RECOGNIZER_API_URL,
                data={'regions': regions, 'config': config_payload, 'mmc': mmc},
                files={'upload': fp},
                headers={'Authorization': f'Token {PLATE_RECOGNIZER_API_KEY}'}
            )
        if response.status_code in [200, 201]:
            logging.info("License plate recognition API call successful")
            return response.json()
        elif response.status_code in [403, 413, 429]:
            logging.error(f"License plate recognition API call failed with status {response.status_code}")
            logging.info("Disabling further API processing due to API error.")
            api_error_occurred = True  # Set the flag to disable further API processing
            return {}
        else:
            logging.error(f"License plate recognition API call failed with status {response.status_code}")
    except Exception as e:
        logging.error(f"Error in license plate recognition API call: {e}")
        api_error_occurred = True  # Disable further API processing on exception
    return {}

def download_image(url, folder, filename, retries=3):
    """
    Download an image from a given URL and save it to the specified folder.
    """
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            image_path = os.path.join(folder, filename)
            with open(image_path, 'wb') as file:
                file.write(response.content)
            logging.info(f"Downloaded {url} as {filename}")
            return image_path
        except requests.RequestException as e:
            logging.error(f"Attempt {attempt + 1}: Error downloading {url}: {e}")
            time.sleep(2)
    logging.error(f"Failed to download {url} after {retries} attempts")
    return None

def get_image_urls(driver):
    """
    Retrieve image URLs from the current page in the web driver.
    """
    try:
        image_elements = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '#photodiv > img')))
        if not image_elements:
            logging.warning("No image elements found in 'photodiv'")
        return [
            img.get_attribute('src') for img in image_elements 
            if img.is_displayed() and img.get_attribute('src')
        ]
    except Exception as e:
        logging.error(f"Error finding images: {e}")
        return []

def crop_license_plate(image_path, plate_data, page_number, car_number, image_number, output_dir, margin=10):
    """
    Crop the detected license plate from the image and save it.
    """
    try:
        image = Image.open(image_path)
        img_width, img_height = image.size
        
        for plate in plate_data:
            plate_text = plate['plate']
            confidence = plate.get('score', 0)

            if not re.fullmatch(plate_pattern, plate_text) or confidence < 0.5:
                logging.info(f"License plate '{plate_text}' does not match the pattern or has low confidence.")
                continue

            logging.info(f"Detected license plate: {plate_text} with confidence {confidence}")

            box = plate['box']
            x1 = max(0, box['xmin'] - margin)
            y1 = max(0, box['ymin'] - margin)
            x2 = min(img_width, box['xmax'] + margin)
            y2 = min(img_height, box['ymax'] + margin)
            
            if x2 > x1 and y2 > y1:
                cropped_plate = image.crop((x1, y1, x2, y2))
                extension = image_path.split('.')[-1]
                cropped_filename = f"web1_{page_number}_{car_number}_{image_number}_cropped.{extension}"
                
                cropped_path = os.path.join(output_dir, cropped_filename)
                cropped_plate.save(cropped_path)
                logging.info(f"Saved cropped image to: {cropped_path}")
            else:
                logging.warning(f"Invalid crop coordinates for plate '{plate_text}' in image '{image_path}'.")
    except Exception as e:
        logging.error(f"Error cropping license plate from image {image_path}: {e}")

def check_for_license_plate(image_path, page_number, car_number, image_number):
    """
    Check for license plates in the image and crop them if found.
    """
    result = process_image_with_plate_recognizer(image_path)
    if 'results' in result and result['results']:
        logging.info(f"License plate detected in image: {image_path}")
        crop_license_plate(image_path, result['results'], page_number, car_number, image_number, CROPPED_IMAGES_FOLDER)
        return True
    return False

def scrape_car_images(car_url, page_number, car_number):
    """
    Scrape images of a car from the specified car URL.
    """
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument(f'--remote-debugging-port={9222 + car_number}')  # Set unique port for each instance
    service = Service(ChromeDriverManager().install())

    with webdriver.Chrome(service=service, options=options) as driver:
        try:
            logging.info(f"Processing car {car_number} on page {page_number}")
            driver.get(car_url)
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, 'photodiv')))
            image_urls = get_image_urls(driver)
            if not image_urls:
                logging.info(f"No images found on {car_url}")
                return
            for index, img_url in enumerate(image_urls, start=1):
                if not img_url.startswith("http"):
                    img_url = BASE_URL + img_url
                extension = img_url.split('.')[-1]
                filename = f"web1_{page_number}_{car_number}_{index}.{extension}"
                image_path = download_image(img_url, WEB_IMAGES_FOLDER, filename)
                if image_path:
                    if api_key_invalid or api_error_occurred:
                        continue  # Skip logging the message again
                    if not check_for_license_plate(image_path, page_number, car_number, index):
                        logging.info(f"No valid license plates found in image {image_path}")
        except Exception as e:
            logging.error(f"Error processing car {car_number}: {e}")

def get_car_links(driver):
    """
    Get links to car detail pages from the main listing page.
    """
    try:
        car_links = WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a[href*="annoncev.cfm?pdtid="]'))
        )
        return [
            link.get_attribute('href') if link.get_attribute('href').startswith("http") else BASE_URL + link.get_attribute('href')
            for link in car_links
        ]
    except Exception as e:
        logging.error(f"Error finding car links: {e}")
        return []

def scrape_page_images(url, page_number, start_car_number):
    """
    Scrape images from all cars on a specific page.
    """
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument(f'--remote-debugging-port={9222 + page_number}')  # Set unique port for each instance
    service = Service(ChromeDriverManager().install())

    with webdriver.Chrome(service=service, options=options) as driver:
        page_url = f"{url}&PN={page_number}"
        logging.info(f"Fetching page {page_number}: {page_url}")
        driver.get(page_url)
        
        try:
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div#dync')))
        except Exception as e:
            logging.error(f"Timeout waiting for 'div#dync' on page {page_number}")
            logging.debug(driver.page_source)
            return
        
        car_links = get_car_links(driver)
        if not car_links:
            logging.info(f"No car links found on page {page_number}")
            return

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(scrape_car_images, car_url, page_number, start_car_number + car_number) 
                       for car_number, car_url in enumerate(car_links)]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"Error processing car: {e}")

def scrape_main_page_images(url, start_page, end_page, start_car_number):
    """
    Scrape images from the main page and all specified pages.
    """
    for page in range(start_page, end_page + 1):
        scrape_page_images(url, page, start_car_number)

if __name__ == "__main__":
    scrape_main_page_images(MAIN_URL, START_PAGE, END_PAGE, START_CAR_NUMBER)
