#!/usr/bin/env bash

# Deployment script - intended to run on Spire servers

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
APP_DIR="${APP_DIR:-/home/ubuntu/app}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
PYTHON_ENV_DIR="${PYTHON_ENV_DIR:-/home/ubuntu/server-env}"
PYTHON="${PYTHON_ENV_DIR}/bin/python"
PIP="${PYTHON_ENV_DIR}/bin/pip"
SCRIPT_DIR="$(realpath $(dirname $0))"
PARAMETERS_SCRIPT="${SCRIPT_DIR}/parameters.py"
SECRETS_DIR="${SECRETS_DIR:-/home/ubuntu/secrets}"
PARAMETERS_ENV_PATH="${SECRETS_DIR}/app.env"
AWS_SSM_PARAMETER_PATH="${AWS_SSM_PARAMETER_PATH:-/spire/prod}"
SERVICE_FILE="${SCRIPT_DIR}/spire.service"

# Logging
LOGGER_SCRIPT="${SCRIPT_DIR}/logger.py"
RSYSLOG_CONF_FILE="/etc/rsyslog.d/spire.conf"
RSYSLOG_CONF_PORT=21514
RSYSLOG_CONF_SERVICE="spire"

# GitHub token updater
TOKEN_SERVICE_FILE="${SCRIPT_DIR}/spiregithubtoken.service"
TOKEN_TIMER_FILE="${SCRIPT_DIR}/spiregithubtoken.timer"

# Humbug tokens synchronizer
HUMBUG_TOKENS_SERVICE_FILE="${SCRIPT_DIR}/spirehumbugtokens.monolith.service"
HUMBUG_TOKENS_TIMER_FILE="${SCRIPT_DIR}/spirehumbugtokens.timer"

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
echo "Retrieving deployment parameters"
mkdir -p "${SECRETS_DIR}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION}" "${PYTHON}" "${PARAMETERS_SCRIPT}" "${AWS_SSM_PARAMETER_PATH}" -o "${PARAMETERS_ENV_PATH}"

echo
echo
if [ -d "$(dirname $RSYSLOG_CONF_FILE)" ]; then
  echo "Setup rsyslog client"
  AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION}" "${PYTHON}" "${LOGGER_SCRIPT}" -o "${RSYSLOG_CONF_FILE}" -p "${RSYSLOG_CONF_PORT}" -s "${RSYSLOG_CONF_SERVICE}"
  systemctl restart rsyslog.service
else
  echo "Skipping rsyslog client setup"
fi

echo
echo
echo "Replacing existing Spire service definition with ${SERVICE_FILE}"
chmod 644 "${SERVICE_FILE}"
cp "${SERVICE_FILE}" /etc/systemd/system/spire.service
systemctl daemon-reload
systemctl restart spire.service
systemctl status spire.service


echo
echo
echo "Replacing existing Spire GitHub service and timer definitions with: ${TOKEN_SERVICE_FILE}, ${TOKEN_TIMER_FILE}"
chmod 644 "${TOKEN_SERVICE_FILE}" "${TOKEN_TIMER_FILE}"
cp "${TOKEN_SERVICE_FILE}" /etc/systemd/system/spiregithubtoken.service
cp "${TOKEN_TIMER_FILE}" /etc/systemd/system/spiregithubtoken.timer
systemctl daemon-reload
systemctl start spiregithubtoken.service
systemctl start spiregithubtoken.timer


echo
echo
echo "Replacing existing Spire Humbug tokens synchronization service and timer definitions with: ${HUMBUG_TOKENS_SERVICE_FILE}, ${HUMBUG_TOKENS_TIMER_FILE}"
chmod 644 "${HUMBUG_TOKENS_SERVICE_FILE}" "${HUMBUG_TOKENS_TIMER_FILE}"
cp "${HUMBUG_TOKENS_SERVICE_FILE}" /etc/systemd/system/spirehumbugtokens.service
cp "${HUMBUG_TOKENS_TIMER_FILE}" /etc/systemd/system/spirehumbugtokens.timer
systemctl daemon-reload
systemctl start spirehumbugtokens.service
systemctl start spirehumbugtokens.timer
