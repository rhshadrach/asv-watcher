import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from asv_watcher import RollingDetector
from asv_watcher._core.parameters import ParameterCollection


def run(asv_collection_url):
    tmpdir = tempfile.TemporaryDirectory()
    cmd = f"cd {tmpdir.name} && git clone {asv_collection_url} --depth 1 asv_collection"
    import time

    timer = time.time()
    subprocess.run(cmd, shell=True, capture_output=True, check=True)
    print(time.time() - timer)
    benchmark_path = Path(tmpdir.name) / "asv_collection" / "pandas"
    index_path = benchmark_path / "index.json"
    benchmark_url_prefixes = determine_benchmark_prefixes(benchmark_path)
    with open(index_path) as f:
        index_data = json.load(f)
    processed_benchmarks = process_benchmarks(index_data, benchmark_url_prefixes)
    os.makedirs("../.cache/", exist_ok=True)
    processed_benchmarks.to_parquet("../.cache/benchmarks.parquet")


def determine_benchmark_prefixes(benchmark_path: Path) -> set[Path]:
    # TODO: Use index json graph_param_list
    paths = set()
    for path in (benchmark_path / "graphs").glob("**/*.json"):
        if "summary" in str(path):
            continue
        paths.add(path.parent)
    return paths


def process_benchmarks(
    index_data: dict[str, dict[str, Any]], benchmark_url_prefixes: set[Path]
) -> dict[tuple[str, str], pd.DataFrame]:
    benchmarks = index_data["benchmarks"]
    results = {}
    for name, benchmark in benchmarks.items():
        parameter_collection = ParameterCollection(
            benchmark["param_names"], benchmark["params"]
        )

        buffer = []
        for prefix in benchmark_url_prefixes:
            # TODO: Use Path object
            benchmark_path = f"{prefix}/{name}.json"
            try:
                with open(benchmark_path) as f:
                    buffer.append(json.load(f))
            except FileNotFoundError:
                # TODO: Why does this happen?
                # print(f"Error in reading {benchmark_path}")
                continue
        json_data = sum(buffer, [])
        if len(json_data) == 0:
            # TODO: Why does this happen?
            # print(benchmark, "has no data. Skipping.")
            continue

        revisions, times = list(zip(*json_data))

        data = []
        for revision, revision_times in zip(revisions, times):
            if revision_times is None:
                # TODO: Not sure why this happens...
                continue
            elif isinstance(revision_times, float):
                # Benchmark has no arguments
                revision_times = [revision_times]
            for param_combo, seconds in zip(
                parameter_collection._params, revision_times
            ):
                data_inner = param_combo.to_dict()
                data_inner["revision"] = str(revision)
                data_inner["time"] = seconds
                data.append(data_inner)
        if len(data) == 0:
            continue
        df = pd.DataFrame(data)
        df["commit_hash"] = df["revision"].map(index_data["revision_to_hash"])

        param_names = benchmark["param_names"]
        if len(param_names) > 0:
            keys = param_names if len(param_names) > 1 else param_names[0]
            for param_combo, d in df.groupby(keys):
                param_string = make_param_string(param_names, param_combo)
                results[name, param_string] = d
        else:
            results[name, ""] = df

    data = {k: v[["revision", "time", "commit_hash"]] for k, v in results.items()}
    data = pd.concat(data).rename(columns={"commit_hash": "hash"}).droplevel(-1)
    data.index.names = ["name", "params"]
    data["revision"] = data["revision"].astype(int)
    data = data.set_index("revision", append=True).sort_index()
    # I think this is due to different dependencies. We should maybe have
    # dependencies as part of the index
    result = data.groupby(["name", "params", "revision"]).agg(
        {"time": "mean", "hash": "first"}
    )

    detector = RollingDetector(window_size=30)
    result = detector.detect_regression(result)

    return result


def make_param_string(
    param_names: list[str], param_combo: str | list[str] | tuple[str]
) -> str:
    if not isinstance(param_combo, (list, tuple)):
        param_combo = [param_combo]
    result = "; ".join(
        [f"{name}={value}" for name, value in zip(param_names, param_combo)]
    )
    return result


if __name__ == "__main__":
    import time

    timer = time.time()
    run("https://github.com/asv-runner/asv-collection.git")
    print(time.time() - timer)
