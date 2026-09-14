"""Scheduler-independent interval job with source-heartbeat freshness gates."""
from datetime import datetime
import json
from pathlib import Path
import uuid
from fitness.pipeline import connect, utc


class StaleSource(ValueError):
    pass


def freshness(heartbeats, required_sources, cutoff, max_age_seconds=86400):
    """Heartbeat is successful export completion, including an empty export."""
    end = datetime.fromisoformat(utc(cutoff))
    if max_age_seconds < 0 or not required_sources:
        raise ValueError('Positive freshness window and required sources are needed')
    statuses = {}
    for source in required_sources:
        value = heartbeats.get(source)
        age = None if value is None else (end - datetime.fromisoformat(utc(value))).total_seconds()
        statuses[source] = {'age_seconds': age, 'fresh': age is not None and 0 <= age <= max_age_seconds}
    return statuses


def run_interval(database, heartbeat_file, output, start, end, required_sources, *, max_age_seconds=86400, transform=None):
    """Publish a pointer only after a fresh source snapshot and successful dbt build.

    Historical invocations leave the latest pointer unchanged. Single writer only.
    Heartbeats are supplied by the upstream export process; ingestion is separate.
    """
    start, end = utc(start), utc(end)
    if start >= end:
        raise ValueError('Interval must have positive duration')
    output = Path(output)
    run_dir = output / 'runs' / uuid.uuid4().hex
    run_dir.mkdir(parents=True)
    checks = freshness(json.loads(Path(heartbeat_file).read_text()), required_sources, end, max_age_seconds)
    report = {'interval_start': start, 'interval_end': end, 'freshness': checks, 'status': 'running'}
    report_file = run_dir / 'status.json'
    try:
        if not all(item['fresh'] for item in checks.values()):
            raise StaleSource('Source export heartbeat is missing, future-dated or stale')
        if transform is None:
            from fitness.dbt_runner import export_revisions, build
            source = connect(str(database))
            try:
                export_revisions(source, run_dir / 'fitness.duckdb')
            finally:
                source.close()
            result = build(run_dir / 'fitness.duckdb', end, run_dir / 'dbt', full_refresh=True)
        else:
            result = transform(run_dir, end)
        (run_dir/'summary.json').write_text(json.dumps({'synthetic_only':True,'as_of':end,'weeks':result.get('weeks',[]),'days':result.get('days',[]),'freshness':checks},indent=2)+'\n')
        report.update(status='success', models=result['models'], tests_passed=result['tests_passed'])
        report_file.write_text(json.dumps(report, indent=2) + '\n')
        latest = output / 'latest.json'
        previous = json.loads(latest.read_text()) if latest.exists() else None
        if previous is None or previous['interval_end'] <= end:
            pointer = {'interval_end': end, 'run_dir': str(run_dir.resolve())}
            temp = run_dir / 'pointer.json'
            temp.write_text(json.dumps(pointer) + '\n')
            temp.replace(latest)
    except Exception as error:
        report.update(status='failed', error_type=type(error).__name__)
        report_file.write_text(json.dumps(report, indent=2) + '\n')
        # Local structured alert evidence only; no external notification delivery.
        (run_dir / 'alert.json').write_text(json.dumps({'event': 'fitness_interval_failed', **report}) + '\n')
        raise
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser()
    for name in ('database', 'heartbeats', 'output', 'start', 'end'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--source', action='append', required=True)
    args = parser.parse_args()
    print(json.dumps(run_interval(args.database, args.heartbeats, args.output, args.start, args.end, args.source)))


if __name__ == '__main__':
    main()
