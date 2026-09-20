import json
import boto3

iam = boto3.client('iam')


def lambda_handler(event, context):
    function_name = event.get('function')

    try:
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

        return respond(event, function_name,
                       {"issues": issues, "count": len(issues)}, "SUCCESS")

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