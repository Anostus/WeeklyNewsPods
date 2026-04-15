#!/usr/bin/env python3
"""
Fetch the most recent episode from each source podcast feed
and produce a single combined RSS feed.
"""

import datetime
import html
import os
import time
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path
from xml.sax.saxutils import escape

import feedparser
import requests

# ── Source feeds ──────────────────────────────────────────────────────────────
SOURCE_FEEDS = [
    "https://nativenews.net/feed/podcast/",
    "https://cgtn-radio-data.cgtn.com/rss/programother/159",
    "https://video-api.wsj.com/podcast/rss/wsj/minute-briefing",
    "https://feeds.cohostpodcasting.com/UCAIrdHo",
]

OUTPUT_DIR = Path("feed")
OUTPUT_FILE = OUTPUT_DIR / "podcast-feed.xml"

REQUEST_TIMEOUT = 30  # seconds
REQUEST_HEADERS = {
    "User-Agent": "PodcastFeedAggregator/1.0 (+https://github.com)",
}


# ── Helpers ──────────────────────────────────────────────────────────────────
def fetch_feed(url: str) -> feedparser.FeedParserDict | None:
    """Download and parse a feed, returning None on failure."""
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        if feed.bozo and not feed.entries:
            print(f"  ⚠ Feed parsed with errors and no entries: {url}")
            return None
        return feed
    except Exception as exc:
        print(f"  ✗ Failed to fetch {url}: {exc}")
        return None


def entry_pub_date(entry) -> datetime.datetime | None:
    """Try to pull a timezone-aware datetime from an entry."""
    for field in ("published", "updated"):
        raw = entry.get(f"{field}_parsed") or entry.get(field)
        if raw is None:
            continue
        # feedparser gives a time.struct_time for *_parsed
        if isinstance(raw, time.struct_time):
            return datetime.datetime(*raw[:6], tzinfo=datetime.timezone.utc)
        if isinstance(raw, str):
            try:
                return parsedate_to_datetime(raw)
            except Exception:
                pass
    return None


def latest_entry(feed: feedparser.FeedParserDict):
    """Return the most recent entry from a parsed feed."""
    if not feed.entries:
        return None
    # Sort descending by date; entries without dates go last
    entries = sorted(
        feed.entries,
        key=lambda e: entry_pub_date(e) or datetime.datetime.min.replace(
            tzinfo=datetime.timezone.utc
        ),
        reverse=True,
    )
    return entries[0]


def get_enclosures_xml(entry) -> str:
    """Build <enclosure> tags for every media link on the entry."""
    lines = []
    # feedparser normalises enclosures into entry.enclosures
    for enc in getattr(entry, "enclosures", []):
        href = enc.get("href") or enc.get("url", "")
        etype = enc.get("type", "audio/mpeg")
        length = enc.get("length", "0")
        if href:
            lines.append(
                f'      <enclosure url="{escape(href)}" '
                f'length="{escape(str(length))}" type="{escape(etype)}" />'
            )
    # Some feeds put media in media:content or links with rel=enclosure
    for link in getattr(entry, "links", []):
        if link.get("rel") == "enclosure" or link.get("type", "").startswith(
            ("audio/", "video/")
        ):
            href = link.get("href", "")
            if href and not any(href in l for l in lines):
                etype = link.get("type", "audio/mpeg")
                length = link.get("length", "0")
                lines.append(
                    f'      <enclosure url="{escape(href)}" '
                    f'length="{escape(str(length))}" type="{escape(etype)}" />'
                )
    # media:content (feedparser exposes as media_content)
    for mc in getattr(entry, "media_content", []):
        href = mc.get("url", "")
        if href and not any(href in l for l in lines):
            etype = mc.get("type", "audio/mpeg")
            length = mc.get("filesize", "0") or "0"
            lines.append(
                f'      <enclosure url="{escape(href)}" '
                f'length="{escape(str(length))}" type="{escape(etype)}" />'
            )
    return "\n".join(lines)


def get_itunes_extras(entry) -> str:
    """Pull common iTunes tags if present."""
    parts = []
    duration = (
        getattr(entry, "itunes_duration", None)
        or entry.get("itunes_duration")
    )
    if duration:
        parts.append(f"      <itunes:duration>{escape(str(duration))}</itunes:duration>")

    image = entry.get("image", {})
    image_href = image.get("href") if isinstance(image, dict) else None
    if not image_href:
        # Try itunes image
        itunes_img = entry.get("itunes_image") or {}
        image_href = itunes_img.get("href") if isinstance(itunes_img, dict) else None
    if image_href:
        parts.append(f'      <itunes:image href="{escape(image_href)}" />')

    explicit = getattr(entry, "itunes_explicit", None)
    if explicit:
        parts.append(f"      <itunes:explicit>{escape(str(explicit))}</itunes:explicit>")

    return "\n".join(parts)


def build_item_xml(entry, feed_title: str) -> str:
    """Render a single <item> block."""
    title = entry.get("title", "Untitled")
    link = entry.get("link", "")
    summary = entry.get("summary") or entry.get("description") or ""
    # Strip HTML for description but keep it in content:encoded
    description = summary
    pub_dt = entry_pub_date(entry)
    pub_date_str = format_datetime(pub_dt) if pub_dt else ""
    guid = entry.get("id") or link or title

    enclosures = get_enclosures_xml(entry)
    itunes = get_itunes_extras(entry)

    item = f"""    <item>
      <title>{escape(title)}</title>
      <link>{escape(link)}</link>
      <description><![CDATA[{description}]]></description>
      <pubDate>{pub_date_str}</pubDate>
      <guid isPermaLink="false">{escape(guid)}</guid>
      <source url="">{escape(feed_title)}</source>
{enclosures}
{itunes}
    </item>"""
    return item


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    now = format_datetime(datetime.datetime.now(datetime.timezone.utc))
    items: list[str] = []

    for url in SOURCE_FEEDS:
        print(f"Fetching: {url}")
        feed = fetch_feed(url)
        if feed is None:
            continue

        feed_title = feed.feed.get("title", url)
        entry = latest_entry(feed)
        if entry is None:
            print(f"  ⚠ No entries found in {feed_title}")
            continue

        print(f"  ✓ Latest: {entry.get('title', '?')}")
        items.append(build_item_xml(entry, feed_title))

    # Assemble full RSS document
    rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>Weekly Podcast Digest</title>
    <link>https://github.com</link>
    <description>A curated feed of the latest episodes from selected podcasts, updated every Friday at 5 AM Denver time.</description>
    <language>en</language>
    <lastBuildDate>{now}</lastBuildDate>
    <generator>build_feed.py</generator>

{chr(10).join(items)}

  </channel>
</rss>
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(rss_xml, encoding="utf-8")
    print(f"\n✓ Feed written to {OUTPUT_FILE} with {len(items)} item(s).")


if __name__ == "__main__":
    main()
