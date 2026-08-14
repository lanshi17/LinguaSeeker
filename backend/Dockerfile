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

# Drop pre-built site-packages (includes rust_io + every Python dep).
# Use BuildKit bind mounts so the multi-GB tarball is not itself stored as
# an image layer. Extract the heaviest dependency groups into separate layers
# so no single layer is a multi-GB blob — some upstream registries / proxies
# reset the connection on oversized blob uploads. Keep each layer well under
# ~500 MB compressed.
# nvidia CUDA libs total ~2.2 GB; cu13/lib alone is ~1.7 GB. Split by library
# family so each layer stays small enough for proxied blob uploads.
RUN --mount=type=bind,source=docker-artifacts/site-packages.tar.gz,target=/tmp/sp.tar.gz,readonly \
    tar xzf /tmp/sp.tar.gz -C /opt/venv/lib/python3.12/site-packages \
        --owner=deploy --group=deploy --wildcards './nvidia/cudnn*'
RUN --mount=type=bind,source=docker-artifacts/site-packages.tar.gz,target=/tmp/sp.tar.gz,readonly \
    tar xzf /tmp/sp.tar.gz -C /opt/venv/lib/python3.12/site-packages \
        --owner=deploy --group=deploy --wildcards './nvidia/cu13/lib/libcublas*'
RUN --mount=type=bind,source=docker-artifacts/site-packages.tar.gz,target=/tmp/sp.tar.gz,readonly \
    tar xzf /tmp/sp.tar.gz -C /opt/venv/lib/python3.12/site-packages \
        --owner=deploy --group=deploy --wildcards \
        './nvidia/cu13/lib/libcufft*' './nvidia/cu13/lib/libcurand*'
RUN --mount=type=bind,source=docker-artifacts/site-packages.tar.gz,target=/tmp/sp.tar.gz,readonly \
    tar xzf /tmp/sp.tar.gz -C /opt/venv/lib/python3.12/site-packages \
        --owner=deploy --group=deploy --wildcards \
        './nvidia/cu13/lib/libcusparse*' './nvidia/cu13/lib/libcusolver*'
RUN --mount=type=bind,source=docker-artifacts/site-packages.tar.gz,target=/tmp/sp.tar.gz,readonly \
    tar xzf /tmp/sp.tar.gz -C /opt/venv/lib/python3.12/site-packages \
        --owner=deploy --group=deploy --wildcards './nvidia/cu13/lib/libnvrtc*'
RUN --mount=type=bind,source=docker-artifacts/site-packages.tar.gz,target=/tmp/sp.tar.gz,readonly \
    tar xzf /tmp/sp.tar.gz -C /opt/venv/lib/python3.12/site-packages \
        --owner=deploy --group=deploy --wildcards \
        './nvidia/cu13*' \
        --exclude='./nvidia/cu13/lib/libcublas*' \
        --exclude='./nvidia/cu13/lib/libcufft*' --exclude='./nvidia/cu13/lib/libcurand*' \
        --exclude='./nvidia/cu13/lib/libcusparse*' --exclude='./nvidia/cu13/lib/libcusolver*' \
        --exclude='./nvidia/cu13/lib/libnvrtc*'
RUN --mount=type=bind,source=docker-artifacts/site-packages.tar.gz,target=/tmp/sp.tar.gz,readonly \
    tar xzf /tmp/sp.tar.gz -C /opt/venv/lib/python3.12/site-packages \
        --owner=deploy --group=deploy --wildcards \
        './nvidia*' --exclude='./nvidia/cudnn*' --exclude='./nvidia/cu13*'
# torch is ~2.8 GB — split its native libs from the rest so no single layer
# is an oversized blob that proxies reset mid-upload. The two ~430 MB shared
# objects (libtorch_cuda / libtorch_cpu) each get their own layer.
RUN --mount=type=bind,source=docker-artifacts/site-packages.tar.gz,target=/tmp/sp.tar.gz,readonly \
    tar xzf /tmp/sp.tar.gz -C /opt/venv/lib/python3.12/site-packages \
        --owner=deploy --group=deploy --wildcards './torch/lib/libtorch_cuda.so'
RUN --mount=type=bind,source=docker-artifacts/site-packages.tar.gz,target=/tmp/sp.tar.gz,readonly \
    tar xzf /tmp/sp.tar.gz -C /opt/venv/lib/python3.12/site-packages \
        --owner=deploy --group=deploy --wildcards './torch/lib/libtorch_cpu.so'
RUN --mount=type=bind,source=docker-artifacts/site-packages.tar.gz,target=/tmp/sp.tar.gz,readonly \
    tar xzf /tmp/sp.tar.gz -C /opt/venv/lib/python3.12/site-packages \
        --owner=deploy --group=deploy --wildcards \
        './torch/lib*' --exclude='./torch/lib/libtorch_cuda.so' \
        --exclude='./torch/lib/libtorch_cpu.so'
RUN --mount=type=bind,source=docker-artifacts/site-packages.tar.gz,target=/tmp/sp.tar.gz,readonly \
    tar xzf /tmp/sp.tar.gz -C /opt/venv/lib/python3.12/site-packages \
        --owner=deploy --group=deploy --wildcards './torch/include*'
RUN --mount=type=bind,source=docker-artifacts/site-packages.tar.gz,target=/tmp/sp.tar.gz,readonly \
    tar xzf /tmp/sp.tar.gz -C /opt/venv/lib/python3.12/site-packages \
        --owner=deploy --group=deploy --wildcards \
        './torch*' --exclude='./torch/lib*' --exclude='./torch/include*'
RUN --mount=type=bind,source=docker-artifacts/site-packages.tar.gz,target=/tmp/sp.tar.gz,readonly \
    tar xzf /tmp/sp.tar.gz -C /opt/venv/lib/python3.12/site-packages \
        --owner=deploy --group=deploy --wildcards './triton*' './cuda*'
# Split the remaining "everything else" (~2.8 GB uncompressed) into balanced
# groups so each pushed layer stays small. Only patterns that exist in the
# production tarball are listed (dev-only deps like scipy/sklearn are absent).
RUN --mount=type=bind,source=docker-artifacts/site-packages.tar.gz,target=/tmp/sp.tar.gz,readonly \
    tar xzf /tmp/sp.tar.gz -C /opt/venv/lib/python3.12/site-packages \
        --owner=deploy --group=deploy --wildcards \
        './sympy*' './numpy*'
RUN --mount=type=bind,source=docker-artifacts/site-packages.tar.gz,target=/tmp/sp.tar.gz,readonly \
    tar xzf /tmp/sp.tar.gz -C /opt/venv/lib/python3.12/site-packages \
        --owner=deploy --group=deploy --wildcards \
        './matplotlib*' './networkx*' './fontTools*' './openai*'
# Final catch-all: everything not extracted above.
RUN --mount=type=bind,source=docker-artifacts/site-packages.tar.gz,target=/tmp/sp.tar.gz,readonly \
    tar xzf /tmp/sp.tar.gz -C /opt/venv/lib/python3.12/site-packages \
        --owner=deploy --group=deploy \
        --exclude='./nvidia*' --exclude='./torch*' --exclude='./triton*' --exclude='./cuda*' \
        --exclude='./sympy*' --exclude='./numpy*' \
        --exclude='./matplotlib*' --exclude='./networkx*' \
        --exclude='./fontTools*' --exclude='./openai*'
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
# The tarball may contain host-specific interpreter paths that don't exist
# inside the container — e.g. /home/user/.venv/bin/python3 or a build venv
# like /tmp/ls-build-venv/bin/python. Match any `bin/python*` shebang rather
# than only the `.venv` form so the fix is robust to the build venv path.
RUN find /opt/venv/bin -maxdepth 1 -type f -exec \
    sed -i '1s|^#!.*bin/python[0-9.]*$|#!/opt/venv/bin/python3|' {} +

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
# Copy the entire project to preserve the directory structure needed by alembic
# We need: backend/src, backend/app, database/migrations all under repo root
COPY --chown=deploy:deploy backend/ /app/backend/
COPY --chown=deploy:deploy database/ /app/database/
COPY --chown=deploy:deploy libs/ /app/libs/
# Operational scripts (ensure_neo4j_indexes, backfill_source_language, etc.)
# so they can run inside the container via `docker compose run/exec`.
COPY --chown=deploy:deploy scripts/ /app/scripts/
# Strip the host venv and create required directories.
# Code resolves runtime dirs relative to the repo root (/app):
#   data/pipeline/*  → /app/data       (phase outputs, uploads)
#   logs             → /app/logs
#   output/*         → /app/output     (legacy cross_lingual)
#   downloads        → /app/downloads
# These must exist and be deploy-owned: the container runs as uid 1000
# (deploy), and named volumes (staging) inherit image ownership on first
# creation — a root-owned /app/data makes the pipeline fail with
# "[Errno 13] Permission denied: /app/data/pipeline".
RUN rm -rf /app/backend/.venv \
 && mkdir -p /app/data /app/downloads /app/output /app/logs /app/backend/logs /app/backend/data \
 && chown deploy:deploy /opt/venv /opt/venv/bin /opt/venv/lib \
 && chown -R deploy:deploy /app/backend /app/data /app/downloads /app/output /app/logs \
 && chmod +x /app/backend/docker-entrypoint.sh

USER deploy

WORKDIR /app/backend

EXPOSE 8000

ENTRYPOINT ["/app/backend/docker-entrypoint.sh"]

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "127.0.0.1,172.16.0.0/12"]
