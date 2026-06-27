"""
axios_text.py — pure-Python text-processing module for Axios newsletter HTML.

Contains NO secrets and NO network calls. Designed to be imported by a
separate fetch script that supplies the raw HTML.

Standard library only: re, html
"""
import re
import html as html_module


# ---------------------------------------------------------------------------
# Regex constants (compiled once)
# ---------------------------------------------------------------------------

_RE_SCRIPT = re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL)
_RE_STYLE = re.compile(r'<style[^>]*>.*?</style>', re.IGNORECASE | re.DOTALL)

# Tags whose closing form produces a newline
_RE_BLOCK_CLOSE = re.compile(
    r'</(?:p|div|tr|li|h[1-6])\s*>',
    re.IGNORECASE,
)

# <br>, <br/>, <br />
_RE_BR = re.compile(r'<br\s*/?>', re.IGNORECASE)

# All remaining tags
_RE_TAG = re.compile(r'<[^>]+>')

# Collapse 3+ newlines to 2
_RE_MULTI_NL = re.compile(r'\n{3,}')


def html_to_text_lines(html: str) -> str:
    """Convert HTML to plain text preserving line structure.

    1. Remove <script> and <style> blocks (including contents).
    2. Convert <br>, <br/>, <br /> and closing block tags to newlines.
    3. Strip all remaining tags.
    4. Unescape HTML entities; replace non-breaking spaces with regular spaces.
    5. Per line: collapse runs of spaces/tabs to one space; strip edges.
    6. Collapse 3+ consecutive newlines to exactly 2.
    7. Return .strip().
    """
    t = html

    # Remove script/style blocks entirely
    t = _RE_SCRIPT.sub('', t)
    t = _RE_STYLE.sub('', t)

    # Block-closing tags → newline
    t = _RE_BLOCK_CLOSE.sub('\n', t)

    # <br> variants → newline
    t = _RE_BR.sub('\n', t)

    # Strip all remaining tags
    t = _RE_TAG.sub('', t)

    # Unescape HTML entities (&amp; → &, &nbsp; → \xa0, etc.)
    t = html_module.unescape(t)

    # Replace non-breaking spaces with regular spaces
    t = t.replace('\xa0', ' ')

    # Per-line cleanup: collapse spaces/tabs, strip edges
    lines = t.split('\n')
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in lines]
    t = '\n'.join(lines)

    # Collapse 3+ newlines to 2
    t = _RE_MULTI_NL.sub('\n\n', t)

    return t.strip()


# ---------------------------------------------------------------------------
# Boilerplate filter
# ---------------------------------------------------------------------------

_BOILERPLATE_SUBSTRINGS = (
    "A MESSAGE FROM",
    "PRESENTED BY",
    "Presented By",
    "Like this comms style",
    "Smart Brevity",
    "Was this email forwarded",
    "Sign up now",
    "Please invite your friends",
    "Advertise with us",
    "Sponsorship has no influence",
    "View in browser",
    "Unsubscribe",
    "Manage preferences",
    "Arlington VA",
    "PO Box 101060",
    "3100 Clarendon",
)

_SPONSOR_STARTS = ("A MESSAGE FROM", "PRESENTED BY", "Presented By")


def strip_axios_boilerplate(text: str) -> str:
    """Remove Axios non-editorial lines.

    Sponsor blocks starting with A MESSAGE FROM / PRESENTED BY / Presented By
    are dropped until "Learn more" (inclusive) or a blank line (exclusive of
    the blank). Other boilerplate substrings cause the line to be dropped
    unconditionally. Smart Brevity editorial labels are preserved.
    """
    lines = text.split('\n')
    output: list[str] = []
    in_sponsor = False

    for line in lines:
        stripped = line.strip()

        if in_sponsor:
            # Exit on blank line (drop the blank)
            if stripped == '':
                in_sponsor = False
                continue
            # Exit after "Learn more" line (drop that line too)
            if 'Learn more' in stripped:
                in_sponsor = False
                continue
            # Otherwise drop the line
            continue

        # Enter sponsor mode
        if any(stripped.startswith(s) for s in _SPONSOR_STARTS):
            in_sponsor = True
            continue

        # Drop any line containing a boilerplate substring
        if any(sub in line for sub in _BOILERPLATE_SUBSTRINGS):
            continue

        output.append(line)

    result = '\n'.join(output)
    result = _RE_MULTI_NL.sub('\n\n', result)
    return result.strip()


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def clean_member_body(raw_html: str, cap: int = 14000) -> str:
    """Full pipeline: html → text → strip boilerplate → truncate to cap."""
    t = html_to_text_lines(raw_html)
    t = strip_axios_boilerplate(t)
    if len(t) > cap:
        t = t[:cap] + '…'
    return t


def build_member_block(label: str, subject: str, clean_body: str) -> str:
    """Wrap a cleaned member body with a header marker."""
    return f"=== MEMBER: {label} | {subject} ===\n{clean_body.strip()}\n"


def concat_members(blocks: list) -> str:
    """Join member blocks with double newlines, skipping empty/None entries."""
    parts = [b.strip() for b in blocks if b and b.strip()]
    return '\n\n'.join(parts)
