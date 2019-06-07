import os

import dash
import dash_core_components as dcc
import dash_html_components as html

import flask

app = dash.Dash(__name__)


def create_image_grid(img, n_row, n_col):
    """
    Create a grid of the same image img with n_row rows and n_col columns
    """
    pad = 2
    img_style = {'display': 'block', 'height': 'auto', 'max-width': '100%'}

    grid_element = html.Td(html.Div(html.Img(src=img, style=img_style), style={'padding': pad}))
    one_row = html.Tr([grid_element] * n_col)
    grid = html.Div(html.Table([one_row] * n_row))

    return grid


# Assumes that images are stored in the img/ directory for now
image_directory = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'img')
static_image_route = '/static/'

# App's layout
n_row, n_col = 7, 5
app.layout = html.Div(
    children=[
        html.H2("Happy Frogs"),
        html.Div([
            html.Table([
                html.Tr([
                    html.Td(
                        create_image_grid(static_image_route + 'happyFrog.jpg', n_row, n_col),
                        style={'width': '50vw', 'height': 'auto', 'border-style': 'solid',}
                        ),
                    html.Td(
                        create_image_grid(static_image_route + 'happyFrog.jpg', n_row, n_col),
                        style={'width': '50vw', 'height': 'auto', 'border-style': 'solid',}
                        ),
                ]),
            ]),
        ]),
    ]
)

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
