import itertools
import random
import unittest
from dataclasses import FrozenInstanceError
from fractions import Fraction as Q
from unittest.mock import patch

import constraint_kernel_prepared as candidate
import constraint_kernel_v6 as reference
import audit as study
from constraint_kernel_oracles import document, variable, atom


class PreparedTests(unittest.TestCase):
    def test_immutable_branch_isolation_and_all_exclusions(self):
        atoms = [('a', '<=', 'x', Q(0)), ('x', '<=', 'y', Q(0)),
                 ('y', '<=', 'b', Q(0)), ('x', '!=', 'y', Q(0))]
        state = candidate._prepare(atoms, ('a', 'x', 'y', 'b'))
        before = state.matrix
        self.assertFalse(state.feasible([('b', '<=', 'a', Q(0))]))
        self.assertTrue(state.feasible([('a', '<', 'b', Q(0))]))
        self.assertEqual(state.matrix, before)
        with self.assertRaises(TypeError): state.matrix[0][0] = None
        with self.assertRaises(TypeError): state.index['a'] = 0
        with self.assertRaises(FrozenInstanceError): state.names = ()
        state = candidate._prepare([('a', '!=', 'b', Q(0))], ('a', 'b'))
        for _ in range(2):
            self.assertTrue(state.feasible([('a', '<=', 'b', Q(0))]))
            self.assertTrue(state.feasible([('b', '<=', 'a', Q(0))]))
            self.assertFalse(state.feasible([('a', '<=', 'b', Q(0)), ('b', '<=', 'a', Q(0))]))
            self.assertFalse(state.feasible([('a', '=', 'b', Q(0))]))
            self.assertTrue(state.feasible([('b', '<', 'a', Q(0))]))

    def test_new_exclusions_strictness_and_exact_precision(self):
        state = candidate._prepare([('a', '=', 'b', Q(1, 3))], ('a', 'b'))
        self.assertFalse(state.feasible([('a', '!=', 'b', Q(1, 3))]))
        self.assertFalse(state.feasible([('a', '<', 'b', Q(1, 3))]))
        self.assertTrue(state.feasible([('a', '<=', 'b', Q(1, 3))]))
        n = 10**18
        state = candidate._prepare([('a', '=', None, Q(n, n-1))], ('a',))
        self.assertFalse(state.feasible([('a', '<=', None, Q(1))]))
        self.assertTrue(state.feasible([('a', '>', None, Q(1))]))

    def test_complete_weak_order_theories(self):
        names = ('a', 'b', 'c')
        operations = {'<': lambda a,b:a<b, '<=': lambda a,b:a<=b,
                      '=': lambda a,b:a==b, '!=': lambda a,b:a!=b,
                      '>': lambda a,b:a>b, '>=': lambda a,b:a>=b}
        atoms = [(a, op, b, Q(0)) for a,b in itertools.combinations(names, 2) for op in operations]
        assignments = [dict(zip(names, values)) for values in itertools.product(range(3), repeat=3)]
        def holds(aa, w): return all(operations[op](w[a], w[b]) for a,op,b,_ in aa)
        for size in range(4):
            for evidence in itertools.combinations(atoms, size):
                worlds = [w for w in assignments if holds(evidence, w)]
                state = candidate._prepare(evidence, names)
                self.assertEqual(state is not None, bool(worlds), evidence)
                if state is None: continue
                for query in atoms:
                    expected = any(holds([query], w) for w in worlds)
                    self.assertEqual(state.feasible([query]), expected, (evidence,query))

    def test_seeded_rational_compound_queries(self):
        rng = random.Random(101820681)
        names = ('a', 'b', 'c', 'd', 'e')
        def atom_():
            return rng.choice(names), rng.choice(tuple(reference.NEGATE)), rng.choice(names+(None,)), Q(rng.randint(-4,4), rng.randint(1,5))
        for _ in range(500):
            source = [atom_() for _ in range(rng.randrange(1,15))]
            prepared = candidate._prepare(source, names)
            self.assertEqual(prepared is not None, reference._sat(source))
            if prepared is None: continue
            matrix = prepared.matrix
            queries = [[atom_() for _ in range(rng.randrange(1,9))] for _ in range(12)]
            for query in queries+list(reversed(queries)):
                self.assertEqual(prepared.feasible(query), reference._sat(source+query), (source,query))
                self.assertEqual(prepared.matrix, matrix)

    def test_source_reuse_is_local_and_provenance_exact(self):
        data = dict(task_id='reuse', revision=1,
                    source=document([variable('a'),variable('b'),atom('a','<','b')]),
                    request=document([dict(operation='compare',variables=['a','b'])]),
                    candidate=document([atom('a','<','b'),atom('a','<=','b'),atom('b','>','a')]))
        prepare = candidate._prepare
        with patch.object(candidate, '_prepare', wraps=prepare) as calls:
            for _ in range(2):
                declaration = candidate.TypedDeclaration(**{k:data[k] for k in ('task_id','revision','source','request')})
                actual = candidate.check(**data,declaration=declaration)
                expected = reference.check(**data,declaration=declaration)
                self.assertEqual(study.stable(actual), study.stable(expected))
            self.assertEqual(calls.call_count, 2)
        self.assertIs(candidate.TypedDeclaration, reference.TypedDeclaration)

    def test_full_frozen_outputs(self):
        plan = study.verify()
        for row in plan['rows']+plan['projections']:
            declaration = study.declaration(row)
            kwargs = dict(row['input'], declaration=declaration, proposal=row.get('proposal'))
            self.assertEqual(study.stable(candidate.check(**kwargs)), study.stable(reference.check(**kwargs)), row['id'])


if __name__ == '__main__': unittest.main()
