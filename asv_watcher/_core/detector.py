from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Detector(ABC):
    @abstractmethod
    def detect_regression(self, data: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError


class RollingDetector(Detector):
    def __init__(self, *, window_size: int):
        self._window_size = window_size

    def detect_regression(self, data: pd.DataFrame) -> pd.DataFrame:
        data = data[data.time.notnull()].sort_values("revision")
        keys = ["name", "params"]
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

        mask = (
            # TODO: is the arg to shift right?
            data["established_worst"].groupby(keys).shift(self._window_size)
            < tol * data["established_best"]
        )
        mask = mask & ~mask.groupby(keys).shift(1, fill_value=False)
        mask = mask.groupby(keys).shift(-(self._window_size - 1) // 2, fill_value=False)

        data["is_regression"] = mask
        data["pct_change"] = data.groupby(keys).time.pct_change()
        data["abs_change"] = data.time - data.groupby(keys).time.shift(1)
        return data
