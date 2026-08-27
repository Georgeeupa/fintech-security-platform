import boto3
import json
import os
from datetime import datetime, timezone

ec2 = boto3.client("ec2")
sns = boto3.client("sns")
s3 = boto3.client("s3")

ISOLATION_SG = os.environ["ISOLATION_SG"]
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]
INCIDENT_BUCKET = os.environ["INCIDENT_BUCKET"]

def lambda_handler(event, context):

    detail = event.get("detail", {})
    finding_id = detail.get("id", "unknown")

    severity = detail.get("severity", 0)

    if isinstance(severity, dict):
        severity = severity.get("normalized", 0)

    severity = int(severity)

    if severity < 7:
        return {
            "status": "ignored",
            "reason": "Finding severity below threshold"
        }

    instance_id = (
        detail.get("resource", {})
        .get("instanceDetails", {})
        .get("instanceId")
    )

    if not instance_id:
        return {
            "status": "no_instance",
            "finding": finding_id
        }

    ec2.modify_instance_attribute(
        InstanceId=instance_id,
        Groups=[ISOLATION_SG]
    )

    evidence = {
        "finding_id": finding_id,
        "severity": severity,
        "instance_id": instance_id,
        "action": "EC2 isolated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event
    }

    key = f"guardduty/{finding_id}.json"

    s3.put_object(
        Bucket=INCIDENT_BUCKET,
        Key=key,
        Body=json.dumps(evidence, indent=2),
        ServerSideEncryption="aws:kms"
    )

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject="GuardDuty High Severity Incident",
        Message=json.dumps(evidence, indent=2)
    )

    return {
        "status": "isolated",
        "instance": instance_id,
        "evidence": f"s3://{INCIDENT_BUCKET}/{key}"
    }
