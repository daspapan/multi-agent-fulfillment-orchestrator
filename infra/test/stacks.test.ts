import * as cdk from "aws-cdk-lib";
import { Template } from "aws-cdk-lib/assertions";
import { NetworkStack } from "../lib/network-stack";
import { DataStack } from "../lib/data-stack";
import { ComputeStack } from "../lib/compute-stack";
import { ApiStack } from "../lib/api-stack";

/**
 * These tests exist mainly to catch the class of mistake that doesn't show
 * up as a TypeScript error: a stack depending on another stack that
 * depends back on it. CDK throws at synth time if that happens, so
 * `app.synth()` succeeding is itself the assertion for that -- the
 * per-resource checks below are the secondary thing worth locking down.
 */
describe("orchestrator infrastructure", () => {
  function buildApp(environmentName: string) {
    const app = new cdk.App({ context: { env: environmentName } });
    const env: cdk.Environment = { account: "123456789012", region: "us-east-1" };

    const network = new NetworkStack(app, `Test-${environmentName}-Network`, { environmentName, env });
    const data = new DataStack(app, `Test-${environmentName}-Data`, { environmentName, env });
    const compute = new ComputeStack(app, `Test-${environmentName}-Compute`, {
      environmentName,
      env,
      vpc: network.vpc,
      taskStateTable: data.taskStateTable,
      documentBucket: data.documentBucket,
    });
    const api = new ApiStack(app, `Test-${environmentName}-Api`, {
      environmentName,
      env,
      vpc: network.vpc,
      listener: compute.listener,
      vpcLinkSecurityGroup: compute.vpcLinkSecurityGroup,
      idempotencyTable: data.idempotencyTable,
    });

    return { app, network, data, compute, api };
  }

  test("app synthesizes without throwing (no circular stack dependency)", () => {
    const { app } = buildApp("dev");
    expect(() => app.synth()).not.toThrow();
  });

  test("stack dependency graph is one-directional: Network/Data -> Compute -> Api", () => {
    const { app, network, data, compute, api } = buildApp("dev");
    app.synth();

    const computeDeps = compute.dependencies.map((s) => s.stackName);
    expect(computeDeps).toEqual(expect.arrayContaining([network.stackName, data.stackName]));
    expect(computeDeps).not.toContain(api.stackName);

    const apiDeps = api.dependencies.map((s) => s.stackName);
    expect(apiDeps).toEqual(
      expect.arrayContaining([network.stackName, data.stackName, compute.stackName])
    );

    // the specific mistake this project almost shipped: Compute must NOT
    // depend on Api for the ALB <-> VPC Link security group rule.
    expect(network.dependencies.map((s) => s.stackName)).not.toContain(compute.stackName);
    expect(network.dependencies.map((s) => s.stackName)).not.toContain(api.stackName);
    expect(data.dependencies.map((s) => s.stackName)).not.toContain(compute.stackName);
    expect(data.dependencies.map((s) => s.stackName)).not.toContain(api.stackName);
  });

  test("compute stack: one Fargate service, one task definition, ALB is internal", () => {
    const { compute } = buildApp("dev");
    const template = Template.fromStack(compute);

    template.resourceCountIs("AWS::ECS::Service", 1);
    template.resourceCountIs("AWS::ECS::TaskDefinition", 1);
    template.hasResourceProperties("AWS::ElasticLoadBalancingV2::LoadBalancer", {
      Scheme: "internal",
    });
  });

  test("data stack: task state table has TTL, idempotency table keyed on order_id", () => {
    const { data } = buildApp("dev");
    const template = Template.fromStack(data);

    template.hasResourceProperties("AWS::DynamoDB::Table", {
      TimeToLiveSpecification: { AttributeName: "ttl", Enabled: true },
    });
    template.hasResourceProperties("AWS::DynamoDB::Table", {
      KeySchema: [{ AttributeName: "order_id", KeyType: "HASH" }],
    });
  });

  test("api stack: VPC Link uses Compute's security group, not one of its own", () => {
    const { api } = buildApp("dev");
    const template = Template.fromStack(api);

    // ApiStack must not create its own AWS::EC2::SecurityGroup resource for
    // the VPC link -- it should import Compute's, or the circular-dependency
    // problem this test suite exists to catch comes right back.
    template.resourceCountIs("AWS::EC2::SecurityGroup", 0);
    template.resourceCountIs("AWS::ApiGatewayV2::VpcLink", 1);
  });
});
