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
        self._regressions = self._data[self._data.is_regression]

    def benchmarks(self):
        return self._data

    def regressions(self):
        return self._regressions

    def commit_range(self, git_hash: str) -> str:
        """Get commit range between a hash and the previous hash that has a benchmark.

        Args:
            git_hash: Hash of a commit. This must be from a commit that has a
                regression.

        Returns:
            The commit range in the form of "{prev_git_hash}...{git_hash}" from the
            previous commit that has a benchmark to the provided git_hash.
        """
        # TODO: Error checking if git_hash is here and list is non-empty
        # We're interested in the hashes, so just grab a single benchmark to get
        # the time series.
        benchmark = (
            self._regressions[self._regressions["git_hash"].eq(git_hash)]
            .droplevel(["revision"])
            .index.tolist()
        )[0]
        time_series = self._data.loc[benchmark]
        prev_git_hash = time_series.shift(1)[
            time_series.git_hash == git_hash
        ].git_hash.iloc[0]
        result = f"{prev_git_hash}...{git_hash}"
        return result

    def generate_report(self, git_hash: str, pr: str, authors: str) -> str:
        """Generate a regression report.

        Args:
            git_hash: git hash of the commit with a regression.
            pr: PR number of the commit.
            authors: List of authors in the form "author1, author2, ...".

        Returns:
            A detailed regression report.
        """
        regressions = self.regressions()
        regressions = regressions[regressions["git_hash"].eq(git_hash)]

        result = ""
        result += (
            f"PR #{pr} may have induced a performance regression. "
            "If it was a necessary behavior change, this may have been "
            "expected and everything is okay."
            "\n\n"
            "Please check the links below. If any ASVs are parameterized, "
            "the combinations of parameters that a regression has been detected "
            "for appear as subbullets."
            "\n\n"
        )

        for idx, regression in regressions.iterrows():
            benchmark, params = idx[0], idx[1]
            base_url = "https://asv-runner.github.io/asv-collection/pandas/#"
            url = f"{base_url}{benchmark}"
            severity = f"{regression['pct_change']} ({regression['abs_change']})"
            result += f" - [ ] [{benchmark}]({url})"
            if params == "":
                result += f" - {severity}\n"
                continue
            result += "\n"
            params_list = [param for param in params.split("; ")]
            params_suffix = "?p-" + "&p-".join(params_list)
            url = f"{base_url}{benchmark}{params_suffix}"
            url = urllib.parse.quote(url, safe="/:?=&#")
            result += f"   - [ ] [{params}]({url}) - {severity}\n"
        result += "\n"

        result += (
            "Subsequent benchmarks may have skipped some commits. The link"
            " below lists the commits that are"
            " between the two benchmark runs where the regression was identified."
            "\n\n"
        )

        base_url = "https://github.com/pandas-dev/pandas/compare/"
        result += f"[Commit Range]({base_url + self.commit_range(git_hash)})"
        result += "\n\n"
        result += "cc @" + ", @".join(authors.split(", ")) + "\n"

        return result
