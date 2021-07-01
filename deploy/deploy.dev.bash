#!/usr/bin/env bash

# Deployment script - intended to run on Spire development servers

# Main
APP_DIR="${APP_DIR:-/home/ubuntu/spire}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
PYTHON_ENV_DIR="${PYTHON_ENV_DIR:-/home/ubuntu/spire-env}"
PYTHON="${PYTHON_ENV_DIR}/bin/python"
PIP="${PYTHON_ENV_DIR}/bin/pip"
SCRIPT_DIR="$(realpath $(dirname $0))"
PARAMETERS_SCRIPT="${SCRIPT_DIR}/parameters.py"
SECRETS_DIR="${SECRETS_DIR:-/home/ubuntu/spire-secrets}"
DEV_ENV_PATH="${SECRETS_DIR}/dev.env"
PARAMETERS_ENV_PATH="${SECRETS_DIR}/app.env"
AWS_SSM_PARAMETER_PATH="${AWS_SSM_PARAMETER_PATH:-/spire/prod}"
SERVICE_FILE="${SCRIPT_DIR}/spire.dev.service"

# Humbug tokens synchronizer
HUMBUG_TOKENS_SERVICE_FILE="${SCRIPT_DIR}/spirehumbugtokens.monolith.service"
HUMBUG_TOKENS_TIMER_FILE="${SCRIPT_DIR}/spirehumbugtokens.timer"

set -eu

echo
echo
read -p "Run migration? [y/n]: " migration_answer
case "$migration_answer" in
    [yY1] ) 
    echo Running migration
    source $DEV_ENV_PATH
    source $PYTHON_ENV_DIR/bin/activate
    $APP_DIR/alembic.sh -c $APP_DIR/alembic.dev.ini upgrade head
    ;;
    [nN0] ) echo "Passing migration";;
    * ) echo "Unexpected answer, passing migration"
esac

echo
echo
read -p "Update environment variables? [y/n]: " env_answer
case "$env_answer" in
    [yY1] )
    echo "Preparing service environment variables"
    cp $DEV_ENV_PATH $PARAMETERS_ENV_PATH
    sed -i 's/export //g' $PARAMETERS_ENV_PATH
    ;;
    [nN0] ) echo "Passing environment variables update";;
    * ) echo "Unexpected answer, passing environment variables update"
esac

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
echo "Replacing existing Spire Humbug tokens synchronization service and timer definitions with: ${HUMBUG_TOKENS_SERVICE_FILE}, ${HUMBUG_TOKENS_TIMER_FILE}"
chmod 644 "${HUMBUG_TOKENS_SERVICE_FILE}" "${HUMBUG_TOKENS_TIMER_FILE}"
cp "${HUMBUG_TOKENS_SERVICE_FILE}" /etc/systemd/system/spirehumbugtokens.service
cp "${HUMBUG_TOKENS_TIMER_FILE}" /etc/systemd/system/spirehumbugtokens.timer
systemctl daemon-reload
systemctl start spirehumbugtokens.service
systemctl start spirehumbugtokens.timer
