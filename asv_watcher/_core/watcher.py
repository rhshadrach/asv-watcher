from __future__ import annotations

import json
import urllib
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from asv_watcher._core.regression import Regression

BASEDIR = (Path(__file__) / ".." / ".." / "..").resolve(strict=True)


class Watcher:
    def __init__(
        self,
    ) -> None:
        self._data = pd.read_parquet(BASEDIR / ".cache" / "benchmarks.parquet")

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
