"""
Store variables needed across the project
"""

import os
import dash_html_components as html

from datetime import date, datetime


# Where images will be served from
STATIC_IMAGE_ROUTE = '/'

# Define the maximal grid dimensions
ROWS_MAX, COLS_MAX = 7, 7
N_GRID = ROWS_MAX * COLS_MAX


# Allowed file extension for image types
IMAGE_TYPES = ['.JPG', '.jpg', '.JPEG', '.jpeg', '.png']

# Globals for the images
img_fname = 'job_done.jpg' # Default image
IMG_PATH = STATIC_IMAGE_ROUTE + img_fname
IMG_STYLE = {'display': 'block', 'height': 'auto', 'max-width': '100%'}


# Assumes that images are stored in the img/ directory for now
IMAGE_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'img')
# List of image objects - pre-load here to avoid re-loading on every grid re-sizing
images = [STATIC_IMAGE_ROUTE + fname for fname in sorted(os.listdir(IMAGE_DIR))]
IMAGE_LIST = [html.Img(src=img, style=IMG_STYLE) for img in images]
IMAGE_LIST = IMAGE_LIST + [html.Img(src=IMG_PATH, style=IMG_STYLE)]*(ROWS_MAX*COLS_MAX - len(IMAGE_LIST))
# Where the image folders should be copied to before deleting images in the original location
IMAGE_BACKUP_PATH = os.path.join(os.path.expanduser('~'), 'Pictures', '_deduplicate_backup')
# Default image
EMPTY_IMAGE = html.Img(src=IMG_PATH, style=IMG_STYLE)

# Where to save metadata and backup images
META_DATA_FNAME = f'image_selector_session_{str(date.today())}_{int(datetime.timestamp(datetime.now()))}.json'
os.makedirs(IMAGE_BACKUP_PATH, exist_ok=True)
os.makedirs(os.path.join(IMAGE_BACKUP_PATH, '_session_data'), exist_ok=True)
META_DATA_FPATH = os.path.join(IMAGE_BACKUP_PATH, '_session_data', META_DATA_FNAME)

# Database details
DATABASE_NAME = 'deduplicate'
DATABASE_URI = f'postgresql:///{DATABASE_NAME}'
DATABASE_TABLE = 'duplicates'