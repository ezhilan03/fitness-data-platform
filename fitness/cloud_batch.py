"""Fargate entrypoint: the same verified batch engine on a full container runtime."""
import json
import os
from fitness.aws_app import handler
if __name__=='__main__':
    result=handler(json.loads(os.environ.get('FITNESS_BATCH_EVENT','{"operation":"run"}')),None)
    print(json.dumps(result))
    if result.get('status')!='success': raise SystemExit(1)
