import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import * as ecrAssets from "aws-cdk-lib/aws-ecr-assets";
import * as logs from "aws-cdk-lib/aws-logs";
import * as path from "path";
import { Construct } from "constructs";

export interface ComputeStackProps extends cdk.StackProps {
  environmentName: string;
  vpc: ec2.IVpc;
  taskStateTable: dynamodb.ITable;
  documentBucket: s3.IBucket;
}

/**
 * One Fargate service runs the whole orchestrator process (see
 * src/api/app.py) -- summarizer, validator, enrichment, and fulfillment
 * agents all execute in that one task, in-process, exactly like they do
 * in this repo's Python tests.
 *
 * This is a deliberate, named scope limit, not an oversight: the app
 * code (src/orchestrator/orchestrator.py) calls agents as plain Python
 * objects, not as separate network services. Splitting each agent into
 * its own Fargate service would mean putting a queue (SQS/EventBridge)
 * between the orchestrator and each agent and rewriting the dispatch
 * logic to be async over that queue -- a real architectural change, not
 * an infra change, and out of scope here. If per-agent compute isolation
 * (as opposed to the in-process context isolation src/agents/base.py
 * already enforces) becomes a real requirement, that rewrite is the
 * prerequisite, not this stack.
 */
export class ComputeStack extends cdk.Stack {
  public readonly loadBalancerDnsName: string;
  public readonly listener: elbv2.ApplicationListener;
  public readonly vpcLinkSecurityGroup: ec2.SecurityGroup;

  constructor(scope: Construct, id: string, props: ComputeStackProps) {
    super(scope, id, props);

    const cluster = new ecs.Cluster(this, "OrchestratorCluster", {
      clusterName: `orchestrator-cluster-${props.environmentName}`,
      vpc: props.vpc,
      containerInsights: true,
    });

    // Populated manually post-deploy (not committed, not synthesized with a
    // real value) -- see README's deployment notes.
    const anthropicApiKeySecret = new secretsmanager.Secret(this, "AnthropicApiKey", {
      secretName: `orchestrator/anthropic-api-key-${props.environmentName}`,
      description: "ANTHROPIC_API_KEY for the orchestrator task. Value set out-of-band, never in code.",
    });

    const taskDefinition = new ecs.FargateTaskDefinition(this, "OrchestratorTaskDef", {
      family: `orchestrator-${props.environmentName}`,
      cpu: 512,
      memoryLimitMiB: 1024,
    });

    // Least-privilege on purpose: this role can read/write exactly the task
    // state table and read exactly the document bucket. No dynamodb:* or
    // s3:* wildcard grants -- same principle src/agents/base.py enforces
    // in code (a subagent only sees what it's explicitly given), enforced
    // here at the IAM boundary instead.
    props.taskStateTable.grantReadWriteData(taskDefinition.taskRole);
    props.documentBucket.grantRead(taskDefinition.taskRole);
    anthropicApiKeySecret.grantRead(taskDefinition.taskRole);

    const logGroup = new logs.LogGroup(this, "OrchestratorLogGroup", {
      logGroupName: `/ecs/orchestrator-${props.environmentName}`,
      retention: logs.RetentionDays.TWO_WEEKS,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const container = taskDefinition.addContainer("orchestrator", {
      image: ecs.ContainerImage.fromAsset(path.join(__dirname, "..", ".."), {
        file: "Dockerfile",
        platform: ecrAssets.Platform.LINUX_AMD64,
      }),
      environment: {
        ENVIRONMENT: props.environmentName,
        TASK_STATE_TABLE_NAME: props.taskStateTable.tableName,
        DOCUMENT_BUCKET_NAME: props.documentBucket.bucketName,
      },
      secrets: {
        ANTHROPIC_API_KEY: ecs.Secret.fromSecretsManager(anthropicApiKeySecret),
      },
      logging: ecs.LogDrivers.awsLogs({ streamPrefix: "orchestrator", logGroup }),
      portMappings: [{ containerPort: 8080 }],
    });

    const serviceSg = new ec2.SecurityGroup(this, "OrchestratorServiceSg", {
      vpc: props.vpc,
      description: "Orchestrator Fargate service -- inbound only from the internal ALB",
      allowAllOutbound: true,
    });

    const service = new ecs.FargateService(this, "OrchestratorService", {
      serviceName: `orchestrator-${props.environmentName}`,
      cluster,
      taskDefinition,
      desiredCount: props.environmentName === "prod" ? 2 : 1,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      securityGroups: [serviceSg],
      minHealthyPercent: 100,
      maxHealthyPercent: 200,
    });

    // Internal ALB only -- no public IP, no direct internet route, matching
    // ARCHITECTURE.md's networking section. API Gateway reaches this via a
    // VPC Link (see api-stack.ts), nothing reaches it directly from outside
    // the VPC.
    const alb = new elbv2.ApplicationLoadBalancer(this, "OrchestratorAlb", {
      vpc: props.vpc,
      internetFacing: false,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
    });

    const listener = alb.addListener("OrchestratorListener", {
      port: 80,
      open: false,
    });

    listener.addTargets("OrchestratorTarget", {
      port: 8080,
      targets: [service],
      healthCheck: {
        path: "/health",
        healthyHttpCodes: "200",
        interval: cdk.Duration.seconds(30),
      },
    });

    serviceSg.addIngressRule(
      ec2.Peer.ipv4(props.vpc.vpcCidrBlock),
      ec2.Port.tcp(8080),
      "ALB health checks and traffic, VPC-internal only"
    );

    // The VPC Link (created in api-stack.ts) needs a security group that's
    // allowed to reach this ALB. That security group has to be created here,
    // not in ApiStack -- if ApiStack created it and Compute tried to import
    // it for the ingress rule, Compute would depend on ApiStack at the same
    // time ApiStack depends on Compute for the listener, a genuine circular
    // stack dependency. Creating it here and exporting it keeps the
    // dependency graph one-directional: Network/Data -> Compute -> Api.
    this.vpcLinkSecurityGroup = new ec2.SecurityGroup(this, "VpcLinkSecurityGroup", {
      vpc: props.vpc,
      description: "API Gateway VPC Link -> internal orchestrator ALB",
      allowAllOutbound: true,
    });
    alb.connections.allowFrom(this.vpcLinkSecurityGroup, ec2.Port.tcp(80), "API Gateway VPC Link");

    this.loadBalancerDnsName = alb.loadBalancerDnsName;
    this.listener = listener;

    new cdk.CfnOutput(this, "AlbDnsName", { value: alb.loadBalancerDnsName });
  }
}
