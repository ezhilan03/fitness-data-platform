"""Real AWS smoke, IAM authorization, idempotency, alert transport and restore."""
import json
from pathlib import Path
import time
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.config import Config
ROOT=Path(__file__).resolve().parents[1]
session=boto3.Session(profile_name='portfolio',region_name='us-east-1')
client=session.client('lambda',config=Config(read_timeout=360))
s3=session.client('s3');sqs=session.client('sqs')
name='fitness-data-platform';bucket='fitness-data-platform-'+session.client('sts').get_caller_identity()['Account']
url=client.get_function_url_config(FunctionName=name)['FunctionUrl']
queue=sqs.get_queue_url(QueueName=name+'-alerts')['QueueUrl']
report={'synthetic_only':True,'function_url':url,'auth_type':'AWS_IAM','runs':[]}
def invoke(fail=False):
    r=client.invoke(FunctionName=name,Payload=json.dumps({'operation':'run','inject_stale':fail}).encode())
    data=json.loads(r['Payload'].read())
    if fail:
        assert r.get('FunctionError') and data['errorType']=='StaleSource',data
    else:
        assert not r.get('FunctionError') and data['status']=='success' and data['tests_passed']==13,data
        report['runs'].append(data)
    return data
first=invoke();second=invoke()
assert all(item['inserted']==0 for item in second['ingestion'])
report['replay_no_new_revisions']=True
before=s3.get_object(Bucket=bucket,Key='published/latest.json')['Body'].read()
invoke(True)
assert s3.get_object(Bucket=bucket,Key='published/latest.json')['Body'].read()==before
report['failure_preserved_publication']=True
messages=sqs.receive_message(QueueUrl=queue,WaitTimeSeconds=10,MaxNumberOfMessages=10).get('Messages',[])
matching=[m for m in messages if json.loads(m['Body']).get('error_type')=='StaleSource']
assert matching,'No stale-source alert delivered to SQS'
report['external_alert_transport']='SQS'
report['verified_alerts']=len(matching)
for message in matching: sqs.delete_message(QueueUrl=queue,ReceiptHandle=message['ReceiptHandle'])
version=s3.head_object(Bucket=bucket,Key='state/source.db')['VersionId']
s3.delete_object(Bucket=bucket,Key='state/source.db')
s3.copy_object(Bucket=bucket,Key='state/source.db',CopySource={'Bucket':bucket,'Key':'state/source.db','VersionId':version})
report['versioned_source_restore']=True
invoke()
try:
    urlopen(url+'summary',timeout=30)
    raise AssertionError('Unsigned request unexpectedly authorized')
except HTTPError as error: assert error.code==403,error.code
report['unsigned_http_status']=403
request=AWSRequest(method='GET',url=url+'summary')
SigV4Auth(session.get_credentials().get_frozen_credentials(),'lambda','us-east-1').add_auth(request)
with urlopen(Request(request.url,headers=dict(request.headers)),timeout=60) as response:
    summary=json.load(response);report['signed_http_status']=response.status
assert sum(row['distance_m'] or 0 for row in summary['weeks'])==8000
assert sum(row['sessions'] for row in summary['days'])==3
report['running_distance_m']=8000
report['daily_sessions']=3
from fitness.dashboard import render
(ROOT/'artifacts/dashboard.html').write_text(render(summary))
(ROOT/'artifacts/published-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
report['passed']=True
report['image_uri']=client.get_function(FunctionName=name)['Code']['ResolvedImageUri']
(ROOT/'artifacts/cloud-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
