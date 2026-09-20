import json
import boto3
from datetime import datetime, timedelta, timezone

ct = boto3.client('cloudtrail')


def lambda_handler(event, context):
    function_name = event.get('function')
    params = event.get('parameters', [])
    param_dict = {p['name']: p['value'] for p in params}

    try:
        hours = int(param_dict.get('hours', 24))
        start_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        response = ct.lookup_events(
            StartTime=start_time,
            MaxResults=50,
        )

        events = []
        for e in response.get('Events', []):
            events.append({
                "time": e['EventTime'].isoformat(),
                "event_name": e['EventName'],
                "user": e.get('Username', 'unknown'),
                "source": e.get('EventSource', 'unknown'),
                "resources": [r.get('ResourceName', '') for r in e.get('Resources', [])],
            })

        return respond(event, function_name,
                       {
                           "events": events,
                           "count": len(events),
                           "lookback_hours": hours,
                       },
                       "SUCCESS")

    except Exception as e:
        return respond(event, function_name, {"error": str(e)}, "FAILURE")


def respond(event, fn, result, state):
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get('actionGroup'),
            "function": fn,
            "functionResponse": {
                "responseState": state,
                "responseBody": {"TEXT": {"body": json.dumps(result)}},
            },
        },
    }