"""Run a real local Airflow scheduler, induce a retry and request a backfill."""
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
import tempfile

ROOT = Path(__file__).resolve().parents[1]
(ROOT/'artifacts/local').mkdir(parents=True, exist_ok=True)
STATE = Path(tempfile.mkdtemp(prefix='airflow-verification-', dir=ROOT/'artifacts/local'))
(ROOT/'artifacts/local/airflow-verification-path.txt').write_text(str(STATE))
HOME = STATE/'airflow'
AIRFLOW = ROOT/'.venv-airflow/bin/airflow'
STATE.mkdir(parents=True, exist_ok=True)
(STATE/'heartbeats').mkdir(exist_ok=True)
(STATE/'exports').mkdir(exist_ok=True)
if (HOME/'airflow.db').exists():
    raise SystemExit('Use a fresh verification directory; do not overwrite previous scheduler evidence')
env = dict(os.environ, PATH=str(ROOT/'.venv-airflow/bin')+os.pathsep+os.environ['PATH'], AIRFLOW_HOME=str(HOME), AIRFLOW__CORE__LOAD_EXAMPLES='false',
           AIRFLOW__CORE__DAGS_FOLDER=str(ROOT/'dags'), AIRFLOW__CORE__PARALLELISM='1',
           AIRFLOW__API__HOST='127.0.0.1', AIRFLOW__API__PORT='9876',
           AIRFLOW__CORE__EXECUTION_API_SERVER_URL='http://127.0.0.1:9876/execution/',
           AIRFLOW__CLI__ENDPOINT_URL='http://127.0.0.1:9876',
           FITNESS_PROJECT_ROOT=str(ROOT), FITNESS_STATE_ROOT=str(STATE), FITNESS_REQUIRED_SOURCES='watch', FITNESS_SCHEDULE_END='2026-09-13T00:00:00Z',
           AIRFLOW__SCHEDULER__SCHEDULER_HEARTBEAT_SEC='1',
           AIRFLOW__DAG_PROCESSOR__MIN_FILE_PROCESS_INTERVAL='5')
# Only synthetic fixture data; the upstream completed-export timeline is explicit.
subprocess.run([str(ROOT/'.venv/bin/python'), '-c',
    "import json; from fitness.pipeline import connect,ingest,ROOT; "
    "c=connect("+repr(str(STATE/'source.db'))+"); "
    "c.close()"], cwd=ROOT, check=True)
for day in range(8, 15):
    path = STATE/'heartbeats'/f'202609{day:02d}T000000Z.json'
    path.write_text(json.dumps({} if day == 8 else {'watch':f'2026-09-{day:02d}T00:00:00Z'}))
    (STATE/'exports'/path.name).write_text(json.dumps({'completed_at':f'2026-09-{day:02d}T00:00:00Z','sources':[] if day==8 else ['watch','phone'],'records':[json.loads(x) for x in (ROOT/'fixtures/baseline.jsonl').read_text().splitlines()] if day==9 else []}))
log = (STATE/'standalone.log').open('w')
process = subprocess.Popen([str(AIRFLOW), 'standalone'], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
report = {'synthetic_only':True, 'airflow_version':'3.1.8', 'scheduler_executed':True}
def query(sql):
    if not (HOME/'airflow.db').exists(): return []
    with sqlite3.connect(HOME/'airflow.db') as db:
        db.row_factory=sqlite3.Row
        try: return [dict(row) for row in db.execute(sql)]
        except sqlite3.OperationalError: return []
def wait_for(predicate, seconds=240):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        if process.poll() is not None: raise RuntimeError('Airflow exited; inspect standalone.log')
        result=predicate()
        if result: return result
        time.sleep(2)
    raise TimeoutError('Airflow verification timed out; inspect local logs')
def cli(*args):
    result=subprocess.run([str(AIRFLOW), *args],cwd=ROOT,env=env,capture_output=True,text=True)
    (STATE/('cli-'+args[0]+'-'+args[1]+'.log')).write_text(result.stdout+result.stderr)
    if result.returncode: raise RuntimeError('Airflow CLI failed: '+' '.join(args[:2]))
try:
    wait_for(lambda: query("select dag_id from dag where dag_id='fitness_daily'"))
    cli('dags','unpause','fitness_daily')
    retry=wait_for(lambda: query("select run_id,task_id,state,try_number from task_instance where dag_id='fitness_daily' and state='up_for_retry'"))
    report['observed_retry']=retry
    failures=[json.loads(p.read_text()) for p in (STATE/'published/runs').glob('*/alert.json')]
    assert any(item.get('error_type')=='StaleSource' for item in failures), 'Retry must be caused by injected stale source'
    report['retry_cause']='StaleSource'
    (STATE/'heartbeats/20260908T000000Z.json').write_text('{"watch":"2026-09-08T00:00:00Z"}')
    scheduled=wait_for(lambda: (rows if len(rows)==7 and all(r['state']=='success' for r in rows) else None)
        if (rows:=query("select run_id,state,data_interval_start,data_interval_end from dag_run where dag_id='fitness_daily' and run_type='scheduled'")) else None, seconds=420)
    report['scheduled_intervals']=scheduled
    ingested=query("select run_id from task_instance where dag_id='fitness_daily' and task_id='ingest_interval' and state='success'")
    assert len(ingested)==7
    report['scheduled_ingestion_tasks']=len(ingested)
    report['recovered_task']=query("select run_id,state,try_number from task_instance where dag_id='fitness_daily' and try_number>1")
    before=json.loads((STATE/'published/latest.json').read_text())
    cli('backfill','create','--dag-id','fitness_daily','--from-date','2026-09-08','--to-date','2026-09-09','--reprocess-behavior','completed','--max-active-runs','1')
    report['backfill_intervals']=wait_for(lambda: (rows if len(rows)==2 and all(r['state']=='success' for r in rows) else None)
        if (rows:=query("select run_id,state,data_interval_start,data_interval_end from dag_run where dag_id='fitness_daily' and run_type='backfill'")) else None,seconds=240)
    assert json.loads((STATE/'published/latest.json').read_text()) == before
    report['backfill_preserved_latest']=True
    successes=[json.loads(p.read_text()) for p in (STATE/'published/runs').glob('*/status.json') if json.loads(p.read_text())['status']=='success']
    assert len(successes)==9 and all(item['models']==3 and item['tests_passed']==13 for item in successes)
    report['verified_dbt_builds']=len(successes)
    report['dbt_tests_per_build']=13
    report['local_alerts']=len(list((STATE/'published/runs').glob('*/alert.json')))
    report['passed']=True
    (ROOT/'artifacts/airflow-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
finally:
    os.killpg(process.pid, signal.SIGTERM)
    try: process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL); process.wait()
    log.close()
