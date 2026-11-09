"""Explicit immutable tree/path facts must agree without inventing missing nodes."""
import copy
import itertools
import unittest

from review_broker.github_journal_identity import git_object_context, git_object_facts, git_object_identity

REPO = 'sample/repo'
R, S, T, B, C = (x * 40 for x in '12345')


def entry(path, sha, kind='blob', mode=None, **metadata):
    return dict(path=path, sha=sha, type=kind,
                mode=mode or {'tree': '040000', 'blob': '100644', 'commit': '160000'}[kind],
                **metadata)


def aliases(first, second):
    return [entry('first', S, 'tree', tree=first), entry('shared', S, 'tree', tree=second)]


class GitTreeBindingTests(unittest.TestCase):
    def check(self, rows):
        return git_object_facts(dict(sha=R, tree=rows), REPO, 'trees')

    def test_conflicting_flat_alias_children_refuse_in_every_order(self):
        rows = [entry('first', S, 'tree'), entry('shared', S, 'tree'),
                entry('first/alpha', B), entry('shared/alpha', C)]
        for ordered in itertools.permutations(rows):
            with self.subTest(paths=[x['path'] for x in ordered]), self.assertRaises(ValueError):
                self.check(list(ordered))

    def test_nested_and_flat_descriptions_meet_in_both_orders(self):
        rows = [entry('first', S, 'tree', tree=[entry('alpha', B)]),
                entry('shared', S, 'tree'), entry('shared/alpha', C)]
        for ordered in (rows, list(reversed(rows)), aliases([entry('alpha', B)], [entry('alpha', C)])):
            with self.assertRaises(ValueError):
                self.check(ordered)

    def test_mode_and_kind_are_part_of_the_binding(self):
        for other in (entry('alpha', B, mode='100755'), entry('alpha', B, mode='120000'),
                      entry('alpha', T, 'tree'), entry('alpha', C, 'commit')):
            rows = aliases([entry('alpha', B)], [other])
            for ordered in (rows, list(reversed(rows))):
                with self.subTest(other=other), self.assertRaises(ValueError):
                    self.check(ordered)

    def test_sparse_relative_paths_still_bind_the_same_known_tree(self):
        # The absent 'missing' prefix has no identity, but S/missing/file is explicit.
        rows = aliases([entry('missing/file', B)], [entry('missing/file', C)])
        with self.assertRaises(ValueError):
            self.check(rows)

    def test_compatible_partial_descriptions_and_shared_dag_pass(self):
        rows = aliases([entry('alpha', B, size=0), entry('deep', T, 'tree')],
                       [entry('beta', C), entry('deep/file', B)])
        before = copy.deepcopy(rows)
        facts = self.check(rows)
        self.assertEqual(len(facts), 4)
        self.assertEqual(git_object_identity(dict(sha=R, tree=rows), REPO, 'trees'), facts[:3])
        self.assertEqual(rows, before)
        self.assertEqual(facts[3][T], frozenset({B}))

    def test_git_path_names_are_exact_not_os_normalized(self):
        names = ['Alpha', 'alpha', 'é', 'e\u0301', 'a\\b', 'a/b', ' spaced ', 'tab\t', 'line\n']
        rows = aliases([entry(name, B) for name in names], [entry(name, B) for name in names])
        self.check(rows)
        # Distinct exact names can name different objects, including Unicode variants.
        self.check(aliases([entry('é', B), entry('Alpha', B)],
                           [entry('e\u0301', C), entry('alpha', C)]))

    def test_binding_does_not_require_complete_child_inventories(self):
        self.check(aliases([entry('only-first', B)], [entry('only-second', C)]))
        self.check([entry('unknown/file', B)])

    def test_nested_flat_prefix_kind_conflict_is_not_absence(self):
        rows = aliases([entry('prefix', B)], [entry('prefix/file', C)])
        with self.assertRaises(ValueError):
            self.check(rows)

    def extend(self, facts, rows, root=R):
        return git_object_context(dict(sha=root, tree=rows), REPO, 'trees',
            known_roles=facts.roles, known_sizes=facts.sizes, known_links=facts.links,
            known_bindings=facts.bindings)

    def test_sparse_facts_survive_later_prefix_identification_in_every_ack_order(self):
        descriptions = [[entry('first/missing/file', B)], [entry('first', S, 'tree')],
                        [entry('missing/file', C)]]
        for order in itertools.permutations(range(3)):
            facts = git_object_context(dict(sha=R), REPO, 'trees')
            with self.subTest(order=order), self.assertRaises(ValueError):
                for index in order:
                    facts = self.extend(facts, descriptions[index], S if index == 2 else R)

    def test_cross_ack_flat_nested_modes_and_types_meet_without_mutating_context(self):
        initial = git_object_context(dict(sha=R, tree=[entry('first', S, 'tree'),
            entry('first/file', B)]), REPO, 'trees')
        before = copy.deepcopy(initial)
        for other in (entry('file', C), entry('file', B, mode='100755'), entry('file', T, 'tree')):
            with self.subTest(other=other), self.assertRaises(ValueError):
                self.extend(initial, [entry('shared', S, 'tree', tree=[other])])
        self.assertEqual(initial, before)
        later = self.extend(initial, [entry('shared', S, 'tree', tree=[entry('file', B)])])
        self.assertEqual(later.bindings[(S, 'file')], ('100644', 'blob', B))
        self.assertEqual(initial, before)

    def test_missing_prefix_identity_is_not_inferred_but_rooted_fact_is_retained(self):
        initial = git_object_context(dict(sha=R, tree=[entry('unknown/file', B)]), REPO, 'trees')
        self.assertEqual(initial.bindings, {(R, 'unknown/file'): ('100644', 'blob', B)})
        self.assertEqual(initial.roles, {R: 'tree', B: 'blob'})
        later = self.extend(initial, [entry('unknown', S, 'tree')])
        self.assertEqual(later.bindings[(S, 'file')], ('100644', 'blob', B))
        self.extend(later, [entry('file', B), entry('other', C)], S)

    def test_prefix_closure_preserves_known_size_role_and_cycle_checks(self):
        initial = git_object_context(dict(sha=R, tree=[entry('unknown/file', B, size=1)]), REPO, 'trees')
        for rows in ([entry('unknown', S, 'tree', tree=[entry('file', B, size=2)])],
                     [entry('unknown', B, 'tree')],
                     [entry('unknown', S, 'tree', tree=[entry('back', R, 'tree')])]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.extend(initial, rows)

    def test_sparse_known_prefix_cross_response_cycles_cannot_disappear(self):
        initial = git_object_context(dict(sha=R, tree=[entry('missing/child', T, 'tree')]), REPO, 'trees')
        later = self.extend(initial, [entry('back', S, 'tree')], T)
        with self.assertRaises(ValueError):
            self.extend(later, [entry('missing', S, 'tree')])
