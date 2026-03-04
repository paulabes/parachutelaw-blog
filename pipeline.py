"""Shared pipeline: Scout -> Scribe -> Critic (with retry) -> parse -> save."""

import re
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from agents.researcher import research
from agents.writer import write, rewrite
from agents.auditor import audit

MAX_AUDIT_RETRIES = 2


OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def slugify(text: str) -> str:
    """Turn a title into a filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_]+", "-", text)


def extract_section(text: str, tag: str) -> str:
    """Extract content between <!-- TAG --> and <!-- /TAG --> delimiters."""
    pattern = rf"<!--\s*{re.escape(tag)}\s*-->(.*?)<!--\s*/{re.escape(tag)}\s*-->"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def extract_brief_section(brief: str, tag: str) -> str:
    """Extract a [TAG] block from researcher output."""
    match = re.search(rf"\[{re.escape(tag)}\]\s*:?\s*(.*?)(?:\n\[|$)", brief, re.DOTALL)
    return match.group(1).strip() if match else ""


def clean_sources(sources_text: str) -> str:
    """Remove junk/internal sources and deduplicate."""
    skip = ["vertexaisearch.cloud.google.com", "googleapis.com", "cloud.google.com",
            "google.com/search", "current time"]
    lines = []
    seen = set()
    for line in sources_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        line_lower = line.lower()
        if any(s in line_lower for s in skip):
            continue
        # Deduplicate by title (strip leading bullet/star)
        clean = re.sub(r"^[\-\*]\s*", "", line)
        if clean in seen:
            continue
        seen.add(clean)
        # Ensure it starts with a bullet
        if not line.startswith("-") and not line.startswith("*"):
            line = f"- {line}"
        lines.append(line)
    return "\n".join(lines)


def run_pipeline(topic: str, mode: str = "original") -> dict:
    """Run the full Scout/Scribe/Critic pipeline and return post metadata.

    mode: "original" — write from scratch on the topic
          "outrank"  — find top competitor article, write a better one
    """
    load_dotenv()

    # 1. Scout
    label = "Outrank" if mode == "outrank" else "Scout"
    print(f"\n[{label}] Researching '{topic}' via Gemini ...")
    brief = research(topic, mode=mode)
    print("    Research brief ready.\n")

    # 2. Scribe
    print("[Scribe] Drafting article via Claude ...")
    draft = write(topic, brief)
    print("    Draft complete.\n")

    # 3. Critic (with retry loop)
    attempt = 1
    while True:
        print(f"[Critic] Auditing draft via Gemini (attempt {attempt}) ...")
        audit_report = audit(brief, draft)
        print("    Audit complete.\n")

        # Check if audit passed
        audit_passed = not re.search(r"^\s*FAIL", audit_report, re.MULTILINE | re.IGNORECASE)
        if audit_passed or attempt >= MAX_AUDIT_RETRIES + 1:
            if not audit_passed:
                print(f"    Audit still FAIL after {attempt} attempts, saving anyway.\n")
            break

        # Rewrite using audit feedback
        print(f"[Scribe] Rewriting based on audit feedback (attempt {attempt + 1}) ...")
        draft = rewrite(topic, brief, draft, audit_report)
        print("    Rewrite complete.\n")
        attempt += 1

    # 4. Parse and save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(topic)
    today = date.today()
    base = f"{today.isoformat()}-{slug}"

    article = extract_section(draft, "ARTICLE")
    editor = extract_section(draft, "EDITOR")

    if not article:
        article = draft

    article_path = OUTPUT_DIR / f"{base}.md"
    article_path.write_text(article + "\n", encoding="utf-8")

    # Build editor file — structured for the client
    editor_parts = [f"# Editor Notes: {topic}\n"]

    # --- 1. Target article (outrank mode only) ---
    target = extract_brief_section(brief, "TARGET_ARTICLE")
    if target:
        # Clean out any vertex redirect URLs
        target = re.sub(r"https?://vertexaisearch\.cloud\.google\.com\S*", "[URL not captured — search manually]", target)
        editor_parts.append("## Competitor Article We're Beating")
        editor_parts.append(target)
        editor_parts.append("")

    # --- 2. Sources (with URLs and dates) ---
    sources = extract_brief_section(brief, "SOURCES")
    if sources:
        cleaned = clean_sources(sources)
        if cleaned:
            editor_parts.append("## Sources Referenced")
            editor_parts.append(cleaned)
            editor_parts.append("")

    # --- 3. Key Statistics ---
    stats = extract_brief_section(brief, "DATA_STATS")
    if stats:
        editor_parts.append("## Key Statistics")
        editor_parts.append(stats)
        editor_parts.append("")

    # --- 4. Legislation & Practice Directions ---
    legal = extract_brief_section(brief, "LEGAL_PILLAR")
    if legal:
        editor_parts.append("## Legislation & Practice Directions")
        editor_parts.append(legal)
        editor_parts.append("")

    # --- 5. Hard Truths ---
    truths = extract_brief_section(brief, "HARD_TRUTHS")
    if truths:
        editor_parts.append("## Hard Truths")
        editor_parts.append(truths)
        editor_parts.append("")

    # --- 6. Audit Report ---
    editor_parts.append("## Audit Report")
    editor_parts.append(audit_report)
    editor_parts.append("")

    # --- 7. SEO Assets (meta, schema — at the end for the client) ---
    if editor:
        editor_parts.append("---")
        editor_parts.append("")
        editor_parts.append("## SEO Assets")
        editor_parts.append("")
        editor_parts.append(editor)

    editor_path = OUTPUT_DIR / f"{base}.editor.md"
    editor_path.write_text("\n".join(editor_parts) + "\n", encoding="utf-8")

    print(f"    Article saved to {article_path}")
    print(f"    Editor notes saved to {editor_path}")
    print("    Done!\n")

    # Extract title from article for metadata
    title_match = re.search(r"^#\s+(.+)$", article, re.MULTILINE)
    title = title_match.group(1) if title_match else topic

    # Excerpt
    body = re.sub(r"^#\s+.+\n*", "", article, count=1).strip()
    body_text = re.sub(r"[#*_\[\]()>`]", "", body)
    excerpt = body_text[:150].rsplit(" ", 1)[0] + "..." if len(body_text) > 150 else body_text

    # Detect category — check title first, then body
    category = "Family Law"
    title_lower = title.lower()
    cat_rules = [
        ("Pensions", ["pension sharing", "pension", "cetv", "actuarial"]),
        ("Property", ["conveyancing", "buying & selling", "buying and selling", "transfer of equity", "deeds of trust", "equity release", "property dispute"]),
        ("Children", ["child arrangement", "custody", "parental", "children act"]),
        ("Wills & LPA", ["lasting power of attorney", "lpa", "will", "probate", "estate planning"]),
        ("Employment", ["employment", "settlement agreement", "unfair dismissal", "tribunal"]),
        ("Business", ["shareholders", "shareholder agreement"]),
        ("Disputes", ["dispute", "ccj", "litigation"]),
        ("Divorce", ["divorce", "separation", "consent order", "clean break", "spousal maintenance", "financial settlement"]),
    ]
    for cat, keywords in cat_rules:
        if any(kw in title_lower for kw in keywords):
            category = cat
            break
    else:
        content_lower = article.lower()
        for cat, keywords in cat_rules:
            if any(kw in content_lower for kw in keywords):
                category = cat
                break

    return {
        "title": title,
        "slug": slug,
        "date_formatted": today.strftime("%d %B %Y"),
        "excerpt": excerpt,
        "category": category,
        "filepath": str(article_path),
    }
