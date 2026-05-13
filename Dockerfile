FROM python:3.11-slim

# Minimum dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Create user for Hugging Face Spaces
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# Copy requirements and install
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download spaCy model and Playwright browsers & their system dependencies
RUN python -m spacy download en_core_web_sm
# Temporarily switch to root to install playwright deps
USER root
RUN playwright install-deps chromium
USER user
RUN playwright install chromium

# Copy the rest of the application
COPY --chown=user:user . .

# Ensure data directory exists for persistent volume and is owned by user
RUN mkdir -p $HOME/app/data

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV PULSE_DB_PATH=$HOME/app/data/pulse.db

EXPOSE 8000

CMD ["python", "run_server.py"]
