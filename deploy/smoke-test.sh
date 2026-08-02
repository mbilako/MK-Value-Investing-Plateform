#!/bin/sh
set -eu

base_url=${1:?"Usage: smoke-test.sh https://invest.example.com"}
base_url=${base_url%/}

curl --fail --silent --show-error "$base_url/api/v1/health"
curl --fail --silent --show-error "$base_url/api/v1/ready"
curl --fail --silent --show-error --head "$base_url/" \
    | grep -i '^strict-transport-security:' >/dev/null

echo "MK-VIP production smoke test passed for $base_url"
