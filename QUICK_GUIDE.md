# Parachute Law Content Engine — Quick Guide

## What It Does

AI writes SEO-optimised legal blog posts for parachutelaw.co.uk. You pick a topic, it researches UK law, writes a 2,000+ word article in your brand voice, fact-checks it, and saves it ready to publish.

## How to Generate an Article

1. Go to **/news** on the site
2. Type a topic into the dropdown (e.g. "Pension Sharing on Divorce")
3. Pick a mode:
   - **Original** — writes a fresh article
   - **Outrank** — finds the top Google competitor and writes a better one
4. Click **Generate Article**
5. A loading card appears — wait 2-3 minutes
6. The finished article appears on the page

## What You Get

For each article, two files are saved:

| File | Contents |
|---|---|
| `topic.md` | The publish-ready article (clean markdown) |
| `topic.editor.md` | Sources, statistics, audit report, SEO metadata, FAQ schema |

## The Pipeline (Behind the Scenes)

**Scout** (Gemini) → Researches UK 2026 legal data, finds competitor articles
**Scribe** (Claude) → Writes the article in Parachute's brand voice
**Critic** (Gemini) → Fact-checks for hallucinated laws or stats, retries if needed

## CLI Alternative

```
python main.py --topic "Consent Orders" --mode original
```
