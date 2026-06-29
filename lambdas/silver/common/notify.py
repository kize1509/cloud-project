import json
import os
import urllib.request


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

    import boto3

    ssm = boto3.client("ssm")
    webhook_url = ssm.get_parameter(Name=parameter_name, WithDecryption=True)["Parameter"]["Value"]
    payload = json.dumps({"content": format_failure_message(stage, job, error, context)}).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "cloud-computing-prj-silver/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        response.read()
