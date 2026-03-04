# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this workspace.

---

## What This Is

The **Parachute Law Content Engine** — a CLI tool that automates the "Scout & Scribe" workflow for ParachuteLaw.co.uk. Uses Gemini for UK legal research and Claude for empathetic blog content generation.

See `parachute_spec.md` for the full project spec.

---

## Workspace Structure

```
.
├── CLAUDE.md              # This file — core context, always loaded
├── parachute_spec.md      # Full project specification
├── .claude/
│   └── commands/          # Slash commands (/prime, /create-plan, /implement)
├── main.py                # Entry point: accepts --topic argument
├── agents/
│   ├── __init__.py
│   ├── researcher.py      # Gemini Logic (Scout)
│   ├── writer.py          # Claude Logic (Scribe)
│   └── auditor.py         # Gemini Logic (Fact-Check)
├── prompts/
│   ├── research_dna.md    # System instructions for legal research
│   └── brand_voice.md     # Parachute Law tone & conversion guidelines
├── output/                # Generated articles saved here
└── site/
    ├── app.py             # Flask demo website (localhost:5000)
    └── templates/
        ├── base.html      # Shared layout (nav, footer, Tailwind/fonts)
        ├── home.html      # Landing page with all conversion sections
        ├── contact.html   # Contact form + office details
        ├── news.html      # Blog listing (reads from output/)
        └── post.html      # Single article view
```

---

## Launch Modes: `cr` and `cs`

Two shell aliases for launching Claude Code in this workspace:

| Alias | Mode | What it does |
|---|---|---|
| `cr` | **Regular** | Claude asks for confirmation before risky actions (default safe mode) |
| `cs` | **Skip confirmations** | Claude executes everything without asking — full auto-approve |

### Setup

Add these to your shell profile (`~/.bashrc` or `~/.bash_profile`):

```bash
# Parachute Law workspace — regular mode (asks for confirmation)
alias cr='cd /d/Dropbox/code/parachutelaw-blog && claude'

# Parachute Law workspace — skip confirmations (auto-approve everything)
alias cs='cd /d/Dropbox/code/parachutelaw-blog && claude --dangerously-skip-permissions'
```

Then reload your shell:

```bash
source ~/.bashrc
```

Now from any terminal:
- `cr` — launches Claude Code here, confirms before acting
- `cs` — launches Claude Code here, no confirmations

---

## Commands

### /prime
Initialize a session with full context awareness.

### /create-plan [request]
Create a detailed implementation plan in `plans/`.

### /implement [plan-path]
Execute a plan step by step.

---

## Workflow

1. **Scout:** Gemini researches UK 2026 legal data using `prompts/research_dna.md`
2. **Scribe:** Claude writes a 1,200-word article using `prompts/brand_voice.md`
3. **Critic:** Gemini audits the draft for hallucinated laws or stats
4. **Save:** Final article saved to `output/`

Run: `python main.py --topic "Pension Sharing"`

---

## Demo Website

A Flask-powered preview site mirroring parachutelaw.co.uk with a premium dark design.

```bash
pip install flask markdown
python site/app.py
# → http://localhost:5000
```

Pages: Home (`/`), Contact (`/contact`), News (`/news`), Article (`/news/<slug>`)

The `/news` page auto-discovers `.md` files from `output/` — generate articles with the content engine and they appear instantly.

---

## Critical Instruction: Maintain This File

Whenever Claude makes structural changes to the workspace, update this file to reflect the new state.
