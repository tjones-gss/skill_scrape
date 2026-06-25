# AI Skills Archive — The Neuron Daily

> 107+ AI Skills of the Day, organized and searchable. Auto-updated daily.

**Live site:** https://tjones-gss.github.io/skill_scrape

Skills sourced from [The Neuron Daily](https://www.theneurondaily.com) newsletter.  
Includes What's New updates from Claude Code and Cursor.

## Setup GitHub Pages

1. Push this repo to GitHub
2. Go to Settings → Pages
3. Source: **Deploy from a branch**
4. Branch: `main` · Folder: `/ (root)`
5. Save — site is live in ~60 seconds at `https://tjones-gss.github.io/skill_scrape`

## Run locally

```bash
pip install requests beautifulsoup4 lxml
python scripts/scrape_neuron.py   # fetch new skills
python scripts/fetch_changelogs.py # fetch tool updates
python scripts/build_html.py       # rebuild index.html
open index.html
```

## Project structure

```
skill_scrape/
├── index.html               # The live UI (GitHub Pages serves this)
├── data/
│   ├── skills.json          # All 107+ skills (source of truth)
│   └── changelog.json       # Recent Claude Code + Cursor updates
├── skills/                  # Individual skill folders (README + prompt)
├── scripts/
│   ├── scrape_neuron.py     # Scrapes new skills daily
│   ├── fetch_changelogs.py  # Fetches Cursor + Claude Code changelogs
│   └── build_html.py        # Rebuilds index.html from data
└── .github/workflows/
    └── daily-update.yml     # Runs Mon-Fri at 9am ET
```

## Manual trigger

Go to **Actions → Daily Skills Update → Run workflow** to trigger a manual update.
