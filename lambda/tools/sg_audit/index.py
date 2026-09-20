import json
import boto3

ec2 = boto3.client('ec2')

SENSITIVE_PORTS = {22, 3389, 3306, 5432, 1433, 27017, 6379, 9200, 11211}


def lambda_handler(event, context):
    function_name = event.get('function')

    try:
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

        return respond(event, function_name,
                       {"findings": findings, "count": len(findings)}, "SUCCESS")

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
