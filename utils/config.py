import os
from configparser import ConfigParser

def load_config(file_path):
    config = ConfigParser()
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Config file not found: {file_path}")
    config.read(file_path)
    return config
