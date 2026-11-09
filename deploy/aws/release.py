"""Publish this checkout through S3 and SSM. Never copies AWS administrator keys.

Run with backend/.venv/bin/python deploy/aws/release.py --profile NAME.
Provider secrets are read from backend/.env and stored as an SSM SecureString.
"""
import argparse
import json
import os
import shlex
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import boto3
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--region', default='ap-south-1')
    parser.add_argument('--stack', default='shiftproof-live')
    args = parser.parse_args()
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    stack = session.client('cloudformation').describe_stacks(StackName=args.stack)['Stacks'][0]
    if stack['StackStatus'] not in {'CREATE_COMPLETE', 'UPDATE_COMPLETE'}:
        raise SystemExit('Wait for the infrastructure stack to finish before publishing.')
    outputs = {item['OutputKey']: item['OutputValue'] for item in stack['Outputs']}
    source = dotenv_values(ROOT / 'backend/.env')
    keys = ('DATABASE_URL', 'SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD',
            'SMTP_STARTTLS', 'MAIL_FROM', 'GNANI_API_KEY', 'GNANI_STT_MODEL',
            'GNANI_TTS_MODEL', 'GNANI_TTS_VOICE', 'GNANI_TTS_SPEED',
            'GEMINI_API_KEY', 'GEMINI_MODEL')
    config = {key: source[key] for key in keys if source.get(key)}
    if urlparse(config.get('DATABASE_URL', '')).path != '/shiftproof':
        raise SystemExit('Refusing to deploy against a database other than shiftproof.')
    config.update(APP_ENV='production', COOKIE_SECURE='true', MAIL_MODE='smtp',
                  FRONTEND_URL=outputs['URL'], ALLOWED_ORIGINS=json.dumps([outputs['URL']]),
                  STORAGE_MODE='s3', S3_BUCKET=outputs['Bucket'], S3_KEY_PREFIX='evidence',
                  AWS_REGION=args.region, MALWARE_SCANNER='/usr/bin/clamscan',
                  LOG_GROUP=outputs['LogGroup'], JOB_NAMESPACE='aws')
    # Compose uses single quotes for literal values, preserving dollar signs in secrets.
    def quote(value):
        if '\n' in value or '\r' in value:
            raise ValueError('Environment values must be single-line')
        return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"
    environment = '\n'.join(f'{key}={quote(str(value))}' for key, value in config.items()) + '\n'
    ssm = session.client('ssm')
    ssm.put_parameter(Name='/shiftproof/production/environment', Value=environment,
                      Type='SecureString', Overwrite=True)
    release = datetime.now(UTC).strftime('%Y%m%d%H%M%S')
    allowed = ['Dockerfile', '.dockerignore', 'package.json', 'package-lock.json',
               'tsconfig.json', 'vite.config.ts', 'index.html', 'src', 'public',
               'scripts/finalize-build.mjs', 'deploy', 'backend/Dockerfile',
               'backend/.dockerignore', 'backend/pyproject.toml', 'backend/uv.lock',
               'backend/alembic.ini', 'backend/app', 'backend/migrations']
    def safe_file(info):
        parts = Path(info.name).parts
        if any(part.startswith('.env') or part == '__pycache__' for part in parts):
            return None
        if info.issym() or info.islnk():
            raise ValueError('Release bundles may not contain symlinks')
        return info
    s3 = session.client('s3')
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / 'release.tar.gz'
        with tarfile.open(archive, 'w:gz') as bundle:
            for name in allowed:
                bundle.add(ROOT / name, arcname=name, filter=safe_file)
        s3.upload_file(str(archive), outputs['Bucket'], f'releases/{release}.tar.gz',
                       ExtraArgs={'ServerSideEncryption': 'AES256'})
    s3.upload_file(str(ROOT / 'deploy/aws/install-release.sh'), outputs['Bucket'],
                   f'releases/{release}-install.sh', ExtraArgs={'ServerSideEncryption': 'AES256'})
    command = ssm.send_command(InstanceIds=[outputs['InstanceId']],
        DocumentName='AWS-RunShellScript', TimeoutSeconds=3600,
        Parameters={'executionTimeout':['3600'], 'commands':[
            f"aws s3 cp s3://{outputs['Bucket']}/releases/{release}-install.sh /tmp/shiftproof-install.sh --region {shlex.quote(args.region)} --only-show-errors",
            f"bash /tmp/shiftproof-install.sh {shlex.quote(outputs['Bucket'])} {release} {shlex.quote(args.region)}",
        ]})['Command']['CommandId']
    result = {**outputs, 'release':release, 'command':command}
    target = ROOT / '.sites-runtime/aws-deployment.json'
    target.parent.mkdir(exist_ok=True)
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as output:
        json.dump(result, output, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
