FROM python:3.11-slim

WORKDIR /app

# Disable Python output buffering
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    ffmpeg \
    nodejs \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Deno (default JS runtime for yt-dlp's EJS / n-challenge solver)
# Required by YouTube extractor in yt-dlp 2026+
RUN curl -fsSL https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip -o /tmp/deno.zip \
    && unzip /tmp/deno.zip -d /usr/local/bin/ \
    && rm /tmp/deno.zip \
    && chmod +x /usr/local/bin/deno \
    && deno --version

# Copy requirements and install Python dependencies
COPY requirements.txt .
# Install CPU-only torch first from the dedicated PyTorch index to avoid
# pulling ~3GB of CUDA libraries from the default PyPI wheels.
RUN pip install --no-cache-dir torch==2.1.2 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p uploads

EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0"]
