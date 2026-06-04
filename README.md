# 🌿 CRISPR-PLANT gRNA Designer

Automated gRNA selection for plant genome editing with safety-first ranking and AI-powered decision support.

**[▶ Try the Live App](https://bioinfo.icgeb.res.in/sharp)**

---

## What it does

- Submits your target to CRISPR-PLANT v2 and ranks all candidate gRNAs
- Flags off-targets in coding regions as critical
- Fetches relevant literature via **OpenAlex**
- AI assistant (Gemini) pre-loaded with your results
- 75+ plant genomes | PAM: `NGG`, `NAG`, `NGA`, `NNGRRT`, `TTTN` | Guide length: 15–22 bp

---

## Installation

> Requires Python 3.10+ and Google Chrome.

```bash
git clone https://github.com/AnveshW/CRISPR-Plant-gRNA-Designer.git
cd CRISPR-Plant-gRNA-Designer
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8501 --reload
```

### Docker

```bash
docker build -t sharp-app .
docker run -d -p 8501:8501 --name sharp sharp-app
```
