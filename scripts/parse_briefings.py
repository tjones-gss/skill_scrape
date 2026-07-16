#!/usr/bin/env python3
"""Parse daily AI dev briefings into a structured learnings.json feed.

Walks the daily-ai-news folder for briefing markdown files, extracts each day's
headlines and action items, tags them by topic, and writes agentic-hub/data/learnings.json.

This is what makes the hub *grow daily* — every briefing becomes a feed entry.

Run from anywhere: python parse_briefings.py [briefings_dir] [output_json]
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime

# Resolve paths
HERE = Path(__file__).resolve().parent
HUB_ROOT = HERE.parent                      # agentic-hub/
BRIEFINGS_DIR = HUB_ROOT.parent             # daily-ai-news/
OUTPUT = HUB_ROOT / "data" / "learnings.json"

if len(sys.argv) > 1:
    BRIEFINGS_DIR = Path(sys.argv[1])
if len(sys.argv) > 2:
    OUTPUT = Path(sys.argv[2])

# Topic tagging by keyword — maps mentions to a normalized tag
TAG_KEYWORDS = {
    "claude-code": ["claude code", "claude in chrome", "/dataviz", "background agent"],
    "cursor": ["cursor"],
    "codex": ["codex", "openai"],
    "copilot": ["copilot", "github copilot"],
    "gemini": ["gemini", "google deepmind", "deepmind"],
    "models": ["fable", "sonnet", "opus", "grok", "terra", "kimi", "mistral", "gpt-5", "model", "elo", "swe-bench"],
    "security": ["security", "vulnerab", "rce", "cve", "exploit", "patch tuesday", "prompt injection", "zero-click", "zero-day", "malware"],
    "vscode": ["vs code", "vscode", "visual studio"],
    "pricing": ["pricing", "$", "cost", "billing", "included access", "promo"],
    "mcp": ["mcp", "model context protocol"],
    "harness": ["harness", "hook", "agent definition", "orchestrat"],
    "tools": ["tool", "hardware", "macro pad", "extension", "cli"],
}

# Which filenames are briefings, and how to get the date out of them
DATE_PATTERNS = [
    re.compile(r"(\d{4}-\d{2}-\d{2})"),
]

# Section header keywords (formats have varied across months)
NEWS_SECTION_KW = ["headline", "big story", "development", "breaking", "hot",
                   "what's new", "top stories", "news"]
ACTION_SECTION_KW = ["action", "what to do", "what you can use", "recommend",
                     "harness update", "do today", "do now"]
LEAD_PREFIXES = ("headline:", "the big story", "breaking:", "big story:")
MAX_HEADLINES = 12


def extract_date(fname):
    for pat in DATE_PATTERNS:
        m = pat.search(fname)
        if m:
            try:
                return datetime.strptime(m.group(1), "%Y-%m-%d").date()
            except ValueError:
                pass
    return None


def tag_text(text):
    """Return the list of topic tags that appear in a chunk of text."""
    low = text.lower()
    tags = []
    for tag, words in TAG_KEYWORDS.items():
        if any(w in low for w in words):
            tags.append(tag)
    return tags


def clean_title(raw):
    """Strip leading 'N. ' numbering and markdown emphasis from a heading."""
    t = re.sub(r"^\d+\.\s*", "", raw.strip())
    t = re.sub(r"[*_`]", "", t)
    return t.strip()


def first_sentence(text, max_len=200):
    plain = re.sub(r"[*_`#>\-]", " ", text)
    plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", plain)
    plain = " ".join(plain.split())
    parts = re.split(r"(?<=[.!?])\s+", plain)
    out = ""
    for p in parts:
        if len(p) > 15 and not re.match(r"^(Released|Launch|Status|Published|Active|Rolling)", p):
            out = p
            break
    if not out and parts:
        out = parts[0]
    if len(out) > max_len:
        out = out[:max_len - 1].rstrip() + "…"
    return out.strip()


def split_h2_sections(text):
    """Return {heading: body} for every '## ' section."""
    sections = {}
    current, buf = None, []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.*)$", line)
        if m:
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current, buf = m.group(1).strip(), []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


def split_h3_items(body):
    """Return [(title, body)] for every '### ' item inside a section body."""
    items = []
    current, buf = None, []
    for line in body.splitlines():
        m = re.match(r"^###\s+(.*)$", line)
        if m:
            if current is not None:
                items.append((current, "\n".join(buf).strip()))
            current, buf = m.group(1).strip(), []
        elif current is not None:
            buf.append(line)
    if current is not None:
        items.append((current, "\n".join(buf).strip()))
    return items


def parse_briefing(path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    date = extract_date(path.name)
    if not date:
        return None

    title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = clean_title(title_m.group(1)) if title_m else ""
    day = date.strftime("%A")

    sections = split_h2_sections(text)

    # --- Headlines: collect h3 items from any news-like section, plus any
    #     h2 that is itself a headline (e.g. "HEADLINE: Fable 5 Is Back"). ---
    headlines = []
    seen_titles = set()

    def add_headline(ct, body):
        key = ct.lower()
        if not ct or key in seen_titles:
            return
        seen_titles.add(key)
        headlines.append({
            "title": ct,
            "note": first_sentence(body),
            "tags": tag_text(ct + " " + body),
        })

    for hkey, hbody in sections.items():
        klow = hkey.lower()
        if any(klow.startswith(p) for p in LEAD_PREFIXES) or ("headline" in klow and ":" in hkey):
            lead = re.sub(r"(?i)^(headline:|the big story:?|breaking:?|big story:?)\s*", "", hkey).strip()
            add_headline(clean_title(lead), hbody)
        if any(kw in klow for kw in NEWS_SECTION_KW):
            for htitle, hb in split_h3_items(hbody):
                add_headline(clean_title(htitle), hb)
        if len(headlines) >= MAX_HEADLINES:
            break
    headlines = headlines[:MAX_HEADLINES]

    # --- Action items ---
    actions = []
    for akey, abody in sections.items():
        if any(kw in akey.lower() for kw in ACTION_SECTION_KW):
            for atitle, ab in split_h3_items(abody):
                ct = clean_title(atitle)
                if ct and ct.lower() not in {a.lower() for a in actions}:
                    actions.append(ct)
            if not actions:
                for m in re.finditer(r"^(?:\d+\.|[-*])\s+(.+)$", abody, re.MULTILINE):
                    ct = clean_title(re.sub(r"\*\*", "", m.group(1)))
                    ct = re.split(r"[—:.]", ct)[0].strip()
                    if ct and len(ct) < 90 and ct.lower() not in {a.lower() for a in actions}:
                        actions.append(ct)
            if actions:
                break
    actions = actions[:8]

    all_tags = set()
    for h in headlines:
        all_tags.update(h["tags"])

    summary = headlines[0]["title"] if headlines else title

    return {
        "date": date.isoformat(),
        "day": day,
        "title": title,
        "summary": summary,
        "headlines": headlines,
        "actions": actions,
        "tags": sorted(all_tags),
        "headline_count": len(headlines),
        "action_count": len(actions),
    }


def main():
    files = []
    for p in BRIEFINGS_DIR.glob("*.md"):
        name = p.name.lower()
        if "briefing" in name and extract_date(p.name):
            files.append(p)

    entries = []
    for p in sorted(files):
        e = parse_briefing(p)
        if e and (e["headlines"] or e["actions"]):
            entries.append(e)

    entries.sort(key=lambda e: e["date"], reverse=True)

    seen, deduped = set(), []
    for e in entries:
        if e["date"] not in seen:
            seen.add(e["date"])
            deduped.append(e)

    payload = {
        "meta": {
            "generated": datetime.now().isoformat(timespec="seconds"),
            "count": len(deduped),
            "first": deduped[-1]["date"] if deduped else None,
            "latest": deduped[0]["date"] if deduped else None,
        },
        "entries": deduped,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(deduped)} daily entries to {OUTPUT}")
    if deduped:
        print(f"  Range: {payload['meta']['first']} -> {payload['meta']['latest']}")
        tagcount = {}
        for e in deduped:
            for t in e["tags"]:
                tagcount[t] = tagcount.get(t, 0) + 1
        top = sorted(tagcount.items(), key=lambda x: -x[1])[:8]
        print("  Top tags:", ", ".join(f"{k}({v})" for k, v in top))


if __name__ == "__main__":
    main()
