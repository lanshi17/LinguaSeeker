# syntax=docker/dockerfile:1.7
# ────────────────────────────────────────────────────────────────────
# Multi-stage backend image.
#   The PyO3 crates (rust-io, files-io, net-io) are built once with
#   maturin in a builder stage; the runtime stage carries only the
#   compiled wheels + uv-installed Python deps.
# ────────────────────────────────────────────────────────────────────

# ── Stage 1: build Rust extensions + resolve Python deps ───────────
FROM python:3.12-slim-bookworm AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH=/root/.cargo/bin:/root/.local/bin:${PATH}

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential curl ca-certificates pkg-config libssl-dev git \
 && rm -rf /var/lib/apt/lists/* \
 && curl -LsSf https://astral.sh/uv/install.sh | sh \
 && curl -LsSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable

WORKDIR /build

# Pull the whole repo slice the backend depends on. Build context for
# this image MUST be the repo root so we can reach ../libs/config-loader.
# See docker-compose.backend.yml for the right `context:` and `dockerfile:`.
COPY backend/ ./backend/
COPY libs/    ./libs/

WORKDIR /build/backend

# Resolve the venv into a stable path we can copy into the runtime stage.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN uv sync --no-dev --frozen

# Build the in-tree rust-io extension into the same venv. maturin develop
# compiles the cdylib and installs it as a wheel under uv's venv.
RUN /opt/venv/bin/python -m pip install --no-cache-dir maturin \
 && cd libs/rust-io \
 && /opt/venv/bin/maturin develop --release


# ── Stage 2: slim runtime ───────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/opt/venv/bin:${PATH} \
    ENVIRONMENT=production

# Runtime libs only: weasyprint needs pango/cairo, pymupdf is self-contained.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ca-certificates curl \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libfontconfig1 \
        libcairo2 libgdk-pixbuf-2.0-0 libffi8 \
 && rm -rf /var/lib/apt/lists/*

# Non-root user — matches the systemd "deploy" convention on bare-metal.
RUN groupadd --system --gid 1000 deploy \
 && useradd  --system --uid 1000 --gid deploy --create-home --shell /bin/bash deploy

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY backend/ /app/
RUN mkdir -p /app/logs /app/data /app/downloads /app/output \
 && chown -R deploy:deploy /app

USER deploy

EXPOSE 8000

# uvicorn binds to 0.0.0.0 inside the container; restrict access at the
# host firewall — the frontend server reaches it across the network.
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
