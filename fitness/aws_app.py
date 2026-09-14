"""IAM-authenticated Lambda API and on-demand synthetic batch execution."""
import json
import os
from pathlib import Path
import tempfile
import uuid
import boto3
from botocore.exceptions import ClientError
from fitness.pipeline import ROOT, connect, ingest, utc
from fitness.operations import run_interval
from fitness.dashboard import render


def response(status, data, html=False):
    return {'statusCode':status,'headers':{'content-type':'text/html; charset=utf-8' if html else 'application/json','cache-control':'no-store','x-content-type-options':'nosniff'},'body':data if html else json.dumps(data)}


def handler(event, context):
    bucket=os.environ['FITNESS_BUCKET']; s3=boto3.client('s3')
    if 'requestContext' in event:
        if event['requestContext'].get('http',{}).get('method')!='GET': return response(405,{'error':'method_not_allowed'})
        path=event.get('rawPath','/')
        if path not in ('/','/summary','/health'): return response(404,{'error':'not_found'})
        try: summary=json.loads(s3.get_object(Bucket=bucket,Key='published/latest.json')['Body'].read())
        except ClientError as error:
            if error.response['Error']['Code']=='NoSuchKey': return response(503,{'error':'no_published_run'})
            raise
        if path=='/': return response(200,render(summary),html=True)
        return response(200,summary if path=='/summary' else {'status':'ready','as_of':summary['as_of'],'synthetic_only':True})
    if event.get('operation')!='run': return response(400,{'error':'unsupported_operation'})
    # Public HTTP requests cannot execute jobs; direct Lambda invocation requires IAM.
    cutoff=utc(event.get('as_of','2026-09-15T12:00:00Z'))
    if cutoff<'2026-09-15T12:00:00Z': return response(400,{'error':'demo_cutoff_precedes_fixture_receipts'})
    run_id=uuid.uuid4().hex
    try:
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); database=root/'source.db'
            try: s3.download_file(bucket,'state/source.db',str(database))
            except ClientError as error:
                if error.response['Error']['Code'] not in ('404','NoSuchKey'): raise
            source=connect(str(database))
            counts=[]
            try:
                for filename,receipt in [('baseline.jsonl','2026-09-08T12:00:00Z'),('corrections.jsonl','2026-09-15T12:00:00Z')]:
                    counts.append(ingest(source,[json.loads(row) for row in (ROOT/'fixtures'/filename).read_text().splitlines()],received_at=receipt))
            finally: source.close()
            s3.upload_file(str(database),bucket,'state/source.db')
            heartbeats=root/'heartbeats.json'
            heartbeats.write_text(json.dumps({} if event.get('inject_stale') else dict.fromkeys(['watch','phone','manual'],cutoff)))
            report=run_interval(database,heartbeats,root/'published','2026-09-14T00:00:00Z',cutoff,['watch','phone','manual'])
            pointer=json.loads((root/'published/latest.json').read_text())
            summary=json.loads((Path(pointer['run_dir'])/'summary.json').read_text())
            summary['run_id']=run_id
            s3.put_object(Bucket=bucket,Key=f'published/runs/{run_id}.json',Body=json.dumps(summary),ContentType='application/json')
            try: previous=json.loads(s3.get_object(Bucket=bucket,Key='published/latest.json')['Body'].read())
            except ClientError as error:
                if error.response['Error']['Code']!='NoSuchKey': raise
                previous=None
            if previous is None or previous['as_of']<=cutoff:
                s3.put_object(Bucket=bucket,Key='published/latest.json',Body=json.dumps(summary),ContentType='application/json')
            result={'status':'success','run_id':run_id,'as_of':cutoff,'models':report['models'],'tests_passed':report['tests_passed'],'ingestion':counts}
            print(json.dumps({'event':'fitness_run_succeeded',**result}))
            return result
    except Exception as error:
        alert={'event':'fitness_run_failed','run_id':run_id,'error_type':type(error).__name__}
        boto3.client('sqs').send_message(QueueUrl=os.environ['FITNESS_ALERT_QUEUE'],MessageBody=json.dumps(alert))
        print(json.dumps(alert))
        raise
