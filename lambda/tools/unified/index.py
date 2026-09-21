"""
Unified tool Lambda for the AWS account Bedrock Agent.

Bedrock Agents route all functions in an action group to a single Lambda ARN.
Each function is dispatched by the 'function' field in the incoming event.
"""
import json
import boto3
from datetime import datetime, timedelta, timezone

ce = boto3.client('ce')
s3 = boto3.client('s3')
iam = boto3.client('iam')
ec2 = boto3.client('ec2')
ct = boto3.client('cloudtrail')

METRIC_RESPONSE_KEY = {
    'UNBLENDED_COST': 'UnblendedCost',
    'AMORTIZED_COST': 'AmortizedCost',
    'BLENDED_COST': 'BlendedCost',
    'NET_UNBLENDED_COST': 'NetUnblendedCost',
    'NET_AMORTIZED_COST': 'NetAmortizedCost',
}

SENSITIVE_PORTS = {22, 3389, 3306, 5432, 1433, 27017, 6379, 9200, 11211}


def lambda_handler(event, context):
    function_name = event.get('function', '')
    params = event.get('parameters', [])
    param_dict = {p['name']: p['value'] for p in params}

    handlers = {
        'cost_query': handle_cost_query,
        'cost_forecast': handle_cost_forecast,
        's3_audit': handle_s3_audit,
        'iam_summary': handle_iam_summary,
        'ec2_inventory': handle_ec2_inventory,
        'security_posture': handle_security_posture,
        'sg_audit': handle_sg_audit,
        'cloudtrail_recent': handle_cloudtrail_recent,
    }

    handler = handlers.get(function_name)
    if not handler:
        return respond(event, function_name, {"error": f"Unknown function: {function_name}"}, "FAILURE")

    try:
        result = handler(param_dict)
        return respond(event, function_name, result, "SUCCESS")
    except Exception as e:
        return respond(event, function_name, {"error": str(e)}, "FAILURE")


def respond(event, fn, result, state):
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get('actionGroup', 'AWSOps'),
            "function": fn,
            "functionResponse": {
                "responseState": state,
                "responseBody": {"TEXT": {"body": json.dumps(result)}},
            },
        },
    }


# ---------- Cost ----------

def handle_cost_query(params):
    days = int(params.get('days', 30))
    metric = params.get('metric', 'UNBLENDED_COST')
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

    return {
        "total_usd": round(total, 2),
        "period_days": days,
        "metric": metric,
        "top_services": [{"service": s, "cost_usd": round(c, 2)} for s, c in top],
    }


def handle_cost_forecast(params):
    days = int(params.get('days', 30))
    metric = params.get('metric', 'UNBLENDED_COST')

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

    return {
        "forecast_total_usd": round(float(total['Amount']), 2),
        "currency": total['Unit'],
        "metric": metric,
        "days_ahead": days,
        "breakdown": breakdown,
    }


# ---------- S3 ----------

def handle_s3_audit(params):
    buckets = s3.list_buckets()['Buckets']
    result = []

    for b in buckets:
        name = b['Name']

        try:
            pab = s3.get_public_access_block(Bucket=name)
            config = pab['PublicAccessBlockConfiguration']
            blocked = all([
                config.get('BlockPublicAcls', False),
                config.get('IgnorePublicAcls', False),
                config.get('BlockPublicPolicy', False),
                config.get('RestrictPublicBuckets', False),
            ])
        except Exception:
            blocked = False

        try:
            versioning = s3.get_bucket_versioning(Bucket=name)
            versioned = versioning.get('Status') == 'Enabled'
        except Exception:
            versioned = False

        result.append({
            "name": name,
            "public_access_blocked": blocked,
            "versioning": versioned,
        })

    return {"buckets": result, "count": len(result)}


# ---------- IAM ----------

def handle_iam_summary(params):
    users = iam.list_users()['Users']
    result = []

    for u in users:
        name = u['UserName']
        mfa = iam.list_mfa_devices(UserName=name)['MFADevices']
        keys = iam.list_access_keys(UserName=name)['AccessKeyMetadata']

        result.append({
            "user": name,
            "mfa_enabled": len(mfa) > 0,
            "access_keys": len(keys),
        })

    return {"users": result, "count": len(result)}


def handle_security_posture(params):
    issues = []

    summary = iam.get_account_summary()['SummaryMap']
    if summary.get('AccountMFAEnabled', 0) == 0:
        issues.append({
            "severity": "HIGH",
            "issue": "Root account MFA is not enabled",
        })

    users = iam.list_users()['Users']
    for u in users:
        mfa = iam.list_mfa_devices(UserName=u['UserName'])['MFADevices']
        if not mfa:
            issues.append({
                "severity": "MEDIUM",
                "issue": f"IAM user {u['UserName']} has no MFA device",
            })

    return {"issues": issues, "count": len(issues)}


# ---------- EC2 ----------

def handle_ec2_inventory(params):
    instances = ec2.describe_instances()
    result = []

    for r in instances['Reservations']:
        for i in r['Instances']:
            name = next(
                (t['Value'] for t in i.get('Tags', []) if t['Key'] == 'Name'),
                'unnamed',
            )
            result.append({
                "id": i['InstanceId'],
                "name": name,
                "state": i['State']['Name'],
                "type": i['InstanceType'],
                "az": i['Placement']['AvailabilityZone'],
            })

    return {"instances": result, "count": len(result)}


def handle_sg_audit(params):
    response = ec2.describe_security_groups()
    findings = []

    for sg in response['SecurityGroups']:
        sg_id = sg['GroupId']
        sg_name = sg.get('GroupName', 'unnamed')

        for perm in sg.get('IpPermissions', []):
            for ip_range in perm.get('IpRanges', []):
                if ip_range.get('CidrIp') != '0.0.0.0/0':
                    continue

                port = perm.get('FromPort', 'all')
                proto = perm.get('IpProtocol', '-1')

                if proto == '-1':
                    findings.append({
                        "severity": "CRITICAL",
                        "sg_id": sg_id,
                        "sg_name": sg_name,
                        "issue": "All ports open to 0.0.0.0/0",
                    })
                elif port in SENSITIVE_PORTS:
                    findings.append({
                        "severity": "HIGH",
                        "sg_id": sg_id,
                        "sg_name": sg_name,
                        "issue": f"Sensitive port {port}/{proto} open to 0.0.0.0/0",
                    })
                elif port != 'all':
                    findings.append({
                        "severity": "MEDIUM",
                        "sg_id": sg_id,
                        "sg_name": sg_name,
                        "issue": f"Port {port}/{proto} open to 0.0.0.0/0",
                    })

    return {"findings": findings, "count": len(findings)}


# ---------- CloudTrail ----------

def handle_cloudtrail_recent(params):
    hours = int(params.get('hours', 24))
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

    return {
        "events": events,
        "count": len(events),
        "lookback_hours": hours,
    }