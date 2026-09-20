import json
import boto3

iam = boto3.client('iam')


def lambda_handler(event, context):
    function_name = event.get('function')

    try:
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

        return respond(event, function_name,
                       {"users": result, "count": len(result)}, "SUCCESS")

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