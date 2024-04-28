import os
from pathlib import Path

import pandas as pd
import pytest

from asv_watcher import Watcher


def test_commit_range():
    watcher = Watcher.__new__(Watcher)
    watcher._data = pd.DataFrame(
        {
            "name": "benchmark",
            "params": "",
            "revision": [0, 1, 2],
            "git_hash": ["a0", "a1", "a2"],
            "is_regression": [True, False, True]
        }
    ).set_index(["name", "params", "revision"])
    watcher._regressions = watcher._data[watcher._data.is_regression]
    expected = "a1...a2"
    result = watcher.commit_range(git_hash="a2")
    assert result == expected, f"{result=} vs {expected=}"
