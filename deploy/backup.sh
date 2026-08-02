#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
environment_file=${MKVIP_PRODUCTION_ENV_FILE:-"$repository_root/deploy/.env.production"}
backup_directory=${1:-"$repository_root/backups"}
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_file="$backup_directory/mkvip-$timestamp.dump"

if [ ! -f "$environment_file" ]; then
    echo "Production environment file not found: $environment_file" >&2
    exit 1
fi

umask 077
mkdir -p "$backup_directory"
cd "$repository_root"
docker compose --env-file "$environment_file" -f compose.production.yml exec -T db \
    sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
    > "$backup_file"

echo "$backup_file"
