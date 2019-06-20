import os

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

# Globals for the images
img_fname = 'happyFrog.jpg' # Default image
img_path = static_image_route + img_fname
img_style = {'display': 'block', 'height': 'auto', 'max-width': '100%'}

# List of image objects - pre-load here to avoid re-loading on every grid re-sizing
images = [static_image_route + fname for fname in sorted(os.listdir(image_directory))]
IMAGE_LIST = [html.Img(src=img, style=img_style) for img in images]
IMAGE_LIST = IMAGE_LIST + [html.Img(src=img_path, style=img_style)]*(ROWS_MAX*COLS_MAX - len(IMAGE_LIST))


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
                       className='focus-off' if x or y else 'focus-on',
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


## Create callbacks for all grid elements (hidden and visible)
## As they are all defined in advance, all grid ids exist from the beginning (i.e. in the static app.layout)
grid_table = app.layout.get('responsive-frogs').children.children
for i in range(ROWS_MAX):
    for j in range(COLS_MAX):

        # We can only set a callback on an element once, so we first check to if it has already been assigned
        if f'grid-td-{i}-{j}.style' not in app.callback_map:
            assert f'grid-td-{i}-{j}.className' not in app.callback_map

            @app.callback(
                Output(f'grid-td-{i}-{j}', 'className'),
                [
                    Input(f'grid-button-{i}-{j}', 'n_clicks'),
                    Input('move-left', 'n_clicks'),
                    Input('move-right', 'n_clicks'),
                    Input('move-up', 'n_clicks'),
                    Input('move-down', 'n_clicks'),
                ],
                [
                    State(f'grid-td-{i}-{j}', 'className'), # my former state
                    State(f'grid-td-{i}-{(j+1) % COLS_MAX}', 'className'), # my right neighbour's state
                    State(f'grid-td-{i}-{(j-1) % COLS_MAX}', 'className'), # my left neighbour's state
                    State(f'grid-td-{(i+1) % ROWS_MAX}-{j}', 'className'), # my below neighbour's state
                    State(f'grid-td-{(i-1) % ROWS_MAX}-{j}', 'className'), # my above neighbour's state
                ]
            )
            def activate_this_cell(n_self, n_left, n_right, n_up, n_down,
                                   class_self, class_right, class_left, class_below, class_above):

                # Find the button that triggered this callback (if any)
                context = dash.callback_context
                if not context.triggered and i+j > 0:
                    return 'focus-off'
                elif not context.triggered and i+j == 0:
                    return 'focus-on'
                else:
                    button_id = context.triggered[0]['prop_id'].split('.')[0]

                # Switch based on the button type

                # If my own button was pressed, toggle state
                if 'grid-button-' in button_id:
                    if class_self == 'focus-on':
                        return 'focus-off'
                    else:
                        return 'focus-on'

                # For movement in a particular direction, check the class of
                # the neighbour in the opposite direction
                if button_id == 'move-left':
                    check_class = class_right
                elif button_id == 'move-right':
                    check_class = class_left
                elif button_id == 'move-up':
                    check_class = class_below
                elif button_id == 'move-down':
                    check_class = class_above

                if check_class == 'focus-on':
                    return 'focus-on'
                else:
                    return 'focus-off'


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
