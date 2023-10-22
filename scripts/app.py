import time
from pathlib import Path

import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, dash_table, dcc, html
from plotly.subplots import make_subplots

from asv_watcher import Watcher

timer = time.time()
watcher = Watcher()
cache_path = Path(__file__).parent / ".." / ".cache"
benchmarks = watcher.benchmarks()
summary = pd.read_parquet(cache_path / "summary.parquet")
summary_columns = [
    "date",
    "benchmarks",
    "pct_change_max",
    "abs_change_max",
    "pct_change_mean",
    "abs_change_mean",
    "git_hash",
]
print("Startup time:", time.time() - timer)

# Initialize the app
app = Dash(__name__)

# App layout
app.layout = html.Div(
    [
        html.Div(children="Regression Navigator"),
        dash_table.DataTable(
            id="summary",
            data=summary[summary_columns].to_dict("records"),
            page_current=0,
            page_size=10,
            sort_action="custom",
            sort_mode="single",
        ),
        html.P(id="commit_range"),
        html.Div(
            [
                html.P("Copy GitHubComment", style={"display": "inline"}),
                dcc.Clipboard(
                    id="copy_github_comment",
                    title="copy",
                    style={
                        "display": "inline",
                        "fontSize": 20,
                        "verticalAlign": "top",
                    },
                ),
            ]
        ),
        dash_table.DataTable(
            id="commit_table",
            data=pd.DataFrame().to_dict("records"),
            page_current=0,
            page_size=10,
            sort_action="custom",
            sort_mode="single",
        ),
        dcc.Graph(id="benchmark_plot", figure={}),
    ]
)

regressions = []


@app.callback(Output("summary", "data"), Input("summary", "sort_by"))
def update_table(sort_by):
    if sort_by is not None:
        name = sort_by[0]["column_id"]
        if name in [
            "pct_change_max",
            "abs_change_max",
            "pct_change_mean",
            "abs_change_mean",
        ]:
            name += "_value"
        result = summary.sort_values(
            name,
            ascending=sort_by[0]["direction"] == "asc",
        )
    else:
        result = summary
    result = result[summary_columns]
    return result.to_dict("records")


@app.callback(
    Output("commit_range", "children"),
    Input("summary", "active_cell"),
    Input("summary", "derived_viewport_data"),
)
def update_commit_range(active_cell, derived_viewport_data):
    if active_cell:
        git_hash = derived_viewport_data[active_cell["row"]]["git_hash"]
        commit_range = watcher.commit_range(git_hash)
        result = (html.A("Commit range", href=commit_range),)
        return result
    return ""


@app.callback(
    Output("copy_github_comment", "content"),
    Input("summary", "active_cell"),
    Input("summary", "derived_viewport_data"),
)
def update_copy_github_comment(active_cell, derived_viewport_data):
    if active_cell:
        git_hash = derived_viewport_data[active_cell["row"]]["git_hash"]
        result = watcher.generate_report(git_hash)
        return result
    return ""


@app.callback(
    Output("commit_table", "data"),
    Input("summary", "active_cell"),
    Input("summary", "derived_viewport_data"),
    Input("commit_table", "sort_by"),
)
def update_commit_table(active_cell, derived_viewport_data, sort_by):
    global regressions

    if active_cell is None:
        return None

    git_hash = derived_viewport_data[active_cell["row"]]["git_hash"]
    regressions = watcher.regressions()
    result = regressions[regressions["git_hash"].eq(git_hash)].reset_index()

    if sort_by is not None:
        name = sort_by[0]["column_id"]
        if name in ["pct_change", "abs_change"]:
            name += "_value"
        result = result.sort_values(
            name,
            ascending=sort_by[0]["direction"] == "asc",
        )

    return result[["name", "params", "pct_change", "abs_change", "time"]].to_dict(
        "records"
    )


@app.callback(
    Output("benchmark_plot", "figure"),
    Input("commit_table", "active_cell"),
    Input("commit_table", "derived_viewport_data"),
)
def update_plot(active_cell, derived_viewport_data):
    if active_cell is None:
        return dash.no_update
    if active_cell["row"] >= len(derived_viewport_data):
        # When the commit table changes, active_cell["row"] may be stale
        # and therefore exceed the derived_viewport_data
        return {}

    name = derived_viewport_data[active_cell["row"]]["name"]
    params = derived_viewport_data[active_cell["row"]]["params"]
    plot_data = benchmarks.loc[(name, params)][
        [
            "date",
            "time_value",
            "established_best",
            "established_worst",
            "is_regression",
        ]
    ].rename(columns={"time_value": "time"})

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    for column in plot_data:
        if column in ["date", "is_regression"]:
            continue
        fig.add_trace(
            go.Scatter(
                x=plot_data.eval("revision"),
                y=plot_data[column],
                name=column,
            ),
        )
    plot_data = plot_data[plot_data.is_regression]
    fig.add_trace(
        go.Scatter(
            x=plot_data.eval("revision"),
            y=plot_data["time"],
            mode="markers",
            name="Regressions",
        )
    )
    fig.update_traces(
        marker={"size": 12, "line": {"width": 2, "color": "DarkSlateGrey"}},
        selector={"mode": "markers"},
    )
    return fig


if __name__ == "__main__":
    app.run(debug=True)
