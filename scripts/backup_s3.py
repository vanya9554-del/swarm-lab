"""Upload a SQLite backup to S3-compatible storage (MinIO/AWS)."""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backup import backup as sqlite_backup


def upload(
    db: str | Path,
    bucket: str,
    key: str,
    *,
    endpoint_url: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
    region: str = "us-east-1",
) -> str:
    import boto3
    from botocore.exceptions import ClientError

    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )
    try:
        client.create_bucket(Bucket=bucket)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            raise
    with tempfile.TemporaryDirectory(prefix="swarmlab-s3-") as tmp:
        local = sqlite_backup(db, Path(tmp) / "swarm.db")
        client.upload_file(str(local), bucket, key)
    client.head_object(Bucket=bucket, Key=key)
    return f"s3://{bucket}/{key}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/swarm.db")
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--key", default="swarm.db")
    ap.add_argument("--endpoint", default=os.environ.get("SWARMLAB_S3_ENDPOINT"))
    ap.add_argument("--access-key", default=os.environ.get("SWARMLAB_S3_ACCESS_KEY"))
    ap.add_argument("--secret-key", default=os.environ.get("SWARMLAB_S3_SECRET_KEY"))
    ap.add_argument("--region", default=os.environ.get("SWARMLAB_S3_REGION", "us-east-1"))
    args = ap.parse_args(argv)
    print(upload(
        args.db, args.bucket, args.key,
        endpoint_url=args.endpoint,
        access_key=args.access_key,
        secret_key=args.secret_key,
        region=args.region,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
