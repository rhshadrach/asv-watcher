from __future__ import annotations

import itertools as it
import json
import urllib

import matplotlib.pyplot as plt
import pandas as pd
from tqdm.notebook import tqdm

from asv_watcher._core.regression import Regression


class Watcher:
    def __init__(self, detector, index_path, benchmark_url_prefixes):
        self._detector = detector
        self._index_path = index_path
        self._benchmark_url_prefixes = benchmark_url_prefixes
        self._index_data = read_json(self._index_path)
        self._hash_to_revision = {
            v: k for k, v in self._index_data["revision_to_hash"].items()
        }

        subset = {}
        for k, (key, value) in enumerate(self._index_data["benchmarks"].items()):
            if k >= 20:
                break
            subset[key] = value

        self._processed_benchmarks = self.process_benchmarks(
            self._index_data["benchmarks"]
        )
        self._mapper = self._identify_regressions(self._processed_benchmarks)

    def download_index_data(self):
        self._index_data = read_json(self._index_url)
        self._hash_to_revision = {
            v: k for k, v in self._index_data["revision_to_hash"].items()
        }

    def process_benchmarks(self, benchmarks):
        results = {}
        for benchmark in tqdm(benchmarks):
            param_names = benchmarks[benchmark]["param_names"]
            params = benchmarks[benchmark]["params"]
            param_combos = [
                dict(zip(param_names, values)) for values in it.product(*params)
            ]

            buffer = []
            for prefix in self._benchmark_url_prefixes:
                benchmark_path = f"{prefix}/{benchmark}.json"
                try:
                    buffer.append(read_json(benchmark_path))
                except FileNotFoundError:
                    print(f"Error in reading {benchmark_path}")
                    continue
            benchmark_json_data = sum(buffer, [])
            if len(benchmark_json_data) == 0:
                print(benchmark, "has no data. Skipping.")
                continue

            revisions, times = list(zip(*benchmark_json_data))

            data = []
            for revision, revision_times in zip(revisions, times):
                if revision_times is None:
                    # Not sure why this happens...
                    continue
                elif isinstance(revision_times, float):
                    # Benchmark has no arguments
                    revision_times = [revision_times]
                for param_combo, time in zip(param_combos, revision_times):
                    data_inner = param_combo.copy()
                    data_inner["revision"] = str(revision)
                    data_inner["time"] = time
                    data.append(data_inner)
            if len(data) == 0:
                print(benchmark, "has no data2. Skipping.")
                continue
            df = pd.DataFrame(data)
            df["commit_hash"] = df["revision"].map(self._index_data["revision_to_hash"])

            param_combos = []
            if len(param_names) > 0:
                keys = param_names if len(param_names) > 1 else param_names[0]
                for param_combo, d in df.groupby(keys):
                    param_string = make_param_string(param_names, param_combo)
                    # d = add_established_best_worst(d)
                    results[benchmark, param_string] = d
            else:
                # df = add_established_best_worst(df)
                results[benchmark, ""] = df

        return results

    def _identify_regressions(self, data):
        result = {}
        for (name, asv_params), data in data.items():
            regression = self._detector.detect_regression(name, asv_params, data)
            if regression is not None:
                result[regression._bad_hash] = result.get(regression._bad_hash, []) + [
                    regression
                ]
        return result

    def identify_regressions(self, ignored_hashes: dict[str:str]):
        result = {k: v for k, v in self._mapper.items() if k not in ignored_hashes}
        return result

    def generate_report(self, regressions: list[Regression]):
        for_report = {}
        for regression in regressions:
            for_report[regression._asv_name] = for_report.get(
                regression._asv_name, []
            ) + [regression._asv_params]

        print(
            "This patch may have induced a potential regression. "
            "Please check the links below. If any ASVs are parameterized, "
            "the combinations of parameters that a regression has been detected "
            "appear as subbullets. This is a partially automated message.\n"
        )

        print(
            "Subsequent benchmarks may have skipped some commits. See the link"
            " below to see which commits are"
            " between the two benchmark runs where the regression was identified.\n"
        )

        offending_hash = regressions[0]._bad_hash
        good_hash = regressions[0]._good_hash
        base_url = "https://github.com/pandas-dev/pandas/compare/"
        url = f"{base_url}{good_hash}...{offending_hash}"
        print(url)
        print()

        for benchmark, param_combos in for_report.items():
            base_url = "https://asv-runner.github.io/asv-collection/pandas/#"
            print(f" - [{benchmark}]({url})")
            for params in param_combos:
                if params == "":
                    continue
                params_list = [param for param in params.split("; ")]
                params_suffix = "?p-" + "&p-".join(params_list)
                url = f"{base_url}{benchmark}{params_suffix}"
                url = urllib.parse.quote(url, safe="/:?=&#")
                print("   -", f"[{params}]({url})")

        print()
        print("---")
        print()

        base_url = "https://github.com/pandas-dev/pandas/compare/"
        for regression in regressions:
            key = regression._asv_name, regression._asv_params
            self.plot_benchmarks(key[0], key[1], regression._plot_data)
            offending_hash = regression._bad_hash
            good_hash = regression._good_hash
            url = f"{base_url}{good_hash}...{offending_hash}"
            print(url)
            print()

    def plot_benchmarks(self, benchmark, param_combo, plot_data):
        params_list = [param for param in param_combo.split("; ")]
        params_suffix = "?p-" + "&p-".join(params_list)
        base_url = "https://asv-runner.github.io/asv-collection/pandas/#"
        url = f"{base_url}{benchmark}{params_suffix}"
        url = urllib.parse.quote(url, safe="/:?=&#")
        print(url)
        plot_data.plot()
        plt.show()


def read_json(path):
    with open(path) as f:
        result = json.load(f)
    return result


def make_param_string(param_names, param_combo):
    if not isinstance(param_combo, (list, tuple)):
        param_combo = [param_combo]
    return "; ".join(
        [f"{name}={value}" for name, value in zip(param_names, param_combo)]
    )
