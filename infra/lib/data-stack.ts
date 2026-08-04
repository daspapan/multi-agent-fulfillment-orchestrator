import * as cdk from "aws-cdk-lib";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as s3 from "aws-cdk-lib/aws-s3";
import { Construct } from "constructs";

export interface DataStackProps extends cdk.StackProps {
  environmentName: string;
}

/**
 * DynamoDB for task state + idempotency (single-key access pattern,
 * exactly what it's good at). S3 for raw documents with a 30-day Glacier
 * transition. RDS is deliberately not part of this stack -- see
 * ARCHITECTURE.md's storage section for why a relational store doesn't
 * fit this workload's access pattern.
 */
export class DataStack extends cdk.Stack {
  public readonly taskStateTable: dynamodb.Table;
  public readonly idempotencyTable: dynamodb.Table;
  public readonly documentBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props: DataStackProps) {
    super(scope, id, props);

    const removalPolicy =
      props.environmentName === "prod" ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY;

    this.taskStateTable = new dynamodb.Table(this, "TaskStateTable", {
      tableName: `orchestrator-task-state-${props.environmentName}`,
      partitionKey: { name: "task_id", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: "ttl",
      removalPolicy,
    });

    this.idempotencyTable = new dynamodb.Table(this, "FulfillmentIdempotencyTable", {
      tableName: `fulfillment-idempotency-${props.environmentName}`,
      partitionKey: { name: "order_id", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy,
    });

    this.documentBucket = new s3.Bucket(this, "DocumentBucket", {
      bucketName: `orchestrator-documents-${props.environmentName}-${this.account}`,
      versioned: true,
      lifecycleRules: [
        {
          id: "archive-after-30-days",
          enabled: true,
          transitions: [
            {
              storageClass: s3.StorageClass.GLACIER,
              transitionAfter: cdk.Duration.days(30),
            },
          ],
        },
      ],
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy,
    });
  }
}
