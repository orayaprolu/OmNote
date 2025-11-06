from __future__ import annotations


def replace_all_case_insensitive(text: str, needle: str, repl: str) -> tuple[str, int]:
    """
    Replace all case-insensitive occurrences of `needle` in `text` with `repl`.

    Returns:
        (new_text, count_replaced)
    """
    if not needle:
        return text, 0
    # Deterministic loop without regex to keep behavior obvious.
    t_lower = text.lower()
    n_lower = needle.lower()
    out: list[str] = []
    i = 0
    count = 0
    n = len(n_lower)
    while i < len(text):
        if t_lower[i : i + n] == n_lower:
            out.append(repl)
            i += n
            count += 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out), count
