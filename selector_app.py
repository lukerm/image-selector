"""
Dash app for grouping images and choosing the best per-group images. You also choose whether to delete any images in
that group.

Images can be loaded from a directory by clicking on the 'Select images' box and navigating to the correct folder. You
need only click on one image, then 'Open'. (Alternatively, drag and drop an image from the folder of interest into the
box.) Due to a technicality, you must select the correct directory from the dropdown menu, then click 'Load directory'.
This will load all valid image files from that directory (but not subdirectories). Images that fit into the left-hand
grid will be displayed immediately, but ALL images will be loaded in the background. In addition, the images will be
backed up to a subfolder in IMAGE_BACKUP_PATH (as raw data, see config) and to directly into /tmp/ (for serving).
Images are ordered by the time they were taken (those without those metadata come last).

Note: it is assumed that your images are stored under ~/Pictures (aka $HOME/Pictures for Unix-based systems).

Note: it is NOT recommended to host this app over the web -- only use it locally! The Dash framework (rightly) protects
      clients from being able to observe the server's folder structure, which makes this second step necessary. This
      program has very strong priveleges over the server's system, so only use it locally!

The left-hand side is a re-sizable grid of images: choose the size from the dropdown menu. You can zoom in on any image
(shown in the right-hand panel), by clicking on it, or by using the directional keys to navigate the blue square to it.

Each grid cell (td element) will have exactly one class name in {'grouped-off', 'grouped-on'}. There can be multiple cells
with grouped-on and it currently draws a red square around it. Together, the cells with a red border represent a group
of images. Those that are 'grouped-off' will (often) have no border, with one exception (i.e. having 'focus' - see below).
A cell can have 'grouped-on' or 'grouped-off' but not both. You make an image part of the group by clicking on it. (It
must be on the image itself.) You can remove an image from a group by double clicking on it.
Note: you can also use the 'g' button to toggle grouped on / off when a cell has focus.

Additionally, one cell can have the special 'focus' class (currently blue border). This applies to one cell -
another cell will lose this when it is superceded. This class is achieved by clicking on a cell (that doesn't already
have it) or by moving the current highlighted cell around with the directional buttons / keys (see Shortcuts).

Once you've chosen the images in the group, you should begin to label those images with whether you want to keep them
or not. Navigate to the image (directional keys or by clicking), then choose to 'keep' it by pressing the '=' or 's'
key or 'delete' it by pressing backspace or 'd' key. Choosing either one of these will add an additional thicker green
or red border (respectively).
Note: there used to be visible buttons for keep / delete options, but now they are just virtual to enable shortcuts.

Once you've marked all the grouped images up for keeping or deleting, check you're happy with the labels, then finalize
your choices by clicking 'Complete group'. There is currently no shortcut key for this operation. You must have marked
all images in the group, or the completion will not go through. If it works, those images will disappear from the grid
and new ones will appear. In the background, several things happen: 1) the meta data are added to a dictionary in memory
(and saved to a json file); 2) the meta data are inserted into the database and 3) most importantly, the images marked
for deletion ARE DELETED from the load folder (but not the backup folder). The main point of this program is to delete
bad duplicated images.

There is an Undo button that will reverse your last completed group, by restoring the images on the grid and your local
file system, and removing the grouped data from the database (if applicable). You can undo as many grouping operations
as you like.

Continue until ALL the images in that directory have been grouped and annotated before selecing and loading a new one.
"""

# TODO: KNOWN BUG: select image directory > Load directory > Resize 4x4 > Click: {(0,1), (0,2), (0,3)} > Resize 5x5 / 3x3
#                   > Click Backspace / +

# TODO: KNOWN BUG: the "empty image" (see config) can be selected and included in a group - this should not be allowed!
# TODO: KNOWN BUG: you cannot traverse over empty padding images, which might be annoying.


## Imports ##

import argparse
import os
import re
import shutil

from datetime import date

import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
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
EMPTY_IMAGE = config.EMPTY_IMAGE

ROWS_MAX = config.ROWS_MAX
COLS_MAX = config.COLS_MAX
N_GRID = config.N_GRID

PREGROUP_FUNCTION = config.PREGROUP_FUNCTION

# Temporary location for serving files
TMP_DIR = '/tmp'


# These define the inputs and outputs to callback function activate_deactivate_cells
ALL_TD_ID_OUTPUTS = [Output(f'grid-td-{i}-{j}', 'className') for i in range(ROWS_MAX) for j in range(COLS_MAX)]
ALL_BUTTONS_IDS = [Input(f'grid-button-{i}-{j}', 'n_clicks') for i in range(ROWS_MAX) for j in range(COLS_MAX)]
ALL_TD_ID_STATES = [State(f'grid-td-{i}-{j}', 'className') for i in range(ROWS_MAX) for j in range(COLS_MAX)]


## Main ##

# Copy default images to the TMP_DIR so they're available when the program starts
for fname in sorted(os.listdir(config.IMAGE_DIR)):
    static_image_path = utils.copy_image(fname, config.IMAGE_DIR, TMP_DIR, IMAGE_TYPES, STATIC_IMAGE_ROUTE)


## Layout ##

app = dash.Dash(__name__)

# App's layout
app.layout = html.Div(
    children=[
        html.Div([
            html.Div(id='hidden-div', style={'display': 'none'}),
            html.H3("Image Selector"),
            dbc.Modal([
                dbc.ModalHeader("Shortcuts"),
                dbc.ModalBody([
                    html.Table([
                        html.Tr([
                            html.Td("←/→", style={'width': '150px'}),
                            html.Td("\t\t\t\t\t\t"),
                            html.Td("Move focus left / right")
                        ]),
                        html.Tr([
                            html.Td("↑/↓"),
                            html.Td("\t\t\t\t\t\t"),
                            html.Td("Move focus up / down")
                        ]),
                        html.Tr([
                            html.Td("Q,W,E,R,T,Y"),
                            html.Td("\t\t\t\t\t\t"),
                            html.Td("Move focus 2,3,4,5,6,7 cells left")
                        ]),
                        html.Tr([
                            html.Td("q,w,e,r,t,y"),
                            html.Td("\t\t\t\t\t\t"),
                            html.Td("Move focus 2,3,4,5,6,7 cells right")
                        ]),
                        html.Tr([
                            html.Td("g"),
                            html.Td("\t\t\t\t\t\t"),
                            html.Td("Add or remove image from group")
                        ]),
                        html.Tr([
                            html.Td("s / ="),
                            html.Td("\t\t\t\t\t\t"),
                            html.Td("Mark image for keeping")
                        ]),
                        html.Tr([
                            html.Td("d / ⌫"),
                            html.Td("\t\t\t\t\t\t"),
                            html.Td("Mark image for deletion")
                        ]),
                        html.Tr([
                            html.Td("Shift + c"),
                            html.Td("\t\t\t\t\t\t"),
                            html.Td("Complete (save) image group")
                        ]),
                        html.Tr([
                            html.Td("Shift + z"),
                            html.Td("\t\t\t\t\t\t"),
                            html.Td("Undo last group")
                        ]),
                        html.Tr([
                            html.Td("0 / Shift + a"),
                            html.Td("\t\t\t\t\t\t"),
                            html.Td("Select all grid cells")
                        ]),
                        html.Tr([
                            html.Td("1, ..., N, ..., 9"),
                            html.Td("\t\t\t\t\t\t"),
                            html.Td("Select grid cells in first N rows")
                        ]),
                    ]),
                ]),
                dbc.ModalFooter(
                    dbc.Button("Close", id="hide-shortcuts", className="ml-auto")
                ),
            ], id="modal"),
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
                            value=4,
                            style={'width': '9.8vw',}
                        ),
                    ),
                ]),
            ),
            html.Table(
                html.Tr([
                    html.Td(
                        html.Button(
                            id='confirm-load-directory',
                            children='Load images',
                            style={'width': '8vw', }
                        ),
                    ),
                    html.Td(
                        html.Button(
                            id='complete-group',
                            children='Save group',
                            style={'width': '8vw', }
                        )
                    ),
                    html.Td(
                        html.Button(
                            id='undo-button',
                            children='Undo',
                            style={'width': '8vw', }
                        )
                    ),
                    html.Td([
                        html.Button(
                            id='view-shortcuts',
                            children='Shortcuts',
                            style={'width': '8vw', }
                        )
                    ]),
                    html.Td([
                        html.Div([dbc.Progress(
                            id='progress_bar',
                            value=0,
                            style={'width': '17.2vw', }
                        )])
                    ]),
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
                html.Button(id='group-button', children='Group'),
            ], style={'display': 'none', 'height': 'auto'}),
        ], style={'height': '17vh'}),
        html.Div([
            html.Table([
                html.Tr([
                    html.Td(
                        id='responsive-image-grid',
                        children=utils.create_image_grid(
                            n_row=4, n_col=4,
                            rows_max=ROWS_MAX, cols_max=COLS_MAX,
                            image_list=config.IMAGE_SRCS, empty_img_path=config.EMPTY_IMG_PATH,
                            pregroup_func_name=PREGROUP_FUNCTION,
                        ),
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
        # Hidden buttons (for shortcuts)
        html.Div([
            html.Td([
                html.Button(
                    id='select-row-upto-1-button',
                    style={'width': '10vw', }
                )
            ]),
            html.Td([
                html.Button(
                    id='select-row-upto-2-button',
                    style={'width': '10vw', }
                )
            ]),
            html.Td([
                html.Button(
                    id='select-row-upto-3-button',
                    style={'width': '10vw', }
                )
            ]),
            html.Td([
                html.Button(
                    id='select-row-upto-4-button',
                    style={'width': '10vw', }
                )
            ]),
            html.Td([
                html.Button(
                    id='select-row-upto-5-button',
                    style={'width': '10vw', }
                )
            ]),
            html.Td([
                html.Button(
                    id='select-row-upto-6-button',
                    style={'width': '10vw', }
                )
            ]),
            html.Td([
                html.Button(
                    id='select-row-upto-7-button',
                    style={'width': '10vw', }
                )
            ]),
            html.Td([
                html.Button(
                    id='select-row-upto-8-button',
                    style={'width': '10vw', }
                )
            ]),
            html.Td([
                html.Button(
                    id='select-row-upto-9-button',
                    style={'width': '10vw', }
                )
            ]),
            # This is basically for selecting all rows
            html.Td([
                html.Button(
                    id='select-row-upto-1000-button',
                    style={'width': '10vw', }
                )
            ]),
            # Jump right buttons
            html.Td([
                html.Button(id='jump-right-2-cells-button', style={'width': '10vw', })
            ]),
            html.Td([
                html.Button(id='jump-right-3-cells-button', style={'width': '10vw', })
            ]),
            html.Td([
                html.Button(id='jump-right-4-cells-button', style={'width': '10vw', })
            ]),
            html.Td([
                html.Button(id='jump-right-5-cells-button', style={'width': '10vw', })
            ]),
            html.Td([
                html.Button(id='jump-right-6-cells-button', style={'width': '10vw', })
            ]),
            html.Td([
                html.Button(id='jump-right-7-cells-button', style={'width': '10vw', })
            ]),
            # Jump left buttons
            html.Td([
                html.Button(id='jump-left-2-cells-button', style={'width': '10vw', })
            ]),
            html.Td([
                html.Button(id='jump-left-3-cells-button', style={'width': '10vw', })
            ]),
            html.Td([
                html.Button(id='jump-left-4-cells-button', style={'width': '10vw', })
            ]),
            html.Td([
                html.Button(id='jump-left-5-cells-button', style={'width': '10vw', })
            ]),
            html.Td([
                html.Button(id='jump-left-6-cells-button', style={'width': '10vw', })
            ]),
            html.Td([
                html.Button(id='jump-left-7-cells-button', style={'width': '10vw', })
            ]),
        ], style={'display': 'none'}),
        # Store the number of images
        dcc.Store(id='n_images', data=[config.N_IMG_SRCS]),
        # Stores the list of image locations (sources) for a given directory - initially the default images are given
        # from the config (until the user loads a new image folder).
        dcc.Store(id='image-container', data=config.IMAGE_SRCS),
        # Corresponding list of image sizes
        dcc.Store(id='image-size-container', data=config.IMAGE_SIZES),
        # The underlying mask is a dict, where each entry contains data about a particular unique file directory where
        # images are stored. For each directory, there are three keys - 'position', 'keep' and 'filename' - where each
        # is a list of lists of (int / bool / str) representing image groups, in time order. This data structure can be
        # handled by the Store component (as it's serializable).
        dcc.Store(id='image-meta-data', data={'__ignore': {'position': [], 'keep': [], 'filename': []}}, storage_type='session'),
        # For storing the image path WHEN THE confirm-load-directory IS CLICKED (the label in choose-image-path may
        # change without their being a new upload, so we need to record this value)
        dcc.Store(id='loaded-image-path', data=['__ignore'], storage_type='session'),
        # store the last cell with focus
        dcc.Store(id='cell_last_clicked', data=None, storage_type='session'),
    ]
)


## Callbacks ##

@app.callback(
    Output("modal", "is_open"),
    [Input("view-shortcuts", "n_clicks"), Input("hide-shortcuts", "n_clicks")],
    [State("modal", "is_open")],
)
def toggle_shortcut_popup(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open


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
     Output('image-size-container', 'data'),
     Output('loaded-image-path', 'data'),
     Output('n_images', 'data'),
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
    try:

        # Need to copy to a corresponding subfolder in the IMAGE_BACKUP_PATH, which is backup_path
        backup_path, relative_path = utils.get_backup_path(image_dir, IMAGE_BACKUP_PATH)

        # Do not allow recopy, as it implies this folder has been worked before (may cause integrity errors)
        if image_dir != config.IMAGE_DIR and backup_path.rstrip('/') != IMAGE_BACKUP_PATH and not program_args.demo:
            os.makedirs(backup_path, exist_ok=False)

        for fname in sorted(os.listdir(image_dir)):

            # Copy the image to various location, but only if it is an image!

            # Copy to the TMP_DIR from where the image can be served (rotate on the fly if necessary)
            # Note: if the return value of copy_image is None, then it's not an image file
            static_image_path = utils.copy_image(fname, image_dir, TMP_DIR, IMAGE_TYPES, STATIC_IMAGE_ROUTE)
            if static_image_path is not None:
                image_list.append(static_image_path)

                # Copy image to appropriate subdirectory in IMAGE_BACKUP_PATH
                if not program_args.demo:
                    shutil.copyfile(os.path.join(image_dir, fname), os.path.join(IMAGE_BACKUP_PATH, relative_path, fname))
                    #_ = utils.copy_image(fname, image_dir, os.path.join(IMAGE_BACKUP_PATH, relative_path), IMAGE_TYPES)

        # Sort the image list by date, earliest to latest
        image_list = utils.sort_images_by_datetime(image_list, image_dir=image_dir)
        image_size_list = [utils.readable_filesize(os.path.getsize(os.path.join(image_dir, os.path.split(image_filename)[-1]))) for image_filename in image_list]
        import re
        from datetime import datetime
        date_re = re.compile(r'_([0-9]{8})_')
        image_size_list = [f'{datetime.strptime(date_re.search(img).group(1), "%Y%m%d").date()} ({image_size_list[i]})' if date_re.search(img) else image_size_list[i] for i, img in enumerate(image_list)]
        assert len(image_list) == len(image_size_list), f"image_list = {len(image_list)}; image_size_list = {len(image_size_list)}"
        n_images = len(image_list)

        # Pad the image container with empty images if necessary
        while len(image_list) < ROWS_MAX*COLS_MAX:
            image_list.append(config.EMPTY_IMG_PATH)
            image_size_list.append("0KB")

    except FileNotFoundError:
        return [], [], ['__ignore'], [0]

    except FileExistsError:
        print(f'This folder has been worked on previously: {image_dir}')
        raise

    # Return a 4-tuple: 0) is a list of image locations; 1) list of image sizes; 2) is a single-entry list containing the loaded path, 2) number of images loaded
    return image_list, image_size_list, [image_dir], [n_images]


@app.callback(
    [Output('image-meta-data', 'data'), Output('progress_bar', 'value')],
    [Input('complete-group', 'n_clicks'), Input('undo-button', 'n_clicks')],
    [
     State('choose-grid-size', 'value'),
     State('choose-grid-size', 'value'),
     State('image-container', 'data'),
     State('image-meta-data', 'data'),
     State('loaded-image-path', 'data'),
     State('n_images', 'data'),
    ] + ALL_TD_ID_STATES
)
def complete_or_undo_image_group(n_group, n_undo, n_rows, n_cols, image_list, image_data, image_path, n_images, *args):
    """
    Updates the image_mask by appending / deleting relevant info to / from it. This happens when either 'Complete group'
    or Undo' button is clicked. We also delete (resp. recreate) the unwanted files when a valid completion (resp. undo)
    is made (although those files are always backed up in the IMAGE_BACKUP_PATH) and send (resp. delete)the meta data to
    the specified database: see DATABASE_NAME and DATABASE_TABLE (in config.py).

    Args:
        n_group = int, number of times the complete-group button is clicked (Input)
        n_undo = int, number of times the undo-button is clicked (Input)
        n_rows = int, current number of rows in the grid (Input: indicates resizing)
        n_cols = int, current number of columns in the grid (Input: indicates resizing)
        image_list = list, containing a list of file paths where the valid images for the chosen directory are stored
        image_data = dict, with keys 'position' (for visible grid locations) and 'keep' (whether to keep / remove the image) (State)
                     Note: each keys contains a list, of lists of ints, a sequence of data about each completed image group
        image_path = str, the filepath where the images in image-container were loaded from
        n_images = int, number of images originally loaded in the given directory
        *args = positional arguments are States (given by the grid-Tds for knowing the class names)

    Returns:
        0) updated version of the image mask (if any new group was legitimately completed)
        1) Percentage of images completed so far
    """

    # Find the button that triggered this callback (if any)
    # Note: also prevent this button from firing when the app first loads (causing the first image to be classified)
    context = dash.callback_context
    button_id = context.triggered[0]['prop_id'].split('.')[0]
    if button_id == 'complete-group':
        mode = 'complete'
    elif button_id == 'undo-button':
        mode = 'undo'
    else:
        PreventUpdate
        return image_data, [0]

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

    if mode == 'complete':

        # Extract the image group and their meta data (filename and keep / delete)
        # Note: Need to adjust for the disconnect between the visible grid size (n_rows * n_cols) and the virtual grid size
        #       (ROWS_MAX * COLS_MAX)
        focus_position = None
        focus_filename = None
        focus_date_taken = None
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

                if 'focus' in my_class:
                    focus_position = list_pos
                    focus_filename = image_filename
                    focus_date_taken = utils.get_image_taken_date(image_path, image_filename, default_date=None)

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

                utils.record_grouped_data(
                    image_data=image_data, image_path=image_path,
                    filename_list=grouped_filenames, keep_list=grouped_cell_keeps, date_taken_list=grouped_date_taken,
                    image_backup_path=IMAGE_BACKUP_PATH,
                    meta_data_fpath=config.META_DATA_FPATH,
                    database_uri=config.DATABASE_URI, database_table=config.DATABASE_TABLE
                )


        # This is a small trick for quickly saving (keeping) the focussed image (provided none have been grouped)
        elif len(grouped_cell_positions) == 0 and focus_position is not None and focus_filename is not None:

            image_data[image_path]['position'].append([focus_position])
            image_data[image_path]['keep'].append([True])
            image_data[image_path]['filename'].append([focus_filename])

            if not program_args.demo:

                utils.record_grouped_data(
                    image_data=image_data, image_path=image_path,
                    filename_list=[focus_filename], keep_list=[True], date_taken_list=[focus_date_taken],
                    image_backup_path=IMAGE_BACKUP_PATH,
                    meta_data_fpath=config.META_DATA_FPATH,
                    database_uri=config.DATABASE_URI, database_table=config.DATABASE_TABLE
                )

        else:
            raise PreventUpdate

        # Note: n_images is a single-entry list
        pct_complete = utils.calc_percentage_complete(image_data[image_path]['position'], n_images[0])
        return image_data, pct_complete

    elif mode == 'undo':

        # Remove the last entry from each list in the metadata (corresponding to the last group)
        try:
            _ = image_data[image_path]['position'].pop()
            _ = image_data[image_path]['keep'].pop()
            filenames_undo = image_data[image_path]['filename'].pop()

            if not program_args.demo:
                utils.undo_last_group(
                    image_data=image_data,
                    image_path=image_path,
                    filename_list=filenames_undo,
                    image_backup_path=IMAGE_BACKUP_PATH,
                    meta_data_fpath=config.META_DATA_FPATH,
                    database_uri=config.DATABASE_URI,
                    database_table=config.DATABASE_TABLE,
                )

        # In case the lists are already empty
        except IndexError:
            pass

        # Note: n_images is a single-entry list
        pct_complete = utils.calc_percentage_complete(image_data[image_path]['position'], n_images[0])
        return image_data, pct_complete

    else:
        raise ValueError(f'Unknown mode: {mode}')


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

    return utils.create_image_grid(
        n_row=n_row, n_col=n_col,
        rows_max=ROWS_MAX, cols_max=COLS_MAX,
        image_list=image_list, empty_img_path=config.EMPTY_IMG_PATH,
        pregroup_func_name=PREGROUP_FUNCTION,
    )


@app.callback(
    ALL_TD_ID_OUTPUTS + [Output('zoomed-image', 'children'), Output('cell_last_clicked', 'data')],
    [
         Input('choose-grid-size', 'value'),
         Input('choose-grid-size', 'value'),
         Input('move-left', 'n_clicks'),
         Input('move-right', 'n_clicks'),
         Input('move-up', 'n_clicks'),
         Input('move-down', 'n_clicks'),
         Input('select-row-upto-1-button', 'n_clicks'),
         Input('select-row-upto-2-button', 'n_clicks'),
         Input('select-row-upto-3-button', 'n_clicks'),
         Input('select-row-upto-4-button', 'n_clicks'),
         Input('select-row-upto-5-button', 'n_clicks'),
         Input('select-row-upto-6-button', 'n_clicks'),
         Input('select-row-upto-7-button', 'n_clicks'),
         Input('select-row-upto-8-button', 'n_clicks'),
         Input('select-row-upto-9-button', 'n_clicks'),
         Input('select-row-upto-1000-button', 'n_clicks'),
         Input('jump-right-2-cells-button', 'n_clicks'),
         Input('jump-right-3-cells-button', 'n_clicks'),
         Input('jump-right-4-cells-button', 'n_clicks'),
         Input('jump-right-5-cells-button', 'n_clicks'),
         Input('jump-right-6-cells-button', 'n_clicks'),
         Input('jump-right-7-cells-button', 'n_clicks'),
         Input('jump-left-2-cells-button', 'n_clicks'),
         Input('jump-left-3-cells-button', 'n_clicks'),
         Input('jump-left-4-cells-button', 'n_clicks'),
         Input('jump-left-5-cells-button', 'n_clicks'),
         Input('jump-left-6-cells-button', 'n_clicks'),
         Input('jump-left-7-cells-button', 'n_clicks'),
         Input('keep-button', 'n_clicks'),
         Input('delete-button', 'n_clicks'),
         Input('group-button', 'n_clicks'),
         Input('image-container', 'data'),
         Input('image-size-container', 'data'),
         Input('image-meta-data', 'data'),
         Input('loaded-image-path', 'data'),
    ] + ALL_BUTTONS_IDS,
    ALL_TD_ID_STATES + [State('cell_last_clicked', 'data')]
)
def activate_deactivate_cells(
        n_rows, n_cols,
        n_left, n_right, n_up, n_down,
        n_row1, n_row2, n_row3, n_row4, n_row5, n_row6, n_row7, n_row8, n_row9, n_row1000,
        n_jump_r2, n_jump_r3, n_jump_r4, n_jump_r5, n_jump_r6, n_jump_r7,
        n_jump_l2, n_jump_l3, n_jump_l4, n_jump_l5, n_jump_l6, n_jump_l7,
        n_keep, n_delete, n_group,
        image_list, image_size_list, image_data, image_path, *args
    ):
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
        n_row1,..9,1000 = int, number of clicks on the 'select row *' button (indicates shortcut to select many rows)
        n_jump_r1,..7 = int, number of clicks on the 'jump right *' button (indicates shortcut to jump several cells)
        n_jump_l1,..7 = int, number of clicks on the 'jump left *' button (indicates shortcut to jump several cells)
        n_keep = int, number of clicks on the 'keep-button' button
        n_delete = int, number of clicks on the 'delete-button' button
        n_group = int, number of clicks on the 'group-button' button
        image_list = list, of str, specifying where the image files are stored
        image_size_list = list, of str, specifying where the image sizes
        image_data = dict, of dict of lists of ints, a sequence of metadata about completed image groups
        image_path = str, the filepath where the images in image-container were loaded from

        *args = positional arguments split into about two equal halves (actually length 2 x N_GRID + 1):
            0) args[:N_GRID] are Inputs (activated by the grid-Buttons)
            1) args[N_GRID:-1] are States (indicating state of the grid-Tds)
            Both are in row-major order (for i in rows: for j in cols: ... )
            2) args[-1] is a tuple representing the last clicked cell

    Returns: a list of new classNames for all the grid cells plus
              - one extra element for the Image that was last clicked (zoomed image)
              - one extra element representing the cell that was last clicked (in focus)
    """

    # Unpack the single-element list
    image_path = image_path[0]
    if image_path not in image_data:
        image_data[image_path] = {'position': [], 'keep': [], 'filename': []}

    # Reduce the image_list by removing the masked images (so they can no longer appear in the image grid / image zoom)
    flat_mask = utils.create_flat_mask(image_data[image_path]['position'], len(image_list))
    image_list = [img for i, img in enumerate(image_list) if not flat_mask[i]]
    image_size_list = [size for i, size in enumerate(image_size_list) if not flat_mask[i]]

    # Find the button that triggered this callback (if any)
    context = dash.callback_context
    if not context.triggered:
        return utils.resize_grid_pressed(
            image_list=image_list,
            rows_max=ROWS_MAX, cols_max=COLS_MAX,
            empty_image=EMPTY_IMAGE, zoom_img_style=config.IMG_STYLE_ZOOM
        )
    else:
        button_id = context.triggered[0]['prop_id'].split('.')[0]


    # Reset the grid
    # Note: image-container is not really a button, but fired when confirm-load-directory is pressed (we need the list
    #       inside image-container in order to populate the grid)
    if button_id in ['choose-grid-size', 'image-container',  'image-size-container', 'image-meta-data', 'loaded-image-path']:
        return utils.resize_grid_pressed(
            image_list=image_list, image_size_list=image_size_list,
            rows_max=ROWS_MAX, cols_max=COLS_MAX,
            empty_image=EMPTY_IMAGE, zoom_img_style=config.IMG_STYLE_ZOOM,
            n_rows=n_rows, n_cols=n_cols,
            pregroup_func_name='DAILY',
        )

    # Toggle the state of this button (as it was pressed)
    elif 'grid-button-' in button_id:
        current_classes, zoomed_img, cell_last_clicked = utils.image_cell_pressed(
            button_id, n_cols, COLS_MAX, ROWS_MAX*COLS_MAX, image_list, image_size_list, EMPTY_IMAGE, config.IMG_STYLE_ZOOM, *args
        )
        return current_classes + [zoomed_img, cell_last_clicked]

    # Toggle the grouping state of all cells in the first rows of the grid
    elif 'select-row-upto-' in button_id:
        n_rows = int(re.findall('select-row-upto-([0-9]+)-button', button_id)[0])
        current_classes, zoomed_img, cell_last_clicked = utils.toggle_group_in_first_n_rows(
            n_rows, n_cols, ROWS_MAX, COLS_MAX, image_list, image_size_list, EMPTY_IMAGE, config.IMG_STYLE_ZOOM, *args
        )
        return current_classes + [zoomed_img, cell_last_clicked]

    # Harder case: move focus in a particular direction
    elif 'move-' in button_id:
        current_classes, zoomed_img, cell_last_clicked = utils.direction_key_pressed(
            button_id, n_rows, n_cols, COLS_MAX, ROWS_MAX * COLS_MAX, image_list, image_size_list, EMPTY_IMAGE, config.IMG_STYLE_ZOOM, *args
        )
        return current_classes + [zoomed_img, cell_last_clicked]

    elif 'jump-' in button_id:
        jump_left = 'left-' in button_id
        n_cells_patt = 'jump-left-([0-9]+)-cells-button' if jump_left else 'jump-right-([0-9]+)-cells-button'
        n_cells = int(re.findall(n_cells_patt, button_id)[0])

        current_classes, zoomed_img, cell_last_clicked = utils.jump_focus_n_cells(
            jump_left, n_cells, n_rows, n_cols, COLS_MAX, ROWS_MAX * COLS_MAX, image_list, image_size_list, EMPTY_IMAGE, config.IMG_STYLE_ZOOM, *args
        )
        return current_classes + [zoomed_img, cell_last_clicked]

    elif button_id in ['keep-button', 'delete-button']:
        current_classes, zoomed_img, cell_last_clicked = utils.keep_delete_pressed(
            button_id, n_cols, COLS_MAX, ROWS_MAX * COLS_MAX, image_list, image_size_list, EMPTY_IMAGE, config.IMG_STYLE_ZOOM, *args
        )
        return current_classes + [zoomed_img, cell_last_clicked]

    elif button_id in ['group-button']:
        current_classes, zoomed_img, cell_last_clicked = utils.group_ungroup_key_pressed(
            button_id, n_cols, COLS_MAX, ROWS_MAX * COLS_MAX, image_list, image_size_list, EMPTY_IMAGE, config.IMG_STYLE_ZOOM, *args
        )
        return current_classes + [zoomed_img, cell_last_clicked]

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

    app.run_server(debug=False)
