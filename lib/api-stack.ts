import * as cdk from 'aws-cdk-lib';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import * as path from 'path';

interface ApiStackProps extends cdk.StackProps {
  sessionTable: dynamodb.Table;
  agentId: string;
  agentAliasId: string;
}

export class ApiStack extends cdk.Stack {
  public readonly apiUrl: string;

  constructor(scope: Construct, id: string, props: ApiStackProps) {
    super(scope, id, props);

    const orchestrator = new lambda.Function(this, 'Orchestrator', {
      functionName: 'aws-agent-orchestrator',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.lambda_handler',
      code: lambda.Code.fromAsset(
        path.join(__dirname, '../lambda/orchestrator')
      ),
      timeout: cdk.Duration.seconds(60),
      memorySize: 512,
      environment: {
        AGENT_ID: props.agentId,
        AGENT_ALIAS_ID: props.agentAliasId,
        SESSION_TABLE: props.sessionTable.tableName,
      },
      description: 'HTTP orchestrator for the AWS account Bedrock Agent',
    });

    // Invoke the Bedrock Agent
    orchestrator.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:InvokeAgent'],
        resources: [
          `arn:aws:bedrock:${this.region}:${this.account}:agent-alias/${props.agentId}/*`,
        ],
      })
    );

    // Read/write session history
    props.sessionTable.grantReadWriteData(orchestrator);

    // REST API
    const api = new apigw.RestApi(this, 'AgentApi', {
      restApiName: 'aws-agent-api',
      description: 'Chat with your AWS account',
      defaultCorsPreflightOptions: {
        allowOrigins: apigw.Cors.ALL_ORIGINS,
        allowMethods: ['POST', 'OPTIONS'],
        allowHeaders: ['Content-Type'],
      },
    });

    const chat = api.root.addResource('chat');
    chat.addMethod('POST', new apigw.LambdaIntegration(orchestrator));

    this.apiUrl = api.url;

    new cdk.CfnOutput(this, 'ApiUrl', {
      value: this.apiUrl,
      description: 'POST to {ApiUrl}chat with {"message": "..."}',
    });

    new cdk.CfnOutput(this, 'OrchestratorArn', {
      value: orchestrator.functionArn,
    });
  }
}