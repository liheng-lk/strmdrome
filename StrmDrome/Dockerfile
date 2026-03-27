FROM python:3.12-slim

# Build argument for platform label
ARG TARGETPLATFORM
ARG BUILDPLATFORM

WORKDIR /app

# Install system deps for Pillow JPEG/PNG support
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create Python package __init__ files for all modules
RUN touch db/__init__.py services/__init__.py api/__init__.py utils/__init__.py

# Expected volumes
VOLUME /music
VOLUME /data

EXPOSE 4533

# Health check using the built-in curl
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD curl -sf "http://localhost:4533/" || exit 1

# Use exec form so signals propagate correctly
CMD ["python", "main.py"]

LABEL org.opencontainers.image.title="StrmDrome" \
      org.opencontainers.image.description="Professional Navidrome-compatible STRM music server" \
      org.opencontainers.image.version="2.0.0" \
      org.opencontainers.image.url="https://github.com/yourusername/strmdrome" \
      org.opencontainers.image.licenses="MIT"
