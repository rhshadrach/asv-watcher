import json
import re
import subprocess
import time
from pathlib import Path

import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dash_table, dcc, html
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


def execute(cmd):
    response = subprocess.run(cmd, shell=True, capture_output=True)
    if response.stderr.decode() != "":
        raise ValueError(response.stderr.decode())
    return response.stdout.decode()


# Exclude any hashes that already have an issue
needle = "Potential regression induced by commit "
cmd = f'gh search issues "{needle}"'
result = execute(cmd)
flagged_hashes = list()
for e in result.split("\t"):
    if e.startswith(needle):
        flagged_hashes.append(e[len(needle) :])

# TODO: Because calling the GH CLI from Juptyer seems to always have color...
def escape_ansi(line):
    ansi_escape = re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]")
    return ansi_escape.sub("", line)


response = execute(
    "cd /home/richard/dev/pandas/ && NO_COLOR=1 gh label list --limit 200 --json name"
)
labels = [e["name"] for e in json.loads(escape_ansi(response))]

response = execute(
    "cd /home/richard/dev/pandas/ "
    "&& gh api repos/:owner/:repo/milestones --jq '.[].title'"
)
milestones = [e for e in response.split("\n") if e != ""]

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
        dash_table.DataTable(
            id="commit_table",
            data=pd.DataFrame().to_dict("records"),
            page_current=0,
            page_size=10,
            sort_action="custom",
            sort_mode="single",
        ),
        dcc.Graph(id="benchmark_plot", figure={}),
        html.Div(
            [
                html.P(
                    "Suspect Commits",
                    style={
                        "display": "inline",
                        "margin-left": "30px",
                        "font-size": "20px",
                    },
                ),
                html.Div(
                    dash_table.DataTable(
                        id="pr_table",
                        data=pd.DataFrame().to_dict("records"),
                        page_current=0,
                        page_size=10,
                        sort_action="custom",
                        sort_mode="single",
                        columns=[
                            {"id": "Authors", "name": "Authors"},
                            {"id": "PR", "name": "PR", "presentation": "markdown"},
                        ],
                        style_table={"width": "60%", "margin": "auto"},
                    ),
                    style={
                        "width": "100%",
                        "margin-left": "auto",
                        "margin-right": "auto",
                        "margin-bottom": "30px",
                    },
                ),
                html.Div(
                    [
                        html.P(
                            "Title:",
                            style={
                                "width": "50px",
                                "margin-right": "10px",
                                "display": "inline",
                            },
                        ),
                        dcc.Input(
                            id="issue_title",
                            type="text",
                            size="80",
                            style={"display": "inline"},
                        ),
                    ],
                    style={"margin-bottom": "30px"},
                ),
                html.Div(
                    [
                        html.P(
                            "Body:",
                            style={
                                "width": "50px",
                                "margin-right": "10px",
                                "display": "inline",
                                "vertical-align": "top",
                            },
                        ),
                        dcc.Textarea(
                            id="issue_body",
                            value="",
                            style={"width": "60%", "height": 200},
                        ),
                    ],
                    style={"margin-bottom": "30px"},
                ),
                html.Div(
                    [
                        html.P(
                            "Labels:",
                            style={
                                "width": "50px",
                                "margin-right": "10px",
                                "display": "inline",
                            },
                        ),
                        dcc.Dropdown(
                            id="issue_labels",
                            options=labels,
                            multi=True,
                            style={"width": "900px"},
                        ),
                    ],
                    style={"margin-bottom": "30px"},
                ),
                html.Div(
                    [
                        html.P(
                            "Milestone:",
                            style={
                                "width": "50px",
                                "margin-right": "10px",
                                "display": "inline",
                            },
                        ),
                        dcc.Dropdown(
                            id="issue_milestone",
                            options=milestones,
                            multi=False,
                            style={"width": "150px"},
                        ),
                    ],
                    style={"margin-bottom": "30px"},
                ),
                html.P(
                    id="gh_cli_cmd",
                    children="",
                    style={"display": "none"},
                ),
                html.Div(
                    children=[
                        html.Div(
                            children=[
                                dcc.Markdown(
                                    id="github_comment",
                                    link_target="_blank",
                                )
                            ],
                            style={
                                "border": "2px black solid",
                                "border-radius": "25px",
                                "padding": "0px 30px 0px 30px",
                                "width": "50%",
                                "float": "left",
                                "display": "flex",
                                "align-items": "center",
                                "justify-content": "center",
                            },
                        ),
                        html.Div(
                            html.Button(
                                "Create GitHub Issue",
                                id="issue_generate",
                                n_clicks=0,
                            ),
                            style={
                                "width": "50%",
                                "float": "right",
                                "display": "flex",
                                "align-items": "center",
                                "justify-content": "center",
                            },
                        ),
                    ],
                    style={
                        "display": "flex",
                        "width": "80%",
                        "align-items": "center",
                        "justify-content": "center",
                    },
                ),
            ]
        ),
        dcc.ConfirmDialog(
            id="issue_confirm",
            message="Are you sure you want to create an issue?",
        ),
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
    Output("github_comment", "children"),
    Input("issue_body", "value"),
)
def update_copy_github_comment(issue_body):
    return issue_body


@app.callback(
    Output("pr_table", "data"),
    Input("summary", "active_cell"),
    Input("summary", "derived_viewport_data"),
)
def update_pr_table(active_cell, derived_viewport_data):
    if active_cell:
        git_hash = derived_viewport_data[active_cell["row"]]["git_hash"]
        commit_range = watcher.commit_range(git_hash)
        response = execute(
            f"cd /home/richard/dev/pandas"
            f" && git rev-list --ancestry-path {commit_range}"
        )
        commits = [e for e in response.split("\n") if e != ""]

        data = []
        for commit in commits:
            response = execute(
                f"cd /home/richard/dev/pandas"
                f" && gh pr list"
                f'    --search "{commit[:7]}"'
                f"    --state merged"
                f"    --json title,number,author"
            )
            titles = [e["title"] for e in json.loads(escape_ansi(response))]
            numbers = [e["number"] for e in json.loads(escape_ansi(response))]
            authors = [e["author"] for e in json.loads(escape_ansi(response))]
            authors = [e for e in authors if not e["is_bot"]]
            authors = [e["login"] for e in authors]
            assert len(titles) == 1, titles
            assert len(numbers) == 1, numbers
            repo_url = "https://github.com/pandas-dev/pandas"
            data.append(
                {
                    "Authors": ", ".join(authors),
                    "PR": f"[{titles[0]}]({repo_url}/pull/{numbers[0]})",
                }
            )
        return pd.DataFrame(data).to_dict("records")
    return pd.DataFrame().to_dict("records")


@app.callback(
    Output("issue_title", "value"),
    Output("issue_body", "value"),
    Output("issue_labels", "value"),
    Input("pr_table", "active_cell"),
    State("pr_table", "derived_viewport_data"),
    State("summary", "active_cell"),
    State("summary", "derived_viewport_data"),
    prevent_initial_call=True,
)
def update_issue_values(pr_cell, pr_table, summary_cell, summary_table):
    if pr_cell and summary_cell:
        git_hash = summary_table[summary_cell["row"]]["git_hash"]

        pr_link = pr_table[pr_cell["row"]]["PR"]
        idx = pr_link.rfind("/pull/")
        pr_number = pr_link[idx + len("/pull/") : -1]

        authors = pr_table[pr_cell["row"]]["Authors"]

        title = f"Potential regression induced by commit {git_hash[:7]}"
        body = watcher.generate_report(git_hash, pr_number, authors)
        return title, body, ["Performance", "Regression"]
    return "", "", ["Performance", "Regression"]


@app.callback(
    Output("gh_cli_cmd", "children"),
    Input("issue_title", "value"),
    Input("issue_body", "value"),
    Input("issue_labels", "value"),
    Input("issue_milestone", "value"),
    prevent_initial_call=True,
)
def update_gh_cli_cmd(issue_title, issue_body, issue_labels, issue_milestone):
    if not all(label in labels for label in issue_labels):
        return ""
    if issue_milestone not in milestones:
        return ""
    issue_labels = ",".join(issue_labels)
    assert '"' not in issue_title, issue_title
    assert '"' not in issue_body, issue_body
    assert '"' not in issue_labels, issue_labels
    assert '"' not in issue_milestone, issue_milestone
    result = (
        f"gh issue create"
        rf' --title "{issue_title}"'
        rf' --body "{issue_body}"'
        rf' --label "{issue_labels}"'
        rf' --milestone "{issue_milestone}"'
    )
    return result


@app.callback(
    Output("gh_cli_cmd", "children", allow_duplicate=True),
    Input("issue_confirm", "submit_n_clicks"),
    State("gh_cli_cmd", "children"),
    prevent_initial_call=True,
    allow_duplicate=True,
)
def generate_issue(submit_n_clicks, gh_cli_cmd):
    if gh_cli_cmd == "":
        return gh_cli_cmd
    execute(f"cd /home/richard/dev/pandas && {gh_cli_cmd}")
    # Hack because dash doesn't seem to let you have no output...
    return gh_cli_cmd


@app.callback(
    Output("issue_confirm", "message"),
    Output("issue_confirm", "displayed"),
    Input("issue_generate", "n_clicks"),
    State("gh_cli_cmd", "children"),
    prevent_initial_call=True,
)
def display_confirm(n_clicks, gh_cli_cmd):
    if gh_cli_cmd == "":
        return "", False
    message = f"Are you sure you want to create the following issue?\n\n{gh_cli_cmd}"
    return message, True


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

    return result[
        ["name", "params", "pct_change", "abs_change", "time", "revision"]
    ].to_dict("records")


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
    columns = [
        "revision",
        "date",
        "time",
        "established_best",
        "established_worst",
        "is_regression",
    ]
    plot_data = (
        benchmarks.loc[(name, params)]
        .drop(columns="time")
        .rename(columns={"time_value": "time"})
        .reset_index()[columns]
    )

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    for column in plot_data:
        if column in ["date", "is_regression", "revision"]:
            continue
        fig.add_trace(
            go.Scatter(
                x=plot_data.index,
                y=plot_data[column],
                name=column,
                visible=column in ["time"],
            ),
        )
    plot_data = plot_data[plot_data.is_regression]

    fig.add_trace(
        go.Scatter(
            x=plot_data.index,
            y=plot_data["time"],
            mode="markers",
            name="Regressions",
            hovertext=plot_data["date"].astype(str).tolist(),
            hoverinfo="text",
        )
    )
    fig.update_traces(
        marker={"size": 12, "line": {"width": 2, "color": "DarkSlateGrey"}},
        selector={"mode": "markers"},
    )
    return fig


if __name__ == "__main__":
    app.run(debug=True)
