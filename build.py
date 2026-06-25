#!/usr/bin/env python3
"""Generate a multi-file static site from the AI_Skills_Neuron source directory.

Walks ../AI_Skills_Neuron/, parses each skill's README.md (+ prompt.md), assigns
a category by keyword matching, and writes:

    index.html                  -- hub with searchable/filterable card grid
    skills/<slug>/index.html     -- one self-contained page per skill
    README.md                    -- minimal project readme

Run from the repo root:  python build.py
"""

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT.parent / "AI_Skills_Neuron"

# ---------------------------------------------------------------------------
# Design system
# ---------------------------------------------------------------------------
THEME = """
  --bg: #0d0d12;
  --surface: #13131a;
  --border: #1e1e2e;
  --text: #e2e2f0;
  --muted: #6b6b8a;
  --accent: #7c5cfc;
  --accent-glow: rgba(124,92,252,0.15);
"""

CATEGORY_COLORS = {
    "Prompting": "#7c5cfc",
    "Agents": "#3b82f6",
    "Coding": "#10b981",
    "Productivity": "#f59e0b",
    "Security": "#ef4444",
    "Tools & Platforms": "#06b6d4",
    "Content": "#ec4899",
    "Learning": "#8b5cf6",
    "Other": "#6b7280",
}

# Keyword -> category. Title hits are weighted more heavily than body hits.
# Order here also defines tie-break priority (earlier wins).
CATEGORY_KEYWORDS = [
    ("Security", ["security", "vulnerab", "exploit", "malware", "phishing",
                  "jailbreak", "attack", "dangerous", "steal", "cyber",
                  "threat", "hack", "breach", "prompt injection"]),
    ("Coding", ["code", "coding", "debug", "codex", "cursor", "repo",
                "git ", "programming", "refactor", "developer", "compile",
                "token waste", "claude code", "definition of done", "ide",
                "terminal", "pull request", "function call"]),
    ("Agents", ["agent", "agentic", "autonomous", "cowork", "multi-agent",
                "subagent", "orchestrat", "agent's memory", "executive assistant"]),
    ("Prompting", ["prompt", "prompting", "system prompt", "instruction",
                   "chain-of-thought", "few-shot", "rewrite", "goal instead of a prompt"]),
    ("Content", ["flowchart", "diagram", "slides", "presentation",
                 "blog", "video", "image", "marketing", "social", "newsletter",
                 "youtube", "docs", "document", "pdf", "writing", "write",
                 "content", "google docs", "sheets"]),
    ("Learning", ["learn", "teach", "study", "course", "tutor", "education",
                  "understand", "explain", "knowledge", "second brain"]),
    ("Productivity", ["productivity", "workflow", "automation", "automate",
                      "email", "calendar", "digest", "assistant", "schedule",
                      "notion", "spreadsheet", "meeting", "inbox", "brief",
                      "morning", "operations", "personal"]),
    ("Tools & Platforms", ["chatgpt", "gemini", "copilot", "microsoft",
                           "openai", "perplexity", "platform", "api",
                           "integration", "vidiq", "connect", "365",
                           "openclaw", "poke", "model"]),
]


def assign_category(title, body):
    title_l = title.lower()
    body_l = body.lower()
    best, best_score = "Other", 0
    for cat, words in CATEGORY_KEYWORDS:
        score = 0
        for w in words:
            score += title_l.count(w) * 3
            score += body_l.count(w)
        if score > best_score:
            best, best_score = cat, score
    return best


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
SECTION_ALIASES = {
    "what": ["What This Skill Is"],
    "why": ["Why It Works"],
    "how": ["How to Use It"],
}


def split_sections(text):
    """Return {heading: body} for every '## ' section in the README."""
    sections = {}
    current = None
    buf = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.*)$", line)
        if m:
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = m.group(1).strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


def parse_skill(skill_dir):
    readme = (skill_dir / "README.md").read_text(encoding="utf-8")

    title_m = re.search(r"^#\s+(.+)$", readme, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else skill_dir.name

    src_m = re.search(r"\*\*Source:\*\*\s*(.+)", readme)
    source_text, source_url = None, None
    if src_m:
        raw = src_m.group(1).strip()
        link = re.match(r"\[([^\]]+)\]\(([^)]+)\)", raw)
        if link:
            source_text, source_url = link.group(1).strip(), link.group(2).strip()
        else:
            source_text = raw

    date_m = re.search(r"\*\*Date:\*\*\s*(.+)", readme)
    date = date_m.group(1).strip() if date_m else None

    sections = split_sections(readme)

    def get_section(keys):
        for k in keys:
            if k in sections:
                return sections[k]
        return ""

    what = get_section(SECTION_ALIASES["what"])
    why = get_section(SECTION_ALIASES["why"])
    how = get_section(SECTION_ALIASES["how"])

    # Prompt: prefer the raw prompt.md (always present, no markdown noise).
    prompt_path = skill_dir / "prompt.md"
    prompt = prompt_path.read_text(encoding="utf-8").strip() if prompt_path.exists() else ""

    category = assign_category(title, f"{what}\n{why}\n{how}")
    summary = first_sentences(what, 2)

    return {
        "slug": skill_dir.name,
        "title": title,
        "source_text": source_text,
        "source_url": source_url,
        "date": date,
        "what": what,
        "why": why,
        "how": how,
        "prompt": prompt,
        "category": category,
        "summary": summary,
    }


def first_sentences(text, n):
    """Grab the first n sentences of plain prose for a card summary."""
    # Drop markdown emphasis and collapse whitespace.
    plain = re.sub(r"[*_`#>]", "", text)
    plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", plain)
    plain = " ".join(plain.split())
    parts = re.split(r"(?<=[.!?])\s+", plain)
    summary = " ".join(parts[:n]).strip()
    if len(summary) > 240:
        summary = summary[:237].rstrip() + "…"
    return summary


# ---------------------------------------------------------------------------
# Minimal markdown -> HTML (handles what these docs actually use)
# ---------------------------------------------------------------------------
def md_inline(text):
    text = html.escape(text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                  lambda m: f'<a href="{m.group(2)}" target="_blank" rel="noopener">{m.group(1)}</a>',
                  text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def md_to_html(text):
    """Block-level converter: paragraphs, bullet/numbered lists, sub-headings,
    fenced code blocks."""
    lines = text.split("\n")
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Fenced code block
        if stripped.startswith("```"):
            i += 1
            code = []
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            out.append("<pre class=\"codeblock\"><code>" +
                       html.escape("\n".join(code)) + "</code></pre>")
            continue

        # Sub-heading
        h = re.match(r"^(#{3,6})\s+(.*)$", stripped)
        if h:
            level = min(len(h.group(1)), 6)
            out.append(f"<h{level}>{md_inline(h.group(2))}</h{level}>")
            i += 1
            continue

        # Unordered list
        if re.match(r"^[-*]\s+", stripped):
            items = []
            while i < n and re.match(r"^[-*]\s+", lines[i].strip()):
                items.append(md_inline(re.sub(r"^[-*]\s+", "", lines[i].strip())))
                i += 1
            out.append("<ul>" + "".join(f"<li>{it}</li>" for it in items) + "</ul>")
            continue

        # Ordered list
        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < n and re.match(r"^\d+\.\s+", lines[i].strip()):
                items.append(md_inline(re.sub(r"^\d+\.\s+", "", lines[i].strip())))
                i += 1
            out.append("<ol>" + "".join(f"<li>{it}</li>" for it in items) + "</ol>")
            continue

        # Paragraph (gather consecutive non-blank, non-special lines)
        para = []
        while i < n and lines[i].strip() and not re.match(
                r"^(```|#{3,6}\s|[-*]\s|\d+\.\s)", lines[i].strip()):
            para.append(lines[i].strip())
            i += 1
        out.append(f"<p>{md_inline(' '.join(para))}</p>")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------
FONT_LINK = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
             '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
             '<link href="https://fonts.googleapis.com/css2?'
             'family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">')


def pill(category):
    color = CATEGORY_COLORS.get(category, CATEGORY_COLORS["Other"])
    return (f'<span class="pill" style="--pill:{color}">'
            f'{html.escape(category)}</span>')


def skill_page(skill):
    title = html.escape(skill["title"])
    meta_bits = []
    if skill["source_url"]:
        meta_bits.append(
            f'<a class="meta-link" href="{html.escape(skill["source_url"])}" '
            f'target="_blank" rel="noopener">Source ↗</a>')
    elif skill["source_text"]:
        meta_bits.append(f'<span class="meta-item">{html.escape(skill["source_text"])}</span>')
    if skill["date"]:
        meta_bits.append(f'<span class="meta-item">{html.escape(skill["date"])}</span>')
    meta_bits.append(pill(skill["category"]))
    meta_row = " ".join(meta_bits)

    prompt_raw = skill["prompt"]
    prompt_html = html.escape(prompt_raw)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Neuron Daily AI Skills</title>
{FONT_LINK}
<style>{PAGE_CSS}</style>
</head>
<body>
<div class="wrap">
  <a class="back" href="../../index.html">← All Skills</a>
  <h1>{title}</h1>
  <div class="meta-row">{meta_row}</div>

  <section>
    <h2>What This Skill Is</h2>
    {md_to_html(skill["what"])}
  </section>

  <section>
    <h2>Why It Works</h2>
    {md_to_html(skill["why"])}
  </section>

  <section>
    <h2>How to Use It</h2>
    {md_to_html(skill["how"])}
  </section>

  <section>
    <div class="prompt-head">
      <h2>Prompt Template</h2>
      <button class="copy-btn" id="copyBtn">Copy</button>
    </div>
    <pre class="prompt-box"><code id="promptText">{prompt_html}</code></pre>
  </section>

  <footer>Sourced from <a href="https://www.theneurondaily.com" target="_blank" rel="noopener">theneurondaily.com</a></footer>
</div>
<script>
const btn = document.getElementById('copyBtn');
btn.addEventListener('click', async () => {{
  const text = document.getElementById('promptText').textContent;
  try {{
    await navigator.clipboard.writeText(text);
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(() => {{ btn.textContent = 'Copy'; btn.classList.remove('copied'); }}, 1800);
  }} catch (e) {{
    const r = document.createRange();
    r.selectNode(document.getElementById('promptText'));
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(r);
    document.execCommand('copy');
    btn.textContent = 'Copied!';
    setTimeout(() => {{ btn.textContent = 'Copy'; }}, 1800);
  }}
}});
</script>
</body>
</html>"""


def index_page(skills):
    cards = [{
        "slug": s["slug"],
        "title": s["title"],
        "date": s["date"] or "",
        "category": s["category"],
        "summary": s["summary"],
    } for s in skills]
    data_json = json.dumps(cards, ensure_ascii=False)

    # Filter pills: "All" + each category that actually appears, in map order.
    present = [c for c in CATEGORY_COLORS if any(s["category"] == c for s in skills)]
    color_js = json.dumps(CATEGORY_COLORS, ensure_ascii=False)

    filter_pills = ['<button class="fpill active" data-cat="All">All</button>']
    for c in present:
        filter_pills.append(
            f'<button class="fpill" data-cat="{html.escape(c)}" '
            f'style="--pill:{CATEGORY_COLORS[c]}">{html.escape(c)}</button>')
    filter_html = "\n      ".join(filter_pills)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Neuron Daily AI Skills</title>
{FONT_LINK}
<style>{INDEX_CSS}</style>
</head>
<body>
<header class="hero">
  <h1>Neuron Daily AI Skills</h1>
  <p class="subtitle">107 prompts, tactics &amp; frameworks sourced from The Neuron Daily newsletter</p>
  <input id="search" class="search" type="search" placeholder="Search skills…" autocomplete="off">
  <div class="filters">
      {filter_html}
  </div>
</header>

<main>
  <div id="grid" class="grid"></div>
  <p id="empty" class="empty" hidden>No skills match your search.</p>
</main>

<footer class="page-footer">Sourced from <a href="https://www.theneurondaily.com" target="_blank" rel="noopener">theneurondaily.com</a></footer>

<script>
const SKILLS = {data_json};
const COLORS = {color_js};
const grid = document.getElementById('grid');
const search = document.getElementById('search');
const empty = document.getElementById('empty');
let activeCat = 'All';
let query = '';

function esc(s) {{
  return s.replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
}}

function cardHTML(s) {{
  const color = COLORS[s.category] || COLORS['Other'];
  const date = s.date ? `<span class="card-date">${{esc(s.date)}}</span>` : '';
  return `<a class="card" href="./skills/${{encodeURIComponent(s.slug)}}/">
    <div class="card-top">
      <span class="pill" style="--pill:${{color}}">${{esc(s.category)}}</span>
      ${{date}}
    </div>
    <h3 class="card-title">${{esc(s.title)}}</h3>
    <p class="card-summary">${{esc(s.summary)}}</p>
    <span class="card-link">View Skill →</span>
  </a>`;
}}

function render() {{
  const q = query.trim().toLowerCase();
  const items = SKILLS.filter(s => {{
    if (activeCat !== 'All' && s.category !== activeCat) return false;
    if (!q) return true;
    return s.title.toLowerCase().includes(q) || s.summary.toLowerCase().includes(q);
  }});
  grid.innerHTML = items.map(cardHTML).join('');
  empty.hidden = items.length !== 0;
}}

search.addEventListener('input', e => {{ query = e.target.value; render(); }});

document.querySelectorAll('.fpill').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.fpill').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeCat = btn.dataset.cat;
    render();
  }});
}});

render();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
BASE_CSS = f"""
:root {{{THEME}}}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{
  background: var(--bg);
  color: var(--text);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.pill {{
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  color: var(--pill);
  background: color-mix(in srgb, var(--pill) 14%, transparent);
  border: 1px solid color-mix(in srgb, var(--pill) 35%, transparent);
  white-space: nowrap;
}}
"""

INDEX_CSS = BASE_CSS + """
.hero {
  max-width: 1200px;
  margin: 0 auto;
  padding: 4rem 1.5rem 1.5rem;
  text-align: center;
}
.hero h1 {
  font-size: clamp(2rem, 5vw, 3.2rem);
  font-weight: 800;
  margin: 0 0 0.5rem;
  letter-spacing: -0.02em;
  background: linear-gradient(120deg, var(--text), var(--accent));
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.subtitle { color: var(--muted); font-size: 1.05rem; margin: 0 auto 2rem; max-width: 640px; }
.search {
  width: 100%;
  max-width: 560px;
  padding: 0.85rem 1.1rem;
  font-size: 1rem;
  font-family: inherit;
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  outline: none;
  transition: border-color .15s, box-shadow .15s;
}
.search:focus { border-color: var(--accent); box-shadow: 0 0 0 4px var(--accent-glow); }
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
  margin-top: 1.5rem;
}
.fpill {
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 600;
  padding: 0.35rem 0.85rem;
  border-radius: 999px;
  cursor: pointer;
  color: var(--muted);
  background: var(--surface);
  border: 1px solid var(--border);
  transition: all .15s;
}
.fpill:hover { color: var(--text); border-color: var(--muted); }
.fpill[data-cat="All"].active { color: #fff; background: var(--accent); border-color: var(--accent); }
.fpill.active:not([data-cat="All"]) {
  color: var(--pill);
  border-color: var(--pill);
  background: color-mix(in srgb, var(--pill) 16%, transparent);
}
main { max-width: 1200px; margin: 0 auto; padding: 1rem 1.5rem 4rem; }
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.25rem;
}
@media (max-width: 900px) { .grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 600px) { .grid { grid-template-columns: 1fr; } .hero { padding-top: 2.5rem; } }
.card {
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1.25rem;
  color: inherit;
  text-decoration: none;
  transition: transform .15s, border-color .15s, box-shadow .15s;
}
.card:hover {
  transform: translateY(-3px);
  border-color: var(--accent);
  box-shadow: 0 8px 30px var(--accent-glow);
  text-decoration: none;
}
.card-top { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.85rem; }
.card-date { color: var(--muted); font-size: 0.75rem; }
.card-title { font-size: 1.05rem; font-weight: 700; margin: 0 0 0.5rem; line-height: 1.35; }
.card-summary { color: var(--muted); font-size: 0.88rem; margin: 0 0 1rem; flex: 1; }
.card-link { color: var(--accent); font-weight: 600; font-size: 0.85rem; }
.empty { text-align: center; color: var(--muted); padding: 3rem 0; }
.page-footer { text-align: center; color: var(--muted); padding: 2rem 1.5rem 3rem; font-size: 0.85rem; }
"""

PAGE_CSS = BASE_CSS + """
.wrap { max-width: 760px; margin: 0 auto; padding: 2.5rem 1.5rem 4rem; }
.back { display: inline-block; color: var(--muted); font-size: 0.9rem; margin-bottom: 1.5rem; }
.back:hover { color: var(--accent); text-decoration: none; }
h1 { font-size: clamp(1.6rem, 4vw, 2.4rem); font-weight: 800; line-height: 1.2; margin: 0 0 1rem; letter-spacing: -0.02em; }
.meta-row { display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem; margin-bottom: 2.5rem; padding-bottom: 1.5rem; border-bottom: 1px solid var(--border); }
.meta-link, .meta-item { font-size: 0.85rem; color: var(--muted); }
.meta-link:hover { color: var(--accent); }
section { margin-bottom: 2.5rem; }
section h2 { font-size: 1.25rem; font-weight: 700; margin: 0 0 0.75rem; color: var(--text); }
section p { color: #c9c9de; margin: 0 0 1rem; }
section ul, section ol { color: #c9c9de; padding-left: 1.4rem; margin: 0 0 1rem; }
section li { margin-bottom: 0.4rem; }
section h3, section h4 { font-size: 1rem; font-weight: 600; margin: 1.25rem 0 0.5rem; color: var(--text); }
code { font-family: 'SF Mono', ui-monospace, 'Cascadia Code', Menlo, Consolas, monospace; font-size: 0.85em; background: var(--bg); padding: 0.1rem 0.35rem; border-radius: 5px; border: 1px solid var(--border); }
.codeblock { background: var(--bg); border: 1px solid var(--border); border-radius: 10px; padding: 1rem; overflow-x: auto; }
.codeblock code { background: none; border: none; padding: 0; }
.prompt-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem; }
.prompt-head h2 { margin: 0; }
.copy-btn {
  font-family: inherit; font-size: 0.8rem; font-weight: 600;
  color: var(--accent); background: var(--accent-glow);
  border: 1px solid color-mix(in srgb, var(--accent) 40%, transparent);
  padding: 0.4rem 0.9rem; border-radius: 8px; cursor: pointer; transition: all .15s;
}
.copy-btn:hover { background: var(--accent); color: #fff; }
.copy-btn.copied { background: #10b981; color: #fff; border-color: #10b981; }
.prompt-box {
  background: #08080c; border: 1px solid var(--border); border-radius: 12px;
  padding: 1.25rem; overflow-x: auto; white-space: pre-wrap; word-wrap: break-word;
}
.prompt-box code {
  font-family: 'SF Mono', ui-monospace, 'Cascadia Code', Menlo, Consolas, monospace;
  font-size: 0.85rem; color: #d7d7e8; background: none; border: none; padding: 0; line-height: 1.55;
}
footer { color: var(--muted); font-size: 0.85rem; text-align: center; padding-top: 2rem; border-top: 1px solid var(--border); }
"""


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def main():
    if not SRC.exists():
        raise SystemExit(f"Source directory not found: {SRC}")

    skill_dirs = sorted(
        d for d in SRC.iterdir()
        if d.is_dir() and (d / "README.md").exists()
    )

    skills = [parse_skill(d) for d in skill_dirs]
    skills.sort(key=lambda s: s["title"].lower())

    # Per-skill pages
    skills_root = ROOT / "skills"
    skills_root.mkdir(exist_ok=True)
    for s in skills:
        out_dir = skills_root / s["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(skill_page(s), encoding="utf-8")

    # Hub
    (ROOT / "index.html").write_text(index_page(skills), encoding="utf-8")

    # README
    (ROOT / "README.md").write_text(readme_text(len(skills)), encoding="utf-8")

    # Category distribution report
    dist = {}
    for s in skills:
        dist[s["category"]] = dist.get(s["category"], 0) + 1
    print(f"Built {len(skills)} skill pages.")
    for cat in CATEGORY_COLORS:
        if cat in dist:
            print(f"  {cat:20s} {dist[cat]}")


def readme_text(n):
    return f"""# Neuron Daily AI Skills

A static, searchable archive of {n} AI skills — prompts, tactics, and frameworks
sourced from [The Neuron Daily](https://www.theneurondaily.com) newsletter.

## Build

```bash
python build.py
```

This walks `../AI_Skills_Neuron/`, parses each skill's `README.md` and
`prompt.md`, assigns a category, and regenerates:

- `index.html` — searchable, filterable card grid of all skills
- `skills/<slug>/index.html` — a self-contained page per skill

Every page is self-contained (only external dependency is Google Fonts).

## View

Open `index.html` in a browser, or serve the folder:

```bash
python -m http.server
```
"""


if __name__ == "__main__":
    main()
