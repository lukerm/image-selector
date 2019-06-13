import os

import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output

import flask

app = dash.Dash(__name__)


# Assumes that images are stored in the img/ directory for now
image_directory = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'img')
static_image_route = '/static/'

# Define the maximal grid dimensions
ROWS_MAX, COLS_MAX = 7, 7


def create_image_grid(img_fname, n_row, n_col):
    """
    Create a grid of the same image img with n_row rows and n_col columns
    """
    img_path = static_image_route + img_fname
    pad = 2
    img_style = {'display': 'block', 'height': 'auto', 'max-width': '100%'}

    def get_grid_element(x, y, hidden):

        # Set the display to none if this grid cell is hidden
        if hidden:
            style = {'padding': 0, 'display': 'none'}
        else:
            style = {'padding': pad}

        my_id = f'{x}-{y}'
        return html.Td(id='grid-td-' + my_id,
                       className='focus-off',
                       children=html.Button(id='grid-button-' + my_id,
                                            children=html.Img(src=img_path, style=img_style),
                                            style=style,
                                            ),
                       style={'border-color': 'white'} # focus off at beginning
                       )

    grid = []
    for i in range(ROWS_MAX):
        row = []
        for j in range(COLS_MAX):
            hidden = (i >= n_row) or (j >= n_col)
            row.append(get_grid_element(i, j, hidden))
        row = html.Tr(row)
        grid.append(row)

    return html.Div(html.Table(grid))


# App's layout
app.layout = html.Div(
    children=[
        html.Div(id='hidden-div', style={'display': 'none'}),
        html.H2("Happy Frogs"),
        html.Div([
            dcc.Dropdown(
                id='choose-image',
                options=[{'label': 'happy frog original', 'value': 'happyFrog.jpg'},],
                value='happyFrog.jpg',
                style={'width': '12vw', 'display': 'inline-block'}
            ),
            dcc.Dropdown(
                id='choose-grid-size',
                options=[{'label': f'{k+1} x {k+1}', 'value': k+1} for k in range(ROWS_MAX) if k > 0],
                value=2,
                style={'width': '5vw', 'display': 'inline-block'}
            ),
        ]),
        html.Div([
            html.Table([
                html.Tr([
                    html.Td(
                        id='responsive-frogs',
                        children=create_image_grid('happyFrog.jpg', 2, 2),
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
    [Input('choose-image', 'value'),
     Input('choose-grid-size', 'value'),
     Input('choose-grid-size', 'value')]
)
def create_reactive_image_grid(img_fname, n_row, n_col):
    return create_image_grid(img_fname, n_row, n_col)


# Create callbacks for all grid elements (hidden and visible)
# As they are all defined in advance, all grid ids exist from the beginning (i.e. in the static app.layout)
grid_table = app.layout.get('responsive-frogs').children.children
for i in range(ROWS_MAX):
    for j in range(COLS_MAX):

        # We can only set a callback on an element once, so we first check to if it has already been assigned
        if f'grid-td-{i}-{j}.style' not in app.callback_map:
            assert f'grid-td-{i}-{j}.className' not in app.callback_map

            @app.callback(
                Output(f'grid-td-{i}-{j}', 'style'),
                [Input(f'grid-button-{i}-{j}', 'n_clicks')]
            )
            def change_style(n):
                if n is None or n % 2 == 0:
                    return {'border-color': 'white', 'border-style': 'solid'}
                else:
                    return {'border-color': 'red', 'border-style': 'solid'}

            @app.callback(
                Output(f'grid-td-{i}-{j}', 'className'),
                [Input(f'grid-button-{i}-{j}', 'n_clicks')]
            )
            def change_class_name(n):
                if n is None or n % 2 == 0:
                    return 'focus-off'
                else:
                    return 'focus-on'


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
