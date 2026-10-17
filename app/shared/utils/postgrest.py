from typing import Any, cast


def as_row(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value)


def as_rows(value: object) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], value)
