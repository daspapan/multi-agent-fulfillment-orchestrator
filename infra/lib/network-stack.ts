import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import { Construct } from "constructs";

export interface NetworkStackProps extends cdk.StackProps {
  environmentName: string;
}

/**
 * Two AZs, one NAT gateway.
 *
 * ARCHITECTURE.md flags this explicitly: a third AZ (and a second NAT
 * gateway) would improve availability, but this workload's current SLA
 * doesn't justify the added cost yet. Revisit if traffic or uptime
 * requirements grow -- this is a named tradeoff, not an oversight.
 */
export class NetworkStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;

  constructor(scope: Construct, id: string, props: NetworkStackProps) {
    super(scope, id, props);

    this.vpc = new ec2.Vpc(this, "OrchestratorVpc", {
      vpcName: `orchestrator-vpc-${props.environmentName}`,
      ipAddresses: ec2.IpAddresses.cidr("10.42.0.0/16"),
      maxAzs: 2,
      natGateways: 1,
      subnetConfiguration: [
        {
          name: "public",
          subnetType: ec2.SubnetType.PUBLIC,
          cidrMask: 24,
        },
        {
          name: "private-app",
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
          cidrMask: 24,
        },
      ],
    });
  }
}
