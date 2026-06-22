FROM python:3.12-slim-trixie
# ────────────────────────────────────────────────────────────────────
# Backend image — single-stage, COPY pre-resolved venv from host.
#   The site-packages tarball is built on the host with `uv sync --frozen`
#   into `backend/.venv`, then tar'd into `backend/build-artifacts/`.
#   This avoids every flaky network step during `docker build`.
#
#   Rebuild artefacts when Python deps change:
#     cd backend && uv sync --no-dev --frozen
#     tar czf build-artifacts/site-packages.tar.gz \
#         --exclude='__pycache__' --exclude='*.pyc' --dereference \
#         -C .venv/lib/python3.12/site-packages .
# ────────────────────────────────────────────────────────────────────

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/opt/venv/bin:${PATH} \
    ENVIRONMENT=production \
    DEBIAN_FRONTEND=noninteractive

# Runtime libs only: weasyprint needs pango/cairo, pymupdf is self-contained.
# Use USTC mirror for apt (faster than deb.debian.org from China).
RUN sed -i 's|http://deb.debian.org/debian|https://mirrors.ustc.edu.cn/debian|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null; \
    sed -i 's|http://deb.debian.org/debian|https://mirrors.ustc.edu.cn/debian|g' /etc/apt/sources.list 2>/dev/null; \
    sed -i 's|bookworm|trixie|g; s|bookworm|trixie|g' /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list 2>/dev/null; \
    apt-get -o Acquire::http::Proxy=false -o Acquire::https::Proxy=false update \
 && apt-get -o Acquire::http::Proxy=false -o Acquire::https::Proxy=false install -y --no-install-recommends \
        ca-certificates curl \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libfontconfig1 \
        libcairo2 libgdk-pixbuf2.0-0 libffi8 \
 && rm -rf /var/lib/apt/lists/*

# Non-root user — matches the systemd "deploy" convention on bare-metal.
RUN groupadd --system --gid 1000 deploy \
 && useradd  --system --uid 1000 --gid deploy --create-home --shell /bin/bash deploy

# Pre-create an empty venv with the matching Python interpreter so
# the site-packages tarball drops into the right layout.
RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/python -m pip install --no-cache-dir --upgrade pip >/dev/null 2>&1 || true

# Drop pre-built site-packages (includes rust_io + every Python dep) and
# console scripts (uvicorn, alembic, …) with already-rewritten shebangs.
COPY backend/build-artifacts/site-packages.tar.gz /tmp/sp.tar.gz
COPY backend/build-artifacts/venv-bin.tar.gz /tmp/bin.tar.gz
RUN tar xzf /tmp/sp.tar.gz -C /opt/venv/lib/python3.12/site-packages \
 && tar xzf /tmp/bin.tar.gz -C /opt/venv/bin \
 && chmod +x /opt/venv/bin/* \
 && rm /tmp/sp.tar.gz /tmp/bin.tar.gz

# Repoint shebangs/RECORD entries from /data/[redacted-user]/.../backend/.venv to /opt/venv
RUN grep -rlIZ --binary-files=without-match '/data/[redacted-user]/Projects/01_ACMG_Lingua/backend/.venv' /opt/venv 2>/dev/null \
    | xargs -0 -r sed -i 's|/data/[redacted-user]/Projects/01_ACMG_Lingua/backend/.venv|/opt/venv|g' || true

WORKDIR /app
COPY backend/ /app/
# Drop the host venv that came along in `backend/` to avoid leaking
# Repoint shebangs/RECORD entries from host path to /opt/venv, and clean
# editable-install stubs that point to non-existent host paths.
RUN grep -rlIZ --binary-files=without-match '/data/[redacted-user]/Projects/01_ACMG_Lingua/backend/.venv' /opt/venv 2>/dev/null \
    | xargs -0 -r sed -i 's|/data/[redacted-user]/Projects/01_ACMG_Lingua/backend/.venv|/opt/venv|g' || true \
 && rm -f /opt/venv/lib/python3.12/site-packages/_editable_impl_*.pth \
    /opt/venv/lib/python3.12/site-packages/*.dist-info/direct_url.json
 && chown -R deploy:deploy /app /opt/venv

USER deploy

EXPOSE 8000

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
