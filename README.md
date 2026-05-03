# Job Hunter

A self-hosted job scraper and dashboard for finding English-friendly tech jobs in Germany. Scrapes multiple job boards daily, uses a free LLM to score relevance against your profile, and serves a clean dashboard to browse and track applications.

## Features

- Scrapes **Arbeitnow**, **Bundesagentur**, **LinkedIn**, **StepStone** in parallel
- LLM-powered relevance scoring (1–10) against your profile via [OpenRouter](https://openrouter.ai) (free tier)
- Auto-detects and filters out German language requirements
- Filter by category (AI / ML, Robotics, Software), source, date, score, seniority
- Track application status: New → Saved → Applied
- Paginated job list — no memory issues with large result sets
- Click "Pending Analysis" to see what's queued for analysis
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
# edit .env and set OPENROUTER_API_KEY=your_key_here
```

Edit `user_config.yaml` to set your profile, search keywords, and preferred model.

### 2. Setup

```bash
./setup.sh
```

Installs all Python dependencies and the Chromium browser for scraping.

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
| `min_relevance_score` | Jobs scoring below this (1–10) are discarded. Default: 4 |
| `search_keywords` | Keywords sent to each job board. |
| `profile` | Your skills/experience summary — used by the LLM to score jobs. |

### Free models

- `openrouter/free` (default — auto-routes to available free models)
- `meta-llama/llama-3.1-8b-instruct:free`
- `mistralai/mistral-7b-instruct:free`

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
    ├── scheduler.py   # parallel scraping + analysis loop
    ├── config.py      # loads user_config.yaml + .env
    ├── scrapers/      # one file per job board
    └── frontend/      # Alpine.js dashboard (no build step)
```

## Running in the background

Use `screen` to keep it running after you close the terminal:

```bash
screen -S jobhunter
./run.sh
```

Detach with `Ctrl+A D` — the process keeps running. Reattach anytime:

```bash
screen -r jobhunter
```

To stop it, reattach and press `Ctrl+C`.

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- An [OpenRouter](https://openrouter.ai) API key (free tier works)

## License

MIT
