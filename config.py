"""
Store variables needed across the project
"""

# Where images will be served from
STATIC_IMAGE_ROUTE = '/'

# Define the maximal grid dimensions
ROWS_MAX, COLS_MAX = 7, 7
N_GRID = ROWS_MAX * COLS_MAX


# Allowed file extension for image types
IMAGE_TYPES = ['.JPG', '.jpg', '.JPEG', '.jpeg', '.png']