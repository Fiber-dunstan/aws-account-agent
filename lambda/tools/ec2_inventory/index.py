import json
import boto3

ec2 = boto3.client('ec2')


def lambda_handler(event, context):
    function_name = event.get('function')

    try:
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

        return respond(event, function_name,
                       {"instances": result, "count": len(result)}, "SUCCESS")

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