"""Check the commits of a pull request: who wrote them and what their messages end with.

The history names the people who worked on the project. A commit signed by a tool is not
merged: an author or committer that is the no-reply address of a service (GitHub's own
aside), a ``Co-Authored-By`` trailer with such an address, or a trailer that links a tool's
session. Set the author with ``git config user.name`` and ``git config user.email`` before
committing, and leave such trailers out of the message.

    python packaging/check_commits.py origin/main..HEAD
"""

from __future__ import annotations

import re
import subprocess
import sys

#: Services whose no-reply address stands for a person or for a merge made on the website.
OWN_SERVICES = ("github.com", "users.noreply.github.com")
_SIGNED = re.compile(r"^co-authored-by:.*<([^>]+)>\s*$", re.IGNORECASE | re.MULTILINE)
_SESSION = re.compile(r"^[A-Za-z][A-Za-z-]*-Session:\s*\S+", re.MULTILINE)


def tool_address(email: str) -> bool:
    """Whether ``email`` is a service's no-reply address rather than a person's."""
    local, _, domain = email.strip().lower().partition("@")
    return local == "noreply" and domain not in OWN_SERVICES


def problems(author: str, committer: str, message: str) -> list[str]:
    """What is wrong with one commit (author and committer e-mail addresses, the whole message)."""
    found = []
    if tool_address(author):
        found.append(f"the author is a tool's address ({author})")
    if tool_address(committer):
        found.append(f"the committer is a tool's address ({committer})")
    for address in _SIGNED.findall(message):
        if tool_address(address):
            found.append(f"a Co-Authored-By trailer names a tool ({address})")
    for line in _SESSION.findall(message):
        found.append(f"a trailer links a tool's session ({line.split(':', 1)[0]})")
    return found


def commits(revisions: str, *, run=None) -> list[tuple[str, str, str, str]]:
    """``(hash, author e-mail, committer e-mail, message)`` of every commit in ``revisions`` (a git range)."""
    out = (run or subprocess.run)(["git", "log", "--format=%H%x1f%ae%x1f%ce%x1f%B%x1e", revisions], capture_output=True, text=True, encoding="utf-8", check=True).stdout
    found = []
    for entry in out.split("\x1e"):
        if entry.strip():
            sha, author, committer, message = entry.strip("\n").split("\x1f", 3)
            found.append((sha, author, committer, message))
    return found


def main(argv: list[str] | None = None, *, run=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python packaging/check_commits.py <git range, e.g. origin/main..HEAD>")
        return 2
    listed = commits(args[0], run=run)
    bad = 0
    for sha, author, committer, message in listed:
        for problem in problems(author, committer, message):
            bad += 1
            print(f"{sha[:7]} {message.splitlines()[0] if message else ''}: {problem}")
    if bad:
        print(f"\n{bad} problem(s). Set the author (git config user.name, user.email), take the trailers out, and rewrite the commits.")
        return 1
    print(f"{len(listed)} commits: authors and trailers are fine")
    return 0


if __name__ == "__main__":
    sys.exit(main())
