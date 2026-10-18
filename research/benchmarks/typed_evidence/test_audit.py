import copy
import unittest

import audit


class ArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = audit.verify()

    def test_complete_archive(self):
        self.assertEqual(audit.audit_samples(self.plan), 11570)

    def changed(self, change):
        plan = copy.deepcopy(self.plan)
        change(plan['archive']['benchmark'])
        with self.assertRaises(ValueError): audit.audit_samples(plan)

    def test_missing_duplicate_and_unknown_samples(self):
        self.changed(lambda b: b['timings'].pop())
        self.changed(lambda b: b['timings'].append(dict(b['timings'][0])))
        self.changed(lambda b: b['timings'][0].update(id='unknown-case'))

    def test_nonfinite_negative_and_boolean_durations(self):
        for value in (float('nan'), float('inf'), -1, True):
            self.changed(lambda b: b['timings'][0].update(ms=value))

    def test_statistics_are_recomputed(self):
        self.changed(lambda b: b['summary']['distinct-claims-exact-32']['v6'].update(mean=1))
        self.changed(lambda b: b['cohorts']['invalid']['prepared'].update(p95=1))
        self.changed(lambda b: b['summary'].pop('distinct-claims-exact-32'))


if __name__ == '__main__': unittest.main()
