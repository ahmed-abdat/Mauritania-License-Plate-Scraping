# Mauritania License Plate Scraping

This repository contains the web scraping code for the 2024 National Data Science Competition by RIMAI. The goal is to collect images of Mauritanian license plates to create a dataset for a computer vision challenge.

## Overview

This project scrapes car images from the <a href="https://www.voursa.com" target="_blank">Voursa website</a> and optionally processes them to detect and crop license plates using the Plate Recognizer API. The collected data will be used in the second phase of the competition for developing and tuning license plate recognition algorithms.

![voursa_screenshott](https://github.com/ahmed-abdat/Mauritania-License-Plate-Scraping/assets/102254583/4b86d7b2-3a3e-494d-9985-2d51b3b4c5e2)

## Prerequisites

To run this project locally, you need the following:

- Python 3.6+
- `pip` (Python package installer)

## Installation

### Clone the repository:
   ```bash
   git clone https://github.com/ahmed-abdat/Mauritania-License-Plate-Scraping.git
```
### Change directory
```bash
 cd Mauritania-License-Plate-Scraping 
```
### Create a virtual environment:

```bash
python -m venv env
```

### Activate the virtual environment if not already activated:

```bash
# On Windows
env\Scripts\activate

# On Mac OS / Linux
source env/bin/activate
```


## Install the required libraries:

```bash
pip install -r requirements.txt
```

## Configuration

```ini
[API]
PLATE_RECOGNIZER_API_URL = https://api.platerecognizer.com/v1/plate-reader/
PLATE_RECOGNIZER_API_KEY = your_api_key_here

[URL]
BASE_URL = https://www.voursa.com
MAIN_URL = https://www.voursa.com/voitures-vendues.cfm?user=637

[SETTINGS]
MAX_WORKERS = 2
START_CAR_NUMBER = 1
START_PAGE = 1
END_PAGE = 3
```

### SETTINGS Section 
- `START_PAGE`: The starting page number for scraping. Adjust this to start scraping from a specific page.
- `END_PAGE`: The ending page number for scraping. Adjust this to stop scraping at a specific page.
- `MAX_WORKERS`: The maximum number of parallel workers for scraping. Increase this number to speed up the scraping process by running multiple tasks in parallel.
- `START_CAR_NUMBER`: The starting car number for naming downloaded images. Adjust this to start numbering from a specific car number.

## Running the Script

```bash
python scrape_car.py
```

## Notes
- The script will download images and save them in the `web_images` folder.
- If a valid API key is provided, the script will attempt to detect and crop license plates, saving the cropped images in the `cropped_images` folder.
- If the API key is invalid or if the API returns an error (e.g., 403, 413, 429), the script will disable further API processing and continue downloading images without attempting license plate recognition.

## Troubleshooting

- Ensure that the required dependencies are installed.
- Check your internet connection if the script fails to download images.
- If the script encounters errors related to the Plate Recognizer API, ensure that your API key is valid and you have not exceeded your usage limits.


For more details on obtaining an API key, visit [Plate Recognizer](https://guides.platerecognizer.com/).
