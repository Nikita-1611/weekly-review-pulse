FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

WORKDIR /app

# Copy dependency files
COPY pyproject.toml .

# Install dependencies using uv
RUN uv pip install --system -r pyproject.toml

# Copy application code
COPY agent/ agent/
COPY products.yaml .
COPY .env .

# Set entrypoint
ENTRYPOINT ["uv", "run", "pulse"]
CMD ["--help"]
