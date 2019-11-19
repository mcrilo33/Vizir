import dash_html_components as html
import dash_core_components as dcc
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from textwrap import dedent as d
import json
import math
import colorlover as cl


from dash.dependencies import Input, Output, State

from app import app, default_columns, logic_manager

styles = {
    'pre': {
        'border': 'thin lightgrey solid',
        'overflowX': 'scroll'
    }
}


layout = html.Div([
    html.H3(
        'Plot',
        style={
            'position': 'relative',
            'top': '8px',
            'margin-bottom': 0
        }
    ),
    html.Div(id='tab-data', style={'display': 'none', 'height': '0'}),
    html.Div(
        dcc.Dropdown(id='metric-dropdown'),
        style={'visibility': 'hidden', 'height':'0'}
    ),
    html.Div(
        dcc.Graph(id='metric-plot')
    ),
    html.Div([
            dcc.Markdown(d("""
                **Selection Data**
            """)),
            html.Pre(id='selected-data', style=styles['pre']),
        ], className='three columns'),
    dcc.Interval(
            id='graph-interval',
            interval=5*60*1000,
            n_intervals=0
        )
])


@app.callback([Output('metric-dropdown', 'options'),
               Output('metric-dropdown', 'value')],
              [Input('tab-data', 'data')],
              [State('plot-storage', 'data')])
def populate_metric_dropdown(data_args, plot_storage_data):
    if data_args is None:
        return []
    selected_ids = data_args.get('selected_ids', [])
    db_name = data_args['db']
    metric_names = logic_manager.metric_names_from_ids(db_name, selected_ids)
    return [{'label': name, 'value': name} for name in sorted(metric_names)], plot_storage_data


@app.callback(Output('plot-storage', 'data'),
              [Input('metric-dropdown', 'value')],)
def store_selected_metric(selected_metric):
    return selected_metric


@app.callback(Output('metric-plot', 'figure'),
              [Input('metric-dropdown', 'value'),
               Input('graph-interval', 'n_intervals')],
              [State('tab-data', 'data')])
def plot_metric(metric_name, n, data_args):
    COLORS = cl.scales['11']['qual']['Set3'] + cl.scales['11']['qual']['Paired'] \
        + cl.scales['9']['qual']['Pastel1'] + cl.scales['9']['qual']['Set1']

    if data_args is None:
        return []
    selected_ids = data_args.get('selected_ids', [])
    db_name = data_args['db']
    metric_names = logic_manager.metric_names_from_ids(db_name, selected_ids)
    grouped_metrics = {}
    for metric_name in metric_names:
        metric_splitted = metric_name.split('/')
        name = metric_splitted[1]
        if name not in grouped_metrics:
            grouped_metrics[name] = [metric_name]
        else:
            grouped_metrics[name] += [metric_name]

    layout = go.Layout(
        title=metric_name,
    )

    # traces = []
    # for d in metric_data:
        # trace = go.Scatter(
            # x=d['steps'],
            # y=d['values'],
            # name=d['run_id'],
            # mode='lines+markers',
        # )
        # traces.append(trace)

    n_rows = len(grouped_metrics)
    titles = [t.capitalize() for t in list(grouped_metrics.keys())]
    fig = make_subplots(
        rows=n_rows,
        cols=1,
        subplot_titles=titles
    )
    i = 1
    grouped_legend = {}
    for group_name in grouped_metrics:
        metric_names = sorted(grouped_metrics[group_name])
        for metric_name in sorted(metric_names):
            metric_splitted = metric_name.split('/')
            dataset_name = metric_splitted[0]

            metric_data = logic_manager.metric_data_from_ids(metric_name, db_name, selected_ids)
            for d in metric_data:
                ratio = math.ceil(len(d['steps'])/500)
                opt = {
                    'x':d['steps'][::ratio],
                    'y':d['values'][::ratio],
                    'type': 'scatter',
                    'mode':'lines+markers'
                }
                legendgroup = 'id:' + str(d['run_id']) + ', ' + dataset_name
                i_color = 0
                if legendgroup not in grouped_legend:
                    opt['name'] = legendgroup
                    if len(grouped_legend)==len(COLORS):
                        i_color = len(COLORS)
                        COLORS = cl.scales['11']['qual']['Set3']
                    grouped_legend[legendgroup] = COLORS[len(grouped_legend)-i_color]
                else:
                    opt['name'] = ''
                    opt['showlegend'] = False
                opt['line']=dict(color=grouped_legend[legendgroup])
                opt['marker']=dict(color=grouped_legend[legendgroup])
                opt['legendgroup'] = legendgroup
                fig.append_trace(
                    opt,
                    i,
                    1
                )
        i += 1
    fig.update_layout(height=300*n_rows)

    return fig


@app.callback(Output('selected-data', 'children'),
              [Input('metric-plot', 'selectedData')],
              [State('metric-plot', 'figure')])
def orint_selected_data(data, graph):
    if data is None:
        return

    out = {}
    for d in data['points']:
        num = d['curveNumber']
        id = graph['data'][num]['name']
        if id not in out:
            out[id] = {d['x'] : d['y']}
        else:
            out[id].update({d['x']: d['y']})
    return json.dumps(out, indent=2)

