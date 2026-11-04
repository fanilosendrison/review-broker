"""Independent value and rejection oracles for the shared subject grammar."""
import unittest

from review_broker.oidc_subject import (
    BROKER_OWNER_ID, BROKER_REF, BROKER_REPOSITORY, BROKER_REPOSITORY_ID,
    immutable_repository_subject,
)


class ImmutableRepositorySubjectTests(unittest.TestCase):
    def context(self):
        return dict(repository='fanilosendrison/review-broker', repository_id='1433701208',
                    owner_id='30498238', ref='refs/heads/dev')

    def test_exact_subject_and_independent_identity_pins(self):
        self.assertEqual((BROKER_REPOSITORY, BROKER_REPOSITORY_ID, BROKER_OWNER_ID, BROKER_REF),
            ('fanilosendrison/review-broker', '1433701208', '30498238', 'refs/heads/dev'))
        self.assertEqual(immutable_repository_subject(**self.context()),
            'repo:fanilosendrison@30498238/review-broker@1433701208:ref:refs/heads/dev')

    def test_allowed_ascii_names_are_preserved_without_case_folding(self):
        self.assertEqual(immutable_repository_subject('Owner_1.-/Repo_2.-', '9', '8', 'refs/heads/dev'),
                         'repo:Owner_1.-@8/Repo_2.-@9:ref:refs/heads/dev')

    def test_ambiguous_or_non_ascii_names_are_rejected(self):
        for repository in ['', '/repo', 'owner/', 'owner/repo/extra', 'owner',
                           'own@er/repo', 'owner/re@po', 'own:er/repo', 'owner/re:po',
                           'own er/repo', 'owner/re po', 'owner/repo\n', 'owner/\trepo',
                           'öwner/repo', 'owner/répo']:
            with self.subTest(repository=repository):
                self.assert_invalid(repository=repository)

    def test_ids_require_positive_canonical_ascii_decimal(self):
        for field in ['repository_id', 'owner_id']:
            for value in ['', '0', '-1', '01', '+1', '1.0', 'abc', ' 1', '1\n', '１２']:
                with self.subTest(field=field, value=value):
                    self.assert_invalid(**{field: value})

    def test_branch_is_exact_and_mandatory(self):
        for ref in ['', 'refs/heads/main', 'refs/heads/Dev', 'refs/heads/dev\n', 'refs/tags/dev']:
            with self.subTest(ref=ref):
                self.assert_invalid(ref=ref)

    def test_all_arguments_require_exact_string_type(self):
        class StringSubclass(str):
            pass
        for field, original in self.context().items():
            for value in [None, 1, True, b'1', [], {}, StringSubclass(original)]:
                with self.subTest(field=field, value_type=type(value).__name__):
                    self.assert_invalid(**{field: value})

    def assert_invalid(self, **changes):
        context = self.context()
        context.update(changes)
        with self.assertRaisesRegex(ValueError, '^OIDC_IMMUTABLE_SUBJECT_CONTEXT_INVALID$'):
            immutable_repository_subject(**context)
