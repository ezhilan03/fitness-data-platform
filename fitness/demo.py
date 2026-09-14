"""Reproducible synthetic timeline; uses a temporary database, never user data."""
import json
from pathlib import Path
import tempfile
from fitness.pipeline import connect, ingest, refresh, erase_user, ContractError


def main():
    root=Path(__file__).resolve().parents[1]
    base=[json.loads(line) for line in (root/'fixtures/baseline.jsonl').read_text().splitlines()]
    changes=[json.loads(line) for line in (root/'fixtures/corrections.jsonl').read_text().splitlines()]
    with tempfile.TemporaryDirectory() as directory:
        db=connect(Path(directory)/'demo.db')
        first=ingest(db,base,received_at='2026-09-08T12:00:00Z')
        initial=refresh(db,'2026-09-08T12:00:00Z')
        replay=ingest(db,base,received_at='2026-09-09T12:00:00Z')
        ingest(db,changes,received_at='2026-09-15T12:00:00Z')
        historical=refresh(db,'2026-09-08T12:00:00Z')
        corrected=refresh(db,'2026-09-15T12:00:00Z')
        assert historical==initial
        assert replay['inserted']==0
        before=initial['weeks'][0];after=corrected['weeks'][0]
        assert (before['sessions'],before['distance_m'])==(1,5000)
        assert (after['sessions'],after['distance_m'])==(2,8000)
        deletion=erase_user(db,'synthetic-alex')
        assert refresh(db,'2026-09-15T12:00:00Z')['weeks']==[]
        try:ingest(db,base,received_at='2026-09-15T12:00:00Z')
        except ContractError:replay_blocked=True
        else:raise AssertionError('Erased records were reintroduced')
        db.close()
    report={'synthetic_only':True,'first_ingestion':first,'replay':replay,
            'historical_summary_unchanged':historical==initial,'initial':initial,
            'after_correction_and_late_arrival':corrected,'erasure':deletion,
            'erased_replay_blocked':replay_blocked,'passed':True}
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
