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


def create_image_grid(img_fname, n_row, n_col):
    """
    Create a grid of the same image img with n_row rows and n_col columns
    """
    img_path = static_image_route + img_fname
    pad = 2
    img_style = {'display': 'block', 'height': 'auto', 'max-width': '100%'}

    def get_grid_element(x, y):
        my_id = f'grid-{x}-{y}'
        return html.Td(id=my_id, children=html.Div(html.Img(src=img_path, style=img_style), style={'padding': pad}))

    grid = []
    for i in range(n_row):
        row = []
        for j in range(n_col):
            row.append(get_grid_element(i, j))
        row = html.Tr(row)
        grid.append(row)

    return html.Div(html.Table(grid))


# App's layout
n_row, n_col = 7, 5
app.layout = html.Div(
    children=[
        html.H2("Happy Frogs"),
        html.Button('Highlight top left', id='button'),
        html.Div([
            dcc.Dropdown(
                id='choose-image',
                options=[{'label': 'happy frog original', 'value': 'happyFrog.jpg'},],
                value='happyFrog.jpg',
                style={'width': '12vw', 'display': 'inline-block'}
            ),
            dcc.Dropdown(
                id='choose-grid-size',
                options=[
                    {'label': '2 x 2', 'value': 2},
                    {'label': '3 x 3', 'value': 3},
                    {'label': '4 x 4', 'value': 4},
                    {'label': '5 x 5', 'value': 5},
                ],
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


@app.callback(
    Output('grid-0-0', 'style'),
    [Input('button', 'n_clicks')]
)
def change_style(n):
    return {'padding': 5, 'border-style': 'solid', 'border-color': 'red'}


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
