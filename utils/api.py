import logging
import requests
import json
from ratelimit import limits, sleep_and_retry

def process_image_with_plate_recognizer(api_url, api_key, config_payload, mmc, regions, image_path, skip_api):
    if skip_api:
        return {"skip_api": True}

    try:
        with open(image_path, 'rb') as fp:
            response = requests.post(
                api_url,
                data={'regions': regions, 'config': config_payload, 'mmc': mmc},
                files={'upload': fp},
                headers={'Authorization': f'Token {api_key}'}
            )
        if response.status_code in [200, 201]:
            logging.info("License plate recognition API call successful")
            return response.json()
        elif response.status_code == 403:
            logging.error("Error 403: Forbidden. Check your API Token or available credits.")
        elif response.status_code == 413:
            logging.error("Error 413: Payload Too Large. The uploaded image exceeds the size limit.")
        elif response.status_code == 429:
            logging.error("Error 429: Too Many Requests. Rate limit exceeded.")
        else:
            logging.error(f"License plate recognition API call failed with status {response.status_code}")
    except Exception as e:
        logging.error(f"Error in license plate recognition API call: {e}")
    return {}

@sleep_and_retry
@limits(calls=1, period=2)
def rate_limited_process_image_with_plate_recognizer(*args, **kwargs):
    return process_image_with_plate_recognizer(*args, **kwargs)
