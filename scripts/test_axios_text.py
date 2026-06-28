"""Tests for axios_text.py — run with: python -m pytest scripts/test_axios_text.py -v"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import axios_text as a


# ---------------------------------------------------------------------------
# html_to_text_lines
# ---------------------------------------------------------------------------

def test_html_to_text_preserves_paragraph_breaks():
    html = "<p>First line.</p><p>Second line.</p>"
    out = a.html_to_text_lines(html)
    assert "First line." in out and "Second line." in out
    assert out.count("\n") >= 1  # paragraphs separated by newline


def test_html_to_text_br_becomes_newline_and_strips_tags():
    html = "Hello<br>World <b>bold</b>"
    out = a.html_to_text_lines(html)
    assert "Hello\nWorld bold" == out


def test_html_to_text_drops_script_style_and_unescapes():
    html = "<style>.x{color:red}</style><p>Tom &amp; Jerry</p><script>evil()</script>"
    out = a.html_to_text_lines(html)
    assert "Tom & Jerry" in out
    assert "color:red" not in out and "evil()" not in out


def test_html_to_text_br_variants():
    """br/>, <br />, and </p> all become newlines."""
    html = "A<br/>B<br />C</p>D"
    out = a.html_to_text_lines(html)
    assert out == "A\nB\nC\nD"


def test_html_to_text_nbsp_replaced():
    """Non-breaking spaces become regular spaces."""
    html = "Hello&nbsp;World"
    out = a.html_to_text_lines(html)
    assert out == "Hello World"


def test_html_to_text_collapses_excess_newlines():
    """Three or more consecutive newlines become exactly two."""
    html = "<p>A</p><p></p><p></p><p>B</p>"
    out = a.html_to_text_lines(html)
    assert "\n\n\n" not in out
    assert "A" in out and "B" in out


def test_html_to_text_closing_tags_produce_newlines():
    """All specified closing tags (div, tr, li, hN) produce newlines."""
    html = "<div>Alpha</div><li>Beta</li><h2>Gamma</h2>"
    out = a.html_to_text_lines(html)
    assert "Alpha" in out and "Beta" in out and "Gamma" in out
    assert out.count("\n") >= 2


# ---------------------------------------------------------------------------
# strip_axios_boilerplate
# ---------------------------------------------------------------------------

def test_strip_removes_sponsor_block_until_learn_more():
    text = "Why it matters: keep me.\nA MESSAGE FROM COMCAST\nBuy stuff. Learn more.\nThe bottom line: keep me too."
    out = a.strip_axios_boilerplate(text)
    assert "keep me." in out and "keep me too." in out
    assert "COMCAST" not in out and "Buy stuff" not in out


def test_strip_removes_footer_and_promo_lines():
    text = (
        "Real content.\n"
        "Like this comms style and format? Smart Brevity.\n"
        "Was this email forwarded to you? Sign up now.\n"
        "Axios, PO Box 101060, Arlington VA 22201\n"
        "Unsubscribe | Manage preferences"
    )
    out = a.strip_axios_boilerplate(text)
    assert "Real content." in out
    for bad in ("Smart Brevity", "Arlington VA", "Unsubscribe", "forwarded"):
        assert bad not in out


def test_strip_keeps_smart_brevity_labels():
    text = "1 big thing: X\nWhy it matters: Y\nThe bottom line: Z"
    out = a.strip_axios_boilerplate(text)
    assert "Why it matters: Y" in out and "The bottom line: Z" in out


def test_strip_sponsor_block_exits_on_blank_line():
    """Blank line exits sponsor block (blank itself dropped)."""
    text = "Before.\nPRESENTED BY ACME\nAd text.\n\nAfter."
    out = a.strip_axios_boilerplate(text)
    assert "Before." in out
    assert "After." in out
    assert "ACME" not in out and "Ad text" not in out


def test_strip_presented_by_inline():
    """PRESENTED BY starts a sponsor block; lines after it are dropped until
    blank line exits the block. Content after the blank is preserved."""
    text = "Good line.\nPRESENTED BY SPONSOR\nAd text.\n\nAfter sponsor."
    out = a.strip_axios_boilerplate(text)
    assert "Good line." in out
    assert "After sponsor." in out
    assert "SPONSOR" not in out
    assert "Ad text" not in out


def test_strip_collapses_excess_newlines():
    """After filtering, 3+ newlines collapse to 2."""
    text = "A\n\n\n\n\nB"
    out = a.strip_axios_boilerplate(text)
    assert "\n\n\n" not in out
    assert "A" in out and "B" in out


# ---------------------------------------------------------------------------
# clean_member_body
# ---------------------------------------------------------------------------

def test_clean_member_body_caps_length():
    raw = "<p>" + ("a" * 20000) + "</p>"
    out = a.clean_member_body(raw, cap=14000)
    assert len(out) <= 14001 and out.endswith("…")


def test_clean_member_body_no_truncation_when_short():
    raw = "<p>Short content.</p>"
    out = a.clean_member_body(raw)
    assert "Short content." in out
    assert not out.endswith("…")


def test_clean_member_body_pipeline():
    """Runs full pipeline: html_to_text_lines then strip_axios_boilerplate."""
    raw = "<p>Real content.</p><p>Unsubscribe here.</p>"
    out = a.clean_member_body(raw)
    assert "Real content." in out
    assert "Unsubscribe" not in out


# ---------------------------------------------------------------------------
# build_member_block
# ---------------------------------------------------------------------------

def test_build_member_block_marker_format():
    block = a.build_member_block("Axios AM", "Blind loyalty", "body")
    assert block.startswith("=== MEMBER: Axios AM | Blind loyalty ===\n")
    assert "body" in block


def test_build_member_block_ends_with_newline():
    block = a.build_member_block("X", "Y", "Z")
    assert block.endswith("\n")


def test_build_member_block_strips_body():
    block = a.build_member_block("X", "Y", "  body  ")
    assert "body" in block
    # Leading/trailing spaces in body should be stripped
    lines = block.split("\n")
    assert lines[1] == "body"


# ---------------------------------------------------------------------------
# concat_members
# ---------------------------------------------------------------------------

def test_concat_members_skips_empty_and_joins():
    assert a.concat_members([]) == ""
    assert a.concat_members(["A", "", None, "B"]) == "A\n\nB"


def test_concat_members_single():
    assert a.concat_members(["Only"]) == "Only"


def test_concat_members_all_empty():
    assert a.concat_members(["", None, "  "]) == ""


def test_concat_members_strips_entries():
    result = a.concat_members(["  A  ", "  B  "])
    assert result == "A\n\nB"
