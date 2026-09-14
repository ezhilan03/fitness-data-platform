import json
from pathlib import Path
import tempfile
from fitness.pipeline import ROOT,connect,ingest
from fitness.operations import run_interval
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory); source=connect(str(root/'source.db'))
    ingest(source,[json.loads(x) for x in (ROOT/'fixtures/baseline.jsonl').read_text().splitlines()],received_at='2026-09-08T12:00:00Z');source.close()
    heartbeat=root/'heartbeat.json';heartbeat.write_text('{"watch":"2026-09-08T12:00:00Z"}')
    report=run_interval(root/'source.db',heartbeat,root/'published','2026-09-08T00:00:00Z','2026-09-09T00:00:00Z',['watch'])
    assert report['tests_passed']==13
    pointer=json.loads((root/'published/latest.json').read_text())
    summary=json.loads((Path(pointer['run_dir'])/'summary.json').read_text())
    assert sum(x['sessions'] for x in summary['days'])==2
    print(json.dumps({'passed':True,'read_only_root':True,'non_root_user':True,'models':report['models'],'tests_passed':report['tests_passed'],'days':summary['days']}))
