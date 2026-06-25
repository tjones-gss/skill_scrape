#!/usr/bin/env python3
"""
build_html.py — Injects skills and changelog data into index.html.

The index.html template must contain these placeholder strings in its JS:
    const SKILLS = __SKILLS_JSON__;
    const CHANGELOG = __CHANGELOG_JSON__;

Usage:
    python scripts/build_html.py
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_FILE = REPO_ROOT / "data" / "skills.json"
CHANGELOG_FILE = REPO_ROOT / "data" / "changelog.json"
INDEX_FILE = REPO_ROOT / "index.html"


def main() -> None:
    # Load data
    with open(SKILLS_FILE, "r", encoding="utf-8") as f:
        skills = json.load(f)

    with open(CHANGELOG_FILE, "r", encoding="utf-8") as f:
        changelog = json.load(f)

    # Read template
    html = INDEX_FILE.read_text(encoding="utf-8")

    # Inject data
    skills_json = json.dumps(skills, ensure_ascii=False)
    changelog_json = json.dumps(changelog, ensure_ascii=False)

    html = html.replace("__SKILLS_JSON__", skills_json)
    html = html.replace("__CHANGELOG_JSON__", changelog_json)

    # Write back
    INDEX_FILE.write_text(html, encoding="utf-8")

    print(f"Built index.html — {len(skills)} skills, {len(changelog)} changelog entries")


if __name__ == "__main__":
    main()
