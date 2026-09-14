"""Run real dbt against a transactionally copied ingestion snapshot."""
import json
import os
from pathlib import Path
import subprocess
import sys
import duckdb
from fitness.pipeline import ROOT, utc


def export_revisions(sqlite_conn, destination):
    # Read schema and records in one source transaction; no SQLite extension download.
    sqlite_conn.execute('BEGIN')
    try:
        columns=sqlite_conn.execute('PRAGMA table_info(revisions)').fetchall()
        rows=sqlite_conn.execute('SELECT * FROM revisions').fetchall()
        sqlite_conn.execute('COMMIT')
    except BaseException:
        sqlite_conn.execute('ROLLBACK');raise
    types={'TEXT':'VARCHAR','INTEGER':'BIGINT','REAL':'DOUBLE'}
    definition=','.join('"'+col[1]+'" '+types[col[2]] for col in columns)
    with duckdb.connect(str(destination)) as db:
        db.execute('BEGIN')
        db.execute('CREATE SCHEMA IF NOT EXISTS raw')
        db.execute('CREATE OR REPLACE TABLE raw.revisions ('+definition+')')
        if rows:
            db.executemany('INSERT INTO raw.revisions VALUES ('+','.join('?' for _ in columns)+')',[tuple(row) for row in rows])
        db.execute('COMMIT')
    return len(rows)


def build(destination, as_of, output, *, full_refresh=False, docs=False):
    cutoff=utc(as_of)
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,FITNESS_DUCKDB_PATH=str(Path(destination).resolve()),
             DBT_SEND_ANONYMOUS_USAGE_STATS='false',DBT_TARGET_PATH=str(output/'target'),DBT_LOG_PATH=str(output/'logs'))
    executable=Path(sys.executable).with_name('dbt')
    command=[str(executable),'build','--project-dir',str(ROOT/'dbt'),'--profiles-dir',str(ROOT/'dbt'),
             '--vars',json.dumps({'as_of':cutoff})]
    if full_refresh:command.append('--full-refresh')
    result=subprocess.run(command,env=env,text=True,capture_output=True,timeout=240)
    (output/'build.log').write_text(result.stdout+result.stderr)
    if result.returncode:
        print(json.dumps({'event':'dbt_build_failed','output':(result.stdout+result.stderr)[-10000:]}))
        raise RuntimeError('dbt build failed; see '+str(output/'build.log'))
    results=json.loads((output/'target/run_results.json').read_text())
    statuses=[r['status'] for r in results['results']]
    if not all(s in {'success','pass'} for s in statuses):raise RuntimeError('dbt checks did not all pass')
    if docs:
        command[1:2]=['docs','generate']
        command=[c for c in command if c!='--full-refresh']
        doc_result=subprocess.run(command,env=env,text=True,capture_output=True,timeout=240)
        (output/'docs.log').write_text(doc_result.stdout+doc_result.stderr)
        if doc_result.returncode:raise RuntimeError('dbt documentation generation failed')
    with duckdb.connect(str(destination),read_only=True) as db:
        cursor=db.execute('SELECT * FROM analytics.weekly_summaries ORDER BY user_id,week_start,activity')
        names=[c[0] for c in cursor.description]
        rows=[dict(zip(names,row),as_of=cutoff) for row in cursor.fetchall()]
        daily_cursor=db.execute('SELECT user_id,local_date,activity,count(*) AS sessions,sum(duration_seconds) AS duration_seconds,sum(distance_m) AS distance_m,count(distance_m) AS distance_observed_sessions FROM analytics.current_sessions GROUP BY user_id,local_date,activity ORDER BY user_id,local_date,activity')
        daily_names=[c[0] for c in daily_cursor.description]
        daily=[dict(zip(daily_names,row)) for row in daily_cursor.fetchall()]
    return {'days':daily,'cutoff':cutoff,'models':sum(s=='success' for s in statuses),
            'tests_passed':sum(s=='pass' for s in statuses),'weeks':rows}
