# Neuron Daily AI Skills

A static, searchable archive of 107 AI skills — prompts, tactics, and frameworks
sourced from [The Neuron Daily](https://www.theneurondaily.com) newsletter.

## Build

```bash
python build.py            # build the site from data/skills.json
python build.py --reseed   # first rebuild data/skills.json from ../AI_Skills_Neuron/
```

`data/skills.json` is the source of truth (the daily scraper appends to it).
`build.py` regenerates, from that JSON:

- `index.html` — searchable, filterable card grid of all skills
- `skills/<slug>/index.html` — a self-contained page per skill

Every page is self-contained (only external dependency is Google Fonts).
The site auto-updates daily via `.github/workflows/daily-update.yml`
(scrape → `build.py` → commit).

## View

Open `index.html` in a browser, or serve the folder:

```bash
python -m http.server
```
