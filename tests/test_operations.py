import json
from pathlib import Path
import tempfile
import unittest
from fitness.operations import freshness, run_interval, StaleSource


class OperationsTests(unittest.TestCase):
    def test_freshness_uses_empty_export_heartbeat_not_workout_date(self):
        self.assertTrue(freshness({'watch': '2026-09-08T00:00:00Z'}, ['watch'], '2026-09-08T00:00:00Z')['watch']['fresh'])
        for values in ({}, {'watch': '2026-09-01T00:00:00Z'}, {'watch': '2026-09-09T00:00:00Z'}):
            self.assertFalse(freshness(values, ['watch'], '2026-09-08T00:00:00Z')['watch']['fresh'])

    def test_failed_attempt_preserves_publication_and_retry_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); heartbeat = root / 'heartbeat.json'
            heartbeat.write_text('{"watch":"2026-09-08T00:00:00Z"}')
            def good(path, cutoff): return {'models': 3, 'tests_passed': 13}
            def bad(path, cutoff): raise RuntimeError('injected build failure')
            def run(transform=good, start='2026-09-07T00:00:00Z', end='2026-09-08T00:00:00Z'):
                return run_interval(root/'source.db', heartbeat, root/'output', start, end, ['watch'], transform=transform)
            run(); latest = root/'output/latest.json'; before = latest.read_bytes()
            with self.assertRaises(RuntimeError): run(bad)
            self.assertEqual(before, latest.read_bytes())
            self.assertEqual(len(list((root/'output/runs').glob('*/alert.json'))), 1)
            self.assertEqual(run()['status'], 'success')
            before = latest.read_bytes()
            heartbeat.write_text('{"watch":"2026-09-07T00:00:00Z"}')
            run(start='2026-09-06T00:00:00Z', end='2026-09-07T00:00:00Z')
            self.assertEqual(before, latest.read_bytes())
            heartbeat.write_text('{}')
            with self.assertRaises(StaleSource): run()
            self.assertEqual(before, latest.read_bytes())
