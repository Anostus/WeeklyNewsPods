# Weekly Podcast Feed Generator

A GitHub Actions workflow that runs every **Friday at 5 AM Denver time (MST)** and builds a single RSS feed containing the most recent episode from each of these podcasts:

| Podcast | Feed URL |
|---------|----------|
| Native News Online | `https://nativenews.net/feed/podcast/` |
| CGTN Radio | `https://cgtn-radio-data.cgtn.com/rss/programother/159` |
| WSJ Minute Briefing | `https://video-api.wsj.com/podcast/rss/wsj/minute-briefing` |
| Cohost Podcast | `https://feeds.cohostpodcasting.com/UCAIrdHo` |

## Output

The combined feed is written to **`feed/podcast-feed.xml`** and committed back to the repo automatically.

You can point any podcast app at the raw GitHub URL for that file to subscribe:

```
https://raw.githubusercontent.com/<owner>/<repo>/main/feed/podcast-feed.xml
```

## Manual trigger

You can also run the workflow on demand from the **Actions** tab → **Generate Weekly Podcast Feed** → **Run workflow**.

## Setup

1. Push this repo to GitHub.
2. Make sure **Actions** are enabled (Settings → Actions → General).
3. The default `GITHUB_TOKEN` permissions need **Read and write** access under Settings → Actions → General → Workflow permissions.
4. That's it — the workflow will fire on the next Friday at noon UTC (5 AM MST).

## Local testing

```bash
pip install feedparser requests
python scripts/build_feed.py
# → writes feed/podcast-feed.xml
```
