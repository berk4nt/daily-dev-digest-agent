"""Turns raw GitHub + CloudWatch activity into a short narrative digest
using Amazon Bedrock's Converse API (model-agnostic, so swapping the Nova
model id in template.yaml is a one-line change).
"""

import json

SYSTEM_PROMPT = """You are an engineering-team assistant that writes a short daily digest \
for a software team. You will receive JSON describing yesterday's GitHub activity \
(commits, merged pull requests, issues) and recent error log lines from CloudWatch. \
Also, if provided, a short note about recurring risks seen on previous days.

Write a concise digest in Markdown with exactly these sections:
## Highlights
(2-4 bullets on what shipped, in plain language a non-engineer could follow)
## Risks & Errors
(bullets on error patterns or stalled work; say "No notable errors" if the log list is empty)
## Suggested priorities for today
(2-3 bullets, concrete and actionable)

Keep it under 200 words total. No preamble, no sign-off, start directly with "## Highlights".
"""


def generate_digest(bedrock_client, model_id: str, activity: dict, recent_errors: list, recurring_risk_note: str) -> str:
    user_content = {
        "github_activity": activity,
        "recent_errors": recent_errors,
        "recurring_risk_note": recurring_risk_note or "None on record.",
    }

    response = bedrock_client.converse(
        modelId=model_id,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[
            {
                "role": "user",
                "content": [{"text": json.dumps(user_content, ensure_ascii=False)}],
            }
        ],
        inferenceConfig={"maxTokens": 500, "temperature": 0.4},
    )

    return response["output"]["message"]["content"][0]["text"].strip()
