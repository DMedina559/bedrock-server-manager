#!/bin/sh
set -e

if [ "$1" = "start" ]; then
    exec bedrock-server-manager web start --host "$HOST" --port "$PORT"
fi

exec "$@"
