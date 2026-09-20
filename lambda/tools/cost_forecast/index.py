import json
import boto3
from datetime import datetime, timedelta

ce = boto3.client('ce')

METRIC_RESPONSE_KEY = {
    'UNBLENDED_COST': 'UnblendedCost',
    'AMORTIZED_COST': 'AmortizedCost',
    'BLENDED_COST': 'BlendedCost',
}


def lambda_handler(event, context):
    function_name = event.get('function')
    params = event.get('parameters', [])
    param_dict = {p['name']: p['value'] for p in params}

    try:
        days = int(param_dict.get('days', 30))
        metric = param_dict.get('metric', 'UNBLENDED_COST')

        start = datetime.now() + timedelta(days=1)
        end = datetime.now() + timedelta(days=days)

        response = ce.get_cost_forecast(
            TimePeriod={
                'Start': start.strftime('%Y-%m-%d'),
                'End': end.strftime('%Y-%m-%d'),
            },
            Granularity='MONTHLY',
            Metric=metric,
        )

        total = response['Total']
        breakdown = []
        for r in response.get('ForecastResultsByTime', []):
            breakdown.append({
                "period": r['TimePeriod'],
                "mean_usd": round(float(r['MeanValue']), 2),
                "lower_usd": round(float(r.get('PredictionIntervalLowerBound', 0)), 2),
                "upper_usd": round(float(r.get('PredictionIntervalUpperBound', 0)), 2),
            })

        result = {
            "forecast_total_usd": round(float(total['Amount']), 2),
            "currency": total['Unit'],
            "metric": metric,
            "days_ahead": days,
            "breakdown": breakdown,
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