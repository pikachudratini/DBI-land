"""Tests for the email-body parser used by ImapSource (no IMAP server needed)."""
from email.message import EmailMessage

from dbi_land.sources.imap_source import parse_email


def _make_msg(html: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = "New listings"
    msg["From"] = "alerts@landsearch.com"
    msg["To"] = "buyer@example.com"
    msg.set_content("text fallback")
    msg.add_alternative(html, subtype="html")
    return msg


def test_parses_landsearch_block():
    html = """
    <html><body>
      <table><tr><td>
        <a href="https://www.landsearch.com/properties/12345">120 acres in Texas County, MO</a>
        <p>$420,000 — 120 acres — Missouri</p>
      </td></tr></table>
      <table><tr><td>
        <a href="https://www.landwatch.com/Hopkins_County_TX/200-acres/123">200 acre east TX ranch</a>
        <span>200 acres / Hopkins County, TX / $1,100,000</span>
      </td></tr></table>
      <a href="https://example.com/not-a-listing">unrelated link</a>
    </body></html>
    """
    listings = list(parse_email(_make_msg(html)))
    assert len(listings) == 2
    by_id = {l.url: l for l in listings}
    mo = next(l for l in listings if l.state == "MO")
    assert mo.acres == 120
    assert mo.price_usd == 420_000
    assert mo.source == "landsearch"
    tx = next(l for l in listings if l.state == "TX")
    assert tx.acres == 200
    assert tx.price_usd == 1_100_000
    assert tx.source == "landwatch"
    assert all("listing" not in url for url in by_id if "example.com" in url)


def test_skips_blocks_missing_required_facts():
    html = """
    <html><body>
      <a href="https://www.landsearch.com/properties/9">no facts here</a>
    </body></html>
    """
    assert list(parse_email(_make_msg(html))) == []


def test_plaintext_fallback():
    msg = EmailMessage()
    msg["Subject"] = "alerts"
    msg["From"] = "alerts@landsearch.com"
    msg.set_content(
        "New listing: 80 acres in Iowa for $640,000 — "
        "https://www.landsearch.com/properties/abc end."
    )
    listings = list(parse_email(msg))
    assert len(listings) == 1
    assert listings[0].acres == 80
    assert listings[0].price_usd == 640_000
    assert listings[0].state == "IA"
