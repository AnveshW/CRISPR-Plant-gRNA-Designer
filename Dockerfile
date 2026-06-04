# 1. Use Python 3.12 as the base
FROM python:3.12-slim

# 2. Install Chrome + ChromeDriver (needed for Selenium)
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 3. Tell Selenium where to find Chrome inside the container
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# 4. Set working directory inside the container
WORKDIR /app

# 5. Copy and install Python dependencies first (for faster rebuilds)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy all your app files
COPY . .

# 7. Expose the FastAPI port
EXPOSE 8501

# 8. Run the FastAPI app via uvicorn
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8501"]
