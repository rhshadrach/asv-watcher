from __future__ import annotations

import pandas as pd

from asv_watcher._core.regression import Regression


class Detector:
    pass


class RollingDetector(Detector):
    def __init__(self, *, window_size: int):
        self._window_size = window_size

    # TODO: Detect multiple regressions
    def detect_regression(
        self, asv_name: str, asv_params: str, data: pd.DataFrame
    ) -> Regression | None:
        data["revision"] = data["revision"].astype(int)
        data = data.sort_values("revision")
        times = data["time"].dropna()
        established_worst = (
            times.rolling(self._window_size, center=True)
            .max()
            .rename("established_worst")
        )
        established_best = (
            times.rolling(self._window_size, center=True)
            .min()
            .rename("established_best")
        )
        established_worst_cummin = established_worst.cummin().rename(
            "established_worst_cummin"
        )
        established_best_cummin_rev = (
            established_best[::-1].cummin()[::-1].rename("established_best_cummin_rev")
        )
        established_best_shifted = established_best.shift(
            -self._window_size // 2 - 1
        ).rename("established_best_shifted")

        if (established_worst_cummin < 0.9 * established_best_cummin_rev).any():
            loc = (
                (established_worst_cummin < 0.9 * times)
                & (established_worst_cummin < 0.9 * established_best_shifted)
            ).idxmax()
            offending_hash = data.loc[loc].commit_hash
            good_hash = data.shift(1).loc[loc].commit_hash
            plot_data = (
                pd.concat(
                    [
                        data["time"],
                        data["revision"],
                        established_worst,
                        established_best,
                        established_worst_cummin,
                        established_best_cummin_rev,
                        established_best_shifted,
                    ],
                    axis=1,
                )
                .reset_index(drop=True)
                .set_index("revision")
            )
            result = Regression(
                asv_name, asv_params, data, offending_hash, good_hash, plot_data
            )
        else:
            result = None
        return result
