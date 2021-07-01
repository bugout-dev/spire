#!/usr/bin/env bash

# Expects access to Python environment with the requirements for this project installed.
set -e

SPIRE_HOST="${SPIRE_HOST:-0.0.0.0}"
SPIRE_PORT="${SPIRE_PORT:-7475}"

uvicorn --port "$SPIRE_PORT" --host "$SPIRE_HOST" spire.api:app --workers 2 $@
