"""
Fulfillment webhook receiver -- the one path in this system that's
genuinely a good fit for Lambda: stateless, bursty, needs to scale to
zero between orders. See ARCHITECTURE.md's compute section for why this
is Lambda and the orchestrator itself is Fargate, not the other way round.

Deliberately separate from src/ -- this is not the orchestrator, it's the
idempotency check the fulfillment agent's DynamoDB table backs (see
src/agents/fulfillment.py for the in-process equivalent used in tests).
"""

import json
import os

import boto3

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    table = dynamodb.Table(os.environ["IDEMPOTENCY_TABLE_NAME"])
    body = json.loads(event.get("body") or "{}")
    order_id = body.get("order_id")

    if not order_id:
        return {"statusCode": 400, "body": json.dumps({"error": "order_id is required"})}

    try:
        table.put_item(
            Item={"order_id": order_id, "status": "received"},
            ConditionExpression="attribute_not_exists(order_id)",
        )
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return {"statusCode": 409, "body": json.dumps({"error": "duplicate_order_id", "order_id": order_id})}

    return {"statusCode": 200, "body": json.dumps({"status": "received", "order_id": order_id})}
