"""Source-bounded credential and rollout checks; no live secrets or Codespace."""
from __future__ import annotations
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
WORKFLOWS=ROOT/".github/workflows"
BROKER=ROOT/"src/review_broker"


def section(source, first, second):
    a=source.find("- name: "+first)
    b=source.find("- name: "+second,a+1)
    if a<0 or b<0: raise ValueError("STEP_NOT_FOUND")
    return source[a:b]


def prep_credential_boundary(source):
    p=section(source,"Admit and prepare immutable packet",
              "Quarantine unsafe prepared packet")
    return ("internal-prepare" in p and "github.token" in p
            and "REVIEW_BROKER_CODESPACE_TOKEN" not in p
            and "CODESPACE_TOKEN" not in p
            and "gh codespace" not in p
            and "user/codespaces/" not in p)


class CredentialRolloutBoundaryTests(unittest.TestCase):
    def test_c01_preparation_does_not_get_dedicated_codespace_secret(self):
        workflow=(WORKFLOWS/"review-request.yml").read_text()
        self.assertTrue(prep_credential_boundary(workflow))
        self.assertNotIn("REVIEW_BROKER_CODESPACE_TOKEN",
                         workflow[:workflow.index("    steps:")])

    def test_c02_injected_early_secret_destroys_preparation_boundary(self):
        workflow=(WORKFLOWS/"review-request.yml").read_text()
        self.assertIn("GH_TOKEN: ${{ github.token }}",workflow)
        unsafe=workflow.replace("GH_TOKEN: ${{ github.token }}",
            "GH_TOKEN: ${{ secrets.REVIEW_BROKER_CODESPACE_TOKEN }}",1)
        self.assertFalse(prep_credential_boundary(unsafe))

    def test_c03_first_codespace_secret_use_follows_prepare(self):
        workflow=(WORKFLOWS/"review-request.yml").read_text()
        p=workflow.index("- name: Admit and prepare immutable packet")
        admission=workflow.index("- name: Enforce selected operational admission")
        start=workflow.index("- name: Start and observe dedicated Codespace")
        self.assertLess(p,admission)
        self.assertLess(admission,start)
        self.assertIn("REVIEW_BROKER_CODESPACE_TOKEN",workflow[admission:start])

    def test_c04_start_uses_codespace_secret_after_prepare_output(self):
        workflow=(WORKFLOWS/"review-request.yml").read_text()
        step=section(workflow,"Start and observe dedicated Codespace",
                     "Transfer and verify packet inside Codespace")
        self.assertIn("steps.prepare.outputs.duplicate == 'false'",step)
        self.assertIn("REVIEW_BROKER_CODESPACE_TOKEN",step)
        self.assertIn("user/codespaces/",step)
        self.assertNotIn("internal-verify-v3-codespace-gate",step)

    def test_c05_stop_cannot_run_from_skipped_start_in_current_workflow(self):
        source=(WORKFLOWS/"review-request.yml").read_text()
        step=section(source,"Stop and independently observe Shutdown",
                     "Record stopped state from observed evidence")
        self.assertIn("steps.start.outcome != 'skipped'",step)
        self.assertIn("always()",step)
        self.assertIn("REVIEW_BROKER_CODESPACE_TOKEN",step)
        self.assertIn("internal-stop-codespace",step)

    def test_c06_reconciler_independently_receives_codespace_secret(self):
        wf=(WORKFLOWS/"review-reconciler.yml").read_text()
        reconciler=(BROKER/"reconciliation.py").read_text()
        self.assertIn("REVIEW_BROKER_CODESPACE_TOKEN",wf)
        self.assertIn("internal-reconcile",wf)
        self.assertIn("controller.stop()",reconciler)

    def test_c07_qualification_workflow_has_different_concurrency_group(self):
        wf=(WORKFLOWS/"codespace-control-qualification.yml").read_text()
        self.assertIn("REVIEW_BROKER_CODESPACE_TOKEN",wf)
        self.assertIn("review-broker-codespace-control-qualification",wf)
        self.assertNotIn("group: review-broker-single-reviewer",wf)
        self.assertIn("user/codespaces/",wf)
        self.assertIn("gh codespace stop",wf)

    def test_c08_source_qualification_explicitly_removes_codespace_token(self):
        wf=(WORKFLOWS/"private-source-qualification.yml").read_text()
        self.assertIn('REVIEW_BROKER_CODESPACE_TOKEN: ""',wf)
        self.assertIn("local_subprocess",wf)

    def test_c09_ci_has_no_secret_codespace_commands(self):
        wf=(WORKFLOWS/"ci.yml").read_text()
        self.assertNotIn("REVIEW_BROKER_CODESPACE_TOKEN",wf)
        self.assertNotIn("secrets.",wf)
        self.assertNotIn("user/codespaces/",wf)
        self.assertNotIn("gh codespace",wf)

    def test_c10_pilot_controller_inherits_external_transport_environment(self):
        pilot=(BROKER/"pilot03_transport.py").read_text()
        self.assertIn("runner: Callable[..., Any] = subprocess.run",pilot)
        self.assertIn("self.lifecycle.start()",pilot)
        self.assertIn("self.lifecycle.stop()",pilot)
        self.assertNotIn("pre_model_control",pilot)

    def test_c11_current_request_workflow_cannot_admit_v3(self):
        wf=(WORKFLOWS/"review-request.yml").read_text()
        parser=(BROKER/"request.py").read_text()
        self.assertIn("review-broker-request:v1",wf)
        self.assertIn("review-broker-request:v2",wf)
        self.assertNotIn("review-broker-request:v3",wf)
        self.assertNotIn("review-broker-request:v3",parser)

    def test_c12_qualifier_literal_and_runtime_variable_equality_unverified(self):
        review=(WORKFLOWS/"review-request.yml").read_text()
        qualifier=(WORKFLOWS/"codespace-control-qualification.yml").read_text()
        self.assertIn("vars.REVIEW_BROKER_CODESPACE_NAME",review)
        self.assertIn("CODESPACE_NAME: review-broker-reviewer-4q4v769jr65hjww9",qualifier)
        # Repository variable value could not be retrieved via connector.
        # This test intentionally does NOT assert equality.

    def test_c13_source_audit_does_not_disable_old_workflow_reruns(self):
        wf=(WORKFLOWS/"review-request.yml").read_text()
        self.assertIn("workflow_dispatch:",wf)
        self.assertNotIn("disable_all_older_reruns",wf)
        # A GitHub re-run may use the historical SHA/REF. Versioned
        # v3 rejection is qualified separately from global Codespace safety.


if __name__=="__main__":
    unittest.main()
