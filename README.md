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

```bash
git clone https://github.com/AnveshW/CRISPR-Plant-gRNA-Designer.git
cd CRISPR-Plant-gRNA-Designer
pip install -r requirements.txt
streamlit run Solvethisfast.py
```

> Requires Python 3.8+ and Google Chrome.

