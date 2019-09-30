"""
Utility functions supporting selector_app.py
"""

## Imports ##

import re
import os
import shutil
import subprocess

from datetime import datetime, timedelta
from sqlalchemy import create_engine

from PIL import Image

import pandas as pd

import dash_html_components as html

import config


## Constants ##

STATIC_IMAGE_ROUTE = config.STATIC_IMAGE_ROUTE
ROWS_MAX = config.ROWS_MAX
COLS_MAX = config.COLS_MAX
N_GRID = config.N_GRID

IMAGE_BACKUP_PATH = config.IMAGE_BACKUP_PATH
EMPTY_IMAGE = config.EMPTY_IMAGE


## Functions ##


# File manipulations #

def copy_image(fname, src_path, dst_path, image_types):
    """
    Perform a copy of the file if it is an image. It will be copied to dst_path.

    Args:
        fname = str, query filename (no path)
        src_path = str, directory of where to copy from (no filename)
        dst_path = str, directory of where to copy to (no filename)
        image_types = list, of str, valid extensions of image files (e.g. .jpg)

    Returns: str, full filepath that the server is expecting
             or None, if not an valid image type (see IMAGE_TYPES)
    """

    # Check if it's a valid image (by extension)
    is_image = False
    for img_type in image_types:
        if img_type in fname:
            is_image = True
            break
    # Only copy images
    if not is_image:
        # Warning on non-directory filenames
        if len(fname.split('.')) > 1:
            print(f"WARNING: ignoring non-image file {fname}")
        return

    # Copy the file to the temporary location (that can be served)
    # Some images must be rotated, in which case we do so before saving
    rotate_degrees = get_image_rotation(src_path, fname)
    if rotate_degrees == 0:
        shutil.copyfile(os.path.join(src_path, fname), os.path.join(dst_path, fname))
    else:
        pil_image = Image.open(os.path.join(src_path, fname))
        pil_image.rotate(rotate_degrees, expand=1).save(os.path.join(dst_path, fname))

    # Append the Img object with the static path
    static_image_path = os.path.join(STATIC_IMAGE_ROUTE, fname)

    return static_image_path


def parse_image_upload(filename, image_types):
    """
    Given an image filename, create a list of options for the 'options' for the Dropdown that chooses
    which path the image should be loaded from.
    """
    is_image = False
    for img_type in image_types:
        if img_type in filename:
            is_image = True
            break

    if is_image:
        path_options = find_image_dir_on_system(filename)
        if len(path_options) > 0:
            return [{'label': path, 'value': i} for i, path in enumerate(path_options[::-1])]
        else:
            return []
    else:
        return []


def get_image_taken_date(image_dir, fname, default_date=datetime.today() + timedelta(days=3652)):
    """
    Obtain the date when the photo was taken from the meta data (if available).

    Args:
        image_dir = str, filepath to the image
        fname = str, name of the image file (no path)
        default_date = datetime.datetime, a value to return in case this data is not available
                        Note: default value is 10 years in the future so that date sorting is possible

    Returns: datetime.datetime object, representing when the image was taken (None if fname cannot be found in image_dir)
    """

    try:
        image = Image.open(os.path.join(image_dir, fname))
        image_metadata = image._getexif()

        if image_metadata is not None:
            datetime_str = image_metadata.get(36867) # Key corresponding to "DateTimeOriginal"
            if datetime_str is not None:
                return datetime.strptime(datetime_str, '%Y:%m:%d %H:%M:%S')

        return default_date

    except FileNotFoundError:
        return None


def get_image_rotation(image_dir, fname):
    """
    Calculate how much to rotate the image from the encoded orientation value (if available).

    Args:
        image_dir = str, filepath to the image
        fname = str, name of the image file (no path)

    Returns: int, the number of degrees to rotate the image to get it the right way up
    Raises: ValueError, if we encounter a rare EXIF orientation value, e.g. 2, 4, 5, 7

    See here for more details: https://www.impulseadventure.com/photo/exif-orientation.html
    """
    image = Image.open(os.path.join(image_dir, fname))
    image_metadata = image._getexif()
    if image_metadata is not None:
        orientation_value = image_metadata.get(274, 1) # Key corresponding to "Orientation"
    else:
        return 0

    if orientation_value in [0, 1]:
        return 0
    elif orientation_value == 8:
        return 90
    elif orientation_value == 3:
        return 180
    elif orientation_value == 6:
        return 270
    else:
        raise ValueError(f'Cannot handle EXIF orientation value of {orientation_value} for image {fname}')


def find_image_dir_on_system(img_fname):
    """
    Find the location(s) of the given filename on the file system.

    Returns: list of filepaths (excluding filename) where the file can be found.
    """
    path_options = subprocess.check_output(['find', os.path.expanduser('~'), '-name', img_fname]).decode()
    path_options = ['/'.join(f.split('/')[:-1]) for f in path_options.split('\n') if len(f) > 0]
    return path_options


def get_backup_path(original_image_dir, intended_backup_root):
    """
    Calculate the location where all the images will be backed up to.

    Args:
        original_image_dir = str, filepath of where the original images are stored (no filename)
        intended_backup_root = str, the filepath to the root folder where all image files will be backed up to

    Returns:
        backup_path = str, full filepath the specific location (within intended_backup_root) these images will be
                           copied to (no filename)
        relative_path = str, the relative filepath under intended_backup_root where the images will be backed up to
                             (no filename)
    """

    relative_path, _ = remove_common_beginning(original_image_dir, IMAGE_BACKUP_PATH)
    backup_path = os.path.join(IMAGE_BACKUP_PATH, relative_path)

    return backup_path, relative_path


# Database #


def send_to_database(database_uri, database_table, image_path, filename_list, keep_list, date_taken_list):
    """
    Send data pertaining to a completed group of images to the database.

    Args:
        database_uri = str, of the form accepted by sqlalchemy to create a database connection
        database_table = str, name of the database table
        image_path = str, the image path where the images are now stored (typically a subfolder of IMAGE_BACKUP_PATH)
        filename_list = list, of str, image filenames within the group
        keep_list = list, of bool, whether to keep those images or not
        date_taken_list = list, of datetime.datetime, when the images were originally taken (elements can be None)

    Returns: None

    Raises: if filename_list and keep_list do not have the same length.
    """

    N = len(keep_list)
    assert N == len(filename_list)

    engine = create_engine(database_uri)
    cnxn = engine.connect()

    # The group's ID is made unique by using the timestamp (up to milliseconds)
    modified_time = datetime.now()
    group_id = int(datetime.timestamp(modified_time)*10)

    # Calculate the path where the image is backed up to (i.e. raw data)
    img_backup_path, _ = get_backup_path(image_path, IMAGE_BACKUP_PATH)

    df_to_send = pd.DataFrame({
        'group_id': [group_id] * N,
        'filename': filename_list,
        'directory_name': [img_backup_path] * N,
        'keep': keep_list,
        'modified_time': [modified_time] * N,
        'picture_taken_time': date_taken_list,
    })

    df_to_send.to_sql(database_table, cnxn, if_exists='append', index=False)
    cnxn.close()


# Grid tools #


def create_image_grid(n_row, n_col, image_list):
    """
    Create a grid of the same image with n_row rows and n_col columns
    """

    if len(image_list) < ROWS_MAX * COLS_MAX:
        image_list = image_list + [config.IMG_PATH]*(ROWS_MAX * COLS_MAX - len(image_list))

    grid = []
    for i in range(ROWS_MAX):
        row = []
        for j in range(COLS_MAX):
            hidden = (i >= n_row) or (j >= n_col)
            row.append(get_grid_element(image_list, i, j, n_row, n_col, hidden))
        row = html.Tr(row)
        grid.append(row)

    return html.Div(html.Table(grid))


def get_grid_element(image_list, x, y, n_x, n_y, hidden):

    # Set the display to none if this grid cell is hidden
    if hidden:
        td_style = {'padding': 0, 'display': 'none',}
        button_style = {'padding': 0, 'display': 'none',}
    else:
        td_style = {'padding': 5}
        button_style = {'padding': 0}

    my_id = f'{x}-{y}'
    image = image_list[y + x*n_y]
    style = {
        'display': 'block',
        'height': 'auto',
        'width': 'auto',
        'max-height': f'{65 // n_x}vh', # < 75vh (see layout) due to the padding
        'max-width': f'{50 // n_y}vw',
    }
    image = html.Img(src=image, style=style)

    return html.Td(id='grid-td-' + my_id,
                   className='grouped-off' if x or y else 'grouped-off focus',
                   children=html.Button(id='grid-button-' + my_id,
                                        children=image,
                                        style=button_style,
                                        ),
                    style=td_style,
                   )


def resize_grid_pressed(image_list):
    class_names = ['grouped-off focus' if i+j == 0 else 'grouped-off' for i in range(ROWS_MAX) for j in range(COLS_MAX)]
    zoomed_img = html.Img(src=image_list[0], style=config.IMG_STYLE_ZOOM) if len(image_list) > 0 else EMPTY_IMAGE
    return class_names + [zoomed_img]


def image_cell_pressed(button_id, n_cols, image_list, *args):
    # Grid location of the pressed button
    cell_loc = [int(i) for i in re.findall('[0-9]+', button_id)]
    # Class name of the pressed button
    previous_class_clicked = args[N_GRID + cell_loc[1] + cell_loc[0]*COLS_MAX]
    previous_class_clicked = previous_class_clicked.split(' ')

    new_classes = []
    cell_last_clicked = None
    for i in range(ROWS_MAX):
        for j in range(COLS_MAX):
            # Toggle the class of the pressed button
            if cell_loc == [i, j]:
                # Toggle the focus according to these rules
                if 'grouped-off' in previous_class_clicked and 'focus' not in previous_class_clicked:
                    new_class_clicked = class_toggle_grouped(class_toggle_focus(previous_class_clicked))
                elif 'grouped-off' in previous_class_clicked and 'focus' in previous_class_clicked:
                    new_class_clicked = class_toggle_grouped(previous_class_clicked)
                elif 'grouped-on' in previous_class_clicked and 'focus' not in previous_class_clicked:
                    new_class_clicked = class_toggle_focus(previous_class_clicked)
                else:
                    assert 'grouped-on' in previous_class_clicked
                    assert 'focus' in previous_class_clicked
                    new_class_clicked = class_turn_off_keep_delete(class_toggle_grouped(class_toggle_focus(previous_class_clicked)))

                cell_last_clicked = cell_loc
                new_class_clicked = ' '.join(new_class_clicked)
                new_classes.append(new_class_clicked)
            # All others retain their class name, except the previous last clicked gets demoted
            else:
                previous_class = args[N_GRID + j + i*COLS_MAX]
                # If it was not previously clicked, this cell just keeps it old class name
                if 'focus' not in previous_class:
                    new_class = previous_class
                # In this case, this cell currently holds the "last clicked" status, but it must now yield it to
                # the newly clicked cell
                elif 'focus' in previous_class and 'focus' not in previous_class_clicked:
                    new_class = ' '.join(class_toggle_focus(previous_class.split(' ')))

                else:
                    # For debugging
                    print(cell_loc)
                    print((i, j))
                    print(previous_class)
                    print(previous_class_clicked)
                    raise ValueError('Impossible combination')

                new_classes.append(new_class)

    img_idx = cell_last_clicked[1] + cell_last_clicked[0]*n_cols
    zoomed_img = html.Img(src=image_list[img_idx], style=config.IMG_STYLE_ZOOM) if len(image_list) > 0 else EMPTY_IMAGE
    return new_classes + [zoomed_img]


def direction_key_pressed(button_id, n_rows, n_cols, image_list, *args):

    new_classes = []
    cell_last_clicked = None
    for i in range(ROWS_MAX):
        for j in range(COLS_MAX):
            my_class = args[N_GRID + j + i*COLS_MAX]

            # There's no need to change the class of a cell that is hidden
            if i >= n_rows or j >= n_cols:
                new_classes.append(my_class)
                continue

            if button_id == 'move-left':
                right_ngbr_i, right_ngbr_j = i, (j+1) % n_cols
                check_class = args[N_GRID + right_ngbr_j + right_ngbr_i*COLS_MAX]
            elif button_id == 'move-right':
                left_ngbr_i, left_ngbr_j = i, (j-1) % n_cols
                check_class = args[N_GRID + left_ngbr_j + left_ngbr_i*COLS_MAX]
            elif button_id == 'move-up':
                above_ngbr_i, above_ngbr_j = (i+1) % n_rows, j
                check_class = args[N_GRID + above_ngbr_j + above_ngbr_i*COLS_MAX]
            elif button_id == 'move-down':
                below_ngbr_i, below_ngbr_j = (i-1) % n_rows, j
                check_class = args[N_GRID + below_ngbr_j + below_ngbr_i*COLS_MAX]

            # Move focus away from the cell with it
            if 'focus' in my_class:
                new_classes.append(' '.join(class_toggle_focus(my_class.split(' '))))
            else:
                # In this case, we receive focus from the appropriate neighbour:
                # update our class name and note the cell location for the image zoom panel
                # Note: as the focus was previously elsewhere, we cannot have it
                if 'focus' in check_class:
                    new_classes.append(' '.join(class_toggle_focus(my_class.split(' '))))
                    cell_last_clicked = [i, j]
                else:
                    new_classes.append(my_class)

    img_idx = cell_last_clicked[1] + cell_last_clicked[0]*n_cols
    zoomed_img = html.Img(src=image_list[img_idx], style=config.IMG_STYLE_ZOOM) if len(image_list) > 0 else EMPTY_IMAGE
    return new_classes + [zoomed_img]


def keep_delete_pressed(button_id, n_rows, n_cols, image_list, *args):

    new_classes = []
    cell_last_clicked = None
    for i in range(ROWS_MAX):
        for j in range(COLS_MAX):
            my_class = args[N_GRID + j + i*COLS_MAX]

            # There's no need to change the class of a cell that is hidden
            if i >= n_rows or j >= n_cols:
                new_classes.append(my_class)
                continue

            if 'focus' in my_class:
                cell_last_clicked = [i, j]

            # It must be in the group to be kept or deleted
            if 'focus' in my_class and 'grouped-on' in my_class:
                if 'keep' in button_id:
                    new_classes.append(' '.join(class_toggle_keep(my_class.split(' '))))
                else:
                    assert 'delete' in button_id
                    new_classes.append(' '.join(class_toggle_delete(my_class.split(' '))))

            else:
                new_classes.append(my_class)

    img_idx = cell_last_clicked[1] + cell_last_clicked[0]*n_cols
    zoomed_img = html.Img(src=image_list[img_idx], style=config.IMG_STYLE_ZOOM) if len(image_list) > 0 else EMPTY_IMAGE
    return new_classes + [zoomed_img]


# Class-name functions #

def class_toggle_grouped(class_list):

    new_class_list = []
    for c in class_list:
        if c == 'grouped-on':
            new_class_list.append('grouped-off')
        elif c == 'grouped-off':
            new_class_list.append('grouped-on')
        else:
            new_class_list.append(c)

    return new_class_list


def class_toggle_focus(class_list):
    if 'focus' in class_list:
        return [c for c in class_list if c != 'focus']
    else:
        return class_list + ['focus']


def class_toggle_keep(class_list):
    if 'keep' in class_list:
        return [c for c in class_list if c != 'keep']
    else:
        return [c for c in class_list if c != 'delete'] + ['keep']


def class_toggle_delete(class_list):
    if 'delete' in class_list:
        return [c for c in class_list if c != 'delete']
    else:
        return [c for c in class_list if c != 'keep'] + ['delete']


def class_turn_off_keep_delete(class_list):
    return [c for c in class_list if c not in ['keep', 'delete']]


# Misc #

def create_flat_mask(image_mask, len_image_container):
    """
    Unpack the image mask into a flat list which states which images from the image container should be masked (as they
    have already been completed by the user).

    Note: each element (list) in the image mask represents a group of images. The int values in that group state the grid
          positions (0..n_rows*n_cols) of those images at the time they were grouped, not taking into account previously
          grouped images. Hence, the image mask must unpacked in order, from left (past) to right (present), in order to
          calculate the true mask on the image container.

    Args:
        image_mask = list, of lists of ints, a sequence of visible grid positions that have been completed (grouped)
                     Note: this is stored in the 'position' key in the image-meta-data
        len_image_container = int, length of the image container (all images) for the current working directory

    Returns:
        list, of bool, stating which images should not be shown if they would otherwise be shown in the visible grid


    >>> create_flat_mask([[0, 1], [0, 1, 2]], 9)
    [True, True, True, True, True, False, False, False, False]

    >>> create_flat_mask([[7, 8], [0, 1, 3, 4]], 10)
    [True, True, False, True, True, False, False, True, True, False]

    >>> create_flat_mask([[0, 1], [1, 2, 3], [1]], 10)
    [True, True, False, True, True, True, True, False, False, False]
    """

    true_mask = [False]*len_image_container
    for group in image_mask:
        available_count = -1
        for i, b in enumerate(true_mask):
            if not b:
                available_count += 1
                if available_count in group:
                    true_mask[i] = True # mask it

    return true_mask


def remove_common_beginning(str1, str2):
    """
    Strip out the common part at the start of both str1 and str2

    >>> remove_common_beginning('chalk', 'cheese')
    ('alk', 'eese')

    >>> remove_common_beginning('/common/path/to/a/b/c', '/common/path/to/d/e/f/')
    ('a/b/c', 'd/e/f/')

    Known failure, should return: ('same', '')
    >>> remove_common_beginning('samesame', 'same')
    ('', '')
    """

    common = ''
    for i, s in enumerate(str1):
        if str2.startswith(str1[:i+1]):
            common = str1[:i+1]
        else:
            break

    if len(common) > 0:
        return str1.split(common)[1], str2.split(common)[1]
    else:
        return str1, str2