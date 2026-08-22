"""Lambda entry point for the Daily Dev Digest Agent.

Runs once a day on an EventBridge schedule. Pulls yesterday's GitHub
activity and recent CloudWatch error logs, asks Amazon Bedrock (Nova) to
turn that into a short digest, posts it to Slack, and records it in
DynamoDB so tomorrow's run can reference recurring risks.
"""

import json
import os
from datetime import datetime, timedelta, timezone

import boto3

from bedrock_client import generate_digest
from cw_logs_client import fetch_recent_errors
from github_client import fetch_activity
from slack_client import post_digest

secrets_client = boto3.client("secretsmanager")
logs_client = boto3.client("logs")
bedrock_client = boto3.client("bedrock-runtime")
dynamodb = boto3.resource("dynamodb")

GITHUB_REPO = os.environ["GITHUB_REPO"]
GITHUB_TOKEN_SECRET_ARN = os.environ["GITHUB_TOKEN_SECRET_ARN"]
SLACK_WEBHOOK_SECRET_ARN = os.environ["SLACK_WEBHOOK_SECRET_ARN"]
LOG_GROUPS = [g.strip() for g in os.environ.get("CLOUDWATCH_LOG_GROUPS", "").split(",") if g.strip()]
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
TABLE_NAME = os.environ["DYNAMODB_TABLE"]

_secret_cache: dict[str, str] = {}


def _get_secret(arn: str) -> str:
    if arn not in _secret_cache:
        _secret_cache[arn] = secrets_client.get_secret_value(SecretId=arn)["SecretString"]
    return _secret_cache[arn]


def _recurring_risk_note(table, days: int = 3) -> str:
    """Look at the last `days` digests and surface repeated risk keywords."""
    today = datetime.now(timezone.utc).date()
    past_digests = []
    for offset in range(1, days + 1):
        date_str = (today - timedelta(days=offset)).isoformat()
        item = table.get_item(Key={"date": date_str}).get("Item")
        if item:
            past_digests.append(item.get("risks_section", ""))

    if not past_digests:
        return ""

    return "Risks mentioned in the last few days:\n" + "\n---\n".join(past_digests)


def handler(event, context):
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=1)
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    until_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    date_str = now.date().isoformat()

    table = dynamodb.Table(TABLE_NAME)

    github_token = _get_secret(GITHUB_TOKEN_SECRET_ARN)
    slack_webhook_url = _get_secret(SLACK_WEBHOOK_SECRET_ARN)

    activity = fetch_activity(GITHUB_REPO, github_token, since_iso, until_iso)
    recent_errors = fetch_recent_errors(
        logs_client, LOG_GROUPS, int(since.timestamp()), int(now.timestamp())
    )
    risk_note = _recurring_risk_note(table)

    digest_markdown = generate_digest(bedrock_client, BEDROCK_MODEL_ID, activity, recent_errors, risk_note)

    risks_section = digest_markdown.split("## Risks & Errors")[-1].split("## Suggested priorities")[0].strip()

    post_digest(slack_webhook_url, GITHUB_REPO, date_str, digest_markdown)

    table.put_item(
        Item={
            "date": date_str,
            "repo": GITHUB_REPO,
            "digest_markdown": digest_markdown,
            "risks_section": risks_section,
            "commit_count": len(activity["commits"]),
            "merged_pr_count": len(activity["merged_pulls"]),
            "error_count": len(recent_errors),
            "generated_at": now.isoformat(),
        }
    )

    return {
        "statusCode": 200,
        "body": json.dumps({"date": date_str, "posted": True}),
    }
