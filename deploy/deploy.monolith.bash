#!/usr/bin/env bash

# Deployment script - intended to run on Spire API server

# Colors
C_RESET='\033[0m'
C_RED='\033[1;31m'
C_GREEN='\033[1;32m'
C_YELLOW='\033[1;33m'

# Logs
PREFIX_INFO="${C_GREEN}[INFO]${C_RESET} [$(date +%d-%m\ %T)]"
PREFIX_WARN="${C_YELLOW}[WARN]${C_RESET} [$(date +%d-%m\ %T)]"
PREFIX_CRIT="${C_RED}[CRIT]${C_RESET} [$(date +%d-%m\ %T)]"

# Main
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
APP_DIR="${APP_DIR:-/home/ubuntu/spire}"
PYTHON_ENV_DIR="${PYTHON_ENV_DIR:-/home/ubuntu/spire-env}"
PYTHON="${PYTHON_ENV_DIR}/bin/python"
PIP="${PYTHON_ENV_DIR}/bin/pip"
SCRIPT_DIR="$(realpath $(dirname $0))"
PARAMETERS_SCRIPT="${SCRIPT_DIR}/parameters.py"
SECRETS_DIR="${SECRETS_DIR:-/home/ubuntu/spire-secrets}"
PARAMETERS_ENV_PATH="${SECRETS_DIR}/app.env"
AWS_SSM_PARAMETER_PATH="${AWS_SSM_PARAMETER_PATH:-/spire/prod}"

# API service service file
SPIRE_SOURCE_SERVICE_FILE="spire.monolith.service"
SPIRE_SERVICE_FILE="spire.service"

# GitHub token updater
SPIRE_SOURCE_TOKEN_SERVICE_FILE="spiregithubtoken.monolith.service"
SPIRE_TOKEN_SERVICE_FILE="spiregithubtoken.service"
SPIRE_TOKEN_TIMER_FILE="spiregithubtoken.timer"

# Humbug tokens synchronizer
SPIRE_SOURCE_HUMBUG_TOKENS_SERVICE_FILE="spirehumbugtokens.monolith.service"
SPIRE_HUMBUG_TOKENS_SERVICE_FILE="spirehumbugtokens.service"
SPIRE_HUMBUG_TOKENS_TIMER_FILE="spirehumbugtokens.timer"

set -eu

echo
echo
echo -e "${PREFIX_INFO} Upgrading Python pip and setuptools"
"${PIP}" install --upgrade pip setuptools

echo
echo
echo -e "${PREFIX_INFO} Installing Python dependencies"
"${PIP}" install -e "${APP_DIR}/"

echo
echo
echo -e "${PREFIX_INFO} Retrieving deployment parameters"
mkdir -p "${SECRETS_DIR}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION}" "${PYTHON}" "${PARAMETERS_SCRIPT}" "${AWS_SSM_PARAMETER_PATH}" -o "${PARAMETERS_ENV_PATH}"

echo
echo
echo -e "${PREFIX_INFO} Set correct permissions for app.env"
chmod 600 "${PARAMETERS_ENV_PATH}"

echo
echo
echo -e "${PREFIX_INFO} Replacing existing Spire service definition with ${SPIRE_SERVICE_FILE}"
chmod 644 "${SCRIPT_DIR}/${SPIRE_SOURCE_SERVICE_FILE}"
cp "${SCRIPT_DIR}/${SPIRE_SOURCE_SERVICE_FILE}" "/home/ubuntu/.config/systemd/user/${SPIRE_SERVICE_FILE}"
XDG_RUNTIME_DIR="/run/user/$UID" systemctl --user daemon-reload
XDG_RUNTIME_DIR="/run/user/$UID" systemctl --user restart "${SPIRE_SERVICE_FILE}"


echo
echo
echo -e "${PREFIX_INFO} Replacing existing Spire GitHub service and timer definitions with: ${SPIRE_TOKEN_SERVICE_FILE}, ${SPIRE_TOKEN_TIMER_FILE}"
chmod 644 "${SCRIPT_DIR}/${SPIRE_SOURCE_TOKEN_SERVICE_FILE}" "${SCRIPT_DIR}/${SPIRE_TOKEN_TIMER_FILE}"
cp "${SCRIPT_DIR}/${SPIRE_SOURCE_TOKEN_SERVICE_FILE}" "/home/ubuntu/.config/systemd/user/${SPIRE_TOKEN_SERVICE_FILE}"
cp "${SCRIPT_DIR}/${SPIRE_TOKEN_TIMER_FILE}" "/home/ubuntu/.config/systemd/user/${SPIRE_TOKEN_TIMER_FILE}"
XDG_RUNTIME_DIR="/run/user/$UID" systemctl --user daemon-reload
XDG_RUNTIME_DIR="/run/user/$UID" systemctl --user restart "${SPIRE_TOKEN_TIMER_FILE}"


echo
echo
echo -e "${PREFIX_INFO} Replacing existing Spire Humbug tokens synchronization service and timer definitions with: ${SPIRE_HUMBUG_TOKENS_SERVICE_FILE}, ${SPIRE_HUMBUG_TOKENS_TIMER_FILE}"
chmod 644 "${SCRIPT_DIR}/${SPIRE_SOURCE_HUMBUG_TOKENS_SERVICE_FILE}" "${SCRIPT_DIR}/${SPIRE_HUMBUG_TOKENS_TIMER_FILE}"
cp "${SCRIPT_DIR}/${SPIRE_SOURCE_HUMBUG_TOKENS_SERVICE_FILE}" "/home/ubuntu/.config/systemd/user/${SPIRE_HUMBUG_TOKENS_SERVICE_FILE}"
cp "${SCRIPT_DIR}/${SPIRE_HUMBUG_TOKENS_TIMER_FILE}" "/home/ubuntu/.config/systemd/user/${SPIRE_HUMBUG_TOKENS_TIMER_FILE}"
XDG_RUNTIME_DIR="/run/user/$UID" systemctl --user daemon-reload
XDG_RUNTIME_DIR="/run/user/$UID" systemctl --user restart "${SPIRE_HUMBUG_TOKENS_TIMER_FILE}"
