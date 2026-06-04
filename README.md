# 🌿 CRISPR-PLANT gRNA Designer

Automated gRNA selection for plant genome editing with safety-first ranking and AI-powered decision support.

**[▶ Try the Live App](https://bioinfo.icgeb.res.in/sharp)**

---

## What it does

Selecting the right CRISPR guide RNA for a plant gene is tedious — one gene can yield 176+ candidates with 3000+ off-targets. This tool automates the entire workflow:

1. Submits your target to the CRISPR-PLANT v2 server automatically
2. Parses and ranks all candidate gRNAs using a **safety-first multi-criteria algorithm**
3. Flags off-targets in coding regions as critical
4. Fetches relevant literature for off-target genes via **OpenAlex**
5. Lets you ask questions via a **Gemini AI assistant** pre-loaded with your results

---

## Features

- 75+ plant genomes (rice, wheat, maize, soybean, Arabidopsis, and more)
- Multiple PAM support: `NGG`, `NAG`, `NGA`, `NNGRRT`, `TTTN`
- Guide length: 15–22 bp
- Three input types: locus tag, DNA sequence, or genomic coordinates
- Ranking prioritizes **fewest critical off-targets → fewest total off-targets → exonic targeting → highest on-target score**

---

## Architecture

The app uses a decoupled **FastAPI backend** and a **Vanilla JS / HTML5 frontend**.

```
CRISPR-Plant-gRNA-Designer/
├── backend/        # FastAPI app (API routes, scraper, Gemini AI)
├── frontend/       # Static HTML/CSS/JS (served by FastAPI)
├── Dockerfile      # Container setup
└── requirements.txt
```

---

## Installation

> Requires Python 3.10+ and Google Chrome.

### Run locally

```bash
git clone https://github.com/AnveshW/CRISPR-Plant-gRNA-Designer.git
cd CRISPR-Plant-gRNA-Designer
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8501 --reload
```

Then open `http://localhost:8501` in your browser.

### Run with Docker

```bash
docker build -t sharp-app .
docker run -d -p 8501:8501 --name sharp sharp-app
```

Then open `http://localhost:8501` in your browser.

### Deploy on a server (behind a reverse proxy at `/sharp`)

```bash
git pull origin main
docker build -t sharp-app .
docker stop sharp && docker rm sharp
docker run -d -p 8501:8501 --name sharp sharp-app
```

> The app is pre-configured to run under the `/sharp` subpath via `root_path="/sharp"` in `backend/main.py`.

---

## Environment Variables

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API key for the AI assistant (optional — can also be entered in the UI) |
