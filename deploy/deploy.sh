#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
environment_file=${1:-"$repository_root/deploy/.env.production"}

if [ ! -f "$environment_file" ]; then
    echo "Production environment file not found: $environment_file" >&2
    exit 1
fi

cd "$repository_root"
docker compose --env-file "$environment_file" -f compose.production.yml config --quiet
docker compose --env-file "$environment_file" -f compose.production.yml build --pull
docker compose --env-file "$environment_file" -f compose.production.yml up -d --remove-orphans
docker compose --env-file "$environment_file" -f compose.production.yml ps
