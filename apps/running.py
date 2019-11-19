import dash
import dash_html_components as html
import dash_table
import dash_daq as daq
import pandas as pd
import numpy as np
import os
import re
import pickle as pkl
import dash_core_components as dcc
from dash.dependencies import Input, Output, State

from app import app, default_columns, logic_manager
import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

GPUS_DATA_PATH = '/home/crilout/Big/Models/gpu-monitor/data/'
RUNNING_OPT_PATH = '/home/crilout/Big/Models/gpu-monitor/data/running_opt.pkl'
TO_KILL_PATH = os.path.join(GPUS_DATA_PATH, 'to_kill.pkl')

files = os.listdir(GPUS_DATA_PATH)
GPUS = [f.split('_')[0] for f in files if f.endswith('_gpus.csv') ]
GPUS_ON = []
ALL_GPUS = []

tabs_html = []
for gpu in GPUS:
    df = pd.read_csv(os.path.join(GPUS_DATA_PATH, gpu + '_gpus.csv'))
    checkboxes = []
    for x in np.sort(df.iloc[:,0].unique()):
        if np.isnan(x) or (gpu=='fb'):
            continue
        x = int(x)
        checkbox_id = gpu + '_' + str(x)
        ALL_GPUS += [checkbox_id]
        checkboxes += \
            [daq.BooleanSwitch(
                id=checkbox_id,
                on=True,
                label=str(x)
            )]
    checkboxes = [html.H6(gpu)] + checkboxes

    tabs_html += [
        html.Div(
            checkboxes,
            style={
                'display': 'inline-grid',
                'padding': '0 10px'
            }
        )
    ]

layout = html.Div([
    html.H3('Running/Queued'),
    html.Div(id='tab-data', style={'display': 'none'}),
    html.Div(id='fake-data', style={'display': 'none'}),
    html.Div(id='fake-data2', style={'display': 'none'}),
    html.Div(
        tabs_html,
        id='checkboxes-gpu',
        style={'display': 'inline-flex'}
    ),
    html.Div(
        dash_table.DataTable(
            id='running_datatable',
            style_data={
                    'whiteSpace': 'pre',
                    'height': 'auto'
            },
            columns=[
                {"name": col, "id": col} for col in
                ['_id', 'start_time', 'status', 'config.modif', 'config.gpu']],
            sorting=True,
            sorting_type="multi",
            row_deletable=True,
            style_cell_conditional=[
                                       {
                                           'if': {'row_index': 'odd'},
                                           'backgroundColor': 'rgb(248,248,248)'
                                       }
                                   ] + [
                                       {
                                           'if': {'id': col},
                                           'textAlign': 'left'
                                       } for col in ['name']
                                   ]
        ),
        style={
            'margin-left':'50px',
            'display': 'inline-block',
            'width': '900px'
        }
    ),
    html.Div([
        html.Div(
            daq.BooleanSwitch(
                id='stop-queue',
                on=True,
                label="Stop Queue",
                color='#eb4034'
            )
        ),
        html.Div([
            html.Div('Max runs'),
            daq.NumericInput(
                id='max-runs',
                max=40,
                value=10,
                min=1
            )],
            style={'padding': '10px'}
        )],
        style={'display': 'inline-grid'}
    ),
    html.Div(id='toggle-switch-output', style={'position':'flex'}),
    dcc.Interval(
        id='running-interval',
        interval=10*1000,
        n_intervals=0
    ),
])

@app.callback(
    Output('fake-data2', 'data'),
    [Input(x, 'on') for x in ALL_GPUS])
def update_gpus_on(*args):
    global GPUS_ON
    GPUS_ON = []
    for id, value in zip(ALL_GPUS, args):
        if value:
            GPUS_ON += [id]

    return ''

@app.callback(
    Output('toggle-switch-output', 'children'),
    [   Input('tab-data', 'data'),
        Input('stop-queue', 'on'),
        Input('max-runs', 'value'),
        Input('running-interval', 'n_intervals')
    ])
def write_current_opt(data_args, stop, max_runs, n):
    global GPUS_ON
    db_name = None if data_args is None else data_args['db']
    print(db_name, GPUS_ON, stop, max_runs)
    with open(RUNNING_OPT_PATH, 'wb') as f:
        pkl.dump((db_name, GPUS_ON, stop, max_runs), f)

    return ''

@app.callback(
    Output('running_datatable', 'data'),
    [Input('tab-data', 'data'), Input('running-interval', 'n_intervals')])
def populate_table(data_args, n):
    db_name = None if data_args is None else data_args['db']
    if db_name is None:
        return ''
    return logic_manager.table_content_running(db_name)

@app.callback(Output('fake-data', 'children'),
              [Input('tab-data', 'data'),
               Input('running_datatable', 'data_previous')],
              [State('running_datatable', 'data')])
def show_removed_rows(data_args, previous, current):
    if previous is None:
        dash.exceptions.PreventUpdate()
    else:
        print([f'Just removed {row}' for row in previous if row not in current])
        ids_queued = [row['_id'] for row in previous if row not in current and row['status']=='QUEUED']
        ids_running = [row['_id'] for row in previous if row not in current and row['status']=='RUNNING']
        logic_manager.update_run_by_id(data_args['db'], ids_queued, 'STOPPED')
        logic_manager.update_run_by_id(data_args['db'], ids_running, 'KILL')
        if not os.path.isfile(TO_KILL_PATH):
            to_kill = []
        else:
            with open(TO_KILL_PATH, 'rb') as f:
                to_kill = pkl.load(f)
        to_kill += ids_running
        with open(TO_KILL_PATH, 'wb') as f:
            pkl.dump(to_kill, f)

    return ''
