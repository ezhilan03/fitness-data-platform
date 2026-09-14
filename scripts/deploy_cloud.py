"""Deploy immutable images and verify an on-demand Fargate task after hosted CI."""
import argparse
import json
import os
from pathlib import Path
import boto3
p=argparse.ArgumentParser();p.add_argument('--image',required=True);args=p.parse_args()
session=boto3.Session(region_name='us-east-1');ecs=session.client('ecs');lam=session.client('lambda')
name='fitness-data-platform'
current=ecs.describe_task_definition(taskDefinition=name)['taskDefinition']
allowed={'family','taskRoleArn','executionRoleArn','networkMode','containerDefinitions','volumes','placementConstraints','requiresCompatibilities','cpu','memory','runtimePlatform','ephemeralStorage'}
new={key:value for key,value in current.items() if key in allowed}
new['containerDefinitions'][0]['image']=args.image
registered=ecs.register_task_definition(**new)['taskDefinition']['taskDefinitionArn']
lam.update_function_code(FunctionName=name,ImageUri=args.image)
lam.get_waiter('function_updated_v2').wait(FunctionName=name)
result=ecs.run_task(cluster=name,taskDefinition=registered,launchType='FARGATE',networkConfiguration={'awsvpcConfiguration':{'subnets':[os.environ['BATCH_SUBNET']],'securityGroups':[os.environ['BATCH_SECURITY_GROUP']],'assignPublicIp':'ENABLED'}})
assert not result.get('failures'),result.get('failures')
arn=result['tasks'][0]['taskArn']
try: ecs.get_waiter('tasks_stopped').wait(cluster=name,tasks=[arn],WaiterConfig={'Delay':5,'MaxAttempts':120})
except Exception:
    # StopTask is intentionally scoped to this project's tasks in the deployment role.
    ecs.stop_task(cluster=name,task=arn,reason='Deployment smoke timeout');raise
stopped=ecs.describe_tasks(cluster=name,tasks=[arn])['tasks'][0]
assert stopped['containers'][0].get('exitCode')==0,stopped
bucket=os.environ['FITNESS_BUCKET']
summary=json.loads(session.client('s3').get_object(Bucket=bucket,Key='published/latest.json')['Body'].read())
assert summary['build']['tests_passed']==13,summary['build']
Path('deployment-report.json').write_text(json.dumps({'passed':True,'image':args.image,'task_definition':registered,'task_arn':arn,'build':summary['build']},indent=2)+'\n')
