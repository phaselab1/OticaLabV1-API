from typing import Any, cast


def as_row(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value)
