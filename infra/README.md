# infra-cdk

AWS CDK (TypeScript) app for the target production architecture described
in `../ARCHITECTURE.md`. This replaces the earlier SAM/CloudFormation
template -- same resources, expressed as CDK, with actual tests.

## What's here

- `bin/app.ts` -- entry point, reads `-c env=dev|staging|prod`.
- `lib/network-stack.ts` -- VPC, 2 AZs, 1 NAT gateway (named cost/availability tradeoff, see comments).
- `lib/data-stack.ts` -- DynamoDB (task state + idempotency), S3 document bucket.
- `lib/compute-stack.ts` -- ECS cluster, one Fargate service running the orchestrator container, internal ALB.
- `lib/api-stack.ts` -- API Gateway HTTP API: VPC Link to the ALB for `/orders/*`, Lambda for `/fulfillment/webhook`.
- `lambda/fulfillment-webhook/` -- the one Lambda in this system, a stateless idempotency check.
- `test/stacks.test.ts` -- jest + `aws-cdk-lib/assertions`. One test class specifically locks down that
  `Network`/`Data` never depend on `Compute`/`Api` -- see the comment on `ComputeStack.vpcLinkSecurityGroup`
  for the circular-dependency trap this test exists to catch.

## Scope note: one Fargate service, not one per agent

The Fargate service runs the whole orchestrator process (`src/api/app.py`).
Summarizer, validator, enrichment, and fulfillment agents all execute
in-process inside that one task -- exactly like they do in this repo's
Python tests. Splitting each agent into its own Fargate service would mean
putting a queue between the orchestrator and each agent and rewriting
`dispatch()` to be async over it. That's an application-code change, not
an infra change, and it's out of scope here. Don't read the per-agent IAM
role structure in `src/agents/base.py`'s context isolation as implying
per-agent compute isolation at the infra layer -- they're two different
things.

## Commands

```bash
npm install
npm test                    # jest -- stack resource + dependency-graph assertions
npx cdk synth -c env=dev    # generates CloudFormation, no AWS credentials required
npx cdk diff -c env=dev     # requires AWS credentials + a bootstrapped account
npx cdk deploy --all -c env=dev   # NOT run as part of this project -- see below
```

## Deploying this for real (not done as part of this project)

1. `cdk bootstrap aws://ACCOUNT/REGION` once per account/region.
2. Docker (or an equivalent OCI builder) available wherever `cdk deploy`
   runs -- `ComputeStack` builds the orchestrator image from the repo's
   `Dockerfile` via `ecs.ContainerImage.fromAsset`, and image publishing
   happens at deploy time, not at synth time. `cdk synth` does **not**
   need Docker (verified: it only hashes the build context); `cdk deploy`
   does.
3. After the first deploy, set the real value of the
   `orchestrator/anthropic-api-key-{env}` secret in Secrets Manager --
   CDK provisions the secret but never writes a real key into it.
