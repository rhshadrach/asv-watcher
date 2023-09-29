import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, dash_table, dcc, html
from plotly.subplots import make_subplots

from asv_watcher import RollingDetector, Watcher

detector = RollingDetector(window_size=30)
benchmark_path = "/home/richard/dev/asv-collection/pandas"
ignored_hashes = {
    "253daaa1a67918f5d71956282a29a14adf74bae7": (
        "Revert Vendored klib quadatric probing - performance improvements due to other"
        " regressions"
    ),
    "b7708f00c7b61990521e9a0e03680ed45b59086b": (
        "Posted comment, haven't raised an issue"
    ),
    "05fb08ecca8850b71f659788183b48db9bc4e391": (
        "Change in NumPy caused performance differences"
    ),
    "8b227f39cecc170ab2a14eaa1d6e349ba59528bf": (
        "GH#49920 - Posted comment, haven't raised an issue"
    ),
    "0a58c03f5dfe643a9ef7ad54bead679a82d2e63b": (
        "GH#49684 - Posted comment, haven't raised an issue"
    ),
    "3b901a4143d2263bbc7fc5076f040eb70166ff92": (
        "GH#48176 - Regression fix that adds a copy"
    ),
    "f6d3cb292e50e77e7cb624ea33167f943c5a2481": (
        "GH#49624 - Posted comment, haven't raised an issue"
    ),
    "27138738a22edeaa644a3aff1a2cd98d1f954632": "GH#49566 - Already commented on in PR",
    "ef23fc75b2adfffd0d82a75f6be8f87fb00a5892": (
        "GH#49466 - Posted comment, haven't raised an issue"
    ),
    "0106c26529900bad0561efb9c9180f7f016365b0": (
        "GH#49053 - Revert of caching since it breaks find_stack_level"
    ),
    "c0445543a10ae6c6abe5a3efc519fd9edcd2d276": (
        "GH#49589 - Posted comment, haven't raised an issue"
    ),
    "d47e052379826ab6085e145e6ee2c654b0d1c471": (
        "GH#49490 - Behavior change in groupby group_keys"
    ),
    "f19aeaf4976228ed936e9cc85b6f430ab72c1793": "GH#49873 - ASVs discussed in PR",
    "6b4fa02e10480c4ddae0714e36b7fe765fa42eac": (
        "GH#49347 - Small regression, not informed"
    ),
    "b77417832c76f0027723cad68ffd5654bbafe2a9": "GH#49378 - Posted comment",
    # TODO: We should altomatically ignore change in dependencies
    "2d6d744f9702b94a616890edc1543ac9bd246e49": (
        "GH#50653 - False positive, change in NumPy"
    ),
    "eff6566cdcc99b41234e0577ab92b779348695ac": (
        "GH#49737 - Expected due to behavior change"
    ),
    "1d5f05c33c613508727ee7b971ad56723d474446": "GH#49024 - Expected behavior change",
    "4f42ecbd0569f645a881f15527709e2069c6672d": "GH#50548 - Expected behavior change",
    "3ea04c383bec5aa82a1f2c57c6d4da81ebd74755": "GH#50507 - Expected behavior change",
    "98323eec0e94ea103412a1a20a1e6b4c6fa0599b": "GH#49008 - Expected behavior change",
}

watcher = Watcher(
    detector=detector,
    benchmark_path=benchmark_path,
    ignored_hashes=ignored_hashes,
)

summary = watcher.summary()
summary_by_hash = (
    summary[summary.is_regression].reset_index().groupby("hash", as_index=False)
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
        html.P(id="github_comment"),
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


@app.callback(Output("github_comment", "children"), Input("summary", "active_cell"))
def update_github_comment(active_cell):
    if active_cell:
        hash = summary_by_hash.index[active_cell["row"]]
        result = html.Pre(watcher.generate_report(hash))
        return result
    return ""


@app.callback(Output("copy_github_comment", "content"), Input("summary", "active_cell"))
def update_copy_github_comment(active_cell):
    if active_cell:
        hash = summary_by_hash.index[active_cell["row"]]
        #     continue
        result = watcher.generate_report(hash)
        return result
    return ""


@app.callback(Output("commit_summary_table", "data"), Input("summary", "active_cell"))
def update_commit_summary_table(active_cell):
    global regressions

    if active_cell:
        hash = summary_by_hash.index[active_cell["row"]]
        regressions = watcher.get_regressions(hash)
        result = summary[summary["hash"].eq(hash) & summary.is_regression].reset_index().to_dict("records")
        return result
    return None


@app.callback(
    Output("benchmark_plot", "figure"), Input("commit_summary_table", "active_cell")
)
def update_plot(active_cell):
    if active_cell is not None and len(regressions) > 0:
        regression = regressions[active_cell["row"]]
        plot_data = summary.loc[regression][['time', 'established_best', 'established_worst']]

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
