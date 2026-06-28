FROM python:3.12-slim-trixie
# ────────────────────────────────────────────────────────────────────
# Backend image — single-stage, COPY pre-resolved venv from CI.
#
# Artifacts are built by the CI workflow before docker build runs:
#   1. uv sync --no-dev --frozen  (builds Rust crates + installs deps)
#   2. tar czf docker-artifacts/site-packages.tar.gz ...
#   3. tar czf docker-artifacts/venv-bin.tar.gz ...
#
# For local builds, run the same steps manually (see CI workflow).
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
# --owner/--group avoids a costly chown -R later.
COPY docker-artifacts/site-packages.tar.gz /tmp/sp.tar.gz
RUN tar xzf /tmp/sp.tar.gz -C /opt/venv/lib/python3.12/site-packages --owner=deploy --group=deploy \
 && rm /tmp/sp.tar.gz
# venv-bin is optional — may be empty when no console scripts exist.
COPY docker-artifacts/venv-bin.tar.gz /tmp/bin.tar.gz
RUN (tar xzf /tmp/bin.tar.gz -C /opt/venv/bin --owner=deploy --group=deploy 2>/dev/null && chmod +x /opt/venv/bin/* 2>/dev/null) || true \
 && rm -f /tmp/bin.tar.gz
# Restore python symlinks — venv-bin tarball may overwrite them with
# host-specific paths that don't exist inside the container.
RUN ln -sf /usr/local/bin/python3 /opt/venv/bin/python3 \
 && ln -sf python3 /opt/venv/bin/python \
 && ln -sf /usr/local/bin/python3 /opt/venv/bin/python3.12

# Fix shebangs in entry-point scripts (uvicorn, fastapi, alembic, etc.)
# The tarball may contain host-specific paths like /home/user/.venv/bin/python3
# that don't exist inside the container.
RUN find /opt/venv/bin -maxdepth 1 -type f -exec \
    sed -i '1s|^#!.*\.venv/bin/python[0-9.]*|#!/opt/venv/bin/python3|' {} +

# Editable installs from the host point at non-existent paths inside the
# container — drop the .pth stubs and install the in-tree deps from source.
COPY --chown=deploy:deploy libs/config-loader /opt/extras/config-loader
RUN rm -f /opt/venv/lib/python3.12/site-packages/_editable_impl_*.pth \
 && /opt/venv/bin/python -m pip install --no-cache-dir --no-deps /opt/extras/config-loader

# Repoint any lingering RECORD references from the build host venv to
# /opt/venv. The host path varies by machine — we replace everything up
# to and including "/.venv" with "/opt/venv".
RUN printf '%s\n' \
    "import glob, re, pathlib" \
    "count = 0" \
    "for f in glob.glob('/opt/venv/**/RECORD', recursive=True):" \
    "    p = pathlib.Path(f)" \
    "    txt = p.read_text()" \
    "    if '.venv' in txt:" \
    "        p.write_text(re.sub(r'.*/\\.venv', '/opt/venv', txt))" \
    "        count += 1" \
    "print(f'Patched {count} RECORD files')" \
    > /tmp/fix_record.py \
 && python3 /tmp/fix_record.py \
 && rm /tmp/fix_record.py

WORKDIR /app
COPY --chown=deploy:deploy backend/ /app/
# Strip the host venv so the image only ships /opt/venv.
# Only chown the top-level dirs — tar extraction already set file ownership.
RUN rm -rf /app/.venv \
 && mkdir -p /app/logs /app/data /app/downloads /app/output \
 && chown deploy:deploy /opt/venv /opt/venv/bin /opt/venv/lib

USER deploy

EXPOSE 8000

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "127.0.0.1,172.16.0.0/12"]
