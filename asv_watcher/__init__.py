from asv_watcher._core.detector import RollingDetector
from asv_watcher._core.watcher import Watcher

__all__ = ["RollingDetector", "Watcher"]


def git_commit_link(git_hash):
    print(f'https://github.com/pandas-dev/pandas/commit/{git_hash}')
