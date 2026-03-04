"""Parachute Law demo website — Flask app serving the premium dark-theme site."""

import os
import re
import glob
from datetime import datetime
from flask import Flask, render_template, abort
import markdown

SITE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(SITE_DIR, "templates"))

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")


def get_posts():
    """Load all markdown files from output/ and return sorted post list."""
    posts = []
    md_files = glob.glob(os.path.join(OUTPUT_DIR, "*.md"))

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

        # Try to detect category from content
        category = "Family Law"
        cat_keywords = {
            "Divorce": ["divorce", "separation", "decree"],
            "Pensions": ["pension", "CETV", "pension sharing"],
            "Property": ["property", "matrimonial home", "equity"],
            "Children": ["child arrangement", "custody", "parental"],
            "Wills & LPA": ["will", "lasting power", "probate", "LPA"],
            "Employment": ["employment", "tribunal", "unfair dismissal"],
        }
        content_lower = content.lower()
        for cat, keywords in cat_keywords.items():
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

    html_content = markdown.markdown(content, extensions=["tables", "fenced_code"])
    return render_template("post.html", post=post_data, content=html_content)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
