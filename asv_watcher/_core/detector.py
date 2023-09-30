from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from asv_watcher._core.regression import Regression


class Detector(ABC):
    @abstractmethod
    def detect_regression(self, data: pd.DataFrame) -> Regression | None:
        raise NotImplementedError


class RollingDetector(Detector):
    def __init__(self, *, window_size: int):
        self._window_size = window_size

    def detect_regression(self, data: pd.DataFrame):
        data = data[data.time.notnull()].copy()
        keys = ["name", "params"]
        gb = data.groupby(keys)
        tol = 0.95

        data["established_worst"] = (
            data.groupby(keys, as_index=False)["time"]
            .rolling(self._window_size, center=True)
            .max()[["time"]]
        )
        data["established_best"] = (
            data.groupby(keys, as_index=False)["time"]
            .rolling(self._window_size, center=True)
            .min()[["time"]]
        )
        data["established_worst_cummin"] = gb["established_worst"].cummin()
        data["established_best_cummin_rev"] = (
            data["established_best"][::-1].groupby(keys).cummin()[::-1]
        )

        mask = (
            data["established_worst_cummin"] < tol * data["established_best_cummin_rev"]
        )
        mask = mask & ~mask.groupby(keys).shift(1, fill_value=False)
        mask = mask.groupby(keys).shift(-(self._window_size - 1) // 2, fill_value=False)

        data["is_regression"] = mask
        data["pct_change"] = data.groupby(keys).time.pct_change()
        data["abs_change"] = data.time - data.groupby(keys).time.shift(1)
        return data

    # # TODO: Detect multiple regressions
    # def detect_regression(
    #     self, asv_name: str, asv_params: str, data: pd.DataFrame
    # ) -> Regression | None:
    #     data["revision"] = data["revision"].astype(int)
    #     data = data.sort_values("revision")
    #     times = data["time"].dropna()
    #     established_worst = (
    #         times.rolling(self._window_size, center=True)
    #         .max()
    #         .rename("established_worst")
    #     )
    #     established_best = (
    #         times.rolling(self._window_size, center=True)
    #         .min()
    #         .rename("established_best")
    #     )
    #     established_worst_cummin = established_worst.cummin().rename(
    #         "established_worst_cummin"
    #     )
    #     established_best_cummin_rev = (
    #         established_best[::-1].cummin()[::-1].rename("established_best_cummin_rev")
    #     )
    #     established_best_shifted = established_best.shift(
    #         -self._window_size // 2 - 1
    #     ).rename("established_best_shifted")
    #
    #     if (established_worst_cummin < 0.9 * established_best_cummin_rev).any():
    #         loc = (
    #             (established_worst_cummin < 0.9 * times)
    #             & (established_worst_cummin < 0.9 * established_best_shifted)
    #         ).idxmax()
    #         offending_hash = data.loc[loc].commit_hash
    #         good_hash = data.shift(1).loc[loc].commit_hash
    #         pct_change = data["time"].loc[loc] / data["time"].shift(1).loc[loc]
    #         abs_change = data["time"].loc[loc] - data["time"].shift(1).loc[loc]
    #         plot_data = (
    #             pd.concat(
    #                 [
    #                     data["time"],
    #                     data["revision"],
    #                     established_worst,
    #                     established_best,
    #                     established_worst_cummin,
    #                     established_best_cummin_rev,
    #                     established_best_shifted,
    #                 ],
    #                 axis=1,
    #             )
    #             .reset_index(drop=True)
    #             .set_index("revision")
    #         )
    #         result = Regression(
    #             asv_name,
    #             asv_params,
    #             data,
    #             offending_hash,
    #             good_hash,
    #             pct_change,
    #             abs_change,
    #             plot_data,
    #         )
    #     else:
    #         result = None
    #     return result
