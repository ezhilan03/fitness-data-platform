"""Validated complete-export envelopes, including explicit empty-source heartbeats."""
import json
from pathlib import Path
from fitness.pipeline import connect, ingest, utc, SOURCES, validate


def ingest_export(database, envelope_file, heartbeat_file, cutoff):
    data=json.loads(Path(envelope_file).read_text())
    if set(data)!={'completed_at','sources','records'}:
        raise ValueError('Export envelope fields do not match contract')
    completed=utc(data['completed_at']); cutoff=utc(cutoff)
    sources=data['sources']; records=data['records']
    if completed>cutoff or not isinstance(sources,list) or len(set(sources))!=len(sources) or not set(sources)<=SOURCES:
        raise ValueError('Invalid export completion or source list')
    if not isinstance(records,list) or any(row.get('source') not in sources for row in records):
        raise ValueError('Export record source is not declared')
    for row in records: validate(row)
    source=connect(str(database))
    try:
        result=ingest(source,records,received_at=completed)
    finally: source.close()
    destination=Path(heartbeat_file); destination.parent.mkdir(parents=True,exist_ok=True)
    temp=destination.with_suffix('.tmp')
    temp.write_text(json.dumps(dict.fromkeys(sources,completed))+'\n')
    temp.replace(destination)
    return result


def main():
    import argparse
    p=argparse.ArgumentParser()
    for name in ('database','envelope','heartbeats','cutoff'): p.add_argument('--'+name,required=True)
    a=p.parse_args(); print(json.dumps(ingest_export(a.database,a.envelope,a.heartbeats,a.cutoff)))

if __name__=='__main__': main()
