"""
Dash app for grouping images and choosing the best per-group images. You also choose whether to delete any images in
that group.

Images can be loaded from a directory by clicking on the 'Select images' box and navigating to the correct folder. You
need only click on one image, then 'Open'. (Alternatively, drag and drop an image from the folder of interest into the
box.) Due to a technicality, you must select the correct directory from the dropdown menu, then click 'Load directory'.
This will load all valid image files from that directory (but not subdirectories). Images that fit into the left-hand
grid will be displayed immediately, but ALL images will be loaded in the background. In addition, the images will be
backed up to a subfolder in IMAGE_BACKUP_PATH (as raw data) and to directly into /tmp/ (for serving). Images are ordered
by the time they were taken.

Note: it is assumed that your images are stored under ~/Pictures (aka $HOME/Pictures for Unix-based systems).

Note: it is NOT recommended to host this app over the web -- only use it locally! The Dash framework (rightly) protects
      clients from being able to observe the server's folder structure, which makes this second step necessary. This
      program has very strong priveleges over the server's system, so only use it locally!

The left-hand side is a re-sizable grid of images: choose the size from the dropdown menu. You can zoom in on any image
(shown in the right-hand panel), by clicking on it, or by using the directional keys to navigate the blue square to it.

Each grid cell (td element) will have exactly one class name in {'grouped-off', 'grouped-on'}. There can be multiple cells
with grouped-on and it currently draws a red square around it. Together, the cells with a red border represent a group
of images. Those with the 'grouped-off' will (often) have no border, with one exception (i.e. having 'focus' - see below).
A cell can have 'grouped-on' or 'grouped-off' but not both. You make an image part of the group by clicking on it (It
must be on the image itself.) You can remove an image from a group by double clicking on it.

Additionally, one cell can have the special 'focus' class (currently blue border). This applies to one cell -
another cell will lose this when it is superceded. This class is achieved by clicking on a cell (that doesn't already
have it) or by moving the current highlighted cell around with the directional buttons / keys.

Note: there is a known bug when no cell has the focus and the user tries to 'complete the group' (causes error message
      but does not crash the program.)

Once you've chosen the images in the group, you should begin to label those images with whether you want to keep them
or not. Navigate to the image (directional keys or by clicking), then choose the 'Keep' or 'Delete' button to mark with
an additional thicker green or red border (respectively). For ease, you can also use the '=' or 's' key for keeping /
saving; and backspace or 'd' key for deletion.

Once you've marked all the grouped images up for keeping or deleting, check you're happy with the labels, then finalize
your choices by clicking 'Complete group'. There is currently no shortcut key for this operation. You must have marked
all images in the group, or the completion will not go through. If it works, those images will disappear from the grid
and new ones will appear. In the background, several things happen: 1) the meta data are added to a dictionary in memory
(and saved to a json file); 2) the meta data are inserted into the database and 3) most importantly, the images marked
for deletion ARE DELETED from the load folder (but not the backup folder). The main point of this program is to delete
bad duplicated images.

TODO: create an undo button that reverses the complete group operation.

Continue until ALL the images in that directory have been grouped and annotated before selecing and loading a new one.
"""

# TODO: KNOWN BUG: select image directory > Load directory > Resize 4x4 > Click: {(0,1), (0,2), (0,3)} > Resize 5x5 / 3x3
#                   > Click Backspace / +

# TODO: KNOWN BUG: the "empty image" (see config) can be selected and included in a group - this should not be allowed!


## Imports ##

import os
import json
import argparse

from datetime import date, datetime

import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

import flask

import utils
import config


## Constants ##

# Redefine some global variables
STATIC_IMAGE_ROUTE = config.STATIC_IMAGE_ROUTE
IMAGE_BACKUP_PATH = config.IMAGE_BACKUP_PATH
IMAGE_TYPES = config.IMAGE_TYPES

ROWS_MAX = config.ROWS_MAX
COLS_MAX = config.COLS_MAX
N_GRID = config.N_GRID

# Temporary location for serving files
TMP_DIR = '/tmp'

# Where to save metadata and backup images
META_DATA_FNAME = f'image_selector_session_{str(date.today())}_{int(datetime.timestamp(datetime.now()))}.json'
os.makedirs(IMAGE_BACKUP_PATH, exist_ok=True)
os.makedirs(os.path.join(IMAGE_BACKUP_PATH, '_session_data'), exist_ok=True)
META_DATA_FPATH = os.path.join(IMAGE_BACKUP_PATH, '_session_data', META_DATA_FNAME)

# Database details
DATABASE_NAME = 'deduplicate'
DATABASE_URI = f'postgresql:///{DATABASE_NAME}'
DATABASE_TABLE = 'duplicates'


# These define the inputs and outputs to callback function activate_deactivate_cells
ALL_TD_ID_OUTPUTS = [Output(f'grid-td-{i}-{j}', 'className') for i in range(ROWS_MAX) for j in range(COLS_MAX)]
ALL_BUTTONS_IDS = [Input(f'grid-button-{i}-{j}', 'n_clicks') for i in range(ROWS_MAX) for j in range(COLS_MAX)]
ALL_TD_ID_STATES = [State(f'grid-td-{i}-{j}', 'className') for i in range(ROWS_MAX) for j in range(COLS_MAX)]


## Main ##

# Copy default images to the TMP_DIR so they're available when the program starts
for fname in sorted(os.listdir(config.IMAGE_DIR)):
    static_image_path = utils.copy_image(fname, config.IMAGE_DIR, TMP_DIR, IMAGE_TYPES)


## Layout ##

app = dash.Dash(__name__)

# App's layout
app.layout = html.Div(
    children=[
        html.Div([
            html.Div(id='hidden-div', style={'display': 'none'}),
            html.H3("Image Selector"),
            dcc.Upload(
                    id='upload-image',
                    children=html.Div([
                        'Drag and Drop or ',
                        html.A('Select Images')
                    ]),
                    style={
                        'width': '50vw',
                        'height': '5vh',
                        'lineHeight': '40px',
                        'borderWidth': '1px',
                        'borderStyle': 'dashed',
                        'borderRadius': '5px',
                        'textAlign': 'center',
                    },
                    multiple=True
            ),
            html.Table(
                html.Tr([
                    html.Td(
                        dcc.Dropdown(
                            id='choose-image-path',
                            options=[{'label': config.IMAGE_DIR, 'value': 0}],
                            value=0,
                            style={'width': '40vw', 'height': '20%'}
                        ),
                    ),
                    html.Td(
                        dcc.Dropdown(
                            id='choose-grid-size',
                            options=[{'label': f'{k+1} x {k+1}', 'value': k+1} for k in range(ROWS_MAX) if k > 0],
                            value=2,
                            style={'width': '10vw',}
                        ),
                    ),
                ]),
            ),
            html.Table(
                html.Tr([
                    html.Td(
                        html.Button(
                            id='confirm-load-directory',
                            children='Load directory',
                            style={'width': '10vw', }
                        ),
                    ),
                    html.Td(
                        html.Button(
                            id='complete-group',
                            children='Complete group',
                            style={'width': '10vw', }
                        )
                    ),
                ]),
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
            ], style={'display': 'none', 'height': 'auto'}),
        ], style={'height': '17vh'}),
        html.Div([
            html.Table([
                html.Tr([
                    html.Td(
                        id='responsive-image-grid',
                        children=utils.create_image_grid(2, 2, config.IMAGE_SRCS),
                        style={'width': '50vw', 'height': 'auto', 'border-style': 'solid',}
                        ),
                    html.Td([
                        html.Div(
                            id='zoomed-image',
                            children=html.Img(src=config.IMAGE_SRCS[0], style=config.IMG_STYLE_ZOOM),
                            style={'width': '70%', 'display': 'block', 'margin-left': 'auto', 'margin-right': 'auto'}
                        )
                    ], style={'width': '50vw', 'height': '75vh', 'border-style': 'solid',}),
                ]),
            ]),
        ]),
        # Stores the list of image locations (sources) for a given directory - initially the default images are given
        # from the config (until the user loads a new image folder).
        dcc.Store(id='image-container', data=config.IMAGE_SRCS),
        # The underlying mask is a dict, where each entry contains data about a particular unique file directory where
        # images are stored. For each directory, there are three keys - 'position', 'keep' and 'filename' - where each
        # is a list of lists of (int / bool / str) representing image groups, in time order. This data structure can be
        # handled by the Store component (as it's serializable).
        dcc.Store(id='image-meta-data', data={'__ignore': {'position': [], 'keep': [], 'filename': []}}, storage_type='session'),
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
            options_list = utils.parse_image_upload(fname, IMAGE_TYPES)
            if len(options_list) > 0:
                return (options_list, 0)
            else:
                continue

    raise PreventUpdate


@app.callback(
    [
     Output('image-container', 'data'),
     Output('loaded-image-path', 'data'),
    ],
    [Input('confirm-load-directory', 'n_clicks')],
    [
     State('choose-image-path', 'value'),
     State('choose-image-path', 'options'),
    ]
)
def load_images(n, dropdown_value, dropdown_opts):
    """
    This callback triggers when "Load directory" (id: 'confirm-load-directory') is pressed. It causes three actions:
        1) The image is copied to TMP_DIR, from where is can be served
        2) If in use, it is also copied to a subfolder of IMAGE_BACKUP_PATH, for data storage
        3) The image is loaded into memory in the image-container Store

    These operations are only applied to image-like files (not videos), as defined by the extensions in IMAGE_TYPES

    Note: It fails to load if it finds that the backup folder already exists, as this implies the folder was worked before
    """

    # Prevent the update if 'confirm-load-directory' Button has never been clicked before
    context = dash.callback_context
    if context.triggered[0]['prop_id'] == 'confirm-load-directory.n_clicks':
        if context.triggered[0]['value'] is None:
            raise PreventUpdate

    opts = {d['value']: d['label'] for d in dropdown_opts}
    image_dir = opts[dropdown_value]

    image_list = []
    image_date = []
    try:

        # Need to copy to a corresponding subfolder in the IMAGE_BACKUP_PATH, which is backup_path
        backup_path, relative_path = utils.get_backup_path(image_dir, IMAGE_BACKUP_PATH)

        # Do not allow recopy, as it implies this folder has been worked before (may cause integrity errors)
        if image_dir != config.IMAGE_DIR and backup_path.rstrip('/') != IMAGE_BACKUP_PATH and not program_args.demo:
            os.makedirs(backup_path, exist_ok=False)

        for fname in sorted(os.listdir(image_dir)):

            # Copy the image to various location, but only if it is an image!

            # Copy to the TMP_DIR from where the image can be served (roate on the fly if necessary)
            static_image_path = utils.copy_image(fname, image_dir, TMP_DIR, IMAGE_TYPES)
            if static_image_path is not None:
                img_datetime = utils.get_image_taken_date(image_dir, fname)
                image_date.append(img_datetime)
                image_list.append(static_image_path)

            # Copy image to appropriate subdirectory in IMAGE_BACKUP_PATH
            if not program_args.demo:
                _ = utils.copy_image(fname, image_dir, os.path.join(IMAGE_BACKUP_PATH, relative_path), IMAGE_TYPES)

        # Sort the image list by date, earliest to latest
        imgs_dates = list(zip(image_list, image_date))
        imgs_dates_sorted = sorted(imgs_dates, key=lambda x: x[1])
        image_list = [img for img, date in imgs_dates_sorted]

        # Pad the image container with empty images if necessary
        while len(image_list) < ROWS_MAX*COLS_MAX:
            image_list.append(config.IMG_PATH)

    except FileNotFoundError:
        return [], ['__ignore']

    except FileExistsError:
        print(f'This folder has been worked on previously: {image_dir}')
        raise

    # Return a 2-tuple: 0) is a list of image locations; 1) is a single-entry list containing the loaded path
    return image_list, [image_dir]


@app.callback(
    Output('image-meta-data', 'data'),
    [Input('complete-group', 'n_clicks')],
    [
     State('choose-grid-size', 'value'),
     State('choose-grid-size', 'value'),
     State('image-container', 'data'),
     State('image-meta-data', 'data'),
     State('loaded-image-path', 'data'),
    ] + ALL_TD_ID_STATES
)
def complete_image_group(n_group, n_rows, n_cols, image_list, image_data, image_path, *args):
    """
    Updates the image_mask by appending relevant info to it. This happens when either 'Complete group' button is clicked
    or the visible grid size is updated. We also delete the unwanted files when a valid completion is made (although
    those files are backed up in the IMAGE_BACKUP_PATH) and send the meta data to the specified database: see
    DATABASE_NAME and DATABASE_TABLE.

    Args:
        n_group = int, number of times the complete-group button is clicked (Input)
        n_rows = int, current number of rows in the grid (Input: indicates resizing)
        n_cols = int, current number of columns in the grid (Input: indicates resizing)
        image_list = list, containing a list of file paths where the valid images for the chosen directory are stored
        image_data = dict, with keys 'position' (for visible grid locations) and 'keep' (whether to keep / remove the image) (State)
                     Note: each keys contains a list, of lists of ints, a sequence of data about each completed image group
        image_path = str, the filepath where the images in image-container were loaded from
        *args = positional arguments are States (given by the grid-Tds for knowing the class names)

    Returns:
        updated version of the image mask (if any new group was legitimately completed)
    """

    # Unpack the single-element list
    image_path = image_path[0]
    if image_path not in image_data:
        image_data[image_path] = {'position': [], 'keep': [], 'filename': []}

    # The image_list (from image-container) contains ALL images in this directory, whereas as the list positions below
    # will refer to the reduced masked list. In order to obtain consistent filenames, we need to apply the previous version
    # of the mask to the image_list (version prior to this completion).
    all_img_filenames = [src.split('/')[-1] for src in image_list]
    prev_mask = utils.create_flat_mask(image_data[image_path]['position'], len(all_img_filenames))
    assert len(all_img_filenames) == len(prev_mask), "Mask should correspond 1-to-1 with filenames in image-container"
    unmasked_img_filenames = [fname for i, fname in enumerate(all_img_filenames) if not prev_mask[i]]

    # Extract the image group and their meta data (filename and keep / delete)
    # Note: Need to adjust for the disconnect between the visible grid size (n_rows * n_cols) and the virtual grid size
    #       (ROWS_MAX * COLS_MAX)
    grouped_cell_positions = []
    grouped_cell_keeps = []
    grouped_filenames = []
    grouped_date_taken = []
    delete_filenames = []
    for i in range(n_rows):
        for j in range(n_cols):
            # Get the class list (str) for this cell
            my_class = args[j + i*COLS_MAX]
            # Position on the visible grid (mapped to list index)
            list_pos = j + i*n_rows
            # As the number of unmasked images shrinks (when the user completes a group, those images disappear), the
            # list position will eventually run out of the valid indices. As there's no valid metadata in this region
            # we skip over it
            if list_pos >= len(unmasked_img_filenames):
                continue
            image_filename = unmasked_img_filenames[list_pos]

            # Check if selected to be in the group, add position if on
            if 'grouped-on' in my_class:
                grouped_cell_positions.append(list_pos)
                grouped_filenames.append(image_filename)
                grouped_date_taken.append(utils.get_image_taken_date(image_path, image_filename, default_date=None))

            # Check for keep / delete status
            # Note: important not to append if keep/delete status not yet specified
            if 'keep' in my_class:
                grouped_cell_keeps.append(True)
            elif 'delete' in my_class:
                grouped_cell_keeps.append(False)
                delete_filenames.append(image_filename)
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
        image_data[image_path]['filename'].append(grouped_filenames)

        if not program_args.demo:
            # Save all meta data in JSON format on disk
            with open(META_DATA_FPATH, 'w') as j:
                json.dump(image_data, j)

            # Save data for the new group in the specified database
            utils.send_to_database(
                    DATABASE_URI,
                    DATABASE_TABLE,
                    image_path,
                    grouped_filenames,
                    grouped_cell_keeps,
                    grouped_date_taken,
            )

            # Delete the discarded images (can be restored manually from IMAGE_BACKUP_PATH)
            for fname in delete_filenames:
                os.remove(os.path.join(image_path, fname))

    return image_data


@app.callback(
    Output('responsive-image-grid', 'children'),
    [Input('choose-grid-size', 'value'),
     Input('choose-grid-size', 'value'),
     Input('image-container', 'data'),
     Input('image-meta-data', 'data'),
    ],
    [State('loaded-image-path', 'data'),]
)
def create_reactive_image_grid(n_row, n_col, image_list, image_data, image_path):
    """
    Get an HTML element corresponding to the responsive image grid.

    Args:
        n_rows = int, current number of rows in the grid (Input: indicates resizing)
        n_cols = int, current number of columns in the grid (Input: indicates resizing)
        image_list = list, containing a list of file paths where the valid images for the chosen directory are stored
        image_data = dict, with keys 'position' (for visible grid locations) and 'keep' (whether to keep / remove the image) (State)
                     Note: each keys contains a list, of lists of ints, a sequence of data about each completed image group
        image_path = list, of 1 str, the filepath where the images in image-container were loaded from

    Returns: html.Div element (containing the grid of images) that can update the responsive-image-grid element
    """

    image_path = image_path[0]
    # If it doesn't already exist, add an entry (dict) for this image path into the data dictionary
    if image_path not in image_data:
        image_data[image_path] = {'position': [], 'keep': [], 'filename': []}

    # Reduce the image_list by removing the masked images (so they can no longer appear in the image grid / image zoom)
    flat_mask = utils.create_flat_mask(image_data[image_path]['position'], len(image_list))
    image_list = [img_src for i, img_src in enumerate(image_list) if not flat_mask[i]]

    return utils.create_image_grid(n_row, n_col, image_list)


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
         Input('image-container', 'data'),
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
        image_list = list, of str, specifying where the image files are stored
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

    # Unpack the single-element list
    image_path = image_path[0]
    if image_path not in image_data:
        image_data[image_path] = {'position': [], 'keep': [], 'filename': []}

    # Reduce the image_list by removing the masked images (so they can no longer appear in the image grid / image zoom)
    flat_mask = utils.create_flat_mask(image_data[image_path]['position'], len(image_list))
    image_list = [img for i, img in enumerate(image_list) if not flat_mask[i]]

    # Find the button that triggered this callback (if any)
    context = dash.callback_context
    if not context.triggered:
        class_names = ['grouped-off focus' if i+j == 0 else 'grouped-off' for i in range(ROWS_MAX) for j in range(COLS_MAX)]
        zoomed_img = html.Img(src=image_list[0], style=config.IMG_STYLE_ZOOM)
        return class_names + [zoomed_img]
    else:
        button_id = context.triggered[0]['prop_id'].split('.')[0]


    # Reset the grid
    # Note: image-container is not really a button, but fired when confirm-load-directory is pressed (we need the list
    #       inside image-container in order to populate the grid)
    if button_id in ['choose-grid-size', 'image-container', 'image-meta-data', 'loaded-image-path']:
        return utils.resize_grid_pressed(image_list)

    # Toggle the state of this button (as it was pressed)
    elif 'grid-button-' in button_id:
        return utils.image_cell_pressed(button_id, n_cols, image_list, *args)

    # Harder case: move focus in a particular direction
    elif 'move-' in button_id:
        return utils.direction_key_pressed(button_id, n_rows, n_cols, image_list, *args)

    elif button_id in ['keep-button', 'delete-button']:
        return utils.keep_delete_pressed(button_id, n_rows, n_cols, image_list, *args)

    else:
        raise ValueError('Unrecognized button ID: %s' % str(button_id))


@app.server.route('{}<image_path>'.format(STATIC_IMAGE_ROUTE))
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
    parser = argparse.ArgumentParser(
        description='Dash app for grouping images and choosing the best per-group images. ' +\
                    'You also choose whether to delete any images in that group.'
    )
    parser.add_argument('--demo', action='store_true', default=False,
                        help='for demonstration purposes only - do not perform any file or database operations'
                        )

    global program_args
    program_args = parser.parse_args()

    app.run_server(debug=True)
