#!/usr/bin/env python3
"""
fetch_changelogs.py — Fetches recent changelog entries from Cursor and Claude Code.

Usage:
    python scripts/fetch_changelogs.py
"""

import json
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG_FILE = REPO_ROOT / "data" / "changelog.json"

CURSOR_URL = "https://cursor.com/changelog"
CLAUDE_CODE_URL = "https://docs.anthropic.com/en/docs/claude-code/changelog"

MAX_ENTRIES = 30
MAX_NEW_PER_SOURCE = 3


def load_changelog() -> list[dict]:
    if CHANGELOG_FILE.exists():
        with open(CHANGELOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_changelog(entries: list[dict]) -> None:
    CHANGELOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHANGELOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def make_key(source: str, headline: str) -> str:
    return f"{source.lower()}|{headline.lower().strip()}"


def fetch_cursor_entries() -> list[dict]:
    """Parse Cursor changelog page for recent entries."""
    resp = requests.get(CURSOR_URL, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    entries = []
    headings = soup.find_all(["h2", "h3"])

    for heading in headings[:MAX_NEW_PER_SOURCE * 3]:
        text = heading.get_text(strip=True)
        if not text or len(text) < 3:
            continue

        # Try to extract a date from nearby text
        date_str = ""
        sibling = heading.find_next_sibling()
        context_text = text
        if sibling:
            context_text += " " + sibling.get_text(strip=True)

        date_match = re.search(
            r"(\d{4}-\d{2}-\d{2})|"
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}",
            context_text,
            re.IGNORECASE,
        )
        if date_match:
            raw = date_match.group(0)
            try:
                if "-" in raw:
                    date_str = raw
                else:
                    date_str = datetime.strptime(raw.replace(",", ""), "%b %d %Y").strftime("%Y-%m-%d")
            except ValueError:
                date_str = datetime.utcnow().strftime("%Y-%m-%d")
        else:
            date_str = datetime.utcnow().strftime("%Y-%m-%d")

        # Summary: grab first paragraph after heading
        summary = ""
        next_p = heading.find_next("p")
        if next_p:
            summary = next_p.get_text(strip=True)[:400]

        entries.append({
            "date": date_str,
            "source": "Cursor",
            "source_url": CURSOR_URL,
            "headline": text[:150],
            "summary": summary,
        })

        if len(entries) >= MAX_NEW_PER_SOURCE:
            break

    return entries


def fetch_claude_code_entries() -> list[dict]:
    """Parse Claude Code changelog page for recent versioned entries."""
    resp = requests.get(CLAUDE_CODE_URL, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    entries = []
    headings = soup.find_all(["h2", "h3"])

    for heading in headings[:MAX_NEW_PER_SOURCE * 3]:
        text = heading.get_text(strip=True)
        if not text or len(text) < 3:
            continue

        # Claude Code headings often look like "v1.2.3 (2026-01-15)" or just a date
        date_str = ""
        date_match = re.search(
            r"(\d{4}-\d{2}-\d{2})|"
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}",
            text,
            re.IGNORECASE,
        )
        if date_match:
            raw = date_match.group(0)
            try:
                if "-" in raw:
                    date_str = raw
                else:
                    date_str = datetime.strptime(raw.replace(",", ""), "%b %d %Y").strftime("%Y-%m-%d")
            except ValueError:
                date_str = datetime.utcnow().strftime("%Y-%m-%d")
        else:
            date_str = datetime.utcnow().strftime("%Y-%m-%d")

        # Summary from next paragraph or list
        summary = ""
        next_el = heading.find_next(["p", "ul", "li"])
        if next_el:
            summary = next_el.get_text(separator=" ", strip=True)[:400]

        entries.append({
            "date": date_str,
            "source": "Claude Code",
            "source_url": CLAUDE_CODE_URL,
            "headline": text[:150],
            "summary": summary,
        })

        if len(entries) >= MAX_NEW_PER_SOURCE:
            break

    return entries


def main() -> None:
    existing = load_changelog()
    existing_keys = {make_key(e["source"], e["headline"]) for e in existing}

    new_entries = []
    sources_updated = []

    # Cursor
    try:
        cursor_entries = fetch_cursor_entries()
        added = 0
        for entry in cursor_entries:
            k = make_key(entry["source"], entry["headline"])
            if k not in existing_keys:
                new_entries.append(entry)
                existing_keys.add(k)
                added += 1
        if added:
            sources_updated.append(f"Cursor ({added})")
    except Exception as e:
        print(f"WARNING: Could not fetch Cursor changelog: {e}")

    # Claude Code
    try:
        claude_entries = fetch_claude_code_entries()
        added = 0
        for entry in claude_entries:
            k = make_key(entry["source"], entry["headline"])
            if k not in existing_keys:
                new_entries.append(entry)
                existing_keys.add(k)
                added += 1
        if added:
            sources_updated.append(f"Claude Code ({added})")
    except Exception as e:
        print(f"WARNING: Could not fetch Claude Code changelog: {e}")

    combined = new_entries + existing
    combined = combined[:MAX_ENTRIES]
    save_changelog(combined)

    total = len(new_entries)
    if sources_updated:
        print(f"Added {total} new changelog entries from {', '.join(sources_updated)}.")
    else:
        print(f"Added {total} new changelog entries (no new entries found).")


if __name__ == "__main__":
    main()
