"""Codex's own error text, said in words a new user can act on.

Only errors Pat marked as Codex's (they start with STARTING) are changed, so a Bluetooth or audio problem that happens
to say "authentication" or "network" keeps its own words."""
import re

STARTING = "Codex couldn't start: "
LOGIN = "Codex's login has run out. Open a terminal, run codex login, then try again."
LIMIT = "Your Codex plan's limit is used up for now, so Codex can't answer calls."
OFFLINE = "Codex can't be reached. Check the internet connection, then try again."
BUSY = "Codex is overloaded right now. Try again in a minute."

# What Codex says in each case, matched without regard to case.
PATTERNS = (
    (LOGIN, r"/login|not logged in|invalid api key|oauth token|token has expired|authenticat|\b401\b"),
    (LIMIT, r"usage limit|limit reached|hit your limit|rate.limit|\b429\b|out of credits|credit balance"),
    (OFFLINE, r"connection error|enotfound|econnrefused|econnreset|etimedout|getaddrinfo|network"),
    (BUSY, r"overloaded|\b529\b"),
)


def plain_reason(reason):
    """reason as the note should show it."""
    text = str(reason or "")
    if not text.startswith(STARTING):
        return text
    for message, pattern in PATTERNS:
        if re.search(pattern, text, re.I):
            resets = re.search(r"resets?\s+(?:at\s+)?([^·|\n]+?)\s*(?:[·|\n]|$)", text, re.I) if message is LIMIT else None
            return f"Your Codex plan's limit is used up. It resets {resets.group(1).rstrip('.')}." if resets else message
    return text
