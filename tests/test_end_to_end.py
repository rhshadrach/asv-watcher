import os

import pandas as pd
import pytest

from asv_watcher._core.detector import RollingDetector
from asv_watcher._core.watcher import Watcher


@pytest.mark.parametrize("window_size", [5, 6])
def test_end_to_end(window_size):
    detector = RollingDetector(window_size=window_size)
    benchmark_path = os.path.join(os.path.dirname(__file__), "data")
    watcher = Watcher(detector=detector, benchmark_path=benchmark_path)

    summary = watcher.summary()
    result = summary[summary.is_regression][[]]
    expected = pd.DataFrame(
        {
            "name": [
                "benchmarks.Benchmark.time_standard_regression",
                "benchmarks.BenchmarkWithParameter.time_standard_regression_parametrized",
                "benchmarks.BenchmarkWithParameter.time_standard_regression_parametrized",
            ],
            "params": ["", "x=0.001", "x=0.002"],
            "revision": 22,
        }
    ).set_index(["name", "params", "revision"])
    pd.testing.assert_frame_equal(result, expected)
