#!/bin/sh
# Render nginx config from env vars. Runs before nginx starts, courtesy
# of nginx:alpine's /docker-entrypoint.sh discovery in /docker-entrypoint.d/.
#
# The base image already supports NGINX_ENVSUBST_TEMPLATE_DIR, but we run
# envsubst explicitly so the script is self-documenting and resilient to
# image-version changes.
set -eu

: "${BACKEND_URL:?BACKEND_URL must be set, e.g. http://10.0.0.20:8000}"
: "${API_KEY:?API_KEY must be set; matches backend api_key in vault}"
: "${FRONTEND_MAX_BODY:=200m}"

# Normalize BASE_PATH to "" (root mount) or "/<segment>" (subpath mount).
# Accepts "", "/", "/linguaseeker", "/linguaseeker/" — all canonicalized
# so the nginx template's location prefixes interpolate cleanly.
raw_base="${BASE_PATH:-}"
# Strip trailing slashes, then a lone "/" becomes "".
base="${raw_base%/}"
base="${base#/}"
BASE_PATH="${base:+/$base}"

export BACKEND_URL API_KEY FRONTEND_MAX_BODY BASE_PATH

envsubst '${BACKEND_URL} ${API_KEY} ${FRONTEND_MAX_BODY} ${BASE_PATH}' \
    < /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf

# At root mount (BASE_PATH empty) the bare-path redirect block renders as an
# invalid "location = {". Remove it — root has no bare-path to redirect.
if [ -z "$BASE_PATH" ]; then
    sed -i '/# Redirect bare BASE_PATH/,/^    }$/d' /etc/nginx/conf.d/default.conf
fi
