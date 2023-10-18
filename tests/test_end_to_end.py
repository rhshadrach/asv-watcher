import os
from pathlib import Path

import pandas as pd
import pytest

from asv_watcher._core.update_data import process_benchmarks


@pytest.mark.parametrize("window_size", [5, 6])
def test_end_to_end(window_size):
    benchmark_path = Path(os.path.dirname(__file__)) / "data"
    summary = process_benchmarks(benchmark_path, window_size=window_size)
    result = summary[summary.is_regression][[]]
    expected = pd.DataFrame(
        {
            "name": [
                "benchmarks.Benchmark.time_standard_regression",
                "benchmarks.BenchmarkWithParameter.time_standard_regression_parametrized",
                "benchmarks.BenchmarkWithParameter.time_standard_regression_parametrized",
            ],
            "params": ["", "x=0.001", "x=0.002"],
            "date": pd.to_datetime("2023-01-28 21:14:40"),
            "revision": 22,
        }
    ).set_index(["name", "params", "date", "revision"])
    pd.testing.assert_frame_equal(result, expected)
