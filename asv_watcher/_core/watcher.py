from __future__ import annotations

import urllib
from pathlib import Path

import pandas as pd

BASEDIR = (Path(__file__) / ".." / ".." / "..").resolve(strict=True)


class Watcher:
    def __init__(
        self,
    ) -> None:
        self._data = pd.read_parquet(BASEDIR / ".cache" / "benchmarks.parquet")

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
