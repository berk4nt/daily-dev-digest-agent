# Daily Dev Digest Agent

An always-on AWS agent that reads your team's GitHub activity and CloudWatch
error logs overnight, asks Amazon Bedrock (Nova) to turn them into a short
plain-language digest, and has it waiting in Slack before standup — so
nobody has to open GitHub, Jira, or CloudWatch first thing in the morning.

Built for the **AWS Weekend Creative Agent Challenge**.

## The problem

Every morning, engineers and leads re-derive "what happened yesterday" by
hand: scrolling commit history, checking which PRs merged, and searching
CloudWatch for anything that broke overnight. It's the same fifteen minutes,
repeated by every team, every day.

## How it works

1. An **EventBridge Schedule** triggers a Lambda function once a day (default
   06:00 UTC).
2. The function pulls the last 24h of **GitHub** activity for a configured
   repo: commits, merged pull requests, and issue activity.
3. It runs a **CloudWatch Logs Insights** query across configured log groups
   for error/exception/timeout patterns.
4. It reads the last few days' digests from **DynamoDB** and pulls out any
   recurring risk language, so the agent notices *patterns*, not just
   isolated incidents.
5. **Amazon Bedrock** (Nova Lite by default) turns all of that into a
   three-section Markdown digest: Highlights, Risks & Errors, Suggested
   priorities for today.
6. The digest is posted to a **Slack** channel via Incoming Webhook, and
   saved back to DynamoDB for tomorrow's run to reference.

```
EventBridge Schedule (daily, cron)
        │
        ▼
    Lambda (Python 3.12)
    ├─ GitHub REST API      → commits / merged PRs / issues (last 24h)
    ├─ CloudWatch Logs Insights → error/exception patterns (last 24h)
    ├─ DynamoDB (read)      → recurring risk notes from prior days
    ├─ Amazon Bedrock (Nova)→ generate the digest
    ├─ Slack Incoming Webhook → post digest
    └─ DynamoDB (write)     → archive today's digest
```

## AWS services used

| Service | Role |
|---|---|
| AWS Lambda | Runs the digest logic once a day |
| Amazon EventBridge Scheduler | Daily trigger, no server ever running |
| Amazon Bedrock (Nova Lite) | Summarizes raw activity into a digest |
| Amazon DynamoDB | Digest history / recurring-risk memory |
| AWS Secrets Manager | Stores the GitHub token and Slack webhook URL |
| Amazon CloudWatch Logs | Source of error signal + the function's own logs |
| AWS SAM | Infrastructure as code / deploy |

Everything here fits comfortably inside the AWS Free Tier for a single
watched repo running once a day.

## Deploy

Requires the [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
and AWS credentials configured locally.

```bash
sam build
sam deploy --guided \
  --parameter-overrides \
    GitHubRepo=your-org/your-repo \
    CloudWatchLogGroups=/aws/lambda/your-prod-function \
    ScheduleExpression="cron(0 6 * * ? *)"
```

`sam deploy` creates two Secrets Manager secrets with a placeholder value
(`REPLACE_ME`). Fill them in after the first deploy:

```bash
./scripts/set-secrets.sh <stack-name> <github-personal-access-token> <slack-webhook-url>
```

- GitHub token: a fine-grained PAT scoped to the target repo, read-only on
  contents, pull requests, and issues.
- Slack webhook: create one at
  [api.slack.com/messaging/webhooks](https://api.slack.com/messaging/webhooks)
  for the channel you want the digest posted to.

## Local testing

```bash
sam local invoke DigestFunction --event events/scheduled-event.json
```

(Needs the secrets populated and `AWS_PROFILE`/region set, since it still
calls real GitHub, Bedrock, and Slack endpoints.)

## Configuration

| Parameter | Default | Description |
|---|---|---|
| `GitHubRepo` | — | `owner/repo` to watch |
| `CloudWatchLogGroups` | *(empty)* | Comma-separated log groups to scan for errors |
| `BedrockModelId` | `amazon.nova-lite-v1:0` | Any Bedrock Converse-compatible model |
| `ScheduleExpression` | `cron(0 6 * * ? *)` | EventBridge schedule, UTC |

## Ideas for extending this

- Swap the Slack webhook for a Teams/Discord connector.
- Add a second Bedrock call that drafts a stand-up talking-points script per
  contributor.
- Publish the DynamoDB history to a static S3 dashboard for a searchable
  archive.

## License

MIT — see [LICENSE](LICENSE).
