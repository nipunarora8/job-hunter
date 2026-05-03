# Job Hunter

A self-hosted job scraper and dashboard for finding English-friendly tech jobs in Germany. Scrapes multiple job boards daily, uses an LLM to score relevance against your profile, and serves a clean dashboard to browse and track applications.

![Dashboard](https://i.imgur.com/placeholder.png)

## Features

- Scrapes **Arbeitnow**, **Bundesagentur**, **LinkedIn**, **StepStone**
- LLM-powered relevance scoring (1–10) against your profile
- Auto-detects German language requirements and filters them out
- Filter by category (AI / Robotics / Software), source, date, score, seniority
- Track application status: New → Saved → Applied
- Daily auto-scrape at 8am + manual trigger from dashboard
- Single command to start everything

## Quickstart

### 1. Clone & configure

```bash
git clone https://github.com/nipunarora8/job-hunter.git
cd job-hunter
```

Copy the env template and add your OpenRouter API key (free at [openrouter.ai](https://openrouter.ai)):

```bash
cp .env.example .env
# edit .env and set OPENROUTER_API_KEY=...
```

Edit `user_config.yaml` to set your profile, search keywords, and preferred model.

### 2. Setup

```bash
./setup.sh
```

This installs all Python dependencies and the Chromium browser for scraping.

### 3. Run

```bash
./run.sh
```

Dashboard available at **http://localhost:8000**

## Configuration

All user-facing settings live in `user_config.yaml`:

| Field | Description |
|---|---|
| `openrouter_model` | LLM model for analysis. Use a `:free` model to stay on the free tier. |
| `min_relevance_score` | Jobs scoring below this (1–10) are discarded. |
| `search_keywords` | Keywords sent to each job board. |
| `profile` | Your skills/experience summary — used by the LLM to score jobs. |

### Free models

The default model is `meta-llama/llama-3.1-8b-instruct:free`. Other free options:
- `mistralai/mistral-7b-instruct:free`
- `google/gemma-2-9b-it:free`

Full list: https://openrouter.ai/models?q=free

## Forking for your own use

1. Fork this repo
2. Edit `user_config.yaml` — update `profile` and `search_keywords`
3. Set `OPENROUTER_API_KEY` in `.env`
4. Run `./setup.sh` then `./run.sh`

## Project structure

```
job-hunter/
├── user_config.yaml   # your profile, keywords, model — edit this
├── .env               # API key (never committed)
├── run.sh             # start everything
├── setup.sh           # one-time setup
└── src/
    ├── api.py         # FastAPI backend
    ├── db.py          # SQLite helpers
    ├── analyzer.py    # LLM scoring
    ├── scheduler.py   # daily scrape job
    ├── config.py      # loads user_config.yaml + .env
    ├── scrapers/      # one file per job board
    └── frontend/      # Alpine.js dashboard (no build step)
```

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- An [OpenRouter](https://openrouter.ai) API key (free tier works)
