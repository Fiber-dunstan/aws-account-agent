import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import * as path from 'path';

interface ToolConfig {
  name: string;
  managedPolicies: string[];
  inlinePolicies?: { [key: string]: iam.PolicyDocument };
}

export class LambdaStack extends cdk.Stack {
  public readonly toolFunctions: { [key: string]: lambda.Function } = {};

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const tools: ToolConfig[] = [
      {
        name: 'cost_query',
        managedPolicies: ['AWSBillingReadOnlyAccess'],
      },
      {
        name: 'cost_forecast',
        managedPolicies: ['AWSBillingReadOnlyAccess'],
        inlinePolicies: {
          CostForecast: new iam.PolicyDocument({
            statements: [
              new iam.PolicyStatement({
                actions: ['ce:GetCostForecast'],
                resources: ['*'],
              }),
            ],
          }),
        },
      },
      {
        name: 's3_audit',
        managedPolicies: ['AmazonS3ReadOnlyAccess'],
      },
      {
        name: 'iam_summary',
        managedPolicies: ['IAMReadOnlyAccess'],
      },
      {
        name: 'ec2_inventory',
        managedPolicies: ['AmazonEC2ReadOnlyAccess'],
      },
      {
        name: 'security_posture',
        managedPolicies: ['IAMReadOnlyAccess'],
      },
      {
        name: 'sg_audit',
        managedPolicies: ['AmazonEC2ReadOnlyAccess'],
      },
      {
        name: 'cloudtrail_recent',
        managedPolicies: [],
        inlinePolicies: {
          CloudTrailLookup: new iam.PolicyDocument({
            statements: [
              new iam.PolicyStatement({
                actions: ['cloudtrail:LookupEvents'],
                resources: ['*'],
              }),
            ],
          }),
        },
      },
    ];

    for (const tool of tools) {
      const fn = new lambda.Function(this, `${tool.name}Fn`, {
        functionName: `aws-agent-${tool.name}`,
        runtime: lambda.Runtime.PYTHON_3_12,
        handler: 'index.lambda_handler',
        code: lambda.Code.fromAsset(
          path.join(__dirname, `../lambda/tools/${tool.name}`)
        ),
        timeout: cdk.Duration.seconds(30),
        memorySize: 256,
        environment: {
          LOG_LEVEL: 'INFO',
        },
        description: `AWS account agent tool: ${tool.name}`,
      });

      for (const policy of tool.managedPolicies) {
        fn.role?.addManagedPolicy(
          iam.ManagedPolicy.fromAwsManagedPolicyName(policy)
        );
      }

      if (tool.inlinePolicies) {
        for (const [policyName, doc] of Object.entries(tool.inlinePolicies)) {
          fn.role?.attachInlinePolicy(
            new iam.Policy(this, `${tool.name}-${policyName}`, {
              policyName: policyName,
              document: doc,
            })
          );
        }
      }

      fn.addPermission(`BedrockInvoke-${tool.name}`, {
        principal: new iam.ServicePrincipal('bedrock.amazonaws.com'),
        action: 'lambda:InvokeFunction',
      });

      this.toolFunctions[tool.name] = fn;

      new cdk.CfnOutput(this, `${tool.name}Arn`, {
        value: fn.functionArn,
        description: `ARN of the ${tool.name} Lambda`,
      });
    }
  }
}