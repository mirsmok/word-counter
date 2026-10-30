# wordcounter

`wordcounter.py` is a small command-line tool that counts the most frequent words in text. Give it one or more UTF-8 files, or pipe text on standard input, and it prints the top words with their counts.

Polish letters (ą, ę, ł, ó, ś, ż, ź, ć, ń, and the capitals) stay inside words. Punctuation is ignored. Matching ignores case unless you pass `--case-sensitive`.

`sample.txt` is a short English and Polish text, including the pangram “Zażółć gęślą jaźń”, so you can try the tool as soon as you have Python.

## Requirements

- Python 3.9 or newer
- No third-party packages to run the tool. It uses the standard library only. See `requirements.txt`.
- [pytest](https://docs.pytest.org/) 7 or newer, listed in `requirements-dev.txt`, to run the tests

## Run on Linux and macOS

From this directory:

```bash
python3 wordcounter.py sample.txt
```

The script is executable, so this works too:

```bash
./wordcounter.py sample.txt
```

Read standard input when you omit the file:

```bash
printf '%s\n' 'Hello, hello! Żółć and żółć.' | python3 wordcounter.py
```

## Run on Windows (PowerShell)

```powershell
py -3 wordcounter.py sample.txt
```

If the Python launcher is not installed, use `python` in place of `py -3`.

Files are always decoded as UTF-8. To print Polish letters in the console, use Windows Terminal, or switch the session to UTF-8 before you run the tool:

```powershell
chcp 65001
$env:PYTHONUTF8 = "1"
py -3 wordcounter.py sample.txt
```

Passing a file path is the reliable way to feed in text. A pipe uses the console encoding, so set UTF-8 as above before piping Polish text:

```powershell
@'
Hello, hello! Żółć and żółć.
'@ | py -3 wordcounter.py
```

## Examples

Top 10 words in the sample (the default):

```bash
python3 wordcounter.py sample.txt
```

```text
the    10
river   5
town    4
is      3
jaźń    3
every   2
gęślą   2
i       2
jest    2
old     2
```

On PowerShell the same command is `py -3 wordcounter.py sample.txt`. The table is the same.

Drop short words and keep five rows. One-letter words such as Polish `i` and `w` are real words; raise `--min-length` when you want longer words only.

```bash
python3 wordcounter.py --top 5 --min-length 4 sample.txt
```

```text
river  5
town   4
jaźń   3
every  2
gęślą  2
```

JSON, which is easier to pass to another program:

```bash
python3 wordcounter.py --json --top 3 --min-length 3 sample.txt
```

```json
[
  {
    "word": "the",
    "count": 10
  },
  {
    "word": "river",
    "count": 5
  },
  {
    "word": "town",
    "count": 4
  }
]
```

Several files are one corpus. This prints a single list:

```bash
python3 wordcounter.py chapter1.txt chapter2.txt
```

Use `-` for standard input alongside files: `python3 wordcounter.py notes.txt -`.

Keep the original case:

```bash
printf '%s\n' 'The the THE. Żółć żółć.' | python3 wordcounter.py --case-sensitive
```

```text
THE   1
The   1
the   1
Żółć  1
żółć  1
```

The same idea with the default, case-insensitive matching, and punctuation stripped:

```bash
printf '%s\n' 'Hello, hello! Żółć and żółć.' | python3 wordcounter.py
```

```text
hello  2
żółć   2
and    1
```

Help:

```bash
python3 wordcounter.py --help
```

## Options

| Option | Meaning |
| --- | --- |
| `FILE` | UTF-8 text file. Repeat to combine files. `-` reads stdin. With no file, the tool reads stdin. |
| `-n N`, `--top N` | How many words to print. Default: 10. `0` prints every word. |
| `-m N`, `--min-length N` | Ignore words shorter than N characters. Default: 1. |
| `-c`, `--case-sensitive` | Keep original case. By default `Żółć` and `żółć` match. |
| `--json` | Print a JSON array of `{"word", "count"}` objects. Letters such as `żółć` are written as themselves. |
| `-h`, `--help` | Show help and exit. |

The highest count is first. Equal counts are ordered by the word in Unicode code-point order, so the order is the same on every machine.

## How words are counted

- A word is a sequence of Unicode letters. Polish letters are letters.
- An apostrophe between letters stays, so `don't` and `Don’t` count as `don't` after case folding.
- Commas, periods, quotes, dashes, digits, and underscores separate words and are left out of the count. `well-known` becomes `well` and `known`. `mp3` becomes `mp`.
- Case-insensitive mode uses Unicode casefold.
- Each file is read as UTF-8. A newline is placed between files, so the last word of one file does not stick to the first word of the next.
- Text output is two aligned columns: the word, then the count. An empty result prints nothing. With `--json`, an empty result is `[]`.

## Errors and exit status

Problems go to standard error, with a short message and no traceback:

```text
wordcounter: file not found: missing.txt
```

| Exit code | Meaning |
| --- | --- |
| 0 | Success. |
| 1 | A path was missing, was a directory, could not be read, or was not valid UTF-8. |
| 2 | The command line was invalid, for example `--top -1`. |

When several paths fail, every problem is reported and no counts are printed.

If you run the tool with no file in a terminal, it reads what you type and prints a one-line hint. Finish with Ctrl-D on Linux and macOS, or Ctrl-Z then Enter on Windows.

## Tests

Linux and macOS:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
```

Windows (PowerShell):

```powershell
py -3 -m pip install -r requirements-dev.txt
py -3 -m pytest
```

## Project files

| File | Purpose |
| --- | --- |
| `wordcounter.py` | The program |
| `sample.txt` | English and Polish sample text |
| `tests/test_wordcounter.py` | pytest suite |
| `requirements.txt` | Runtime dependencies (none) |
| `requirements-dev.txt` | pytest |
