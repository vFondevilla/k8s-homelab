#!/bin/sh
set -eu

infra_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

if [ -f .env.op ]; then
  exec op run --env-file="$infra_dir/.env.op" --env-file=.env.op -- "$@"
fi

exec op run --env-file="$infra_dir/.env.op" -- "$@"
