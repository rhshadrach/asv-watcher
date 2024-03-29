from __future__ import annotations

import itertools as it


class Parameters:
    def __init__(self, names: list[str], values: tuple[str]):
        self._names = names
        self._values = values

    def to_dict(self) -> dict[str, str]:
        result = dict(zip(self._names, self._values))
        return result


class ParameterCollection:
    def __init__(self, names: list[str], values: list[str]):
        self._params = [
            # mypy doesn't understand that v is a tuple of strings
            Parameters(names, v)  # type: ignore[arg-type]
            for v in it.product(*values)
        ]
