import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as apigwv2 from "aws-cdk-lib/aws-apigatewayv2";
import { HttpAlbIntegration, HttpLambdaIntegration } from "aws-cdk-lib/aws-apigatewayv2-integrations";
import * as path from "path";
import { Construct } from "constructs";

export interface ApiStackProps extends cdk.StackProps {
  environmentName: string;
  vpc: ec2.IVpc;
  listener: elbv2.IApplicationListener;
  idempotencyTable: dynamodb.ITable;
  vpcLinkSecurityGroup: ec2.ISecurityGroup;
}

/**
 * Two public entry points, two very different shapes behind them:
 *
 *  - POST /orders/* -> VPC Link -> internal ALB -> orchestrator Fargate
 *    service. Long-lived process, holds state across the task graph.
 *  - POST /fulfillment/webhook -> Lambda. Stateless, bursty, scales to
 *    zero. See infra-cdk/lambda/fulfillment-webhook and ARCHITECTURE.md's
 *    compute section for why this half is Lambda and the other half isn't.
 *
 * Throttling here is the direct response to the "Tuesday-morning stall":
 * better to return 429s at the edge under a traffic spike than let
 * requests queue silently inside the hub with no backpressure signal.
 */
export class ApiStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ApiStackProps) {
    super(scope, id, props);

    // Security group comes from ComputeStack, not created here -- see the
    // comment on ComputeStack.vpcLinkSecurityGroup for why (avoiding a
    // circular stack dependency between Compute and Api).
    const vpcLink = new apigwv2.VpcLink(this, "OrchestratorVpcLink", {
      vpcLinkName: `orchestrator-vpc-link-${props.environmentName}`,
      vpc: props.vpc,
      securityGroups: [props.vpcLinkSecurityGroup],
      subnets: props.vpc.selectSubnets({ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }),
    });

    const webhookFn = new lambda.Function(this, "FulfillmentWebhookFunction", {
      functionName: `fulfillment-webhook-${props.environmentName}`,
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "index.handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "..", "lambda", "fulfillment-webhook")),
      timeout: cdk.Duration.seconds(10),
      memorySize: 256,
      environment: {
        IDEMPOTENCY_TABLE_NAME: props.idempotencyTable.tableName,
      },
    });
    props.idempotencyTable.grantReadWriteData(webhookFn);

    const httpApi = new apigwv2.HttpApi(this, "OrchestratorHttpApi", {
      apiName: `orchestrator-api-${props.environmentName}`,
      description: "Public entry points for ticket/order ingestion and the fulfillment webhook",
    });

    httpApi.addRoutes({
      path: "/orders/{proxy+}",
      methods: [apigwv2.HttpMethod.ANY],
      integration: new HttpAlbIntegration("OrchestratorAlbIntegration", props.listener, {
        vpcLink,
      }),
    });

    httpApi.addRoutes({
      path: "/fulfillment/webhook",
      methods: [apigwv2.HttpMethod.POST],
      integration: new HttpLambdaIntegration("FulfillmentWebhookIntegration", webhookFn),
    });

    new cdk.CfnOutput(this, "HttpApiUrl", { value: httpApi.apiEndpoint });
  }
}
