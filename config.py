"""
Store variables needed across the project
"""

import os
import dash_html_components as html

from datetime import date, datetime

import utils


# Where images will be served from
STATIC_IMAGE_ROUTE = '/'

# Define the maximal grid dimensions
ROWS_MAX, COLS_MAX = 7, 7
N_GRID = ROWS_MAX * COLS_MAX


# Allowed file extension for image types
IMAGE_TYPES = ['.JPG', '.jpg', '.JPEG', '.jpeg', '.png', '.PNG']


# Globals for the images

IMG_STYLE = {'display': 'block', 'height': 'auto', 'max-width': '100%'}  # Applies to grid images
IMG_STYLE_ZOOM = {'display': 'block', 'height': 'auto', 'max-width': '100%'}  # Applies to zoomed image

# Default image
EMPTY_IMG_FNAME = 'job_done.jpg'
EMPTY_IMG_PATH = STATIC_IMAGE_ROUTE + EMPTY_IMG_FNAME
EMPTY_IMAGE = html.Img(src=EMPTY_IMG_PATH, style=IMG_STYLE)

# Assumes that images are stored in the img/ directory for now
IMAGE_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'img')
# List of image objects - pre-load here to avoid re-loading on every grid re-sizing
IMAGE_SRCS = [STATIC_IMAGE_ROUTE + fname for fname in sorted(os.listdir(IMAGE_DIR)) if fname != EMPTY_IMG_FNAME]
IMAGE_SRCS = utils.sort_images_by_datetime(IMAGE_SRCS, IMAGE_DIR)
IMAGE_SIZES = [utils.readable_filesize(os.path.getsize(os.path.join(IMAGE_DIR, fname))) for fname in sorted(os.listdir(IMAGE_DIR)) if fname != EMPTY_IMG_FNAME]
N_IMG_SRCS = len(IMAGE_SRCS)
IMAGE_SRCS = IMAGE_SRCS + [EMPTY_IMG_PATH] * (N_GRID - len(IMAGE_SRCS))
IMAGE_SIZES = IMAGE_SIZES + ["0KB"] * (N_GRID - len(IMAGE_SRCS))

# Where the image folders should be copied to before deleting images in the original location
IMAGE_BACKUP_PATH = os.path.join(os.path.expanduser('~'), 'Pictures', '_deduplicate_backup')

# Where to save metadata and backup images
META_DATA_FNAME = f'image_selector_session_{str(date.today())}_{int(datetime.timestamp(datetime.now()))}.json'
os.makedirs(IMAGE_BACKUP_PATH, exist_ok=True)
os.makedirs(os.path.join(IMAGE_BACKUP_PATH, '_session_data'), exist_ok=True)
META_DATA_FPATH = os.path.join(IMAGE_BACKUP_PATH, '_session_data', META_DATA_FNAME)

# Database details
DATABASE_NAME = 'deduplicate'
DATABASE_URI = f'postgresql:///{DATABASE_NAME}'
DATABASE_TABLE = 'duplicates'

# Pre-labelling details (None => no pre-labelling)
# Choices: [None, 'GROUP_SAME_DAY_TAKEN']
PRELABEL_RULE = None
