"""Tests for find/replace logic.

These tests verify the core replace algorithms using pure Python,
independent of GTK TextBuffer. The actual GTK integration is tested
via smoke tests with Xvfb.
"""
from __future__ import annotations


def replace_current(text: str, selection_start: int, selection_end: int,
                    find_text: str, replace_text: str) -> tuple[str, int, int]:
    """
    Pure Python implementation of single replace logic.

    Mirrors the behavior of OmNoteWindow._replace_current_or_next():
    - If selection matches find_text (case-insensitive), replace it
    - Return new text and selection bounds around replacement

    Returns:
        (new_text, new_selection_start, new_selection_end)
    """
    selected = text[selection_start:selection_end]
    if selected.lower() == find_text.lower():
        # Perform replacement
        new_text = text[:selection_start] + replace_text + text[selection_end:]
        # Selection should cover the replacement text
        new_start = selection_start
        new_end = selection_start + len(replace_text)
        return new_text, new_start, new_end
    return text, selection_start, selection_end


def replace_all(text: str, find_text: str, replace_text: str) -> str:
    """
    Pure Python implementation of replace-all logic (case-insensitive).

    Mirrors the behavior of OmNoteWindow._replace_all().
    """
    if not find_text:
        return text

    result = []
    i = 0
    find_lower = find_text.lower()
    text_lower = text.lower()

    while i < len(text):
        if text_lower[i:i + len(find_text)] == find_lower:
            result.append(replace_text)
            i += len(find_text)
        else:
            result.append(text[i])
            i += 1

    return "".join(result)


class TestReplaceCurrentSelection:
    """Tests for single replacement at current selection."""

    def test_replace_exact_match(self):
        """Replace when selection exactly matches find text."""
        text = "Hello world, hello universe"
        # Selection is "Hello" (0-5)
        new_text, start, end = replace_current(text, 0, 5, "Hello", "Hi")
        assert new_text == "Hi world, hello universe"
        assert start == 0
        assert end == 2  # "Hi" is 2 chars

    def test_replace_case_insensitive(self):
        """Replace matches case-insensitively."""
        text = "Hello world"
        new_text, start, end = replace_current(text, 0, 5, "hello", "Hi")
        assert new_text == "Hi world"
        assert start == 0
        assert end == 2

    def test_no_replace_when_selection_differs(self):
        """No replacement when selection doesn't match find text."""
        text = "Hello world"
        # Selection is "world" but we're looking for "Hello"
        new_text, start, end = replace_current(text, 6, 11, "Hello", "Hi")
        assert new_text == "Hello world"  # Unchanged
        assert start == 6
        assert end == 11

    def test_replace_with_longer_text(self):
        """Replace with longer replacement text."""
        text = "Hi there"
        new_text, start, end = replace_current(text, 0, 2, "Hi", "Hello")
        assert new_text == "Hello there"
        assert start == 0
        assert end == 5

    def test_replace_with_empty_string(self):
        """Replace with empty string (deletion)."""
        text = "Hello world"
        new_text, start, end = replace_current(text, 0, 6, "Hello ", "")
        assert new_text == "world"
        assert start == 0
        assert end == 0

    def test_replace_in_middle(self):
        """Replace text in middle of document."""
        text = "The quick brown fox"
        # Select "quick" (4-9)
        new_text, start, end = replace_current(text, 4, 9, "quick", "slow")
        assert new_text == "The slow brown fox"
        assert start == 4
        assert end == 8

    def test_selection_bounds_after_replace(self):
        """After replacement, selection covers exactly the new text."""
        text = "abc def ghi"
        new_text, start, end = replace_current(text, 4, 7, "def", "REPLACED")
        assert new_text == "abc REPLACED ghi"
        # Selection should be around "REPLACED"
        assert new_text[start:end] == "REPLACED"


class TestReplaceAll:
    """Tests for replace-all functionality."""

    def test_replace_all_occurrences(self):
        """Replace all occurrences of find text."""
        text = "hello world hello universe hello"
        result = replace_all(text, "hello", "hi")
        assert result == "hi world hi universe hi"

    def test_replace_all_case_insensitive(self):
        """Replace all matches case-insensitively."""
        text = "Hello HELLO hello HeLLo"
        result = replace_all(text, "hello", "hi")
        assert result == "hi hi hi hi"

    def test_replace_all_no_matches(self):
        """Return unchanged text when no matches."""
        text = "Hello world"
        result = replace_all(text, "foo", "bar")
        assert result == "Hello world"

    def test_replace_all_empty_find(self):
        """Empty find text returns unchanged."""
        text = "Hello world"
        result = replace_all(text, "", "bar")
        assert result == "Hello world"

    def test_replace_all_with_empty_replacement(self):
        """Replace all with empty string (delete all occurrences)."""
        text = "a-b-c-d"
        result = replace_all(text, "-", "")
        assert result == "abcd"

    def test_replace_all_overlapping_potential(self):
        """Handles non-overlapping replacement correctly."""
        text = "aaa"
        result = replace_all(text, "aa", "b")
        # Should replace first "aa", leaving "a", not try to overlap
        assert result == "ba"

    def test_replace_all_longer_replacement(self):
        """Replace with longer text doesn't cause issues."""
        text = "a b c"
        result = replace_all(text, " ", "   ")
        assert result == "a   b   c"

    def test_replace_all_special_characters(self):
        """Handles special characters in find/replace."""
        text = "price: $10, tax: $2"
        result = replace_all(text, "$", "USD ")
        assert result == "price: USD 10, tax: USD 2"

    def test_replace_all_multiline(self):
        """Works with multiline text."""
        text = "line1\nline2\nline3"
        result = replace_all(text, "\n", " | ")
        assert result == "line1 | line2 | line3"


class TestEdgeCases:
    """Edge cases and regression tests."""

    def test_replace_at_end_of_text(self):
        """Replace text at the very end."""
        text = "Hello world"
        new_text, start, end = replace_current(text, 6, 11, "world", "universe")
        assert new_text == "Hello universe"
        assert start == 6
        assert end == 14

    def test_replace_entire_text(self):
        """Replace when entire text is selected."""
        text = "Hello"
        new_text, start, end = replace_current(text, 0, 5, "Hello", "Goodbye")
        assert new_text == "Goodbye"
        assert start == 0
        assert end == 7

    def test_replace_all_single_char(self):
        """Replace all single characters."""
        text = "a.b.c.d"
        result = replace_all(text, ".", "-")
        assert result == "a-b-c-d"

    def test_unicode_replace(self):
        """Handles unicode text correctly."""
        text = "Hello 世界 Hello"
        result = replace_all(text, "Hello", "你好")
        assert result == "你好 世界 你好"

    def test_unicode_selection_replace(self):
        """Single replace with unicode."""
        text = "Say 你好 to everyone"
        new_text, start, end = replace_current(text, 4, 6, "你好", "hello")
        assert new_text == "Say hello to everyone"
