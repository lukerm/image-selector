"""
Dash app for grouping images and choosing the best per-group images.

The left-hand side is a re-sizable grid of images. You can zoom in on any image (shown in the right-hand panel), by
clicking on it, or by using the directional keys to move the blue square around.

Each grid cell (td element) will have at least one class name in {'grouped-off', 'grouped-on'}. You can have multiple cells
with grouped-on and it currently draws a red square around it. This will eventually represent the grouping. Those with
the 'grouped-off' will (often) have no border, with one exception. A cell can have 'grouped-on' or 'grouped-off' but not both.

Additionally, one cell can have the special 'focus' class (currently blue border). This applies to one cell -
another cell will lose this when it is superceded. This class is achieved by clicking on a cell (that doesn't already
have it) or by moving the current highlighted cell around with the directional buttons / keys.

Note: the way this is coded means that the class ordering is always as follows: 'grouped-o[n|ff][ focus]'.
        This is not ideal and maybe fixed in the future so that the order does not matter.
"""

# TODO: KNOWN BUG: select image directory > Load directory > Resize 4x4 > Click: {(0,1), (0,2), (0,3)} > Resize 5x5 / 3x3
#                   > Click Backspace / +


## Imports ##

import os
import re
import json
import shutil
import subprocess

from datetime import date, datetime

import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State

import flask


## Constants ##

app = dash.Dash(__name__)


# Assumes that images are stored in the img/ directory for now
image_directory = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'img')
static_image_route = '/'
TMP_DIR = '/tmp'

# Where to save metadata
META_DATA_FNAME = f'image_selector_session_{str(date.today())}_{int(datetime.timestamp(datetime.now()))}.json'
META_DATA_FPATH = os.path.join(os.path.expanduser('~'), META_DATA_FNAME)

# Define the maximal grid dimensions
ROWS_MAX, COLS_MAX = 7, 7
N_GRID = ROWS_MAX * COLS_MAX

# Allowed file extension for image types
IMAGE_TYPES = ['.JPG', '.jpg', '.JPEG', '.jpeg', '.png']

# Globals for the images
img_fname = 'job_done.jpg' # Default image
img_path = static_image_route + img_fname
img_style = {'display': 'block', 'height': 'auto', 'max-width': '100%'}


# These define the inputs and outputs to callback function activate_deactivate_cells
ALL_TD_ID_OUTPUTS = [Output(f'grid-td-{i}-{j}', 'className') for i in range(ROWS_MAX) for j in range(COLS_MAX)]
ALL_BUTTONS_IDS = [Input(f'grid-button-{i}-{j}', 'n_clicks') for i in range(ROWS_MAX) for j in range(COLS_MAX)]
ALL_TD_ID_STATES = [State(f'grid-td-{i}-{j}', 'className') for i in range(ROWS_MAX) for j in range(COLS_MAX)]


## Functions ##

def create_image_grid(n_row, n_col, image_list):
    """
    Create a grid of the same image with n_row rows and n_col columns
    """

    if len(image_list) < ROWS_MAX * COLS_MAX:
        image_list = image_list + [EMPTY_IMAGE]*(ROWS_MAX * COLS_MAX - len(image_list))

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

    pad = 30/min(n_x, n_y)

    # Set the display to none if this grid cell is hidden
    if hidden:
        td_style = {'padding': 0, 'display': 'none',}
        button_style = {'padding': 0, 'display': 'none',}
    else:
        td_style = {'padding': pad}
        button_style = {'padding': 0}

    my_id = f'{x}-{y}'
    return html.Td(id='grid-td-' + my_id,
                   className='grouped-off' if x or y else 'grouped-off focus',
                   children=html.Button(id='grid-button-' + my_id,
                                        children=image_list[y + x*n_y],
                                        style=button_style,
                                        ),
                    style=td_style,
                   )


def copy_image(fname, src_path, dst_path):
    """
    Perform a copy of the file if it is an image. It will be copied to dst_path.

    Args:
        fname = str, query filename (no path)
        src_path = str, directory of where to copy from (no filename)
        dst_path = str, directory of where to copy to (no filename)

    Returns: str, full filepath that the server is expecting
             or None, if not an valid image type (see IMAGE_TYPES)
    """

    # Check if it's a valid image (by extension)
    is_image = False
    for img_type in IMAGE_TYPES:
        if img_type in fname:
            is_image = True
            break
    # Only copy images
    if not is_image:
        return

    # Copy the file to the temporary location (that can be served)
    shutil.copyfile(os.path.join(src_path, fname), os.path.join(dst_path, fname))
    # Append the Img object with the static path
    static_image_path = os.path.join(static_image_route, fname)

    return static_image_path


## Main ##


# List of image objects - pre-load here to avoid re-loading on every grid re-sizing
images = [static_image_route + fname for fname in sorted(os.listdir(image_directory))]
IMAGE_LIST = [html.Img(src=img, style=img_style) for img in images]
IMAGE_LIST = IMAGE_LIST + [html.Img(src=img_path, style=img_style)]*(ROWS_MAX*COLS_MAX - len(IMAGE_LIST))
EMPTY_IMAGE = html.Img(src=img_path, style=img_style)

# Copy default images to the TMP_DIR so they're available when the program starts
for fname in sorted(os.listdir(image_directory)):
    static_image_path = copy_image(fname, image_directory, TMP_DIR)


## Layout ##

# App's layout
app.layout = html.Div(
    children=[
        html.Div(id='hidden-div', style={'display': 'none'}),
        html.H2("Image Selector"),
        dcc.Upload(
                id='upload-image',
                children=html.Div([
                    'Drag and Drop or ',
                    html.A('Select Images')
                ]),
                style={
                    'width': '40vw',
                    'height': '60px',
                    'lineHeight': '60px',
                    'borderWidth': '1px',
                    'borderStyle': 'dashed',
                    'borderRadius': '5px',
                    'textAlign': 'center',
                },
                multiple=True
        ),
        dcc.Dropdown(
            id='choose-image-path',
            options=[{'label': 'NO PATH SELECTED', 'value': 0}],
            value=0,
            style={'width': '40vw',}
        ),
        html.Tr([
            html.Td([
                html.Button(
                    id='confirm-load-directory',
                    children='Load directory',
                    style={'width': '10vw', }
                ),
            ]),
            html.Td([
                html.Button(
                    id='complete-group',
                    children='Complete group',
                    style={'width': '10vw', }
                )
            ]),
        ]),
        dcc.Dropdown(
            id='choose-grid-size',
            options=[{'label': f'{k+1} x {k+1}', 'value': k+1} for k in range(ROWS_MAX) if k > 0],
            value=2,
            style={'width': '10vw'}
        ),
        html.Div([
            html.Button(id='move-left', children='Move left'),
            html.Button(id='move-right', children='Move right'),
            html.Button(id='move-up', children='Move up'),
            html.Button(id='move-down', children='Move down'),
        ], style={'display': 'none'}),
        html.Div([
            html.Button(id='keep-button', children='Keep'),
            html.Button(id='delete-button', children='Delete'),
        ], style={'display': 'none'}),
        html.Div([
            html.Table([
                html.Tr([
                    html.Td(
                        id='responsive-image-grid',
                        children=create_image_grid(2, 2, IMAGE_LIST),
                        style={'width': '50vw', 'height': 'auto', 'border-style': 'solid',}
                        ),
                    html.Td([
                        html.Div(
                            id='zoomed-image',
                            children=IMAGE_LIST[0],
                            style={'width': '50%', 'display': 'block', 'margin-left': 'auto', 'margin-right': 'auto'}
                        )
                    ], style={'width': '50vw', 'height': 'auto', 'border-style': 'solid',}),
                ]),
            ]),
        ]),
        html.Div(id='image-container', children=html.Tr(IMAGE_LIST), style={'display': 'none'}),
        # The underlying mask is a dict, where each entry contains data about a particular unique file directory where
        # images are stored. For each directory, there are two keys - 'position' and 'keep' - where each is a list of
        # lists of ints (representing image groups, in time order). This data structure can be handled by the Store
        # component (as it's serializable).
        dcc.Store(id='image-meta-data', data={'__ignore': {'position': [], 'keep': []}}, storage_type='session'),
        # For storing the image path WHEN THE confirm-load-directory IS CLICKED (the label in choose-image-path may
        # change without their being a new upload, so we need to record this value)
        dcc.Store(id='loaded-image-path', data=['__ignore'], storage_type='session'),
    ]
)


## Callbacks ##

@app.callback(
    [Output('choose-image-path', 'options'), Output('choose-image-path', 'value')],
    [Input('upload-image', 'contents')],
    [State('upload-image', 'filename')]
)
def update_image_path_selector(contents_list, filenames_list):
    if contents_list is not None:
        for fname in filenames_list:
            options_list = parse_image_upload(fname)
            if len(options_list) > 0:
                return (options_list, 0)
            else:
                continue

    return ([{'label': 'NO IMAGE SELECTED', 'value': 0}], 0)


def parse_image_upload(filename):
    """
    Given an image filename, create a list of options for the 'options' for the Dropdown that chooses
    which path the image should be loaded from.
    """
    is_image = False
    for img_type in IMAGE_TYPES:
        if img_type in filename:
            is_image = True
            break

    if is_image:
        path_options = find_image_dir_on_system(filename)
        if len(path_options) > 0:
            return [{'label': path, 'value': i} for i, path in enumerate(path_options)]
        else:
            return []
    else:
        return []


def find_image_dir_on_system(img_fname):
    """
    Find the location(s) of the given filename on the file system.

    Returns: list of filepaths (excluding filename) where the file can be found.
    """
    path_options = subprocess.check_output(['find', os.path.expanduser('~'), '-name', img_fname]).decode()
    path_options = ['/'.join(f.split('/')[:-1]) for f in path_options.split('\n') if len(f) > 0]
    return path_options


@app.callback(
    [
     Output('image-container', 'children'),
     Output('loaded-image-path', 'data'),
    ],
    [Input('confirm-load-directory', 'n_clicks')],
    [
     State('choose-image-path', 'value'),
     State('choose-image-path', 'options'),
    ]
)
def load_images(n, dropdown_value, dropdown_opts):
    opts = {d['value']: d['label'] for d in dropdown_opts}
    image_dir = opts[dropdown_value]

    image_list = []
    try:
        for fname in sorted(os.listdir(image_dir)):
            static_image_path = copy_image(fname, image_dir, TMP_DIR)

            if static_image_path is not None:
                image_list.append(html.Img(src=static_image_path, style=img_style))

        while len(image_list) < ROWS_MAX*COLS_MAX:
            image_list.append(EMPTY_IMAGE)

    except FileNotFoundError:
        return html.Tr([]), ['__ignore']

    # Return a 2-tuple: 0) is a wrapped list of Imgs; 1) is a single-entry list containing the loaded path
    return html.Tr(image_list), [image_dir]


@app.callback(
    Output('image-meta-data', 'data'),
    [Input('complete-group', 'n_clicks')],
    [
     State('choose-grid-size', 'value'),
     State('choose-grid-size', 'value'),
     State('image-meta-data', 'data'),
     State('loaded-image-path', 'data'),
    ] + ALL_TD_ID_STATES
)
def complete_image_group(n_group, n_rows, n_cols, image_data, image_path, *args):
    """
    Updates the image_mask by appending relevant info to it. This happens when either 'Complete group' button is clicked
    or the visible grid size is updated.

    Args:
        n_group = int, number of times the complete-group button is clicked (Input)
        n_rows = int, current number of rows in the grid (Input: indicates resizing)
        n_cols = int, current number of columns in the grid (Input: indicates resizing)
        image_data = dict, with keys 'position' (for visible grid locations) and 'keep' (whether to keep / remove the image) (State)
                     Note: each keys contains a list, of lists of ints, a sequence of data about each completed image group

    Returns:
        updated version of the image mask (if any new group was legitimately completed)
    """

    # Unpack the single-element list
    image_path = image_path[0]
    if image_path not in image_data:
        image_data[image_path] = {'position': [], 'keep': []}

    # Need to adjust for the disconnect between the visible grid size (n_rows * n_cols) and the virtual grid size (ROWS_MAX * COLS_MAX)
    grouped_cell_positions = []
    grouped_cell_keeps = []
    for i in range(n_rows):
        for j in range(n_cols):
            # Get the class list (str) for this cell
            my_class = args[j + i*COLS_MAX]
            # Position on the visible grid
            list_pos = j + i*n_rows

            # Check if selected to be in the group, add position if on
            if 'grouped-on' in my_class:
                grouped_cell_positions.append(list_pos)

            # Check for keep / delete status
            # Note: important not to append if keep/delete status not yet specified
            if 'keep' in my_class:
                grouped_cell_keeps.append(True)
            elif 'delete' in my_class:
                grouped_cell_keeps.append(False)
            else:
                pass

    # Check 1: some data has been collected since last click (no point appending empty lists)
    # Check 2: list lengths match, i.e. for each cell in the group, the keep / delete status has been declared
    # If either check fails, do nothing
    # TODO: flag something (warning?) to user if list lengths do not match
    # TODO: if check 2 fails, it currently junks the data - possible to hold onto it?
    if len(grouped_cell_positions) > 0 and len(grouped_cell_positions) == len(grouped_cell_keeps):
        image_data[image_path]['position'].append(grouped_cell_positions)
        image_data[image_path]['keep'].append(grouped_cell_keeps)

        with open(META_DATA_FPATH, 'w') as j:
            json.dump(image_data, j)

    return image_data


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


@app.callback(
    Output('responsive-image-grid', 'children'),
    [Input('choose-grid-size', 'value'),
     Input('choose-grid-size', 'value'),
     Input('image-container', 'children'),
     Input('image-meta-data', 'data'),
    ],
    [State('loaded-image-path', 'data'),]
)
def create_reactive_image_grid(n_row, n_col, image_list, image_data, image_path):

    # Unpack the image_list if necessary
    if type(image_list) is dict:
        image_list = image_list['props']['children']

    # Unpack the single-element list
    image_path = image_path[0]
    if image_path not in image_data:
        image_data[image_path] = {'position': [], 'keep': []}

    # Reduce the image_list by removing the masked images (so they can no longer appear in the image grid / image zoom)
    flat_mask = create_flat_mask(image_data[image_path]['position'], len(image_list))
    image_list = [img for i, img in enumerate(image_list) if not flat_mask[i]]

    return create_image_grid(n_row, n_col, image_list)


@app.callback(
    ALL_TD_ID_OUTPUTS + [Output('zoomed-image', 'children')],
    [
         Input('choose-grid-size', 'value'),
         Input('choose-grid-size', 'value'),
         Input('move-left', 'n_clicks'),
         Input('move-right', 'n_clicks'),
         Input('move-up', 'n_clicks'),
         Input('move-down', 'n_clicks'),
         Input('keep-button', 'n_clicks'),
         Input('delete-button', 'n_clicks'),
         Input('image-container', 'children'),
         Input('image-meta-data', 'data'),
         Input('loaded-image-path', 'data'),
    ] + ALL_BUTTONS_IDS,
    ALL_TD_ID_STATES
)
def activate_deactivate_cells(n_rows, n_cols, n_left, n_right, n_up, n_down, n_keep, n_delete, image_list, image_data, image_path, *args):
    """
    Global callback function for toggling classes. There are three toggle modes:
        1) Pressing a grid cell will toggle its state
        2) Pressing a directional button will force the "last-clicked" focus (only) to shift in the direction stated
        3) Resizing the grid will cause the top-left only to be in last-click focus
        4) Mark a cell as keep or delete (must already have "grouped-on" class)

    Note: some of these operations respond to key presses (e.g. directional buttons), which click hidden buttons.

    Args:
        n_rows = int, current number of rows in the grid (indicates resizing)
        n_cols = int, current number of columns in the grid (indicates resizing)
        n_left = int, number of clicks on the 'move-left' button (indicates shifting)
        n_right = int, number of clicks on the 'move-right' button (indicates shifting)
        n_up = int, number of clicks on the 'move-up' button (indicates shifting)
        n_down = int, number of clicks on the 'move-down' button (indicates shifting)
        n_keep = int, number of clicks on the 'keep-button' button
        n_delete = int, number of clicks on the 'delete-button' button
        image_list = dict, containing a list of Img objects under ['props']['children']
        image_data = dict, of dict of lists of ints, a sequence of metadata about completed image groups
        image_path = str, the filepath where the images in image-container were loaded from

        *args = positional arguments split into two equal halves (i.e. of length 2 x N_GRID):
            0) args[:N_GRID] are Inputs (activated by the grid-Buttons)
            1) args[N_GRID:] are States (indicating state of the grid-Tds)
            Both are in row-major order (for i in rows: for j in cols: ... )

    Returns: a list of new classNames for all the grid cells (plus one extra element for the Image that was last clicked)

    Note: args split into two halves:
        args[:N_GRID] are Inputs (Buttons)
        args[N_GRID:] are States (Tds)
    """

    # Unpack the image list / mask
    if image_list:
        image_list = image_list['props']['children']

    # Unpack the single-element list
    image_path = image_path[0]
    if image_path not in image_data:
        image_data[image_path] = {'position': [], 'keep': []}

    # Reduce the image_list by removing the masked images (so they can no longer appear in the image grid / image zoom)
    flat_mask = create_flat_mask(image_data[image_path]['position'], len(image_list))
    image_list = [img for i, img in enumerate(image_list) if not flat_mask[i]]

    # Find the button that triggered this callback (if any)
    context = dash.callback_context
    if not context.triggered:
        class_names = ['grouped-off focus' if i+j == 0 else 'grouped-off' for i in range(ROWS_MAX) for j in range(COLS_MAX)]
        zoomed_img = image_list[0]
        return class_names + [zoomed_img]
    else:
        button_id = context.triggered[0]['prop_id'].split('.')[0]


    # Reset the grid
    # Note: image-container is not really a button, but fired when confirm-load-directory is pressed (we need the list
    #       inside image-container in order to populate the grid)
    if button_id in ['choose-grid-size', 'image-container', 'image-meta-data', 'loaded-image-path']:
        return resize_grid_pressed(image_list)

    # Toggle the state of this button (as it was pressed)
    elif 'grid-button-' in button_id:
        return image_cell_pressed(button_id, n_cols, image_list, *args)

    # Harder case: move focus in a particular direction
    elif 'move-' in button_id:
        return direction_key_pressed(button_id, n_rows, n_cols, image_list, *args)

    elif button_id in ['keep-button', 'delete-button']:
        return keep_delete_pressed(button_id, n_rows, n_cols, image_list, *args)

    else:
        raise ValueError('Unrecognized button ID: %s' % str(button_id))


def resize_grid_pressed(image_list):
    class_names = ['grouped-off focus' if i+j == 0 else 'grouped-off' for i in range(ROWS_MAX) for j in range(COLS_MAX)]
    zoomed_img = image_list[0] if len(image_list) > 0 else EMPTY_IMAGE
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

    zoomed_img = image_list[cell_last_clicked[1] + cell_last_clicked[0]*n_cols] if len(image_list) > 0 else EMPTY_IMAGE
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

    zoomed_img = image_list[cell_last_clicked[1] + cell_last_clicked[0]*n_cols] if len(image_list) > 0 else EMPTY_IMAGE
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

    zoomed_img = image_list[cell_last_clicked[1] + cell_last_clicked[0]*n_cols] if len(image_list) > 0 else EMPTY_IMAGE
    return new_classes + [zoomed_img]


# Functions for dealing with class names

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


@app.server.route('{}<image_path>'.format(static_image_route))
def serve_image(image_path):
    """
    Allows an image to be served from the given image_path
    """
    image_name = '{}'.format(image_path)
    # For more secure deployment, see: https://github.com/plotly/dash/issues/71#issuecomment-313222343
    #if image_name not in list_of_images:
    #    raise Exception('"{}" is excluded from the allowed static files'.format(image_path))
    return flask.send_from_directory(TMP_DIR, image_name)


if __name__ == '__main__':
    app.run_server(debug=True)
