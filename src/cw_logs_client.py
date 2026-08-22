"""CloudWatch Logs Insights helper: pulls error-level events from the last
24h across one or more log groups so the digest can flag production risk
alongside GitHub activity.
"""

import time

QUERY = """
fields @timestamp, @log, @message
| filter @message like /(?i)(error|exception|timeout|fail)/
| sort @timestamp desc
| limit 20
"""


def fetch_recent_errors(logs_client, log_groups: list[str], start_epoch: int, end_epoch: int) -> list[dict]:
    if not log_groups:
        return []

    start_query = logs_client.start_query(
        logGroupNames=log_groups,
        startTime=start_epoch,
        endTime=end_epoch,
        queryString=QUERY,
    )
    query_id = start_query["queryId"]

    for _ in range(15):
        result = logs_client.get_query_results(queryId=query_id)
        if result["status"] in ("Complete", "Failed", "Cancelled"):
            break
        time.sleep(2)
    else:
        return []

    if result["status"] != "Complete":
        return []

    events = []
    for row in result.get("results", []):
        fields = {item["field"]: item["value"] for item in row}
        events.append(
            {
                "timestamp": fields.get("@timestamp", ""),
                "log_group": fields.get("@log", ""),
                "message": fields.get("@message", "")[:300],
            }
        )
    return events
