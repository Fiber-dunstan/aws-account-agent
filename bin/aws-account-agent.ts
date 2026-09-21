#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { DataStack } from '../lib/data-stack';
import { LambdaStack } from '../lib/lambda-stack';
import { AgentStack } from '../lib/agent-stack';
import { ApiStack } from '../lib/api-stack';

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: 'us-east-1',
};

const dataStack = new DataStack(app, 'DataStack', {
  env,
  description: 'DynamoDB table for agent session history',
});

const lambdaStack = new LambdaStack(app, 'LambdaStack', {
  env,
  description: 'Unified tool Lambda for the AWS account agent',
});

const agentStack = new AgentStack(app, 'AgentStack', {
  env,
  description: 'Bedrock Agent for AWS account queries',
  toolFunction: lambdaStack.toolFunction,
});

new ApiStack(app, 'ApiStack', {
  env,
  description: 'HTTP API for the AWS account agent',
  sessionTable: dataStack.sessionTable,
  agentId: agentStack.agentId,
  agentAliasId: agentStack.agentAliasId,
});