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

## Installation

> Requires Python 3.10+ and Google Chrome.

### Run locally

```bash
git clone https://github.com/AnveshW/CRISPR-Plant-gRNA-Designer.git
cd CRISPR-Plant-gRNA-Designer
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8501 --reload
```

### Run with Docker

```bash
docker build -t sharp-app .
docker run -d -p 8501:8501 --name sharp sharp-app
```

Then open `http://localhost:8501` in your browser.
