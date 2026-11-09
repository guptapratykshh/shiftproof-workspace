"""Copy retained local evidence to private S3 without changing report records.

Run from backend with .venv/bin/python ../deploy/aws/migrate_evidence.py.
The copy is resumable, verifies SHA-256 and never deletes the local originals.
"""
import argparse
import hashlib
import json
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import or_, select

from app.config import get_settings
from app.db import SessionLocal, now
from app.models import FileAsset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--bucket', required=True)
    parser.add_argument('--region', default='ap-south-1')
    args = parser.parse_args()
    client = boto3.Session(profile_name=args.profile, region_name=args.region).client('s3')
    with SessionLocal() as db:
        assets = db.scalars(select(FileAsset).where(
            FileAsset.deleted_at.is_(None),
            or_(FileAsset.retention_until.is_(None), FileAsset.retention_until > now()),
        )).all()
    counts = {'copied':0, 'verified_existing':0, 'missing_local':0}
    for asset in assets:
        key = f'evidence/{asset.storage_key}'
        try:
            stored = client.head_object(Bucket=args.bucket, Key=key)
            if stored['ContentLength'] != asset.byte_size or stored.get('Metadata', {}).get('sha256') != asset.sha256:
                raise ValueError('Existing object does not match the recorded evidence')
            counts['verified_existing'] += 1
            continue
        except ClientError as error:
            if error.response['Error']['Code'] not in {'404','NoSuchKey','NotFound'}:
                raise
        source = get_settings().storage_directory / asset.storage_key
        if not source.is_file():
            counts['missing_local'] += 1
            continue
        data = source.read_bytes()
        if len(data) != asset.byte_size or hashlib.sha256(data).hexdigest() != asset.sha256:
            raise ValueError('Local evidence checksum does not match its report record')
        client.put_object(Bucket=args.bucket, Key=key, Body=data, ContentType=asset.mime_type,
                          ServerSideEncryption='AES256', Metadata={'sha256':asset.sha256})
        if client.head_object(Bucket=args.bucket, Key=key)['ContentLength'] != asset.byte_size:
            raise ValueError('Uploaded evidence verification failed')
        counts['copied'] += 1
    print(json.dumps(counts))


if __name__ == '__main__':
    main()
