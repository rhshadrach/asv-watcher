import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, dash_table, dcc, html
from plotly.subplots import make_subplots

from asv_watcher import Watcher

watcher = Watcher()
summary = watcher.summary()
summary_by_hash = (
    summary[summary.is_regression]
    .reset_index()
    .groupby("hash", as_index=False)
    .agg(
        benchmarks=("name", "size"),
        pct_change_max=("pct_change", "max"),
        absolute_change_max=("abs_change", "max"),
        pct_change_mean=("pct_change", "mean"),
        absolute_change_mean=("abs_change", "mean"),
    )
    .sort_values(by="benchmarks", ascending=False)
    .set_index("hash", drop=False)
)

# Initialize the app
app = Dash(__name__)

# App layout
app.layout = html.Div(
    [
        html.Div(children="My First App with Data"),
        dash_table.DataTable(
            id="summary",
            data=summary_by_hash.to_dict("records"),
            page_size=10,
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
            id="commit_summary_table", data=pd.DataFrame().to_dict("records")
        ),
        dcc.Graph(id="benchmark_plot", figure={}),
    ]
)

regressions = []


@app.callback(Output("commit_range", "children"), Input("summary", "active_cell"))
def update_commit_range(active_cell):
    if active_cell:
        hash = summary_by_hash.index[active_cell["row"]]
        commit_range = watcher.commit_range(hash)
        result = (html.A("Commit range", href=commit_range),)
        return result
    return ""


@app.callback(Output("copy_github_comment", "content"), Input("summary", "active_cell"))
def update_copy_github_comment(active_cell):
    if active_cell:
        hash = summary_by_hash.index[active_cell["row"]]
        result = watcher.generate_report(hash)
        return result
    return ""


@app.callback(Output("commit_summary_table", "data"), Input("summary", "active_cell"))
def update_commit_summary_table(active_cell):
    global regressions

    if active_cell:
        hash = summary_by_hash.index[active_cell["row"]]
        regressions = watcher.get_regressions(hash)
        result = (
            summary[summary["hash"].eq(hash) & summary.is_regression]
            .reset_index()
            .to_dict("records")
        )
        return result
    return None


@app.callback(
    Output("benchmark_plot", "figure"), Input("commit_summary_table", "active_cell")
)
def update_plot(active_cell):
    if active_cell is not None and len(regressions) > 0:
        regression = regressions[active_cell["row"]]
        plot_data = summary.loc[regression][
            ["time", "established_best", "established_worst"]
        ]

        fig = make_subplots()
        for column in plot_data:
            fig.add_trace(
                go.Scatter(
                    x=plot_data.eval("revision"),
                    y=plot_data[column],
                    name=column,
                ),
                secondary_y=False,
            )
        return fig
    return dash.no_update


if __name__ == "__main__":
    app.run(debug=True)
