from __future__ import annotations


def time_to_str(x: float) -> str:
    is_negative = x < 0.0
    if x >= 1.0:
        result = f"{x : 0.3f}s"
    elif x >= 0.001:
        result = f"{x * 1000 : 0.3f}ms"
    elif x >= 0.000001:
        result = f"{x * (1000 ** 2) : 0.3f}us"
    else:
        result = f"{x * (1000 ** 3) : 0.3f}ns"
    # TODO: Why does the result of the f-string have a leading space?
    result = result.strip(" ")
    if is_negative:
        result = "-" + result
    return result
