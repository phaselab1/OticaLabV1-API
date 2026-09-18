LOWERCASE_WORDS = {
    "de",
    "da",
    "do",
    "das",
    "dos",
    "e",
    "em",
    "na",
    "no",
    "nas",
    "nos",
    "a",
    "o",
    "as",
    "os",
    "para",
    "por",
    "com",
}


def format_title_case(text: str | None) -> str:
    if not text:
        return ""
    words = text.strip().split()
    if not words:
        return ""

    result: list[str] = []
    for idx, word in enumerate(words):
        cleaned = word.lower()
        if idx > 0 and cleaned in LOWERCASE_WORDS:
            result.append(cleaned)
        else:
            result.append(cleaned.capitalize())

    return " ".join(result)
