# Neuron Daily AI Skills

A static, searchable archive of 107 AI skills — prompts, tactics, and frameworks
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
