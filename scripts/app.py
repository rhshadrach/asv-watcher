import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, dash_table, dcc, html
from plotly.subplots import make_subplots

from asv_watcher import Watcher
from asv_watcher._core import util

watcher = Watcher()
summary = watcher.summary()
summary_by_hash = (
    summary[summary.is_regression]
    .reset_index()
    .groupby("hash", as_index=False)
    .agg(
        date=("date", "first"),
        benchmarks=("name", "size"),
        pct_change_max=("pct_change", "max"),
        abs_change_max=("abs_change", "max"),
        pct_change_mean=("pct_change", "mean"),
        abs_change_mean=("abs_change", "mean"),
    )
    .sort_values(by="date", ascending=False)
    .set_index("hash", drop=False)[
        [
            "date",
            "benchmarks",
            "pct_change_max",
            "abs_change_max",
            "pct_change_mean",
            "abs_change_mean",
            "hash",
        ]
    ]
)
summary["pct_change"] = summary["pct_change"].apply(lambda x: f"{x:0.3%}")
for c in ["pct_change_max", "pct_change_mean"]:
    summary_by_hash[c] = summary_by_hash[c].apply(lambda x: f"{x:0.3%}")

summary["time_float"] = summary["time"]
summary["time"] = summary["time"].apply(util.time_to_str)
summary["abs_change"] = summary["abs_change"].apply(util.time_to_str)
for c in ["abs_change_max", "abs_change_mean"]:
    summary_by_hash[c] = summary_by_hash[c].apply(util.time_to_str)


# Initialize the app
app = Dash(__name__)

# App layout
app.layout = html.Div(
    [
        html.Div(children="Regression Navigator"),
        dash_table.DataTable(
            id="summary",
            data=summary_by_hash.to_dict("records"),
            page_size=10,
            sort_action="native",
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
            page_size=10,
            sort_action="native",
        ),
        dcc.Graph(id="benchmark_plot", figure={}),
    ]
)

regressions = []


@app.callback(
    Output("commit_range", "children"),
    Input("summary", "active_cell"),
    Input("summary", "derived_viewport_data"),
)
def update_commit_range(active_cell, derived_viewport_data):
    if active_cell:
        hash = derived_viewport_data[active_cell["row"]]["hash"]
        commit_range = watcher.commit_range(hash)
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
        hash = derived_viewport_data[active_cell["row"]]["hash"]
        result = watcher.generate_report(hash)
        return result
    return ""


@app.callback(
    Output("commit_table", "data"),
    Input("summary", "active_cell"),
    Input("summary", "derived_viewport_data"),
)
def update_commit_table(active_cell, derived_viewport_data):
    global regressions

    if active_cell:
        hash = derived_viewport_data[active_cell["row"]]["hash"]
        regressions = watcher.get_regressions(hash)
        result = (
            summary[summary["hash"].eq(hash) & summary.is_regression]
            .reset_index()[["name", "params", "pct_change", "abs_change", "time"]]
            .to_dict("records")
        )
        return result
    return None


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
    plot_data = summary.loc[(name, params)][
        [
            "date",
            "time_float",
            "established_best",
            "established_worst",
            "is_regression",
        ]
    ].rename(columns={"time_float": "time"})

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    for column in plot_data:
        if column == "date":
            continue
        fig.add_trace(
            go.Scatter(
                x=plot_data.eval("revision"),
                y=plot_data[column],
                name=column,
            ),
            secondary_y=column == "is_regression",
        )
    return fig


if __name__ == "__main__":
    app.run(debug=True)
