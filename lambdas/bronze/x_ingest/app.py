import json
import os
from urllib.parse import unquote, unquote_plus
import urllib.request


SUPPORTED_DATASETS = {"bitcoin-tweets", "covid-tweets"}


def normalized_prefix(prefix):
    return prefix.strip("/")


def x_bronze_key(incoming_key, bronze_prefix=None):
    key = incoming_key.lstrip("/")
    parts = key.split("/", 3)
    if len(parts) != 4 or parts[0] != "incoming" or parts[1] != "x":
        raise ValueError(f"unsupported incoming key: {incoming_key}")

    dataset = parts[2]
    relative_path = parts[3]
    if dataset not in SUPPORTED_DATASETS:
        raise ValueError(f"unsupported X dataset category: {dataset}")
    if not relative_path or relative_path.endswith("/"):
        raise ValueError(f"incoming key does not point to a file: {incoming_key}")

    prefix = normalized_prefix(bronze_prefix or os.environ.get("BRONZE_PREFIX", "bronze"))
    return f"{prefix}/x/{dataset}/raw/{relative_path}"


def extract_s3_objects(event):
    if "Records" in event:
        objects = []
        for record in event["Records"]:
            if record.get("eventSource") != "aws:s3":
                continue
            bucket = record["s3"]["bucket"]["name"]
            key = unquote_plus(record["s3"]["object"]["key"])
            objects.append((bucket, key))
        return objects

    if event.get("source") == "aws.s3" and event.get("detail-type") == "Object Created":
        detail = event["detail"]
        return [(detail["bucket"]["name"], unquote(detail["object"]["key"]))]

    return []


def get_s3_client():
    import boto3

    return boto3.client("s3")


def get_ssm_client():
    import boto3

    return boto3.client("ssm")


def format_failure_message(stage, job, error, context=None):
    project = os.environ.get("PROJECT_NAME", "cloud-computing-prj")
    environment = os.environ.get("ENVIRONMENT", "dev")
    lines = [f"[{project}][{environment}][{stage}] {job} failed", f"Error: {error}"]

    clean_context = {key: value for key, value in (context or {}).items() if value not in (None, "", [], {})}
    if clean_context:
        context_text = " ".join(f"{key}={value}" for key, value in sorted(clean_context.items()))
        lines.append(f"Context: {context_text}")
    return "\n".join(lines)


def notify_failure(stage, job, error, context=None):
    parameter_name = os.environ.get("DISCORD_WEBHOOK_PARAMETER_NAME", "")
    if not parameter_name:
        return

    ssm = get_ssm_client()
    webhook_url = ssm.get_parameter(Name=parameter_name, WithDecryption=True)["Parameter"]["Value"]
    payload = json.dumps({"content": format_failure_message(stage, job, error, context)}).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "cloud-computing-prj-bronze/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        response.read()


def lambda_handler(event, context):
    objects = []
    try:
        expected_bucket = os.environ["DATA_LAKE_BUCKET"]
        objects = extract_s3_objects(event or {})
        if not objects:
            raise ValueError("event did not contain any S3 object create records")

        s3 = get_s3_client()
        copied = []
        for bucket, source_key in objects:
            if bucket != expected_bucket:
                raise ValueError(f"unexpected bucket {bucket}; expected {expected_bucket}")

            destination_key = x_bronze_key(source_key)
            s3.copy_object(
                Bucket=bucket,
                Key=destination_key,
                CopySource={"Bucket": bucket, "Key": source_key},
                MetadataDirective="COPY",
            )
            copied.append({"source_key": source_key, "destination_key": destination_key})

        return {"copied": copied}
    except Exception as exc:
        try:
            first_object = objects[0] if objects else (None, None)
            notify_failure(
                "bronze",
                "x-ingest",
                exc,
                {"bucket": first_object[0], "source_key": first_object[1]},
            )
        except Exception as notify_exc:
            print(f"failed to send Discord notification: {notify_exc}")
        raise
