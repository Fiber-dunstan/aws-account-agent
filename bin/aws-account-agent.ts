#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { DataStack } from '../lib/data-stack';
import { LambdaStack } from '../lib/lambda-stack';

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: 'us-east-1',
};

new DataStack(app, 'DataStack', {
  env,
  description: 'DynamoDB table for agent session history',
});

new LambdaStack(app, 'LambdaStack', {
  env,
  description: 'Tool Lambda functions for the AWS account agent',
});