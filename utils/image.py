import os
import logging
import requests
from PIL import Image
import re
import time

def download_image(url, folder, filename, retries=3):
    os.makedirs(folder, exist_ok=True)
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            image_path = os.path.join(folder, filename)
            with open(image_path, 'wb') as file:
                file.write(response.content)
            logging.info(f"Downloaded {url}")
            return image_path
        except requests.RequestException as e:
            logging.error(f"Attempt {attempt + 1}: Error downloading {url}: {e}")
            time.sleep(2)
    logging.error(f"Failed to download {url} after {retries} attempts")
    return None

def crop_license_plate(image_path, plate_data, output_dir, pattern, margin=10):
    try:
        if not os.path.exists(image_path):
            logging.error(f"Image path does not exist: {image_path}")
            return
        image = Image.open(image_path)
        img_width, img_height = image.size

        for plate in plate_data:
            plate_text = plate['plate']
            confidence = plate.get('score', 0)

            if not re.fullmatch(pattern, plate_text) or confidence < 0.5:
                logging.info(f"License plate '{plate_text}' does not match the pattern or has low confidence and will be skipped.")
                continue

            logging.info(f"Detected license plate: {plate_text} with confidence {confidence}")

            box = plate['box']
            x1 = max(0, box['xmin'] - margin)
            y1 = max(0, box['ymin'] - margin)
            x2 = min(img_width, box['xmax'] + margin)
            y2 = min(img_height, box['ymax'] + margin)

            if x2 > x1 and y2 > y1:
                cropped_plate = image.crop((x1, y1, x2, y2))
                base_filename = os.path.basename(image_path)
                cropped_path = os.path.join(output_dir, base_filename)
                os.makedirs(output_dir, exist_ok=True)
                cropped_plate.save(cropped_path)
                logging.info(f"Saved cropped image to: {cropped_path}")
            else:
                logging.warning(f"Invalid crop coordinates for plate '{plate_text}' in image '{image_path}'.")
    except Exception as e:
        logging.error(f"Error cropping license plate from image {image_path}: {e}")
