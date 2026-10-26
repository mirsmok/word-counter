#!/usr/bin/env python3
"""Count the most frequent words in UTF-8 text.

A word is a run of Unicode letters. Apostrophes that sit between letters
are kept, so contractions such as "don't" stay one word. Punctuation,
digits, underscores, and other characters separate words and are ignored.
Polish letters (ą, ę, ł, ó, ś, ż, ź, ć, ń and their capitals) are letters.

Matching is case-insensitive by default (Unicode casefold). Use
--case-sensitive to keep the original casing.

Examples:
    python3 wordcounter.py sample.txt
    python3 wordcounter.py --top 20 --min-length 3 a.txt b.txt
    python3 wordcounter.py --json < article.txt
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import List, Optional, Sequence, TextIO, Tuple


# Letters, plus an apostrophe only when it joins two letter-groups.
# [^\W\d_] is the standard-library spelling of "Unicode letter":
# a word character that is neither a digit nor an underscore.
_WORD_RE = re.compile(r"[^\W\d_]+(?:['’‘][^\W\d_]+)*")

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'"})


class WordCounterError(Exception):
    """A problem with the input that should be reported without a traceback."""


def tokenize(text: str) -> List[str]:
    """Return words in *text*, in order, with surrounding punctuation removed."""
    return _WORD_RE.findall(text)


def normalize_word(word: str, *, case_sensitive: bool) -> str:
    """Fold curly apostrophes, and casefold unless case is significant."""
    word = word.translate(_APOSTROPHES)
    if not case_sensitive:
        word = word.casefold()
    return word


def count_words(
    text: str,
    *,
    case_sensitive: bool = False,
    min_length: int = 1,
) -> Counter[str]:
    """Count words in *text*.

    *min_length* is measured after normalization, in Unicode characters.
    """
    counts: Counter[str] = Counter()
    for raw in tokenize(text):
        word = normalize_word(raw, case_sensitive=case_sensitive)
        if len(word) < min_length:
            continue
        counts[word] += 1
    return counts


def rank_words(counts: Counter[str], top: int) -> List[Tuple[str, int]]:
    """Return ``(word, count)`` pairs, most frequent first.

    Ties break by the word itself in Unicode code-point order, so the
    result does not depend on the locale. *top* of ``0`` means no limit.
    """
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    if top == 0:
        return ranked
    return ranked[:top]


def format_table(rows: Sequence[Tuple[str, int]]) -> str:
    """Format rows as an aligned ``word  count`` table."""
    if not rows:
        return ""
    word_width = max(len(word) for word, _count in rows)
    count_width = max(len(str(count)) for _word, count in rows)
    lines = [
        f"{word:<{word_width}}  {count:>{count_width}}" for word, count in rows
    ]
    return "\n".join(lines) + "\n"


def format_json(rows: Sequence[Tuple[str, int]]) -> str:
    """Format rows as a JSON array of objects, preserving non-ASCII letters."""
    payload = [{"word": word, "count": count} for word, count in rows]
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _stdin_is_tty(stream: TextIO) -> bool:
    isatty = getattr(stream, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except (AttributeError, OSError, ValueError):
        return False


def _read_stream(stream: TextIO, label: str) -> str:
    try:
        return stream.read()
    except UnicodeDecodeError as exc:
        raise WordCounterError(
            f"wordcounter: {label} is not valid UTF-8 "
            f"({exc.reason} at position {exc.start})"
        ) from exc


def load_corpus(paths: Sequence[str]) -> str:
    """Read *paths* as UTF-8 and join them with newlines.

    An empty *paths* reads stdin. A path of ``-`` also reads stdin, which
    lets you mix files and a pipe. Stdin is read at most once.
    """
    if not paths:
        if _stdin_is_tty(sys.stdin):
            print(
                "wordcounter: reading from stdin. "
                "Finish with Ctrl-D (Linux/macOS) or Ctrl-Z then Enter (Windows).",
                file=sys.stderr,
            )
        return _read_stream(sys.stdin, "stdin")

    parts: List[str] = []
    errors: List[str] = []
    stdin_used = False

    for raw in paths:
        if raw == "-":
            if stdin_used:
                errors.append("wordcounter: stdin ('-') was given more than once")
                continue
            stdin_used = True
            try:
                parts.append(_read_stream(sys.stdin, "stdin"))
            except WordCounterError as exc:
                errors.append(str(exc))
                continue
            parts.append("\n")
            continue

        path = Path(raw)
        if not path.exists():
            errors.append(f"wordcounter: file not found: {raw}")
            continue
        if not path.is_file():
            errors.append(f"wordcounter: not a file: {raw}")
            continue
        try:
            parts.append(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError as exc:
            errors.append(
                f"wordcounter: cannot decode '{raw}' as UTF-8 "
                f"({exc.reason} at position {exc.start})"
            )
            continue
        except OSError as exc:
            detail = exc.strerror or str(exc)
            errors.append(f"wordcounter: cannot read '{raw}': {detail}")
            continue
        # Keep a word at the end of one file from gluing to the next file.
        parts.append("\n")

    if errors:
        raise WordCounterError("\n".join(errors))
    return "".join(parts)


def _non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"must be an integer (got {value!r})"
        ) from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError(
            f"must be zero or a positive integer (got {parsed})"
        )
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wordcounter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Count the most frequent words in one or more UTF-8 text files.\n"
            "With no FILE, read standard input.\n"
            "\n"
            "A word is a sequence of Unicode letters. Polish letters\n"
            "(ą, ę, ł, ó, ś, ż, ź, ć, ń and capitals) are part of words.\n"
            "Punctuation, digits, and underscores are separators and are\n"
            "ignored. An apostrophe between letters is kept (don't).\n"
            "Matching is case-insensitive unless --case-sensitive is set."
        ),
        epilog=(
            "examples:\n"
            "  wordcounter.py sample.txt\n"
            "  wordcounter.py --top 5 --min-length 3 sample.txt\n"
            "  wordcounter.py --json chapter1.txt chapter2.txt\n"
            "  wordcounter.py --case-sensitive < notes.txt"
        ),
    )
    parser.add_argument(
        "files",
        nargs="*",
        metavar="FILE",
        help="UTF-8 text file to read. Use - for stdin. If omitted, read stdin.",
    )
    parser.add_argument(
        "-n",
        "--top",
        type=_non_negative_int,
        default=10,
        metavar="N",
        help="show the N most frequent words (default: 10). 0 shows every word.",
    )
    parser.add_argument(
        "-m",
        "--min-length",
        type=_non_negative_int,
        default=1,
        metavar="N",
        help="ignore words shorter than N characters (default: 1).",
    )
    parser.add_argument(
        "-c",
        "--case-sensitive",
        action="store_true",
        help="keep the original case. By default, 'Żółć' and 'żółć' match.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help='print a JSON array of {"word", "count"} objects.',
    )
    return parser


def configure_stdio() -> None:
    """Ask standard streams to use UTF-8 so Polish letters survive the console.

    File inputs are opened as UTF-8 separately. This only affects stdin,
    stdout, and stderr. Streams that cannot be reconfigured (for example
    test doubles) are left alone.
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            continue


def count_paths(
    paths: Sequence[str],
    *,
    top: int,
    min_length: int,
    case_sensitive: bool,
) -> List[Tuple[str, int]]:
    text = load_corpus(paths)
    counts = count_words(
        text,
        case_sensitive=case_sensitive,
        min_length=min_length,
    )
    return rank_words(counts, top)


def render(rows: Sequence[Tuple[str, int]], *, as_json: bool) -> str:
    if as_json:
        return format_json(rows)
    return format_table(rows)


def main(argv: Optional[Sequence[str]] = None) -> int:
    configure_stdio()
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        rows = count_paths(
            args.files,
            top=args.top,
            min_length=args.min_length,
            case_sensitive=args.case_sensitive,
        )
        sys.stdout.write(render(rows, as_json=args.json))
    except WordCounterError as exc:
        print(exc, file=sys.stderr)
        return 1
    except BrokenPipeError:
        # Downstream closed the pipe (for example `wordcounter | head`).
        try:
            sys.stdout.close()
        except BrokenPipeError:
            pass
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
