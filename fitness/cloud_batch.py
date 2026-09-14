"""Fargate entrypoint: the same verified batch engine on a full container runtime."""
import json
import os
import signal
from fitness.aws_app import handler
if __name__=='__main__':
    def deadline(signum, frame): raise TimeoutError('Batch exceeded eight-minute execution deadline')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(480)
    result=handler(json.loads(os.environ.get('FITNESS_BATCH_EVENT','{"operation":"run"}')),None)
    print(json.dumps(result))
    if result.get('status')!='success': raise SystemExit(1)
