import os


def get_s3_client():
    import boto3

    return boto3.client("s3")


def read_object_bytes(bucket, key):
    response = get_s3_client().get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def read_json_from_s3(bucket, key):
    return read_object_bytes(bucket, key)


def list_objects_under_prefix(bucket, prefix):
    client = get_s3_client()
    paginator = client.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            keys.append(item["Key"])
    return keys


def write_posts_dataset(bucket, dataframe):
    import awswrangler as wr

    if dataframe.empty:
        return []
    path = f"s3://{bucket}/{os.environ.get('SILVER_PREFIX', 'silver').strip('/')}/posts/"
    wr.s3.to_parquet(
        df=dataframe,
        path=path,
        dataset=True,
        partition_cols=["year", "month", "day"],
        mode="overwrite_partitions",
    )
    return [path]


def write_users_partition(bucket, platform_partition, dataframe):
    import awswrangler as wr

    silver_prefix = os.environ.get("SILVER_PREFIX", "silver").strip("/")
    path = f"s3://{bucket}/{silver_prefix}/users/platform={platform_partition}/"
    if dataframe.empty:
        return path

    existing = None
    keys = list_objects_under_prefix(bucket, f"{silver_prefix}/users/platform={platform_partition}/")
    if keys:
        existing = wr.s3.read_parquet(path=f"s3://{bucket}/{silver_prefix}/users/platform={platform_partition}/", dataset=True)

    if existing is not None and not existing.empty:
        import pandas as pd

        merged = pd.concat([existing, dataframe], ignore_index=True)
        merged = merged.sort_values("username").drop_duplicates(subset=["username"], keep="last")
        dataframe = merged

    wr.s3.to_parquet(
        df=dataframe,
        path=f"s3://{bucket}/{silver_prefix}/users/platform={platform_partition}/",
        dataset=True,
        mode="overwrite",
    )
    return f"s3://{bucket}/{silver_prefix}/users/platform={platform_partition}/"
