import unittest
from fitness.pipeline import connect, ingest, refresh, erase_user, validate, ContractError

EARLY='2026-09-08T12:00:00Z'
LATE='2026-09-15T12:00:00Z'


def event(**changes):
    result=dict(user_id='synthetic-alex',source='watch',event_id='watch-1',revision=1,
                session_id='workout-1',activity='run',started_at='2026-09-07T07:00:00-05:00',
                ended_at='2026-09-07T07:30:00-05:00',timezone='America/Chicago',
                available_at='2026-09-07T13:00:00Z',distance=5,distance_unit='km')
    result.update(changes)
    return result


class PipelineTests(unittest.TestCase):
    def setUp(self):self.db=connect(':memory:')
    def tearDown(self):self.db.close()
    def load(self, rows, at=EARLY):return ingest(self.db,rows,received_at=at)
    def summary(self, at=LATE):return refresh(self.db,at)

    def test_same_export_is_noop(self):
        self.assertEqual(self.load([event()]),{'inserted':1,'replayed':0})
        self.assertEqual(self.load([event()],LATE),{'inserted':0,'replayed':1})
        row=self.summary()['weeks'][0]
        self.assertEqual((row['sessions'],row['distance_m']),(1,5000))
        self.assertEqual(self.db.execute('SELECT received_at FROM revisions').fetchone()[0],EARLY)

    def test_correction_replaces_current_but_preserves_history(self):
        self.load([event()]);self.load([event(revision=2,distance=6)],LATE)
        self.assertEqual(self.summary()['weeks'][0]['distance_m'],6000)
        self.assertEqual(self.summary(EARLY)['weeks'][0]['distance_m'],5000)
        self.assertEqual(self.db.execute('SELECT count(*) FROM revisions').fetchone()[0],2)

    def test_late_arrival_updates_event_week_not_receipt_week(self):
        self.load([event()],LATE)
        self.assertEqual(self.summary(EARLY)['weeks'],[])
        self.assertEqual(self.summary()['weeks'][0]['week_start'],'2026-09-07')

    def test_older_revision_arriving_last_does_not_downgrade(self):
        self.load([event(revision=2,distance=6)])
        self.load([event()],LATE)
        self.assertEqual(self.summary()['weeks'][0]['distance_m'],6000)

    def test_correction_moving_week_removes_old_week(self):
        self.load([event()])
        self.load([event(revision=2,started_at='2026-09-14T07:00:00-05:00',ended_at='2026-09-14T07:30:00-05:00',available_at='2026-09-14T13:00:00Z')],LATE)
        self.assertEqual([w['week_start'] for w in self.summary()['weeks']],['2026-09-14'])

    def test_source_priority_collapses_only_explicit_shared_identity(self):
        self.load([event(source='phone',event_id='phone-1',distance=5.5),event()])
        row=self.summary()['weeks'][0]
        self.assertEqual((row['sessions'],row['distance_m']),(1,5000))

    def test_distinct_overlapping_workouts_are_flagged_not_dropped(self):
        self.load([event(),event(event_id='watch-2',session_id='workout-2')])
        result=self.summary()
        self.assertEqual(result['overlapping_session_pairs'],1)
        self.assertEqual(result['weeks'][0]['sessions'],2)

    def test_missing_distance_and_days_do_not_become_zero(self):
        self.load([event(activity='strength',distance=None,distance_unit=None)])
        row=self.summary()['weeks'][0]
        self.assertIsNone(row['distance_m'])
        self.assertEqual((row['distance_observed_sessions'],row['observed_days']),(0,1))

    def test_miles_are_normalized(self):
        self.load([event(distance=1,distance_unit='mi')])
        self.assertAlmostEqual(self.summary()['weeks'][0]['distance_m'],1609.344)

    def test_dst_spring_forward_uses_elapsed_utc_time(self):
        row=validate(event(started_at='2026-03-08T01:30:00-06:00',ended_at='2026-03-08T03:30:00-05:00',available_at='2026-03-08T09:00:00Z'))
        self.assertEqual(row['duration_seconds'],3600)

    def test_dst_fall_back_uses_elapsed_utc_time(self):
        row=validate(event(started_at='2026-11-01T01:30:00-05:00',ended_at='2026-11-01T01:30:00-06:00',available_at='2026-11-01T08:00:00Z'))
        self.assertEqual(row['duration_seconds'],3600)

    def test_local_week_is_not_utc_week(self):
        row=validate(event(started_at='2026-09-06T23:00:00-05:00',ended_at='2026-09-06T23:30:00-05:00'))
        self.assertEqual(row['week_start'],'2026-08-31')

    def test_bad_contract_rejects_entire_batch(self):
        cases=[{'distance':-1},{'distance':float('nan')},{'distance':True},
               {'started_at':'2026-09-07T07:00:00'}, {'revision':True},
               {'timezone':'Europe/London'}, {'distance':None}, {'extra':'unexpected'},
               {'source':[]}, {'distance_unit':[]}, {'revision':2**64}]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ContractError):
                self.load([event(),event(event_id='bad',session_id='bad',**change)])
        self.assertEqual(self.db.execute('SELECT count(*) FROM revisions').fetchone()[0],0)

    def test_conflicting_revision_rolls_back_prior_insert(self):
        self.load([event()])
        with self.assertRaises(ContractError):
            self.load([event(event_id='new',session_id='new'),event(distance=8)])
        self.assertEqual(self.db.execute('SELECT count(*) FROM revisions').fetchone()[0],1)

    def test_event_cannot_switch_session_identity(self):
        self.load([event()])
        with self.assertRaises(ContractError):self.load([event(revision=2,session_id='other')])

    def test_same_source_cannot_claim_identity_twice(self):
        self.load([event()])
        with self.assertRaises(ContractError):self.load([event(event_id='duplicate-id')])

    def test_future_availability_rejected(self):
        with self.assertRaises(ContractError):self.load([event(available_at=LATE)])

    def test_failed_refresh_preserves_previous_mart_and_recovery_succeeds(self):
        self.load([event()]);before=self.summary()
        self.load([event(revision=2,distance=6)],LATE)
        self.db.execute("CREATE TRIGGER fail_summary BEFORE INSERT ON weekly_summaries BEGIN SELECT RAISE(ABORT,'injected failure'); END")
        with self.assertRaises(Exception):self.summary()
        self.assertEqual(self.db.execute('SELECT distance_m FROM weekly_summaries').fetchone()[0],5000)
        self.db.execute('DROP TRIGGER fail_summary')
        self.assertEqual(self.summary()['weeks'][0]['distance_m'],6000)

    def test_erasure_removes_history_and_mart_and_blocks_replay(self):
        self.load([event(),event(revision=2,distance=6),event(user_id='synthetic-sam')])
        self.summary();self.assertEqual(erase_user(self.db,'synthetic-alex')['removed_revisions'],2)
        self.assertEqual([r['user_id'] for r in self.summary()['weeks']],['synthetic-sam'])
        with self.assertRaises(ContractError):self.load([event()])
        self.assertEqual(self.db.execute('SELECT count(*) FROM revisions').fetchone()[0],1)


if __name__=='__main__':unittest.main()
