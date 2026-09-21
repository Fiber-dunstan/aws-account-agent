import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import * as path from 'path';

export class LambdaStack extends cdk.Stack {
  public readonly toolFunction: lambda.Function;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    this.toolFunction = new lambda.Function(this, 'UnifiedToolsFn', {
      functionName: 'aws-agent-tools',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.lambda_handler',
      code: lambda.Code.fromAsset(
        path.join(__dirname, '../lambda/tools/unified')
      ),
      timeout: cdk.Duration.seconds(60),
      memorySize: 512,
      environment: {
        LOG_LEVEL: 'INFO',
      },
      description: 'Unified tool Lambda for the AWS account Bedrock Agent',
    });

    const managedPolicies = [
      'AWSBillingReadOnlyAccess',
      'AmazonS3ReadOnlyAccess',
      'IAMReadOnlyAccess',
      'AmazonEC2ReadOnlyAccess',
    ];

    for (const policy of managedPolicies) {
      this.toolFunction.role?.addManagedPolicy(
        iam.ManagedPolicy.fromAwsManagedPolicyName(policy)
      );
    }

    this.toolFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['ce:GetCostForecast'],
        resources: ['*'],
      })
    );

    this.toolFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['cloudtrail:LookupEvents'],
        resources: ['*'],
      })
    );

    this.toolFunction.addPermission('BedrockInvoke', {
      principal: new iam.ServicePrincipal('bedrock.amazonaws.com'),
      action: 'lambda:InvokeFunction',
    });

    new cdk.CfnOutput(this, 'ToolFunctionArn', {
      value: this.toolFunction.functionArn,
    });

    new cdk.CfnOutput(this, 'ToolFunctionName', {
      value: this.toolFunction.functionName,
    });
  }
}