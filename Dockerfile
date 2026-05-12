FROM python:3.11-slim

# Minimum dependencies (if needed)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download spaCy model and Playwright browsers & their system dependencies
RUN python -m spacy download en_core_web_sm
RUN playwright install-deps chromium
RUN playwright install chromium

# Copy the rest of the application
COPY . .

# Ensure data directory exists for persistent volume
RUN mkdir -p /app/data

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV PULSE_DB_PATH=/app/data/pulse.db

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
