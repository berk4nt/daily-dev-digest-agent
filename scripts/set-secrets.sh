#!/usr/bin/env bash
# Populate the two placeholder secrets created by template.yaml after `sam deploy`.
# Usage: ./scripts/set-secrets.sh <stack-name> <github-token> <slack-webhook-url>
set -euo pipefail

STACK_NAME="${1:?Usage: set-secrets.sh <stack-name> <github-token> <slack-webhook-url>}"
GITHUB_TOKEN="${2:?Missing github-token}"
SLACK_WEBHOOK_URL="${3:?Missing slack-webhook-url}"

aws secretsmanager put-secret-value \
  --secret-id "${STACK_NAME}/github-token" \
  --secret-string "${GITHUB_TOKEN}"

aws secretsmanager put-secret-value \
  --secret-id "${STACK_NAME}/slack-webhook-url" \
  --secret-string "${SLACK_WEBHOOK_URL}"

echo "Secrets updated for stack ${STACK_NAME}."
