#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { NetworkStack } from "../lib/network-stack";
import { DataStack } from "../lib/data-stack";
import { ComputeStack } from "../lib/compute-stack";
import { ApiStack } from "../lib/api-stack";

const app = new cdk.App();

// cdk deploy -c env=dev|staging|prod (defaults to dev). See config/*.yaml
// in the repo root for the matching application-level config per
// environment -- this only controls infrastructure sizing/naming.
const environmentName = (app.node.tryGetContext("env") as string) || "dev";

const env: cdk.Environment = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || "us-east-1",
};

const stackPrefix = `Orchestrator-${environmentName}`;

const network = new NetworkStack(app, `${stackPrefix}-Network`, { environmentName, env });

const data = new DataStack(app, `${stackPrefix}-Data`, { environmentName, env });

const compute = new ComputeStack(app, `${stackPrefix}-Compute`, {
  environmentName,
  env,
  vpc: network.vpc,
  taskStateTable: data.taskStateTable,
  documentBucket: data.documentBucket,
});

new ApiStack(app, `${stackPrefix}-Api`, {
  environmentName,
  env,
  vpc: network.vpc,
  listener: compute.listener,
  vpcLinkSecurityGroup: compute.vpcLinkSecurityGroup,
  idempotencyTable: data.idempotencyTable,
});
