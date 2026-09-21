import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';

interface AgentStackProps extends cdk.StackProps {
  toolFunction: lambda.Function;
}

export class AgentStack extends cdk.Stack {
  public readonly agentId: string;
  public readonly agentAliasId: string;

  constructor(scope: Construct, id: string, props: AgentStackProps) {
    super(scope, id, props);

    const agentRole = new iam.Role(this, 'AgentRole', {
      roleName: 'aws-agent-bedrock-role',
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
      description: 'Execution role for the AWS account Bedrock Agent',
    });

    agentRole.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          'bedrock:InvokeModel',
          'bedrock:InvokeModelWithResponseStream',
        ],
        resources: ['*'],
      })
    );

    props.toolFunction.grantInvoke(agentRole);

    const instruction = `You are an AWS account assistant. You have eight tools available:

- cost_query: Returns AWS spending for the last N days, grouped by service. Optional parameter: days (integer, default 30).
- cost_forecast: Forecasts AWS spending for the next N days. Optional parameter: days (integer, default 30).
- s3_audit: Lists all S3 buckets with public access and versioning status.
- iam_summary: Lists IAM users with MFA and access key counts.
- ec2_inventory: Lists all EC2 instances with state, type, and AZ.
- security_posture: Returns basic security issues (root MFA, users without MFA).
- sg_audit: Lists security groups that allow traffic from 0.0.0.0/0.
- cloudtrail_recent: Returns recent CloudTrail API activity. Optional parameter: hours (integer, default 24).

Always call the appropriate tool before answering. Never fabricate results. If no tool fits the question, say so directly.`;

    const agent = new cdk.aws_bedrock.CfnAgent(this, 'Agent', {
      agentName: 'aws-account-helper',
      description: 'Answers questions about AWS account resources and costs',
      foundationModel: 'amazon.nova-micro-v1:0',
      instruction: instruction,
      agentResourceRoleArn: agentRole.roleArn,
      idleSessionTtlInSeconds: 1800,
      autoPrepare: true,
      actionGroups: [
        {
          actionGroupName: 'AWSOps',
          description: 'AWS account operations',
          actionGroupExecutor: {
            lambda: props.toolFunction.functionArn,
          },
          functionSchema: {
            functions: [
              {
                name: 'cost_query',
                description: 'Returns AWS spending for the last N days, grouped by service',
                parameters: {
                  days: {
                    type: 'integer',
                    description: 'Number of days to look back',
                    required: false,
                  },
                },
              },
              {
                name: 'cost_forecast',
                description: 'Forecasts AWS spending for the next N days',
                parameters: {
                  days: {
                    type: 'integer',
                    description: 'Number of days to forecast',
                    required: false,
                  },
                },
              },
              {
                name: 's3_audit',
                description: 'Lists all S3 buckets with public access and versioning status',
              },
              {
                name: 'iam_summary',
                description: 'Lists IAM users with MFA and access key counts',
              },
              {
                name: 'ec2_inventory',
                description: 'Lists all EC2 instances with state and type',
              },
              {
                name: 'security_posture',
                description: 'Returns basic security issues in the account',
              },
              {
                name: 'sg_audit',
                description: 'Lists security groups that allow inbound traffic from 0.0.0.0/0',
              },
              {
                name: 'cloudtrail_recent',
                description: 'Returns recent CloudTrail API activity',
                parameters: {
                  hours: {
                    type: 'integer',
                    description: 'Number of hours to look back',
                    required: false,
                  },
                },
              },
            ],
          },
        },
      ],
    });

    const alias = new cdk.aws_bedrock.CfnAgentAlias(this, 'AgentAlias', {
      agentId: agent.ref,
      agentAliasName: 'live',
    });

    this.agentId = agent.ref;
    this.agentAliasId = alias.attrAgentAliasId;

    new cdk.CfnOutput(this, 'AgentId', { value: this.agentId });
    new cdk.CfnOutput(this, 'AgentAliasId', { value: this.agentAliasId });
    new cdk.CfnOutput(this, 'AgentRoleArn', { value: agentRole.roleArn });
  }
}