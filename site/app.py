"""Parachute Law demo website — Flask app serving the premium dark-theme site."""

import os
import re
import sys
import glob
import uuid
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

# Background task tracking
_tasks = {}


def get_posts():
    """Load all markdown files from output/ and return sorted post list."""
    posts = []
    md_files = [f for f in glob.glob(os.path.join(OUTPUT_DIR, "*.md"))
                if not f.endswith(".editor.md") and not f.endswith(".audit.md")]

    for filepath in md_files:
        filename = os.path.basename(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract title from first H1
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1) if title_match else filename.replace(".md", "").replace("-", " ").title()

        # Extract date from filename (e.g., 2026-03-04-pension-sharing.md)
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
        if date_match:
            date_str = date_match.group(1)
            date = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            date = datetime.fromtimestamp(os.path.getmtime(filepath))

        # Generate slug from filename (strip date prefix and extension)
        slug = re.sub(r"^\d{4}-\d{2}-\d{2}-?", "", filename)
        slug = slug.replace(".md", "")
        if not slug:
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")

        # Excerpt: first 150 chars of body text (skip title line)
        body = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
        body_text = re.sub(r"[#*_\[\]()>`]", "", body)
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
    content = re.sub(r"^#\s+.+\n*", "", content, count=1).strip()
    html_content = markdown.markdown(content, extensions=["tables", "fenced_code"])

    # Load editor notes if available
    editor_path = post_data["filepath"].replace(".md", ".editor.md")
    editor_html = None
    if os.path.exists(editor_path):
        with open(editor_path, "r", encoding="utf-8") as f:
            editor_raw = f.read()
        # Strip the top-level "# Editor Notes: ..." heading
        editor_raw = re.sub(r"^#\s+Editor Notes:.*\n*", "", editor_raw, count=1).strip()
        # Promote plain-text labels from the Scribe's SEO output to headings
        for label in ["Meta Description", "Word Count", "Schema FAQ", "Editor Notes", "AEO Snippet"]:
            editor_raw = re.sub(rf"^(\*?\*?{label}\*?\*?):\s*", rf"### \1\n\n", editor_raw, flags=re.MULTILINE)
        # Clean stray bold markers around section tags
        editor_raw = re.sub(r"^\*\*\[.*?\]\*\*\s*$", "", editor_raw, flags=re.MULTILINE)
        editor_raw = re.sub(r"^\*\*\[.*?\]:\*\*\s*$", "", editor_raw, flags=re.MULTILINE)
        editor_html = markdown.markdown(editor_raw, extensions=["tables", "fenced_code"])

    return render_template("post.html", post=post_data, content=html_content, editor_html=editor_html)


# --- API: Article Generation ---

def _run_generation(task_id, area, mode):
    """Run the pipeline in a background thread."""
    try:
        from pipeline import run_pipeline
        result = run_pipeline(area, mode=mode)
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
    app.run(debug=True, port=5000)
