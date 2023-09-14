from __future__ import annotations

import pandas as pd


class Regression:
    def __init__(
        self,
        asv_name: str,
        asv_params: str,
        data: pd.DataFrame,
        bad_hash: str,
        good_hash: str,
        pct_change: float,
        abs_change: float,
        plot_data: pd.DataFrame,
    ):
        self._asv_name = asv_name
        self._asv_params = asv_params
        self._data = data
        self._bad_hash = bad_hash
        self._good_hash = good_hash
        self._pct_change = pct_change
        self._abs_change = abs_change
        self._plot_data = plot_data
