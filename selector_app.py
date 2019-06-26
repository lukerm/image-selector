import os
import re

import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State

import flask

app = dash.Dash(__name__)


# Assumes that images are stored in the img/ directory for now
image_directory = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'img')
static_image_route = '/static/'

# Define the maximal grid dimensions
ROWS_MAX, COLS_MAX = 7, 7
N_GRID = ROWS_MAX * COLS_MAX

# Globals for the images
img_fname = 'happyFrog.jpg' # Default image
img_path = static_image_route + img_fname
img_style = {'display': 'block', 'height': 'auto', 'max-width': '100%'}

# List of image objects - pre-load here to avoid re-loading on every grid re-sizing
images = [static_image_route + fname for fname in sorted(os.listdir(image_directory))]
IMAGE_LIST = [html.Img(src=img, style=img_style) for img in images]
IMAGE_LIST = IMAGE_LIST + [html.Img(src=img_path, style=img_style)]*(ROWS_MAX*COLS_MAX - len(IMAGE_LIST))

# These define the inputs and outputs to callback function activate_deactivate_cells
ALL_TD_ID_OUTPUTS = [Output(f'grid-td-{i}-{j}', 'className') for i in range(ROWS_MAX) for j in range(COLS_MAX)]
ALL_BUTTONS_IDS = [Input(f'grid-button-{i}-{j}', 'n_clicks') for i in range(ROWS_MAX) for j in range(COLS_MAX)]
ALL_TD_ID_STATES = [State(f'grid-td-{i}-{j}', 'className') for i in range(ROWS_MAX) for j in range(COLS_MAX)]


def create_image_grid(n_row, n_col):
    """
    Create a grid of the same image with n_row rows and n_col columns
    """

    pad = 2

    def get_grid_element(x, y, n_x, n_y, hidden):

        # Set the display to none if this grid cell is hidden
        if hidden:
            style = {'padding': 0, 'display': 'none'}
        else:
            style = {'padding': pad}

        my_id = f'{x}-{y}'
        return html.Td(id='grid-td-' + my_id,
                       className='focus-off' if x or y else 'focus-off focus-last-clicked',
                       children=html.Button(id='grid-button-' + my_id,
                                            children=IMAGE_LIST[y + x*n_y],
                                            style=style,
                                            ),
                        style=style,
                       )

    grid = []
    for i in range(ROWS_MAX):
        row = []
        for j in range(COLS_MAX):
            hidden = (i >= n_row) or (j >= n_col)
            row.append(get_grid_element(i, j, n_row, n_col, hidden))
        row = html.Tr(row)
        grid.append(row)

    return html.Div(html.Table(grid))


# App's layout
app.layout = html.Div(
    children=[
        html.Div(id='hidden-div', style={'display': 'none'}),
        html.H2("Happy Frogs"),
        dcc.Dropdown(
            id='choose-grid-size',
            options=[{'label': f'{k+1} x {k+1}', 'value': k+1} for k in range(ROWS_MAX) if k > 0],
            value=2,
            style={'width': '5vw', 'display': 'inline-block'}
        ),
        html.Div([
            html.Button(id='move-left', children='Move left'),
            html.Button(id='move-right', children='Move right'),
            html.Button(id='move-up', children='Move up'),
            html.Button(id='move-down', children='Move down'),
        ]),
        html.Div([
            html.Table([
                html.Tr([
                    html.Td(
                        id='responsive-frogs',
                        children=create_image_grid(2, 2),
                        style={'width': '50vw', 'height': 'auto', 'border-style': 'solid',}
                        ),
#                    html.Td(
#                        create_image_grid(static_image_route + 'happyFrog.jpg', n_row, n_col),
#                        style={'width': '50vw', 'height': 'auto', 'border-style': 'solid',}
#                        ),
                ]),
            ]),
        ]),
    ]
)


@app.callback(
    Output('responsive-frogs', 'children'),
    [Input('choose-grid-size', 'value'),
     Input('choose-grid-size', 'value')]
)
def create_reactive_image_grid(n_row, n_col):
    return create_image_grid(n_row, n_col)


@app.callback(
    ALL_TD_ID_OUTPUTS,
    [
         Input('choose-grid-size', 'value'),
         Input('choose-grid-size', 'value'),
         Input('move-left', 'n_clicks'),
         Input('move-right', 'n_clicks'),
         Input('move-up', 'n_clicks'),
         Input('move-down', 'n_clicks'),
    ] + ALL_BUTTONS_IDS,
    ALL_TD_ID_STATES
)
def activate_deactivate_cells(n_rows, n_cols, n_left, n_right, n_up, n_down, *args):
    """
    Global callback function for toggling classes. There are three toggle modes:
        1) Pressing a grid cell will toggle its state
        2) Pressing a directional button will force the focus to shift in the direction stated
        3) Resizing the grid will cause the top-left only to be in focus

    Args:
        n_rows = int, current number of rows in the grid (indicates resizing)
        n_cols = int, current number of columns in the grid (indicates resizing)
        n_left = int, number of clicks on the 'move-left' buttons (indicates shifting)
        n_right = int, number of clicks on the 'move-right' buttons (indicates shifting)
        n_up = int, number of clicks on the 'move-up' buttons (indicates shifting)
        n_down = int, number of clicks on the 'move-down' buttons (indicates shifting)

        *args = positional arguments split into two equal halves (i.e. of length 2 x N_GRID):
            0) args[:N_GRID] are Inputs (activated by the grid-Buttons)
            1) args[N_GRID:] are States (indicating state of the grid-Tds)
            Both are in row-major order (for i in rows: for j in cols: ... )

    Returns: a list of new classNames for all the grid cells.

    Note: args split into two halves:
        args[:N_GRID] are Inputs (Buttons)
        args[N_GRID:] are States (Tds)
    """

    # Find the button that triggered this callback (if any)
    context = dash.callback_context
    if not context.triggered:
        return ['focus-off focus-last-clicked' if i+j == 0 else 'focus-off' for i in range(ROWS_MAX) for j in range(COLS_MAX)]
    else:
        button_id = context.triggered[0]['prop_id'].split('.')[0]

    # Easy case: toggle the state of this button (as it was pressed)
    if 'grid-button-' in button_id:
        # Grid location of the pressed button
        cell_loc = [int(i) for i in re.findall('[0-9]+', button_id)]
        # Class name of the pressed button
        previous_class_clicked = args[N_GRID + cell_loc[1] + cell_loc[0]*COLS_MAX]

        new_classes = []
        for i in range(ROWS_MAX):
            for j in range(COLS_MAX):
                # Toggle the pressed button
                if cell_loc == [i, j]:
                    # Toggle the background focus, but keep the last
                    if previous_class_clicked == 'focus-off':
                        new_class_clicked = 'focus-on focus-last-clicked'
                    elif previous_class_clicked == 'focus-off focus-last-clicked':
                        new_class_clicked = 'focus-on focus-last-clicked'
                    elif previous_class_clicked == 'focus-on':
                        new_class_clicked = 'focus-on focus-last-clicked'
                    else:
                        new_class_clicked = 'focus-off'
                    new_classes.append(new_class_clicked)
                # All others retain their class name, except the previous last clicked moves to focus on
                else:
                    previous_class = args[N_GRID + j + i*COLS_MAX]
                    # Only demote the previous last clicked to focus-on if we are turning another cell on (not off!)
                    if 'focus-last-clicked' in previous_class and 'focus-off' in previous_class_clicked:
                        new_class = 'focus-on'
                    else:
                        new_class = previous_class
                    new_classes.append(new_class)

    # Harder case: move all in a particular direction
    elif 'move-' in button_id:

        new_classes = []
        for i in range(ROWS_MAX):
            for j in range(COLS_MAX):
                my_class = args[N_GRID + j + i*COLS_MAX]
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

                if 'focus-last-clicked' in my_class:
                    new_classes.append(my_class.split(' ')[0])
                else:
                    new_classes.append(my_class + ' focus-last-clicked' if 'focus-last-clicked' in check_class  else my_class)

    # Reset the grid
    elif button_id == 'choose-grid-size':
        return ['focus-off focus-last-clicked' if i+j == 0 else 'focus-off' for i in range(ROWS_MAX) for j in range(COLS_MAX)]

    else:
        raise ValueError('Unrecognized button ID')

    return new_classes


@app.server.route('{}<image_path>'.format(static_image_route))
def serve_image(image_path):
    """
    Allows an image to be served from the given image_path
    """
    image_name = '{}'.format(image_path)
    # For more secure deployment, see: https://github.com/plotly/dash/issues/71#issuecomment-313222343
    #if image_name not in list_of_images:
    #    raise Exception('"{}" is excluded from the allowed static files'.format(image_path))
    return flask.send_from_directory(image_directory, image_name)


if __name__ == '__main__':
    app.run_server(debug=True)
