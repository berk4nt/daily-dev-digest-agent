# Weekend Creative Agent Challenge: Daily Dev Digest Agent

**Tag:** #agents

## Vision and what it does

Every engineering team relearns "what happened yesterday" by hand, every single morning. Someone scrolls the commit history, checks which pull requests merged overnight, and greps CloudWatch for anything that broke while everyone was asleep. It's a small tax, but it's paid daily, by every team, forever.

The **Daily Dev Digest Agent** is an always-on AWS agent that pays that tax for you. Once a day, without anyone opening a laptop, it reads a repository's GitHub activity and a service's CloudWatch error logs, asks Amazon Bedrock to turn that into a short, plain-language digest, and drops it into Slack before the first person joins standup. The best tool is the one you never have to open — this is that, applied to "what's going on with our code."

It's designed to produce something like this each morning:

> **📋 Daily Dev Digest — acme/checkout-service — 2026-08-22**
>
> **Highlights**
> - 14 commits landed, focused on the refund-flow refactor
> - PR #482 merged: retry logic for the payment gateway timeout
> - PR #479 merged: input validation fix for the coupon endpoint
>
> **Risks & Errors**
> - Recurring `TimeoutError` in `payment-worker` logs, 6 occurrences overnight
> - Same pattern flagged two days running — worth a closer look before it becomes an incident
>
> **Suggested priorities for today**
> - Investigate the payment-worker timeout before it repeats a third day
> - Follow up on PR #481, open for 3 days with no review

*(This is a sample of the agent's intended output, shown to illustrate the format — the project below is built and ready to deploy, not yet running against a live repo.)*

## How I built it

I started from the constraint that mattered most for a weekend build: zero deployment friction. That ruled out a framework or a dependency layer — the Lambda function uses only `boto3` (already in the runtime) and the Python standard library's `urllib`, so `sam build` never needs to reach `pip`. That one decision cut the entire class of "works locally, breaks in the Lambda zip" problems out of the build.

The harder design decision was what makes this an *agent* rather than a cron job that calls an LLM once. A cron job that summarizes yesterday's activity is useful for exactly one day. To make it something that improves with time, each run reads the last three days of its own digest history back out of DynamoDB before calling Bedrock, and asks the model to flag *recurring* risks — not just "there was an error last night" but "this is the second day in a row this error showed up." That single feedback loop is what turns a static summarizer into something that behaves like it's paying attention over time.

The main challenge was scoping the CloudWatch Logs Insights query. `filter @message like /error/` is noisy in a real service — Insights queries are async, so the Lambda has to poll `get_query_results` with a bounded retry loop rather than blocking indefinitely, which shaped how I structured the client module.

## AWS services used and architecture

| Service | Role |
|---|---|
| AWS Lambda | Runs the digest logic on a schedule |
| Amazon EventBridge Scheduler | Triggers the run daily, no server ever idles |
| Amazon Bedrock (Nova Lite) | Synthesizes raw activity into the digest |
| Amazon DynamoDB | Stores digest history for recurring-risk detection |
| AWS Secrets Manager | Holds the GitHub token and Slack webhook URL |
| Amazon CloudWatch Logs | Source of error signal, and the function's own logs |
| AWS SAM | Infrastructure as code for the whole stack |

![Architecture diagram showing EventBridge Scheduler triggering a Lambda function, which reads from GitHub REST API, CloudWatch Logs Insights, and DynamoDB, sends the combined context to Amazon Bedrock, then posts the digest to Slack and writes it back to DynamoDB.](docs/architecture-diagram.png)

One Lambda function is the whole orchestration layer. It fetches three inputs (GitHub activity, CloudWatch errors, its own history), makes one Bedrock call, and produces two outputs (a Slack message, an archived record). Keeping it to a single function instead of a Step Functions workflow was a deliberate weekend-scope call — the sequence is linear enough that a state machine would add ceremony without adding reliability.

## What I learned

Building this reframed how I think about "agent" for infrastructure that isn't customer-facing. The interesting design surface wasn't the LLM call — Bedrock's Converse API made that almost boring, in a good way — it was the memory loop. An agent that reads its own past output before acting is a genuinely different system than one that doesn't, even when the difference in code is a few lines and one DynamoDB table.

I also came away with a stronger opinion on dependency-free Lambdas for small, single-purpose agents. Skipping `requests` for `urllib` cost a little code cleanliness but bought a build that's trivially reproducible and fast to iterate on — worth it for something meant to run unattended for months.

## Try it

Code, SAM template, and setup instructions: **https://github.com/berk4nt/daily-dev-digest-agent**
