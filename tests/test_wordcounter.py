"""Tests for the wordcounter CLI and its counting rules."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

import wordcounter


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample.txt"


class TtyBuffer(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_tokenize_strips_punctuation_and_keeps_contractions():
    words = wordcounter.tokenize("Hello, world! Don't stop. It's \"done\".")
    assert words == ["Hello", "world", "Don't", "stop", "It's", "done"]


def test_curly_apostrophe_is_a_contraction():
    words = wordcounter.tokenize("Don’t you’ll")
    assert words == ["Don’t", "you’ll"]


def test_digits_and_underscores_separate_words():
    assert wordcounter.tokenize("mp3 some_word covid-19") == [
        "mp",
        "some",
        "word",
        "covid",
    ]


def test_polish_letters_stay_inside_words():
    text = "Zażółć gęślą jaźń. ąćęłńóśźż ĄĆĘŁŃÓŚŹŻ"
    assert wordcounter.tokenize(text) == [
        "Zażółć",
        "gęślą",
        "jaźń",
        "ąćęłńóśźż",
        "ĄĆĘŁŃÓŚŹŻ",
    ]


def test_casefold_merges_polish_and_latin():
    counts = wordcounter.count_words(
        "Żółć żółć ŻÓŁĆ The the THE",
        case_sensitive=False,
    )
    assert counts["żółć"] == 3
    assert counts["the"] == 3
    assert "Żółć" not in counts


def test_case_sensitive_keeps_distinct_casings():
    counts = wordcounter.count_words("The the THE", case_sensitive=True)
    assert counts["The"] == 1
    assert counts["the"] == 1
    assert counts["THE"] == 1


def test_curly_and_straight_apostrophes_match_when_casefolded():
    counts = wordcounter.count_words("Don't Don’t don't", case_sensitive=False)
    assert counts["don't"] == 3


def test_min_length_filters_short_words():
    counts = wordcounter.count_words(
        "a an and łąka",
        case_sensitive=False,
        min_length=3,
    )
    assert list(counts) == ["and", "łąka"]


def test_rank_orders_by_count_then_code_point():
    counts = wordcounter.count_words(
        "b b a a c",
        case_sensitive=True,
    )
    assert wordcounter.rank_words(counts, top=10) == [
        ("a", 2),
        ("b", 2),
        ("c", 1),
    ]


def test_rank_top_zero_returns_every_word():
    counts = wordcounter.count_words("one two two", case_sensitive=False)
    assert wordcounter.rank_words(counts, top=0) == [("two", 2), ("one", 1)]
    assert wordcounter.rank_words(counts, top=1) == [("two", 2)]


def test_format_table_aligns_columns():
    table = wordcounter.format_table([("river", 12), ("a", 3), ("żółć", 3)])
    assert table.splitlines() == [
        "river  12",
        "a       3",
        "żółć    3",
    ]


def test_format_json_keeps_polish_letters():
    raw = wordcounter.format_json([("żółć", 2)])
    assert json.loads(raw) == [{"word": "żółć", "count": 2}]
    assert "żółć" in raw


def test_files_do_not_glue_a_split_word(tmp_path: Path):
    first = tmp_path / "a.txt"
    second = tmp_path / "b.txt"
    first.write_text("hell", encoding="utf-8")
    second.write_text("o", encoding="utf-8")
    counts = wordcounter.count_words(
        wordcounter.load_corpus([str(first), str(second)]),
        case_sensitive=False,
    )
    assert counts["hell"] == 1
    assert counts["o"] == 1
    assert "hello" not in counts


def test_sample_file_known_words():
    text = SAMPLE.read_text(encoding="utf-8")
    counts = wordcounter.count_words(text, case_sensitive=False, min_length=1)
    assert counts["the"] == 10
    assert counts["river"] == 5
    assert counts["town"] == 4
    assert counts["żółć"] == 2
    assert counts["jaźń"] == 3
    assert counts["gęślą"] == 2
    assert counts["rzeka"] == 2
    assert counts["zażółć"] == 1
    # Single Polish letters are real words and must not be stripped.
    for letter in "ąęłóśżźćń":
        assert counts[letter] == 1


def test_cli_sample_top_is_aligned(capsys: pytest.CaptureFixture[str]):
    assert wordcounter.main([str(SAMPLE), "--top", "3", "--min-length", "3"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines() == [
        "the    10",
        "river   5",
        "town    4",
    ]


def test_cli_multiple_files_are_combined(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text("alpha beta", encoding="utf-8")
    right.write_text("beta beta", encoding="utf-8")
    assert wordcounter.main(["--json", str(left), str(right)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == [
        {"word": "beta", "count": 3},
        {"word": "alpha", "count": 1},
    ]


def test_cli_reads_stdin_when_no_file_is_given(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr(sys, "stdin", io.StringIO("one two two\n"))
    assert wordcounter.main([]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.splitlines() == ["two  2", "one  1"]


def test_cli_dash_reads_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr(sys, "stdin", io.StringIO("Żółć żółć\n"))
    assert wordcounter.main(["--json", "-"]) == 0
    assert json.loads(capsys.readouterr().out) == [{"word": "żółć", "count": 2}]


def test_tty_stdin_prints_a_hint_and_still_counts(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr(sys, "stdin", TtyBuffer("cat cat\n"))
    assert wordcounter.main([]) == 0
    captured = capsys.readouterr()
    assert "stdin" in captured.err
    assert "Ctrl-D" in captured.err
    assert captured.out.splitlines() == ["cat  2"]


def test_missing_file_has_a_friendly_error(capsys: pytest.CaptureFixture[str]):
    code = wordcounter.main(["no-such-file.txt"])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "file not found: no-such-file.txt" in captured.err


def test_several_missing_files_are_all_reported(
    capsys: pytest.CaptureFixture[str],
):
    code = wordcounter.main(["missing-a.txt", "missing-b.txt"])
    err = capsys.readouterr().err
    assert code == 1
    assert "missing-a.txt" in err
    assert "missing-b.txt" in err


def test_directory_is_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    code = wordcounter.main([str(tmp_path)])
    assert code == 1
    assert "not a file" in capsys.readouterr().err


def test_invalid_utf8_is_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"hello \xff world")
    code = wordcounter.main([str(bad)])
    err = capsys.readouterr().err
    assert code == 1
    assert "UTF-8" in err
    assert "bad.txt" in err


def test_good_file_is_not_counted_when_another_is_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    good = tmp_path / "good.txt"
    good.write_text("alpha alpha", encoding="utf-8")
    code = wordcounter.main([str(good), "missing.txt"])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "missing.txt" in captured.err


def test_cli_case_sensitive_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    path = tmp_path / "case.txt"
    path.write_text("The the", encoding="utf-8")
    assert wordcounter.main(["--case-sensitive", "--json", str(path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == [
        {"word": "The", "count": 1},
        {"word": "the", "count": 1},
    ]


def test_cli_min_length_flag(capsys: pytest.CaptureFixture[str]):
    assert wordcounter.main([str(SAMPLE), "--min-length", "6", "--top", "3"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "evening  1",
        "jeszcze  1",
        "lights   1",
    ]


def test_empty_input_text_and_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    assert wordcounter.main([]) == 0
    assert capsys.readouterr().out == ""

    monkeypatch.setattr(sys, "stdin", io.StringIO("... ---"))
    assert wordcounter.main(["--json"]) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_help_covers_the_options(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc:
        wordcounter.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--top" in out
    assert "--min-length" in out
    assert "--case-sensitive" in out
    assert "--json" in out
    assert "ą" in out
    assert "stdin" in out


def test_negative_top_is_rejected(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc:
        wordcounter.main(["--top", "-3"])
    assert exc.value.code == 2
    assert "positive" in capsys.readouterr().err or "zero" in capsys.readouterr().err


def test_top_must_be_an_integer(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc:
        wordcounter.main(["--top", "ten"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "integer" in err


def test_repeated_stdin_marker_is_an_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr(sys, "stdin", io.StringIO("hello\n"))
    code = wordcounter.main(["-", "-"])
    assert code == 1
    assert "more than once" in capsys.readouterr().err
