#!/bin/bash
set -e

echo "[+] Pulling latest code..."
git pull origin main

echo "[+] Building Docker image..."
docker build -t cpgrd .

echo "[+] Stopping and removing old container (if exists)..."
docker stop crispr-app 2>/dev/null || true
docker rm crispr-app 2>/dev/null || true

# Create secrets directory and file if GEMINI_API_KEY env var is set
if [ -n "$GEMINI_API_KEY" ]; then
  echo "[+] Writing Gemini API key to secrets..."
  mkdir -p secrets
  echo "GEMINI_API_KEY = \"$GEMINI_API_KEY\"" > secrets/secrets.toml
fi

echo "[+] Starting new container..."
docker run -d \
  --name crispr-app \
  --restart unless-stopped \
  -p 8501:8501 \
  -v "$(pwd)/secrets:/app/.streamlit" \
  cpgrd

echo "[✓] App updated and running at http://localhost:8501"
