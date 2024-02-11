from __future__ import annotations

import pandas as pd

from asv_watcher._core.detector import RollingDetector
from asv_watcher._core.watcher import Watcher

pd.options.mode.copy_on_write = True

__all__ = ["RollingDetector", "Watcher"]


def git_commit_link(git_hash):
    print(f"https://github.com/pandas-dev/pandas/commit/{git_hash}")
