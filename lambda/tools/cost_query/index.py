import json
import boto3
from datetime import datetime, timedelta

ce = boto3.client('ce')

METRIC_RESPONSE_KEY = {
    'UNBLENDED_COST': 'UnblendedCost',
    'AMORTIZED_COST': 'AmortizedCost',
    'BLENDED_COST': 'BlendedCost',
    'NET_UNBLENDED_COST': 'NetUnblendedCost',
    'NET_AMORTIZED_COST': 'NetAmortizedCost',
}


def lambda_handler(event, context):
    function_name = event.get('function')
    params = event.get('parameters', [])
    param_dict = {p['name']: p['value'] for p in params}

    try:
        days = int(param_dict.get('days', 30))
        metric = param_dict.get('metric', 'UNBLENDED_COST')
        response_key = METRIC_RESPONSE_KEY.get(metric, 'UnblendedCost')

        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        response = ce.get_cost_and_usage(
            TimePeriod={'Start': start, 'End': end},
            Granularity='DAILY',
            Metrics=[response_key],
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}],
        )

        total = 0.0
        by_service = {}
        for day in response['ResultsByTime']:
            for group in day['Groups']:
                service = group['Keys'][0]
                amount = float(group['Metrics'][response_key]['Amount'])
                by_service[service] = by_service.get(service, 0) + amount
                total += amount

        top = sorted(by_service.items(), key=lambda x: -x[1])[:5]

        result = {
            "total_usd": round(total, 2),
            "period_days": days,
            "metric": metric,
            "top_services": [{"service": s, "cost_usd": round(c, 2)} for s, c in top],
        }
        return respond(event, function_name, result, "SUCCESS")

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