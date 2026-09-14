"""Real adapter regression: SQLite full refresh is an independent result oracle."""
from copy import deepcopy
import json
from importlib.metadata import version
from pathlib import Path
import tempfile
from fitness.pipeline import ROOT, connect, ingest, refresh, erase_user
from fitness.dbt_runner import export_revisions, build


def main():
    output=ROOT/'artifacts/local/dbt';output.mkdir(parents=True,exist_ok=True)
    base=[json.loads(line) for line in (ROOT/'fixtures/baseline.jsonl').read_text().splitlines()]
    corrections=[json.loads(line) for line in (ROOT/'fixtures/corrections.jsonl').read_text().splitlines()]
    report={'synthetic_only':True,'scenarios':[]}
    with tempfile.TemporaryDirectory() as directory:
        source=connect(':memory:');target=Path(directory)/'fitness.duckdb'
        def verify(label,cutoff,full=False,docs=False):
            exported=export_revisions(source,target)
            result=build(target,cutoff,output/label,full_refresh=full,docs=docs)
            expected=refresh(source,cutoff)['weeks']
            assert result['weeks']==expected,(label,result['weeks'],expected)
            assert sum(row['sessions'] for row in result['days'])==sum(row['sessions'] for row in expected)
            assert sum(row['duration_seconds'] for row in result['days'])==sum(row['duration_seconds'] for row in expected)
            report['scenarios'].append({'name':label,'source_revisions':exported,'tests_passed':result['tests_passed'],
                                        'models':result['models'],'matches_sqlite_full_refresh':True,'groups':len(expected)})
        early='2026-09-08T12:00:00Z';late='2026-09-15T12:00:00Z'
        ingest(source,base,received_at=early);verify('initial',early,full=True)
        ingest(source,base,received_at=late);verify('replay',early)
        ingest(source,corrections,received_at=late);verify('correction_and_late_arrival',late)
        verify('historical_cutoff',early)
        verify('return_to_current',late)
        moved=deepcopy(base[0]);moved.update(revision=3,started_at='2026-09-14T07:00:00-05:00',ended_at='2026-09-14T07:30:00-05:00',available_at='2026-09-14T13:00:00Z')
        ingest(source,[moved],received_at=late);verify('moved_week',late)
        # Move the remaining old-week run too: the obsolete group must disappear.
        moved_late=deepcopy(corrections[1]);moved_late.update(revision=2,started_at='2026-09-14T09:00:00-05:00',ended_at='2026-09-14T09:20:00-05:00',available_at='2026-09-14T15:00:00Z')
        ingest(source,[moved_late],received_at=late);verify('obsolete_week_removed',late)
        erase_user(source,'synthetic-alex');verify('erasure',late,docs=True)
        source.close()
    report['passed']=True
    report['versions']={name.replace('-', '_'):version(name) for name in ('dbt-core','dbt-duckdb','duckdb')}
    target_dir=output/'erasure/target'
    manifest=json.loads((target_dir/'manifest.json').read_text())
    catalog=json.loads((target_dir/'catalog.json').read_text())
    report['documentation']={'generated':(target_dir/'index.html').is_file(),
        'catalog_models':len(catalog['nodes']),'catalog_sources':len(catalog['sources']),
        'lineage':{key:node['depends_on']['nodes'] for key,node in manifest['nodes'].items() if node['resource_type']=='model'}}
    assert report['documentation']['generated'] and report['documentation']['catalog_models']==3
    (ROOT/'artifacts/dbt-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
