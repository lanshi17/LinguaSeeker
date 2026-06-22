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

export BACKEND_URL API_KEY FRONTEND_MAX_BODY

envsubst '${BACKEND_URL} ${API_KEY} ${FRONTEND_MAX_BODY}' \
    < /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf
