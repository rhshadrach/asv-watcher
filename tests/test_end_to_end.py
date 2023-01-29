import os

from asv_watcher._core.detector import RollingDetector
from asv_watcher._core.watcher import Watcher


def test_end_to_end():
    detector = RollingDetector(window_size=5)
    index_path = os.path.join(os.path.dirname(__file__), "data", "index.json")

    # TODO: Use index json graph_param_list
    import glob
    import os

    paths = set()
    for e in glob.glob(
        "data/graphs/**",
        recursive=True,
    ):
        if "summary" in e:
            continue
        if not e.endswith(".json"):
            continue
        paths.add(os.path.split(e)[0])

    benchmark_url_prefixes = tuple(paths)
    watcher = Watcher(
        detector=detector,
        index_path=index_path,
        benchmark_url_prefixes=benchmark_url_prefixes,
    )

    regressions = watcher.identify_regressions(ignored_hashes={})
    assert len(regressions) == 1
    results = regressions[next(iter(regressions.keys()))]
    for result in results:
        revision = watcher._hash_to_revision[result._bad_hash]
        assert revision == "22"
