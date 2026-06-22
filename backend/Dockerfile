FROM python:3.12-slim-trixie
# ────────────────────────────────────────────────────────────────────
# Backend image — single-stage, COPY pre-resolved venv from host.
#
# Pre-build artefacts on the host BEFORE `docker build`:
#   cd backend
#   uv sync --no-dev --frozen                 # populate .venv
#
#   mkdir -p ../docker-artifacts
#   tar czf ../docker-artifacts/site-packages.tar.gz \
#       --exclude='__pycache__' --exclude='*.pyc' --dereference \
#       -C .venv/lib/python3.12/site-packages .
#
#   # console scripts (uvicorn/alembic/…) with shebangs rewritten to /opt/venv
#   tmp=$(mktemp -d) && cp -P .venv/bin/* "$tmp"/ && rm -f "$tmp"/python*
#   sed -i "s|$(pwd)/.venv/bin/python3|/opt/venv/bin/python3|g" "$tmp"/* || true
#   tar czf ../docker-artifacts/venv-bin.tar.gz -C "$tmp" . && rm -rf "$tmp"
#
# Trixie ships glibc 2.41, accepting any wheel built on the host
# (Ubuntu 24.04 glibc 2.39) without manylinux acrobatics.
# ────────────────────────────────────────────────────────────────────

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/opt/venv/bin:${PATH} \
    ENVIRONMENT=production \
    DEBIAN_FRONTEND=noninteractive

# Runtime libs only: weasyprint needs pango/cairo, pymupdf is self-contained.
# USTC mirror — apt directly hits debian, faster than going through the
# household proxy (which returns 502 for deb.debian.org).
RUN sed -i 's|http://deb.debian.org/debian|https://mirrors.ustc.edu.cn/debian|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null; \
    sed -i 's|http://deb.debian.org/debian|https://mirrors.ustc.edu.cn/debian|g' /etc/apt/sources.list 2>/dev/null; \
    apt-get -o Acquire::http::Proxy=false -o Acquire::https::Proxy=false update \
 && apt-get -o Acquire::http::Proxy=false -o Acquire::https::Proxy=false install -y --no-install-recommends \
        ca-certificates curl \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libfontconfig1 \
        libcairo2 libgdk-pixbuf-2.0-0 libffi8 \
 && rm -rf /var/lib/apt/lists/*

# Non-root user — matches the systemd "deploy" convention on bare-metal.
RUN groupadd --system --gid 1000 deploy \
 && useradd  --system --uid 1000 --gid deploy --create-home --shell /bin/bash deploy

# Pre-create an empty venv with the matching interpreter so the
# site-packages tarball drops into the right layout.
RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/python -m pip install --no-cache-dir --upgrade pip >/dev/null 2>&1 || true

# Drop pre-built site-packages (includes rust_io + every Python dep)
# and the console-script shims with already-rewritten shebangs.
COPY docker-artifacts/site-packages.tar.gz /tmp/sp.tar.gz
COPY docker-artifacts/venv-bin.tar.gz /tmp/bin.tar.gz
RUN tar xzf /tmp/sp.tar.gz -C /opt/venv/lib/python3.12/site-packages \
 && tar xzf /tmp/bin.tar.gz -C /opt/venv/bin \
 && chmod +x /opt/venv/bin/* \
 && rm /tmp/sp.tar.gz /tmp/bin.tar.gz

# Editable installs from the host point at non-existent paths inside the
# container — drop the .pth stubs and install the in-tree deps from source.
COPY libs/config-loader /opt/extras/config-loader
RUN rm -f /opt/venv/lib/python3.12/site-packages/_editable_impl_*.pth \
 && /opt/venv/bin/pip install --no-cache-dir --no-deps /opt/extras/config-loader >/dev/null 2>&1

# Repoint any lingering RECORD/console-script references from the host
# venv to /opt/venv.
RUN grep -rlIZ --binary-files=without-match '/data/[redacted-user]/Projects/01_ACMG_Lingua/backend/.venv' /opt/venv 2>/dev/null \
    | xargs -0 -r sed -i 's|/data/[redacted-user]/Projects/01_ACMG_Lingua/backend/.venv|/opt/venv|g' || true

WORKDIR /app
COPY backend/ /app/
# Strip the host venv so the image only ships /opt/venv.
RUN rm -rf /app/.venv \
 && mkdir -p /app/logs /app/data /app/downloads /app/output \
 && chown -R deploy:deploy /app /opt/venv

USER deploy

EXPOSE 8000

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
