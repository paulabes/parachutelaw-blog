"""Parachute Law demo website — Flask app serving the premium dark-theme site."""

import os
import re
import sys
import glob
import uuid
import shutil
import threading
from datetime import datetime
from flask import Flask, render_template, abort, request, jsonify
import markdown

SITE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(SITE_DIR, "templates"))

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")

# Add project root to path so we can import pipeline
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Seed volume: when Railway mounts an empty volume over output/, copy git articles in.
# The git articles are stashed in output_seed/ at build time (see below).
SEED_DIR = os.path.join(PROJECT_ROOT, "output_seed")
if os.path.isdir(SEED_DIR) and not glob.glob(os.path.join(OUTPUT_DIR, "*.md")):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for f in glob.glob(os.path.join(SEED_DIR, "*.md")):
        dest = os.path.join(OUTPUT_DIR, os.path.basename(f))
        if not os.path.exists(dest):
            shutil.copy2(f, dest)

# Background task tracking
_tasks = {}

# ⚡ Pre-compiled regexes — avoids recompilation on every request
_RE_H1 = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_RE_DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})")
_RE_STRIP_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}-?")
_RE_SLUG_CLEAN = re.compile(r"[^a-z0-9]+")
_RE_STRIP_H1 = re.compile(r"^#\s+.+\n*")
_RE_STRIP_MD = re.compile(r"[#*_\[\]()>`]")

# ⚡ Posts cache — avoids re-reading every .md file on each request.
# Invalidates when the output directory's mtime changes (new/modified files).
_posts_cache = {"mtime": 0, "posts": []}


def _output_dir_mtime():
    """Cheap check: latest mtime across output dir and its .md files."""
    try:
        return max(
            os.path.getmtime(OUTPUT_DIR),
            max((os.path.getmtime(f) for f in glob.glob(os.path.join(OUTPUT_DIR, "*.md"))), default=0),
        )
    except OSError:
        return 0


def get_posts():
    """Load all markdown files from output/ and return sorted post list.

    ⚡ Cached: only re-reads files when the output directory changes.
    Reduces per-request I/O from O(n) file reads to a single stat() check.
    """
    current_mtime = _output_dir_mtime()
    if current_mtime == _posts_cache["mtime"] and _posts_cache["posts"]:
        return _posts_cache["posts"]

    posts = []
    md_files = [f for f in glob.glob(os.path.join(OUTPUT_DIR, "*.md"))
                if not f.endswith(".editor.md") and not f.endswith(".audit.md")]

    for filepath in md_files:
        filename = os.path.basename(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract title from first H1
        title_match = _RE_H1.search(content)
        title = title_match.group(1) if title_match else filename.replace(".md", "").replace("-", " ").title()

        # Extract date from filename (e.g., 2026-03-04-pension-sharing.md)
        date_match = _RE_DATE_PREFIX.match(filename)
        if date_match:
            date_str = date_match.group(1)
            date = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            date = datetime.fromtimestamp(os.path.getmtime(filepath))

        # Generate slug from filename (strip date prefix and extension)
        slug = _RE_STRIP_DATE.sub("", filename).replace(".md", "")
        if not slug:
            slug = _RE_SLUG_CLEAN.sub("-", title.lower()).strip("-")

        # Excerpt: first 150 chars of body text (skip title line)
        body = _RE_STRIP_H1.sub("", content, count=1).strip()
        body_text = _RE_STRIP_MD.sub("", body)
        excerpt = body_text[:150].rsplit(" ", 1)[0] + "..." if len(body_text) > 150 else body_text

        # Detect category — check title first (most specific), then body
        category = "Family Law"
        title_lower = title.lower()
        # Ordered specific-to-broad so narrow topics match before "divorce" catches everything
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
        # Try title/slug first
        for cat, keywords in cat_rules:
            if any(kw in title_lower for kw in keywords):
                category = cat
                break
        else:
            # Fall back to body content
            content_lower = content.lower()
            for cat, keywords in cat_rules:
                if any(kw in content_lower for kw in keywords):
                    category = cat
                    break

        posts.append({
            "title": title,
            "date": date,
            "date_formatted": date.strftime("%d %B %Y"),
            "slug": slug,
            "excerpt": excerpt,
            "category": category,
            "filepath": filepath,
        })

    posts.sort(key=lambda p: p["date"], reverse=True)

    # ⚡ Store in cache
    _posts_cache["mtime"] = current_mtime
    _posts_cache["posts"] = posts
    return posts



@app.route("/")
def home():
    return render_template("home.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/news")
def news():
    posts = get_posts()
    return render_template("news.html", posts=posts)


@app.route("/news/<slug>")
def post(slug):
    posts = get_posts()
    post_data = next((p for p in posts if p["slug"] == slug), None)
    if not post_data:
        abort(404)

    with open(post_data["filepath"], "r", encoding="utf-8") as f:
        content = f.read()

    # Strip the first H1 (already displayed in the page hero)
    content = _RE_STRIP_H1.sub("", content, count=1).strip()
    html_content = markdown.markdown(content, extensions=["tables", "fenced_code"])

    # Load editor notes if available
    editor_path = post_data["filepath"].replace(".md", ".editor.md")
    editor_html = None
    if os.path.exists(editor_path):
        with open(editor_path, "r", encoding="utf-8") as f:
            editor_raw = f.read()
        # Strip the top-level "# Editor Notes: ..." heading
        editor_raw = re.sub(r"^#\s+Editor Notes:.*\n*", "", editor_raw, count=1).strip()

        # Strip any leftover raw [TAG]: markers from research brief
        editor_raw = re.sub(r"^\*{0,2}\[[\w_]+\]\*{0,2}\s*:?\s*$", "", editor_raw, flags=re.MULTILINE)

        # Promote plain-text labels from the Scribe's SEO output to headings
        for label in ["Meta Description", "Word Count", "Schema FAQ", "Editor Notes", "AEO Snippet"]:
            editor_raw = re.sub(rf"^(\*?\*?{label}\*?\*?):\s*", rf"### \1\n\n", editor_raw, flags=re.MULTILINE)

        # Strip stray standalone bold markers (e.g. "**\n")
        editor_raw = re.sub(r"^\*{2,}\s*$", "", editor_raw, flags=re.MULTILINE)

        # Collapse triple+ blank lines to double
        editor_raw = re.sub(r"\n{3,}", "\n\n", editor_raw)

        editor_html = markdown.markdown(editor_raw, extensions=["tables", "fenced_code"])

        # Style the audit verdict banner green/red
        editor_html = editor_html.replace(
            '<blockquote>\n<p>✅',
            '<div style="background:#ecfdf5;border-left:4px solid #10b981;border-radius:0.375rem;padding:0.75rem 1rem;margin-bottom:1.5rem;font-size:0.875rem;color:#065f46"><p>✅'
        ).replace(
            '<blockquote>\n<p>❌',
            '<div style="background:#fef2f2;border-left:4px solid #ef4444;border-radius:0.375rem;padding:0.75rem 1rem;margin-bottom:1.5rem;font-size:0.875rem;color:#991b1b"><p>❌'
        )
        if '<div style="background:#ecfdf5' in editor_html or '<div style="background:#fef2f2' in editor_html:
            editor_html = editor_html.replace('</blockquote>', '</div>', 1)

    return render_template("post.html", post=post_data, content=html_content, editor_html=editor_html)


# --- API: Article Generation ---

def _run_generation(task_id, area, mode):
    """Run the pipeline in a background thread."""
    try:
        from pipeline import run_pipeline

        def _on_stage(stage):
            _tasks[task_id]["stage"] = stage

        result = run_pipeline(area, mode=mode, on_stage=_on_stage)
        _tasks[task_id] = {"status": "done", "post": result}
    except Exception as e:
        _tasks[task_id] = {"status": "error", "message": str(e)}


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(force=True)
    area = data.get("area", "").strip()
    mode = data.get("mode", "original").strip()
    if not area:
        return jsonify({"error": "Missing 'area' field"}), 400

    task_id = str(uuid.uuid4())
    _tasks[task_id] = {"status": "running"}

    thread = threading.Thread(target=_run_generation, args=(task_id, area, mode), daemon=True)
    thread.start()

    return jsonify({"task_id": task_id})


@app.route("/api/generate/<task_id>")
def api_generate_status(task_id):
    task = _tasks.get(task_id)
    if not task:
        return jsonify({"error": "Unknown task"}), 404
    return jsonify(task)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
