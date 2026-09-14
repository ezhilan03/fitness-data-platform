"""Actual dbt interval run followed by stale-source failure and recovery."""
import json
from pathlib import Path
import tempfile
from fitness.pipeline import ROOT, connect, ingest
from fitness.operations import run_interval, StaleSource


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory); database = root/'source.db'; heartbeat = root/'heartbeat.json'
        source = connect(str(database))
        ingest(source, [json.loads(row) for row in (ROOT/'fixtures/baseline.jsonl').read_text().splitlines()], received_at='2026-09-08T12:00:00Z')
        source.close()
        healthy = '{"watch":"2026-09-08T12:00:00Z"}'
        heartbeat.write_text(healthy)
        def run():
            return run_interval(database, heartbeat, root/'published', '2026-09-08T00:00:00Z', '2026-09-09T00:00:00Z', ['watch'])
        initial = run(); pointer = root/'published/latest.json'; before = pointer.read_bytes()
        heartbeat.write_text('{}')
        try:
            run()
            raise AssertionError('Stale source was accepted')
        except StaleSource:
            pass
        assert pointer.read_bytes() == before
        alerts = list((root/'published/runs').glob('*/alert.json'))
        assert len(alerts) == 1
        heartbeat.write_text(healthy)
        recovery = run()
        report = {'passed': True, 'synthetic_only': True, 'actual_dbt_runs': 2,
                  'initial': initial, 'recovery': recovery, 'stale_failure_preserved_latest': True,
                  'local_alert_files': len(alerts), 'airflow_executed': False,
                  'note': 'Direct Python interval runs; no scheduler retry or backfill execution claimed.'}
    (ROOT/'artifacts/operations-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
