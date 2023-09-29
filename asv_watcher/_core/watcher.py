from __future__ import annotations

import json
import urllib
from pathlib import Path
from typing import Any

import pandas as pd

from asv_watcher._core.detector import Detector
from asv_watcher._core.parameters import ParameterCollection
from asv_watcher._core.regression import Regression


class Watcher:
    def __init__(
        self,
        detector: Detector,
        benchmark_path: str,
        ignored_hashes: dict[str, str] | None = None,
    ) -> None:
        self._detector = detector
        self._benchmark_path = Path(benchmark_path)
        self._ignored_hashes = {} if ignored_hashes is None else ignored_hashes.copy()
        self._index_path = self._benchmark_path / "index.json"
        self._benchmark_url_prefixes = self._determine_benchmark_prefixes()
        with open(self._index_path) as f:
            self._index_data = json.load(f)
        self._revision_to_hash = self._index_data["revision_to_hash"]
        self._hash_to_revision = {v: k for k, v in self._revision_to_hash.items()}
        self._processed_benchmarks = self._process_benchmarks(
            self._index_data["benchmarks"]
        )
        self._data = self._detector.detect_regression(self._processed_benchmarks)

    def _determine_benchmark_prefixes(self) -> set[str]:
        # TODO: Use index json graph_param_list
        paths = set()
        for path in (self._benchmark_path / "graphs").glob("**/*.json"):
            if "summary" in str(path):
                continue
            paths.add(path.parent)
        return paths

    def _process_benchmarks(
        self, benchmarks: dict[str, dict[str, Any]]
    ) -> dict[tuple[str, str], pd.DataFrame]:
        results = {}
        count = 0
        for name, benchmark in benchmarks.items():
            count += 1
            if count > 800:
                break
            parameter_collection = ParameterCollection(
                benchmark["param_names"], benchmark["params"]
            )

            buffer = []
            for prefix in self._benchmark_url_prefixes:
                # TODO: Use Path object
                benchmark_path = f"{prefix}/{name}.json"
                try:
                    with open(benchmark_path) as f:
                        buffer.append(json.load(f))
                except FileNotFoundError:
                    print(f"Error in reading {benchmark_path}")
                    continue
            json_data = sum(buffer, [])
            if len(json_data) == 0:
                print(benchmark, "has no data. Skipping.")
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
                for param_combo, time in zip(
                    parameter_collection._params, revision_times
                ):
                    data_inner = param_combo.to_dict()
                    data_inner["revision"] = str(revision)
                    data_inner["time"] = time
                    data.append(data_inner)
            if len(data) == 0:
                continue
            df = pd.DataFrame(data)
            df["commit_hash"] = df["revision"].map(self._index_data["revision_to_hash"])

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

        return result

    def _identify_regressions(
        self, data: dict[tuple[str, str], pd.DataFrame]
    ) -> dict[str, list[Regression]]:
        result = {}
        for (name, asv_params), df in data.items():
            regression = self._detector.detect_regression(name, asv_params, df)
            if (
                regression is not None
                and regression._bad_hash not in self._ignored_hashes
            ):
                result[regression._bad_hash] = result.get(regression._bad_hash, []) + [
                    regression
                ]
        return result

    def summary(self):
        return self._data

    def commit_range(self, hash):
        # TODO: Error checking if hash is here and list is non-empty
        regression = self.get_regressions(hash)[0]
        time_series = self._data.loc[regression]
        prev_hash = time_series.shift(1)[time_series.hash == hash].hash.iloc[0]
        base_url = "https://github.com/pandas-dev/pandas/compare/"
        url = f"{base_url}{prev_hash}...{hash}"
        return url

    def get_regressions(self, hash: str):
        result = (
            self._data[self._data["hash"].eq(hash) & self._data.is_regression]
            .droplevel("revision")
            .index.tolist()
        )
        return result

    def generate_report(self, hash: str) -> str:
        regressions = self.get_regressions(hash)
        for_report = {}
        for regression in regressions:
            for_report[regression[0]] = for_report.get(regression[0], []) + [
                regression[1]
            ]

        result = ""
        result += (
            "This patch may have induced a potential regression. "
            "Please check the links below. If any ASVs are parameterized, "
            "the combinations of parameters that a regression has been detected "
            "appear as subbullets. This is a partially automated message.\n\n"
            "\n"
        )

        result += (
            "Subsequent benchmarks may have skipped some commits. See the link"
            " below to see which commits are"
            " between the two benchmark runs where the regression was identified.\n\n"
            "\n"
        )

        result += self.commit_range(hash)
        result += "\n"

        for benchmark, param_combos in for_report.items():
            base_url = "https://asv-runner.github.io/asv-collection/pandas/#"
            url = f"{base_url}{benchmark}"
            result += f" - [{benchmark}]({url})\n"
            for params in param_combos:
                if params == "":
                    continue
                params_list = [param for param in params.split("; ")]
                params_suffix = "?p-" + "&p-".join(params_list)
                url = f"{base_url}{benchmark}{params_suffix}"
                url = urllib.parse.quote(url, safe="/:?=&#")
                result += f"   - [{params}]({url})\n"

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
