"""
Utility functions supporting selector_app.py
"""

## Imports ##

import re
import os
import json
import shutil
import subprocess

from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import create_engine
from PIL import Image

import pandas as pd

import dash_html_components as html


# File manipulations #

def copy_image(fname, src_path, dst_path, image_types, static_image_route='/'):
    """
    Perform a copy of the file if it is an image. It will be copied to dst_path.

    Args:
        fname = str, query filename (no path)
        src_path = str, directory of where to copy from (no filename)
        dst_path = str, directory of where to copy to (no filename)
        image_types = list, of str, valid extensions of image files (e.g. .jpg)
        static_image_route = str, the path where the static images will be served from

    Returns: str, full filepath that the server is expecting
             or None, if not an valid image type (see IMAGE_TYPES)

    WARNING: known bug - when saving via rotation, the image metadata is not preserved!
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
    static_image_path = os.path.join(static_image_route, fname)

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

        # Failed to obtain date from metadata, try to extract it from filename using regex
        # This list should contain pairs of:
        #   0) The regex to use on the filename, incl. a grouping around the useful date(time)
        #   1) How to parse the found match with strptime
        regex_parse_options = [('[A-Z]+-([0-9]{8})-WA[0-9]+', '%Y%m%d')]
        for regex_pattern, parse_pattern in regex_parse_options:
            match = re.search(regex_pattern, fname)
            if match:
                try:
                    return datetime.strptime(match.group(1), parse_pattern)
                except (ValueError, IndexError):
                    continue

        return default_date

    except FileNotFoundError:
        return None


def sort_images_by_datetime(image_filepaths: List[str], image_dir: str = None) -> List[str]:
    """
    Sort images by time taken (ascending, i.e. earliest to latest).

    :param image_filepaths: list, of str, full filepaths to the unsorted images
    :param image_dir: str, image directory to look in first (None => filepath supplied with image_filepaths will be used)
    :return: list, of str, the images sorted by their date taken
    """
    image_datetimes = []
    for fullpath in image_filepaths:
        my_dir, filename = os.path.split(fullpath)
        image_datetimes.append(get_image_taken_date(image_dir if image_dir else my_dir, filename))

    sorted_images = [img for img, _ in sorted(list(zip(image_filepaths, image_datetimes)), key=lambda x: x[1])]
    return sorted_images


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
    path_options = subprocess.check_output(['find', os.path.expanduser('~/Pictures'), '-name', img_fname]).decode()
    path_options = ['/'.join(f.split('/')[:-1]) for f in path_options.split('\n') if len(f) > 0]
    return path_options


def get_backup_path(original_image_dir: str, image_backup_path: str):
    """
    Calculate the location where all the images will be backed up to.

    Args:
        original_image_dir = str, filepath of where the original images are stored (no filename)
        image_backup_path = str, the filepath to the root folder where all image files will be backed up to

    Returns:
        backup_path = str, full filepath the specific location (within intended_backup_root) these images will be
                           copied to (no filename)
        relative_path = str, the relative filepath under intended_backup_root where the images will be backed up to
                             (no filename)
    """

    relative_path, _ = remove_common_beginning(original_image_dir, image_backup_path)
    backup_path = os.path.join(image_backup_path, relative_path)

    return backup_path, relative_path


# Database #


def send_to_database(database_uri, database_table, image_path, filename_list, keep_list, date_taken_list, image_backup_path):
    """
    Send data pertaining to a completed group of images to the database.

    Args:
        database_uri = str, of the form accepted by sqlalchemy to create a database connection
        database_table = str, name of the database table
        image_path = str, the image path where the images are now stored (typically a subfolder of image_backup_path)
        filename_list = list, of str, image filenames within the group
        keep_list = list, of bool, whether to keep those images or not
        date_taken_list = list, of datetime.datetime, when the images were originally taken (elements can be None)
        image_backup_path = str, the filepath to the root folder where all image files will be backed up to

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
    img_backup_path, _ = get_backup_path(image_path, image_backup_path)
    img_backup_path = img_backup_path.replace(os.path.expanduser('~'), '~')  # save with soft-coded path

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


def delete_from_database(database_uri, database_table, image_path, filename_list, image_backup_path):
    """
    Remove data pertaining to a completed group of images to the database (via undo button).

    Args:
        database_uri = str, of the form accepted by sqlalchemy to create a database connection
        database_table = str, name of the database table
        image_path = str, the image path where the images are now stored (typically a subfolder of image_backup_path)
        filename_list = list, of str, image filenames within the group
        image_backup_path = str, the filepath to the root folder where all image files will be backed up to

    Returns: None
    """

    engine = create_engine(database_uri)
    cnxn = engine.connect()

    # Calculate the path where the image is backed up to (i.e. raw data)
    img_backup_path, _ = get_backup_path(image_path, image_backup_path)

    delete_query = f'''
                    DELETE FROM {database_table}
                    WHERE directory_name=%(directory_name)s
                    AND filename IN %(filenames)s
                    '''
    cnxn.execute(delete_query, {'directory_name': img_backup_path, 'filenames': tuple(filename_list)})
    cnxn.close()


def record_grouped_data(
        image_data: dict,
        image_path: str,
        filename_list: list,
        keep_list: list,
        date_taken_list: list,
        image_backup_path: str,
        meta_data_fpath: str,
        database_uri: str,
        database_table: str,
    ):
    """
    Perform a collection of operations that record the choices for a group of images:
        1) dump data in a JSON file,
        2) save the data to the specified database
        3) delete unwanted files from the system

    All arguments (except image_data) correspond to a single set of grouped images.

    Args:
        image_data = dict, indexed by str keys referring to the filepath of this set of images, each with three subkeys:
                     position, keep, filename
        image_path = str, the filepath to this group of images
        filename_list = list, of str, the filename of each image in this group (can be found at image_path)
        keep_list = list, of bool, choice of whether to keep each image or not
                    Note: order corresponds to filenames list
        date_taken_list = list, of datetime.datetime, when the image was taken
                          Note: order corresponds to filenames list
        meta_data_fpath = str, a full filepath of where to dump session metadata as JSON (see config.py)
        database_uri = str, address to database according to SQLAlchemy (see config.py)
        database_table = str, table name in which to store the image group data (see config.py)

    Returns: None

    Note: a major side effect is that all files that are not kept (see keeps) are deleted from the file system.
            However, they can be recovered from IMAGE_BACKUP_PATH (see config.py)
    """

    # Save all meta data in JSON format on disk
    with open(meta_data_fpath, 'w') as j:
        json.dump(image_data, j)

    # Save data for the new group in the specified database
    send_to_database(
            database_uri=database_uri,
            database_table=database_table,
            image_path=image_path,
            filename_list=filename_list,
            keep_list=keep_list,
            date_taken_list=date_taken_list,
            image_backup_path=image_backup_path,
    )

    # Delete the discarded images (can be restored manually from IMAGE_BACKUP_PATH (see config.py))
    for i, fname in enumerate(filename_list):
        if not keep_list[i]:
            os.remove(os.path.join(image_path, fname))


def undo_last_group(
        image_data: dict,
        image_path: str,
        filename_list: list,
        image_backup_path: str,
        meta_data_fpath: str,
        database_uri: str,
        database_table: str,
    ):
    """
    Perform a collection of operations that undo the choices for a group of images:
        1) dump data in a JSON file (overwrites with one less group)
        2) remove the data from the specified database
        3) copy the files from the backup back to their original location

    Args:
        image_data = dict, indexed by str keys referring to the filepath of this set of images, each with three subkeys:
                     position, keep, filename
        image_path = str, the filepath to this group of images
        filename_list = list, of str, the filename of each image in this group (can be found at image_path)
        image_backup_path = str, the filepath to the root folder where all image files will be backed up to
        meta_data_fpath = str, a full filepath of where to dump session metadata as JSON (see config.py)
        database_uri = str, address to database according to SQLAlchemy (see config.py)
        database_table = str, table name in which to store the image group data (see config.py)

    Returns: None

    Note: this is the inverse operation of record_grouped_data
    """

    # Save all meta data in JSON format on disk
    with open(meta_data_fpath, 'w') as j:
        json.dump(image_data, j)

    # Save data for the new group in the specified database
    delete_from_database(
        database_uri=database_uri,
        database_table=database_table,
        image_path=image_path,
        filename_list=filename_list,
        image_backup_path=image_backup_path,
    )

    # Restore the previously discarded images from image_backup_path to their original location
    img_backup_path, _ = get_backup_path(image_path, image_backup_path)
    for i, fname in enumerate(filename_list):
        shutil.copyfile(os.path.join(img_backup_path, fname), os.path.join(image_path, fname))
        #copy_image(fname, img_backup_path, image_path, config.IMAGE_TYPES)


# Grid tools #


def create_image_grid(n_row: int, n_col: int, rows_max: int, cols_max: int, image_list: List[str], empty_img_path: str):
    """
    Create a grid of the same image with n_row rows and n_col columns

    :param n_row: int, the current number of rows visible
    :param n_col: int, the current number of columns visible
    :param rows_max: int, the maximum available number of rows (e.g. see config.py)
    :param cols_max: int, the maximum available number of columns (e.g. see config.py)
    :param image_list: list, of str, filepaths of the images
    :param empty_img_path: str, full filepath to where the empty / default image can be served from (for padding the grid)
    :return: html.Div, containing a grid of images of size n_row x n_col
    """

    if len(image_list) < rows_max * cols_max:
        image_list = image_list + [empty_img_path] * (rows_max * cols_max - len(image_list))

    grid = []
    for i in range(rows_max):
        row = []
        for j in range(cols_max):
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
        button_style = {'padding': 0, 'display': 'block', 'margin-left': 'auto', 'margin-right': 'auto'}

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


def resize_grid_pressed(image_list: List[str], image_size_list: List[str], rows_max: int, cols_max: int, empty_image: html.Img, zoom_img_style: Dict[str, str]):
    class_names = ['grouped-off focus' if i+j == 0 else 'grouped-off' for i in range(rows_max) for j in range(cols_max)]
    zoomed_img = html.Img(src=image_list[0], style=zoom_img_style, title=image_size_list[0]) if len(image_list) > 0 else empty_image
    return class_names + [zoomed_img, [0,0]]


def image_cell_pressed(
        button_id: str,
        n_cols: int, cols_max: int, n_grid: int,
        image_list: List[str],
        image_size_list: List[str],
        empty_image: html.Img,
        zoom_img_style: Dict[str, str],
        *args
    ):
    # Get the last clicked cell from args
    cell_last_clicked = args[-1]

    # Grid location of the pressed button
    cell_loc = list(map(int, re.findall('[0-9]+', button_id)))

    # Class name of the pressed button
    previous_class_clicked = args[n_grid + cell_loc[1] + cell_loc[0]*cols_max]
    previous_class_clicked = previous_class_clicked.split(' ')
    new_classes = list(args[n_grid:-1])
    i, j = cell_loc
    idx = i * cols_max + j
    if not cell_last_clicked:
        cell_last_clicked = [0,0]

    if cell_last_clicked != cell_loc:
        previous_class_idx = cell_last_clicked[1] + cell_last_clicked[0]*cols_max
        previous_class = args[n_grid + previous_class_idx]
        # If it was not previously clicked, this cell just keeps it old class name
        if 'focus' not in previous_class:
            new_class = previous_class
        # In this case, this cell currently holds the "last clicked" status, but it must now yield it to
        # the newly clicked cell
        elif 'focus' in previous_class and 'focus' not in previous_class_clicked:
            new_class = ' '.join(class_toggle_focus(previous_class.split(' ')))
        new_classes[previous_class_idx] = new_class

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
    new_classes[idx] = new_class_clicked
    img_idx = cell_last_clicked[1] + cell_last_clicked[0]*n_cols
    zoomed_img = html.Img(src=image_list[img_idx], style=zoom_img_style, title=image_size_list[img_idx]) if len(image_list) > 0 else empty_image
    return new_classes,zoomed_img, cell_last_clicked


def toggle_group_in_first_n_rows(
        row: int, n_cols: int, rows_max: int, cols_max: int,
        image_list: List[str],
        image_size_list: List[str],
        empty_image: html.Img,
        zoom_img_style: Dict[str, str],
        *args
    ):

    cell_last_clicked = args[-1]
    if not cell_last_clicked:
        cell_last_clicked = [0,0]

    n_grid = rows_max * cols_max
    new_classes = list(args[n_grid:-1])
    for i in range(min(row, rows_max)):
        for j in range(n_cols):
            cell_list_idx = j + i*cols_max
            previous_class = new_classes[cell_list_idx]
            new_classes[cell_list_idx] = ' '.join(class_turn_off_keep_delete(class_toggle_grouped(previous_class.split(' '))))

    img_idx = cell_last_clicked[1] + cell_last_clicked[0]*n_cols
    zoomed_img = html.Img(src=image_list[img_idx], style=zoom_img_style, title=image_size_list[img_idx]) if len(image_list) > 0 else empty_image
    return new_classes, zoomed_img, cell_last_clicked


def direction_key_pressed(
        button_id: str,
        n_rows: int, n_cols: int, cols_max: int, n_grid: int,
        image_list: List[str],
        image_size_list: List[str],
        empty_image: html.Img,
        zoom_img_style: Dict[str, str],
        *args
    ):
    # Get the last clicked cell from args
    cell_last_clicked = args[-1]

    # Get the classes from args and only change the value of the affected cell
    new_classes = list(args[n_grid:-1])
    if not cell_last_clicked:
        cell_last_clicked = [0,0]
    i, j = cell_last_clicked
    idx = i * cols_max + j
    my_class = new_classes[idx]

    # Move focus away from the cell with it
    if 'focus' in my_class:
        new_classes[idx] = ' '.join(class_toggle_focus(my_class.split(' ')))
    new_i, new_j = i, j
    if button_id == 'move-left':
        new_i, new_j = i, (j-1) % n_cols
        check_class = args[n_grid + new_j + new_i*cols_max]
    elif button_id == 'move-right':
        new_i, new_j = i, (j+1) % n_cols
        check_class = args[n_grid + new_j + new_i*cols_max]
    elif button_id == 'move-up':
        new_i, new_j = (i-1) % n_rows, j
        check_class = args[n_grid + new_j + new_i*cols_max]
    elif button_id == 'move-down':
        new_i, new_j = (i+1) % n_rows, j
        check_class = args[n_grid + new_j + new_i*cols_max]

    # Add focus to check_class
    if check_class:
        current_idx = new_i * cols_max + new_j
        new_classes[current_idx]= ' '.join(class_toggle_focus(new_classes[current_idx].split(' ')))
        cell_last_clicked = [new_i, new_j]
    img_idx = cell_last_clicked[1] + cell_last_clicked[0]*n_cols
    zoomed_img = html.Img(src=image_list[img_idx], style=zoom_img_style, title=image_size_list[img_idx]) if len(image_list) > 0 else empty_image
    return new_classes, zoomed_img, cell_last_clicked


def keep_delete_pressed(
        button_id: str,
        n_cols: int, cols_max: int, n_grid: int,
        image_list: List[str],
        image_size_list: List[str],
        empty_image: html.Img,
        zoom_img_style: Dict[str, str],
        *args
    ):

    cell_last_clicked = args[-1]
    new_classes = list(args[n_grid:-1])
    if not cell_last_clicked:
        cell_last_clicked = [0,0]
    i, j = cell_last_clicked
    idx = i * cols_max + j
    my_class = new_classes[idx]

    # It must be in the group to be kept or deleted
    if 'focus' in my_class and 'grouped-on' in my_class:
        if 'keep' in button_id:
            new_classes[idx] = (' '.join(class_toggle_keep(my_class.split(' '))))
        else:
            assert 'delete' in button_id
            new_classes[idx] = (' '.join(class_toggle_delete(my_class.split(' '))))

    img_idx = cell_last_clicked[1] + cell_last_clicked[0]*n_cols
    zoomed_img = html.Img(src=image_list[img_idx], style=zoom_img_style, title=image_size_list[img_idx]) if len(image_list) > 0 else empty_image
    return new_classes, zoomed_img, cell_last_clicked


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


def calc_percentage_complete(completed_groups: List[List[Any]], total_images: int) -> int:
    """
    Calculate the approximate (rounded to int) percentage of images completed, calculated from the current list of
    completed groups.

    :param: completed_groups, list, of list of ?, a two-depth list containing group information (to be flattened)
    :param: int, target number of images to do
    :return: int, % of images done so far, rounded

    >>> calc_percentage_complete([[0, 1, 3], [0, 1]], 10)
    50
    """

    n_imgs_completed = len([image for group in completed_groups for image in group])
    pct_complete = round(100 * n_imgs_completed / total_images)

    return pct_complete


def readable_filesize(num, suffix='B'):
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Y', suffix)
