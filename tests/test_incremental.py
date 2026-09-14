import unittest
from test_pipeline import event, EARLY, LATE
from fitness.pipeline import connect, ingest, refresh, refresh_incremental, erase_user, ContractError

class IncrementalTests(unittest.TestCase):
    def setUp(self):
        self.db=connect(':memory:');self.oracle=connect(':memory:')
    def tearDown(self):
        self.db.close();self.oracle.close()
    def load(self,rows,at=EARLY):
        for db in [self.db,self.oracle]:ingest(db,rows,received_at=at)
    def compare(self,at=LATE):
        actual=refresh_incremental(self.db,at)
        self.assertEqual(actual['weeks'],refresh(self.oracle,at)['weeks'])
        return actual
    def test_initial_replay_and_unchanged_partition(self):
        self.load([event(),event(user_id='other')])
        self.assertEqual(self.compare(EARLY)['partitions_rebuilt'],2)
        self.assertEqual(self.compare()['partitions_rebuilt'],0)
        self.load([event(revision=2,distance=6)],LATE)
        self.assertEqual(self.compare()['partitions_rebuilt'],1)
    def test_moved_week_rebuilds_both_old_and_new(self):
        self.load([event()]);self.compare(EARLY)
        self.load([event(revision=2,started_at='2026-09-14T07:00:00-05:00',ended_at='2026-09-14T07:30:00-05:00',available_at='2026-09-14T13:00:00Z')],LATE)
        result=self.compare();self.assertEqual(result['partitions_rebuilt'],2)
        self.assertEqual([r['week_start'] for r in result['weeks']],['2026-09-14'])
    def test_late_source_priority_and_erasure(self):
        self.load([event(source='phone')]);self.compare(EARLY)
        self.load([event(distance=6)],LATE);self.compare()
        for db in [self.db,self.oracle]:erase_user(db,'synthetic-alex')
        self.assertEqual(self.compare()['weeks'],[])
        self.assertEqual(self.db.execute('SELECT count(*) FROM session_snapshot').fetchone()[0],0)
    def test_backward_cutoff_requires_full_refresh(self):
        self.load([event()]);self.compare()
        with self.assertRaises(ContractError):refresh_incremental(self.db,EARLY)
        refresh(self.db,EARLY)
        self.compare(EARLY)
    def test_write_failure_preserves_snapshot_and_checkpoint(self):
        self.load([event()]);self.compare(EARLY)
        self.load([event(revision=2,distance=6)],LATE)
        self.db.execute("CREATE TRIGGER fail_incremental BEFORE INSERT ON weekly_summaries BEGIN SELECT RAISE(ABORT,'injected failure'); END")
        with self.assertRaises(Exception):refresh_incremental(self.db,LATE)
        self.assertEqual(self.db.execute('SELECT as_of FROM incremental_state').fetchone()[0],EARLY)
        self.assertEqual(self.db.execute('SELECT distance_m FROM session_snapshot').fetchone()[0],5000)
        self.db.execute('DROP TRIGGER fail_incremental')
        self.compare()
