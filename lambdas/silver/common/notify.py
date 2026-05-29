import json
import os
import urllib.request


def notify_failure(message):
    parameter_name = os.environ.get("DISCORD_WEBHOOK_PARAMETER_NAME", "")
    if not parameter_name:
        return

    import boto3

    ssm = boto3.client("ssm")
    webhook_url = ssm.get_parameter(Name=parameter_name, WithDecryption=True)["Parameter"]["Value"]
    payload = json.dumps({"content": message}).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "cloud-computing-prj-silver/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        response.read()
