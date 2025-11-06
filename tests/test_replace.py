from omnote.replace import replace_all_case_insensitive


def test_replace_all_basic():
    text, n = replace_all_case_insensitive("hello world, hello!", "hello", "yo")
    assert text == "yo world, yo!"
    assert n == 2


def test_replace_all_case_insensitive():
    text, n = replace_all_case_insensitive("HeLLo hElLo", "hello", "x")
    assert text == "x x"
    assert n == 2


def test_replace_all_noop_on_empty_needle():
    text, n = replace_all_case_insensitive("abc", "", "x")
    assert text == "abc" and n == 0
