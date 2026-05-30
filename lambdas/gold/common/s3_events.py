from urllib.parse import unquote, unquote_plus


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
