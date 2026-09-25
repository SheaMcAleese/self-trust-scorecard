#!/usr/bin/env python3
"""Refuse to publish if any tracked file names a listed athlete. Runs on GitHub.

ONE IMPLEMENTATION. The source is shea-os/guard/ci/check.py; every publishing
repo carries a byte-identical copy at .github/name-guard/check.py, because a
GitHub runner cannot read this Mac. Edit here, then re-copy with
`name_codes.py install <repo>`. `name_codes.py --check` flags any copy that
has drifted from this one.

WHY THIS EXISTS ALONGSIDE THE TWO CHECKS ON THE MAC.

The pre-commit and pre-push hooks only run on Shea's Mac. A push from the
GitHub web editor, another computer, or a cloud agent skips both, and so
does `--no-verify`. This runs inside the Pages workflow itself, so nothing
reaches the public site without passing it, whoever pushed.

WHY THERE ARE NO NAMES IN HERE.

The roster must never be in git. name-codes.txt holds a salted SHA-256 code
for each name instead, made on the Mac by shea-os/guard/ci/name_codes.py.
This script codes
every candidate word run in every file the same way and compares codes.
It never learns a name, and its output never prints one: it reports file,
line and how many names, which is enough to find and fix the problem.

SAME MATCHING AS shea-os/pulse/roster.py, deliberately.

A name counts only as written in the roster ("Surname") or in capitals
("SURNAME"), on word boundaries, with single spaces inside multi-word names.
If the two disagreed about who counts as named, the noisier one would be
the one that got switched off.

Exit 0 = safe. Exit 1 = names found. Exit 2 = could not check, which also
blocks: not being able to look is never the same as nothing being there.
"""

import hashlib
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODES = os.path.join(HERE, "name-codes.txt")

# Mirrors roster.SKIP_EXT: things a name cannot be read out of as text.
SKIP_EXT = frozenset([
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".avif", ".pdf",
    ".zip", ".gz", ".mp4", ".mov", ".mp3", ".wav", ".woff", ".woff2",
    ".ttf", ".otf", ".eot", ".xlsx", ".pptx", ".docx",
])

WORD = re.compile(r"\w+")


def fail(code, msg):
    sys.stderr.write("\nname-guard: BLOCKED - %s\n\n" % msg)
    sys.exit(code)


def load_codes():
    if not os.path.exists(CODES):
        fail(2, "name-codes.txt is missing, so nothing could be checked.\n"
                "  Run shea-os/guard/ci/name_codes.py install <repo> on the Mac\n"
                "  and commit the result.")
    salt, max_words, codes = None, None, set()
    for line in io.open(CODES, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        if key == "salt":
            salt = value
        elif key == "max_words":
            max_words = int(value)
        else:
            codes.add(line)
    if not salt or not max_words or not codes:
        fail(2, "name-codes.txt is incomplete (salt, max_words or codes missing).")
    return salt, max_words, codes


def code(salt, text):
    return hashlib.sha256((salt + "\n" + text).encode("utf-8")).hexdigest()


def candidates(line, max_words):
    """Every run of 1..max_words whole words joined by exactly one space.

    Equivalent to the roster regex \\b(name)\\b for names made of word
    characters and single spaces, which is all the roster holds."""
    words = [(m.start(), m.end()) for m in WORD.finditer(line)]
    for i in range(len(words)):
        start, end = words[i]
        yield line[start:end]
        for j in range(i + 1, min(i + max_words, len(words))):
            if line[words[j - 1][1]:words[j][0]] != " ":
                break
            end = words[j][1]
            yield line[start:end]


def main():
    salt, max_words, codes = load_codes()

    proc = subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        fail(2, "could not list tracked files (%s)" % proc.stderr.strip())
    files = [f for f in proc.stdout.splitlines() if f.strip()]

    hits, checked = [], 0
    for rel in files:
        if os.path.splitext(rel)[1].lower() in SKIP_EXT:
            continue
        if os.path.basename(rel) == ".publish-blocklist":
            continue
        blob = subprocess.run(["git", "show", "HEAD:" + rel], capture_output=True)
        if blob.returncode != 0:
            fail(2, "could not read %s" % rel)
        checked += 1
        text = blob.stdout.decode("utf-8", errors="replace")
        lines, found = [], set()
        for number, line in enumerate(text.splitlines(), 1):
            matched = {c for c in (code(salt, w) for w in candidates(line, max_words))
                       if c in codes}
            if matched:
                lines.append(number)
                found |= matched
        if lines:
            hits.append((rel, len(found), lines))

    if hits:
        sys.stderr.write(
            "\nname-guard: PUBLISH BLOCKED. The public site was NOT updated.\n"
            "  These files name listed athletes. Names are not printed here on\n"
            "  purpose; run the same file through the Mac check to see them.\n\n")
        for rel, count, lines in hits:
            shown = ", ".join(str(n) for n in lines[:10])
            more = " (+%d more)" % (len(lines) - 10) if len(lines) > 10 else ""
            sys.stderr.write("    %s\n        %d name(s), line %s%s\n"
                             % (rel, count, shown, more))
        sys.stderr.write("\n  Fix: remove the names, or untrack the file:\n"
                         "      git rm --cached \"<file>\"   then add it to .gitignore\n\n")
        sys.exit(1)

    print("name-guard: %d files checked against %d codes, none name a listed athlete"
          % (checked, len(codes)))


if __name__ == "__main__":
    main()
