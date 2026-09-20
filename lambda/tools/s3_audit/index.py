import json
import boto3

s3 = boto3.client('s3')


def lambda_handler(event, context):
    function_name = event.get('function')

    try:
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
            except s3.exceptions.ClientError:
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

        return respond(event, function_name,
                       {"buckets": result, "count": len(result)}, "SUCCESS")

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