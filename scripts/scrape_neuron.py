#!/usr/bin/env python3
"""
scrape_neuron.py — Scrapes The Neuron Daily newsletter for AI Skills of the Day.

Usage:
    python scripts/scrape_neuron.py           # normal run, writes data
    python scripts/scrape_neuron.py --dry-run # fetch only, no writes
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_FILE = REPO_ROOT / "data" / "skills.json"
SKILLS_DIR = REPO_ROOT / "skills"

ARCHIVE_URL = "https://www.theneurondaily.com/archive"
BASE_URL = "https://www.theneurondaily.com"

CATEGORIES = {
    "Agents":      ["agent", "workflow", "autonomous", "loop", "subagent", "tool"],
    "Claude Code": ["claude code", "boris", "workflow mode", "subagent", "claude fable"],
    "ChatGPT":     ["chatgpt", "gpt", "openai", "record a task"],
    "Google":      ["gemini", "google flow", "google", "pomelli", "vidiq"],
    "Prompting":   ["prompt", "leitwort", "debug your prompt", "work receipt", "leading word", "judge"],
    "Coding":      ["code", "coding", "debug", "screenshot", "risk", "review"],
    "Business":    ["marketing", "campaign", "sales", "business", "stakeholder"],
    "Media":       ["video", "translation", "image", "camera", "stunning"],
}
DEFAULT_CATEGORY = "Productivity"


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:80].strip("-")


def auto_categorize(title: str, description: str) -> str:
    combined = (title + " " + description).lower()
    for category, keywords in CATEGORIES.items():
        if any(kw in combined for kw in keywords):
            return category
    return DEFAULT_CATEGORY


def fetch_archive_urls() -> list[str]:
    """Fetch all issue URLs from the Neuron Daily archive page."""
    resp = requests.get(ARCHIVE_URL, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    urls = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Match /p/<slug> pattern
        if re.match(r"^/p/[^/?#]+$", href):
            full_url = BASE_URL + href
            if full_url not in seen:
                seen.add(full_url)
                urls.append(full_url)
    return urls


def extract_skill_from_page(url: str) -> dict | None:
    """
    Fetch an issue page and extract the AI Skill of the Day section.
    Returns a skill dict or None if no skill found.
    """
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    # Find "AI Skill of the Day" heading (case-insensitive)
    skill_heading = None
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        if "ai skill of the day" in tag.get_text(strip=True).lower():
            skill_heading = tag
            break

    if not skill_heading:
        return None

    # The skill title is usually the next h2/h3 after the heading
    title = ""
    description_parts = []
    prompt_text = ""

    # Walk siblings after the skill heading
    current = skill_heading.find_next_sibling()
    collected = 0
    while current and collected < 20:
        tag_name = current.name if current.name else ""

        # Stop at next major heading that's not part of the skill
        if tag_name in ("h1", "h2", "h3") and title:
            text = current.get_text(strip=True).lower()
            if "ai skill" not in text:
                break

        if tag_name in ("h2", "h3") and not title:
            title = current.get_text(strip=True)
        elif tag_name == "p":
            description_parts.append(current.get_text(strip=True))
        elif tag_name in ("pre", "code", "blockquote"):
            prompt_text = current.get_text(strip=True)

        current = current.find_next_sibling()
        collected += 1

    if not title:
        return None

    description = " ".join(description_parts[:3])
    slug = slugify(title)
    category = auto_categorize(title, description)

    # Try to extract date from URL or page meta
    date_str = ""
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", url)
    if date_match:
        date_str = date_match.group(1)
    else:
        time_tag = soup.find("time")
        if time_tag and time_tag.get("datetime"):
            date_str = time_tag["datetime"][:10]

    return {
        "slug": slug,
        "title": title,
        "date": date_str,
        "source": url,
        "summary": description[:300],
        "what": description,
        "why": "",
        "how": "",
        "prompt": prompt_text,
        "category": category,
    }


def load_skills() -> list[dict]:
    if SKILLS_FILE.exists():
        with open(SKILLS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_skills(skills: list[dict]) -> None:
    SKILLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SKILLS_FILE, "w", encoding="utf-8") as f:
        json.dump(skills, f, indent=2, ensure_ascii=False)


def write_skill_files(skill: dict) -> None:
    skill_dir = SKILLS_DIR / skill["slug"]
    skill_dir.mkdir(parents=True, exist_ok=True)

    readme = skill_dir / "README.md"
    readme.write_text(
        f"# {skill['title']}\n\n"
        f"**Category:** {skill['category']}  \n"
        f"**Date:** {skill['date']}  \n"
        f"**Source:** {skill['source']}\n\n"
        f"## Summary\n\n{skill['summary']}\n\n"
        f"## What\n\n{skill['what']}\n\n"
        f"## Why\n\n{skill['why']}\n\n"
        f"## How\n\n{skill['how']}\n",
        encoding="utf-8",
    )

    prompt_file = skill_dir / "prompt.md"
    prompt_file.write_text(
        f"# Prompt: {skill['title']}\n\n"
        f"```\n{skill['prompt']}\n```\n",
        encoding="utf-8",
    )


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    existing_skills = load_skills()
    existing_sources = {s.get("source", "") for s in existing_skills}

    print(f"Fetching archive from {ARCHIVE_URL} ...")
    try:
        issue_urls = fetch_archive_urls()
    except Exception as e:
        print(f"ERROR: Could not fetch archive: {e}")
        sys.exit(1)

    new_urls = [u for u in issue_urls if u not in existing_sources]
    print(f"Found {len(issue_urls)} issues total, {len(new_urls)} new.")

    if dry_run:
        print("--dry-run: exiting without writing.")
        return

    new_skills = []
    for url in new_urls:
        try:
            skill = extract_skill_from_page(url)
            if skill:
                new_skills.append(skill)
                write_skill_files(skill)
                print(f"  + {skill['title'][:60]}")
        except Exception as e:
            print(f"  WARNING: skipping {url}: {e}")
        time.sleep(1)

    if new_skills:
        updated = existing_skills + new_skills
        save_skills(updated)

    print(f"Added {len(new_skills)} new skills.")


if __name__ == "__main__":
    main()
