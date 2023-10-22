from __future__ import annotations

import urllib.parse
from pathlib import Path

import pandas as pd

BASEDIR = (Path(__file__) / ".." / ".." / "..").resolve(strict=True)


class Watcher:
    def __init__(
        self,
    ) -> None:
        self._data = pd.read_parquet(BASEDIR / ".cache" / "benchmarks.parquet")
        self._regressions = self._data[self._data.is_regression].copy()

    def benchmarks(self):
        return self._data

    def regressions(self):
        return self._regressions

    def commit_range(self, git_hash):
        # TODO: Error checking if git_hash is here and list is non-empty
        regression = self.get_regressions(git_hash)[0]
        time_series = self._data.loc[regression]
        prev_git_hash = time_series.shift(1)[
            time_series.git_hash == git_hash
        ].git_hash.iloc[0]
        base_url = "https://github.com/pandas-dev/pandas/compare/"
        url = f"{base_url}{prev_git_hash}...{git_hash}"
        return url

    def get_regressions(self, git_hash: str) -> list[tuple[str, str]]:
        result = (
            self._regressions[self._regressions["git_hash"].eq(git_hash)]
            .droplevel(["revision"])
            .index.tolist()
        )
        return result

    def generate_report(self, git_hash: str) -> str:
        regressions = self.get_regressions(git_hash)
        for_report: dict[str, list[str]] = {}
        for regression in regressions:
            for_report[regression[0]] = for_report.get(regression[0], []) + [
                regression[1]
            ]

        result = ""
        result += (
            "This patch may have induced a performance regression. "
            "If it was a necessary behavior change, this may have been "
            "expected and everything is okay."
            "\n\n"
            "Please check the links below. If any ASVs are parameterized, "
            "the combinations of parameters that a regression has been detected "
            "for appear as subbullets."
            "\n\n"
        )

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
        result += "\n"

        result += (
            "Subsequent benchmarks may have skipped some commits. The link"
            " below lists the commits that are"
            " between the two benchmark runs where the regression was identified."
            "\n\n"
        )

        result += self.commit_range(git_hash)
        result += "\n"

        return result
