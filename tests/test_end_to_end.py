import os

from asv_watcher._core.detector import RollingDetector
from asv_watcher._core.watcher import Watcher


def test_end_to_end():
    detector = RollingDetector(window_size=5)
    benchmark_path = os.path.join(os.path.dirname(__file__), "data")
    watcher = Watcher(detector=detector, benchmark_path=benchmark_path)

    regressions = watcher._mapper
    assert len(regressions) == 1
    results = regressions[next(iter(regressions.keys()))]
    for result in results:
        revision = watcher._hash_to_revision[result._bad_hash]
        assert revision == "22"
