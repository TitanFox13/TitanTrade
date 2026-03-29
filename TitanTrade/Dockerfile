FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies (frozen = exact lockfile versions)
RUN uv sync --frozen --no-dev

# Copy source code and static data
COPY src/ src/
COPY data/ data/

# Create mount points for persistent data
RUN mkdir -p state logs

ENTRYPOINT ["uv", "run", "python", "-m", "titantrade"]
