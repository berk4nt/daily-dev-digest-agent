"""Posts the digest to Slack via an Incoming Webhook, stdlib-only."""

import json
import urllib.error
import urllib.request


def post_digest(webhook_url: str, repo: str, date_str: str, digest_markdown: str) -> None:
    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"📋 Daily Dev Digest — {repo} — {date_str}"},
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": digest_markdown}},
        ]
    }

    request = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=10)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Slack webhook error {exc.code}: {body}") from exc
