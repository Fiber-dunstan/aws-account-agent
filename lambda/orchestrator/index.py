"""
Orchestrator Lambda for the AWS Account Agent.

Receives HTTP POST from API Gateway, invokes the Bedrock Agent,
persists conversation turns to DynamoDB, and returns the response.
"""
import json
import os
import uuid
import boto3
from datetime import datetime

bedrock_agent = boto3.client('bedrock-agent-runtime')
dynamodb = boto3.resource('dynamodb')

AGENT_ID = os.environ['AGENT_ID']
AGENT_ALIAS_ID = os.environ['AGENT_ALIAS_ID']
SESSION_TABLE = os.environ['SESSION_TABLE']

table = dynamodb.Table(SESSION_TABLE)


def lambda_handler(event, context):
    try:
        body = event.get('body') or '{}'
        if isinstance(body, str):
            body = json.loads(body)

        message = body.get('message')
        session_id = body.get('sessionId') or str(uuid.uuid4())

        if not message:
            return response(400, {"error": "message is required"})

        now_ms = int(datetime.now().timestamp() * 1000)
        ttl = int(datetime.now().timestamp()) + 86400

        table.put_item(Item={
            'sessionId': session_id,
            'timestamp': now_ms,
            'role': 'user',
            'content': message,
            'ttl': ttl,
        })

        agent_response = bedrock_agent.invoke_agent(
            agentId=AGENT_ID,
            agentAliasId=AGENT_ALIAS_ID,
            sessionId=session_id,
            inputText=message,
            enableTrace=False,
        )

        completion = ""
        for chunk_event in agent_response['completion']:
            if 'chunk' in chunk_event:
                completion += chunk_event['chunk']['bytes'].decode('utf-8')

        table.put_item(Item={
            'sessionId': session_id,
            'timestamp': now_ms + 1,
            'role': 'assistant',
            'content': completion,
            'ttl': ttl,
        })

        return response(200, {
            "sessionId": session_id,
            "response": completion,
        })

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {str(e)}")
        return response(500, {"error": str(e)})


def response(status, body):
    return {
        'statusCode': status,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
        },
        'body': json.dumps(body),
    }