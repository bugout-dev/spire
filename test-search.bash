#!/usr/bin/env bash

# Tests for journal search
# Requirements:
# - Environment configured to connect to Elasticsearch (see sample.env)
# - Python with which the spire.journal.search module can be run (see requirements.txt)

set -eu

TIMESTAMP=$(date -u +%s)
USER_ID="test-${TIMESTAMP}"
INDEX_OF_JOURNALS=$(python -m spire.journal.search --bugout-user-id "${USER_ID}" create-journals-index)
JOURNAL_ID="test-journal-id"
JOURNAL_NAME="test journal name"
INDEX_NAME=$(python -m spire.journal.search --bugout-user-id "${USER_ID}" create-index -j "${JOURNAL_ID}" -n "${JOURNAL_NAME}")

python -m spire.journal.search --bugout-user-id "${USER_ID}" new-entry \
    -j "${JOURNAL_ID}" \
    -e "beatles" \
    -T "The Beatles" \
    -c "goodbye hello" \
    -t song beatles rock classic

python -m spire.journal.search --bugout-user-id "${USER_ID}" new-entry \
    -j "${JOURNAL_ID}" \
    -e "dylan" \
    -T "Bob Dylan" \
    -c "shelter from the storm" \
    -t song bob dylan guitar nasal

python -m spire.journal.search --bugout-user-id "${USER_ID}" new-entry \
    -j "${JOURNAL_ID}" \
    -e "doors" \
    -T "The Doors" \
    -c "riders on the storm" \
    -t song doors rock

echo "Query: shelter, Filters: none"
python -m spire.journal.search --bugout-user-id "${USER_ID}" search -j "${JOURNAL_ID}" \
    -q shelter

echo "Query: storm, Filters: none"
python -m spire.journal.search --bugout-user-id "${USER_ID}" search -j "${JOURNAL_ID}" \
    -q storm

echo "Query: storm, Filters: tag:guitar"
python -m spire.journal.search --bugout-user-id "${USER_ID}" search -j "${JOURNAL_ID}" \
    -q storm \
    -f tag:guitar

echo "Query: stor, Filters: tag:guitar"
python -m spire.journal.search --bugout-user-id "${USER_ID}" search -j "${JOURNAL_ID}" \
    -q stor \
    -f tag:guitar

echo "Query: goodbye, Filters: none"
python -m spire.journal.search --bugout-user-id "${USER_ID}" search -j "${JOURNAL_ID}" \
    -q goodbye

echo "Query: goodbye, Filters: tag:guitar"
python -m spire.journal.search --bugout-user-id "${USER_ID}" search -j "${JOURNAL_ID}" \
    -q goodbye \
    -f tag:guitar

echo "Dropping indices"
python -m spire.journal.search --bugout-user-id "${USER_ID}" drop-index -i "${INDEX_NAME}"
python -m spire.journal.search --bugout-user-id "${USER_ID}" drop-index -i "${INDEX_OF_JOURNALS}"
