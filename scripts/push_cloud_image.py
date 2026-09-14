import base64
import json
from pathlib import Path
import subprocess
import boto3
root=Path(__file__).resolve().parents[1]
session=boto3.Session(profile_name='portfolio',region_name='us-east-1')
ecr=session.client('ecr');auth=ecr.get_authorization_token()['authorizationData'][0]
user,password=base64.b64decode(auth['authorizationToken']).decode().split(':',1)
subprocess.run(['docker','login','--username',user,'--password-stdin',auth['proxyEndpoint']],input=password,text=True,check=True,capture_output=True)
repository=ecr.describe_repositories(repositoryNames=['fitness-data-platform'])['repositories'][0]['repositoryUri']
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
image=repository+':'+commit
subprocess.run(['docker','tag','fitness-data:cloud',image],check=True)
subprocess.run(['docker','push',image],check=True)
digest=ecr.describe_images(repositoryName='fitness-data-platform',imageIds=[{'imageTag':commit}])['imageDetails'][0]['imageDigest']
(root/'infra/aws/deployment.auto.tfvars').write_text('image_uri = '+json.dumps(repository+'@'+digest)+'\n')
print(json.dumps({'image_uri':repository+'@'+digest,'commit':commit}))
