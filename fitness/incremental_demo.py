"""Compare incremental marts with the independently rebuilt full-refresh oracle."""
import json
from pathlib import Path
from fitness.pipeline import connect, ingest, refresh, refresh_incremental


def main():
    root=Path(__file__).resolve().parents[1]
    inc,oracle=connect(':memory:'),connect(':memory:')
    steps=[]
    try:
        for filename,cutoff in [('baseline','2026-09-08T12:00:00Z'),('corrections','2026-09-15T12:00:00Z')]:
            rows=[json.loads(line) for line in (root/f'fixtures/{filename}.jsonl').read_text().splitlines()]
            for db in [inc,oracle]:ingest(db,rows,received_at=cutoff)
            actual=refresh_incremental(inc,cutoff)
            assert actual['weeks']==refresh(oracle,cutoff)['weeks']
            steps.append({'step':filename,'partitions_rebuilt':actual['partitions_rebuilt'],'matches_full_refresh':True})
        replay=refresh_incremental(inc,cutoff)
        assert replay['partitions_rebuilt']==0
        steps.append({'step':'unchanged replay','partitions_rebuilt':0,'matches_full_refresh':replay['weeks']==refresh(oracle,cutoff)['weeks']})
        assert all(step['matches_full_refresh'] for step in steps)
        print(json.dumps({'synthetic_only':True,'steps':steps,'passed':True},indent=2))
    finally:
        inc.close();oracle.close()


if __name__=='__main__':main()
