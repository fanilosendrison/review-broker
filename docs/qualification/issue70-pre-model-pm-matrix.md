---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "qualification-matrix"
domain: "independent-review"
severity: "draft"
name: "Issue 70 Pre-model PM Matrix"
version: "0.1.2"
---

# Issue 70 — Pre-model PM01–PM35 matrix

## Subject, verdicts and evidence boundaries

The original requirements below are documentary candidate scenarios from the
pre-model annex at `d827df21b1ccd179408f0624709cc2446795e134`.
The owner RWP-05 mandate selects the narrower experimental subcases, without
adopting that annex as a public contract. Tests do not load the annex or any
external Git object. BLOCKED in the verdict column means an unmet qualification
gate, not the journal disposition.

Base: PR #89, SHA `a7a4bcc2a21c3fa3961c7095e0c59b1bf1ecfd8e`,
tree `4fd57168bbb656a97c97340795094920f2097b19`.
The local source candidate ran 1086 tests in 4261.819 seconds: 1074 executed,
12 Linux-only Darwin skips, no failures. The explicit-authority phase-cut
measurement follow-up ran three tests in 341.966 seconds, PASS.
Initial exact-tree Ubuntu CI passed on candidate
`5f4ee4f307db7d91339c8b4c338a9f44755ef48e`, tree
`caace23b837721c3366ff47f851141df5f901417`, run
[42229015539](https://github.com/fanilosendrison/review-broker/actions/runs/42229015539),
job `127929779929`, checkout `b53cfc7a0aeb8642fc0ac4500d92968567b3b813`
with that same tree: 1086 tests, 1199.081 seconds, zero skips. All twelve Linux
witnesses and required cold cases passed. These are observed prior-commit facts,
not transferred acceptance for a later tree. Final published
SHA/tree, full base diff digest, tested checkout/tree, run/job and independent
review are bound by the final successor-PR receipt. Until that receipt proves
exact-tree CI and GO, the global qualification remains NOT_QUALIFIED.
A passing local subcase does not waive these common gates.

The independent R1 NO_GO on `6cae20fefc577a17ada95085ff07f0f35f80b73b`
identified a missing thrown-read subcase in PM12/20/35, not an assertion failure
in that prior CI. E21 now exercises the corrected original-ticket/concrete-HTTP
paths. A corrected full Darwin run passed 1090 tests in 3743.354 seconds, twelve
Linux-only skips; fresh corrected-tree Ubuntu CI and GO remain mandatory.
No prior-tree qualification is transferred.

Each A row is required; each X row is explicitly excluded. E references resolve
to exact module paths and test names in the register. The Stage 1 report carries
commands, assumptions, construction failures and operational prerequisites.

## Scenario/subcase matrix

| ID | Original requirement / selected subcase | Evidence | Verdict | Live limit / remaining work |
| -- | --------------------------------------- | -------- | ------- | --------------------------- |
| PM01.A | One v3 Issue observed by reconciler three times — **Selected:** Three discoveries, one reservation/dispatch; repeated post-failure discovery has no effects. | E01 E16 E18 | PASS | GitHub services are injected. |
| PM02.A | Two concurrent reconcilers reserve generation 1 — **Selected:** Concurrent controllers have one attributable winner, including identical proposed bytes. | E01 E02 | PASS | No operational concurrency claim. |
| PM03.A | CAS committed; GitHub dispatch response lost — **Selected:** Lost dispatch response preserves RESERVED uncertainty; no redispatch or pre-binding failure writer. | E01 E02 | PASS | Unknown dispatch is not BLOCKED. |
| PM03.X | Excluded: New pre-binding failure writer. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM04.A | Dispatch delivered late after explicit generation 2 — **Selected:** Wrong generation/run/attempt rejected before effects. | E02 E03 E16 | PASS | Generation 1 only. |
| PM04.X | Excluded: Positive generation-2 recovery followed by late generation 1. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM05.A | Permanent failure while source acquisition might already be in flight — **Selected:** Attributed competing failure during acquisition/reference/persistence fences the next effect and PREPARED. | E12 E16 | PASS | An already emitted read/write may finish. |
| PM06.A | Permanent-refusal CAS vs competing `PREPARED` CAS — **Selected:** BLOCKED and permanent refusal race actual PREPARED transitions on the same expected-old, both orders. | E13 E14 | PASS | Local exclusivity is separate from Git CAS. |
| PM06.X | Excluded: ARMED race. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM07.A | Permanent-refusal CAS committed, terminal-evidence processing crashes — **Selected:** Confirmed failure survives Worker destruction; observer/replay cannot cleanup or retry. | E15 E16 | PASS | Commitment and cause availability are distinct. |
| PM07.X | Excluded: Terminal-evidence collection and specialized STOPPED. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM08.A | Invalid/mismatched terminal proof, or unknown Codespace acquisition — **Selected:** New APIs have no terminal/Codespace permission; unsupported operations and tripwires remain closed. | E06 E16 | PASS | Negative boundary witness, not a terminal proof validator. |
| PM08.X | Excluded: Positive terminal/non-acquisition proof and Codespace ownership. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM09.A | Pre-`PREPARED` permanent failure with verified no-Codespace-access receipt — **Selected:** No specialized STOPPED entry or shortcut is introduced. | E16 | PASS | Existing future-operation refusal remains. |
| PM09.X | Excluded: Specialized REQUESTED/ADMITTED to STOPPED. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM10.A | Temporary API failure with saved blocked receipt — **Selected:** Original recognized transient fact, exact retained receipt and attributed BLOCKED; no retry. | E08 E09 E10 E13 | PASS | TRANSIENT does not predict availability. |
| PM10.X | Excluded: Owner recovery and new generation. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM11.A | Ambiguous permission/404 or unknown dispatch ownership — **Selected:** After attributed A, recognized ambiguous source gives UNKNOWN/BLOCKED; before A existing refusal/UNRESOLVED and zero new writer. | E01 E02 E03 E08 E10 | PASS | Pre-A and post-A are separately bounded. |
| PM11.X | Excluded: Universal BLOCKED for every UNKNOWN irrespective of authority/phase. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM12.A | Crash before failure/disposition CAS — **Selected:** Cuts before failure CAS create no fictitious BLOCKED; after entry only read reconciliation. | E13 E17 E21 | PASS | Corrected thrown-read witness passed locally; final CI/GO remain mandatory. |
| PM12.X | Excluded: New crash recovery or generation. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM13.A | Worker A and worker B race over one reservation — **Selected:** One bound run; wrong attempt, copied handoff/ticket and restarted process have no new active permission. | E02 E03 E05 E07 E08 E15 E16 | PASS | Original-process decision provenance only. |
| PM13.X | Excluded: New recovery mechanism. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM14.A | `PREPARED` packet rebuilt with different mutable bytes — **Selected:** Original packet and receipts survive cold rebuild; changed/lost bytes after PREPARED cannot rewrite commitment. | E04 E05 E07 E19 | PASS | Availability loss is not rollback. |
| PM15.A | `ARMED` then lost transport response — **Selected:** Old v1/v2 no-retry regressions retained; v3 model-capable advance remains unavailable. | E16 | PASS | Full regression and no new ARMED API. |
| PM15.X | Excluded: Positive v3 ARMED/invocation. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM16.A | Replayed/stale owner recovery nonce, wrong actor or previous reservation — **Selected:** Recovery/generation-2 entry refused without effects. | E02 E13 E16 | PASS | Negative witness only. |
| PM16.X | Excluded: Positive nonce/owner/recovery protocol. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM17.A | v1/v2 claim/read/reconciler and historical results — **Selected:** Historical bytes/identities and v1/v2/RWP01-04 regression suite; twelve Linux witnesses required on final tree. | E03 E04 E05 E06 E20 | PASS | Initial exact-tree Ubuntu CI passed all 1086 tests without skips; final-tree CI remains mandatory. |
| PM18.A | Receipt contains raw secret, unsupported code or malformed canonical bytes — **Selected:** Closed observation/receipt canonical grammar, arbitrary fields/codes/secrets and unrecognized provenance rejected before mutation. | E06 E07 E08 | PASS | No free-text evidence authority. |
| PM18.X | Excluded: New terminal receipt. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM19.A | Permanent refusal already `STOPPED` when duplicate event arrives — **Selected:** Distinct BLOCKED and REFUSED_PERMANENT rediscovery/new-worker cases preserve history and have zero new effects. | E16 | PASS | No inference from successful failure status to packet success. |
| PM19.X | Excluded: Original STOPPED scenario. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM20.A | Reservation and failure-write endpoint return ambiguous status — **Selected:** Reservation ambiguity and post-A failure-write ambiguity preserve attribution and read-only reconciliation. | E01 E13 E21 | PASS | Corrected thrown-read/ACK witnesses passed locally; no inferred attribution or retry. |
| PM20.X | Excluded: New pre-binding writer. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM21.A | Current journal reader receives canonical v2 record with `pre_model_control` — **Selected:** Closed journal v2 BLOCKED roundtrip; original fields/history retained and reopening/version corruption rejected. | E06 E13 E15 | PASS | No downcast to v1. |
| PM21.X | Excluded: Public v3 adoption. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM22.A | Refused A has not acquired Codespace, while B legitimately owns an Available Codespace — **Selected:** Codespace tripwires remain zero across rediscovery, old/new Workers and future API refusals. | E15 E16 | PASS | Only the bounded APIs are qualified. |
| PM22.X | Excluded: Positive terminal proof while another request owns a Codespace. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM23.A | v3 Issue opening event and reconciler discover the same request concurrently — **Selected:** Issue-opened and reconciler discoveries enter the actual common Controller, at most one dispatch. | E01 E18 | PASS | Event sources are injected. |
| PM23.X | Excluded: Live issues:opened/reconciler deployment and activation. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM24.A | Worker A validates generation, worker B wins recovery/refusal CAS before A commits `PREPARED` or `ARMED` — **Selected:** Winning failure fences generation-1 continuation and stale PREPARED CAS. | E11 E12 E13 E14 | PASS | Expected-old is the original A, force=false. |
| PM24.X | Excluded: Recovery generation 2 and ARMED. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM25.A | Manual generation advance from `PREPARED`, or failed worker cleanup tries to carry old `worker`/failure fields forward — **Selected:** PREPARED cannot advance through new APIs; BLOCKED cannot reopen or reset failure/worker history. | E13 E16 | PASS | Future operations refuse without mutations. |
| PM25.X | Excluded: Positive generation advancement/reset. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM26.A | Refusal before `PREPARED` with complete no-Codespace-access proof — **Selected:** No new terminal shortcut exists. | E16 | PASS | Static API scope plus unsupported-operation witness. |
| PM26.X | Excluded: Non-acquisition terminal transition. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM27.A | Codespace already Available under independent request B — **Selected:** No Codespace effect exposed or emitted by the bounded APIs. | E15 E16 | PASS | No claim about another deployed request. |
| PM27.X | Excluded: Available Codespace owned by request B. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM28.A | Unqualified mandatory start gate, executable identity or old-worker path coverage — **Selected:** Deployment and universal preventive coverage remain explicitly unqualified in the Stage 1 report. | E16 | PASS | Documentation of absence, not proof of deployment. |
| PM28.X | Excluded: Universal start-gate and historical executable coverage. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM29.A | Start/SSH/copy/stop observed or outcome ambiguous, despite declared false flag — **Selected:** Closed schemas/APIs add no non-acquisition receipt. | E06 E16 | PASS | Failure receipt cannot stand in for terminal evidence. |
| PM29.X | Excluded: Validate a non-acquisition receipt against observed/ambiguous Codespace effects. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM30.A | Old worker attempts Codespace start before `PREPARED` or after refusal — **Selected:** The new APIs expose no Codespace operation. | E15 E16 | PASS | No claim about an old deployed Worker. |
| PM30.X | Excluded: Mandatory start gate of a previously deployed Worker. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM31.A | Claim has reached `PREPARED` or `ARMED` — **Selected:** PREPARED selection is irreversible; uncertainty or later storage loss creates no failure repair. | E04 E16 | PASS | Commitment and remote availability are separate. |
| PM31.X | Excluded: Non-acquisition terminal mechanism and ARMED. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM32.A | Receipt binds wrong request, worker, admission, reservation, generation or Codespace — **Selected:** Rehashed RWP-05 observation/receipt bindings rejected before Git creation. | E07 E11 E13 | PASS | No transfer of this verdict to other receipt types. |
| PM32.X | Excluded: Future terminal receipt. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM33.A | Crash after permanent refusal but before run-evidence collection — **Selected:** Confirmed failure followed by crash retains disposition, without cleanup/retry/new observation. | E15 E16 | PASS | Original cause may become UNAVAILABLE/REJECTED. |
| PM33.X | Excluded: Terminal trace collection. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM34.A | Unknown run delivery and incomplete step logs — **Selected:** No failure or terminal verdict is derived from missing/skipped logs; cause requires independently recognized original observation. | E06 E07 E15 E16 | PASS | Log absence is not non-acquisition evidence. |
| PM34.X | Excluded: Universal preventive-gate/non-acquisition proof. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |
| PM35.A | Terminal receipt CAS loses to concurrent state change or is replayed — **Selected:** Actual failure/PREPARED and failure/failure races, lost responses, attribution and replays are qualified separately. | E11 E13 E14 E21 | PASS | Corrected pending/evidence preservation passed locally; no verdict transfer to terminal CAS. |
| PM35.X | Excluded: Future terminal CAS. | No positive qualification claimed | OUT_OF_SCOPE | Separate mandate/operational qualification required. |

## Bounded PM11 interpretation

The annex's control/crash clauses preserve RESERVED if no failure receipt was
committed. Consequently a lost dispatch response or unestablished pre-A authority
has no new writer. Only the original attributable, read-back A and independently
recognized original catalog observation may select UNKNOWN/BLOCKED. The two
branches are distinct in E01–E03 and E08/E10. Neither a negative pre-A test nor a
post-A PASS asserts that all UNKNOWN states are journalized.

## Evidence register

E01–E20 below ran in the initial exact-tree Ubuntu CI; E21 is separated below. E20 comprises the
twelve Linux-only tests skipped locally on Darwin and passed without skips in
that CI. Final-tree Ubuntu regression remains mandatory. Full-suite regression additionally includes the unchanged v1/v2,
journal reconciliation and legacy identity tests, not just this selected register.

### E01

tests/test_issue70_rwp01_controller.py:

- `test_RWP01_N01_exact_admission_reservation_then_dispatch`
- `test_RWP01_N02_duplicate_discovery_does_not_dispatch`
- `test_RWP01_N03_two_controllers_have_one_attributed_cas_winner`
- `test_RWP01_F07_unresolved_claim_creation_or_read_never_dispatches`
- `test_RWP01_F09_graphql_applied_but_ambiguous_has_no_dispatch_right`
- `test_RWP01_F10_dispatch_ambiguity_or_error_has_no_retry`
- `test_RWP01_F12_lost_response_and_reexecution_never_dispatch_again`
- `test_RWP01_F15_no_dispatch_before_attributed_committed_reservation`

### E02

tests/test_issue70_rwp02_worker.py:

- `test_RWP02_N01_nominal`
- `test_RWP02_N03_worker_starts_before_ack`
- `test_RWP02_N04_two_identical_workers`
- `test_RWP02_F01_other_run`
- `test_RWP02_F02_rerun`
- `test_RWP02_F05_other_generation`
- `test_RWP02_F15_ack_cas_unresolved`
- `test_RWP02_F19_identical_target_cas_attribution`
- `test_RWP02_F20_interruptions_no_automatic_retry`
- `test_RWP02_F21_no_source_acquisition_before_or_after_binding`

### E03

tests/test_issue70_rwp03_continuation.py:

- `test_N05_continuation_attributes_admitted_before_capture_handoff`
- `test_F29_unresolved_applied_admitted_is_not_inferred_or_retried`
- `test_N08_F30_identical_target_competition_has_one_attributed_handoff`
- `test_interruption_before_and_after_admitted_never_retries`
- `test_R4_git_internal_read_stops_on_journal_movement`
- `test_R4_reference_internal_http_stops_on_authority_loss`

### E04

tests/test_issue70_rwp04_continuation.py:

- `test_Q06_Q22_committed_prepared_survives_loss_expiry_or_metadata_replacement`
- `test_Q22_read_unavailable_after_attributed_cas_preserves_committed`
- `test_Q20_lost_cas_ack_has_visible_prepared_but_no_attributed_success`
- `test_Q20_divergent_cas_readback_never_retries_mutation`
- `test_Q18_Q21_new_producer_or_copied_handoff_cannot_upload`

tests/test_issue70_rwp04_packet_binding.py:

- `test_R3_coherent_changed_diff_with_genuine_handoff_has_zero_uploads_or_cas`

### E05

tests/test_issue70_rwp04_cold.py:

- `test_Q01_Q21_full_worker_disappearance_and_fresh_isolated_process`
- `test_Q02_no_remote_references_cold_reconstruction`
- `test_RQ18_Q21_fresh_admitted_process_has_no_continuation_effect_permission`
- `test_Q14_Q18_historical_verification_cannot_build_persist_or_authorize_new_selection`

### E06

tests/test_issue70_rwp05_failure.py:

- `test_F01_six_reasons_and_every_verification_fact`
- `test_F01_every_http_catalog_status_and_non_catalog_remote_permission`
- `test_F01_closed_fields_and_strict_numbers`
- `test_F01_phase_nulls_time_and_canonical_bytes`
- `test_F01_every_fact_is_closed_and_requires_its_own_fields`
- `test_F01_blocked_receipt_closed_types_codes_and_reference_nulls`
- `test_F01_permanent_bytes_identity_and_diagnostics_unchanged`

### E07

tests/test_issue70_rwp05_authority.py:

- `test_F03_rehashed_journal_worker_reference_and_phase_bindings_refuse_before_git`
- `test_F03_remote_original_packet_artifact_plan_and_id_falsifications`
- `test_F02_F03_actual_origin_query_and_authenticated_principal_are_checked`
- `test_F03_F06_final_receipt_rehash_cannot_change_recognized_cause_or_reuse_choice`
- `test_RWP04_original_packet_substitution_remains_refused_with_failure_support`
- `test_F03_invalid_observation_address_is_refused_before_external_read`

### E08

tests/test_issue70_rwp05_continuation.py:

- `test_F07_recognized_reference_503_transient`
- `test_F08_recognized_comment_404_is_unknown_not_absence`
- `test_F04_lost_retention_ack_exact_readback_no_second_put`
- `test_F04_no_retained_original_no_failure_git_proposal`
- `test_F02_F03_status_or_wrong_actual_target_without_recognition_is_not_authority`
- `test_F05_unattributed_applied_admission_emits_no_ticket`
- `test_F06_direct_copy_subclass_and_forged_ticket_refuse`
- `test_F06_two_original_handlers_share_one_retention_and_journal_entry`
- `test_F20_committed_failure_survives_immediate_original_proof_loss`
- `test_F20_historical_commitment_separate_from_original_cause_availability`
- `test_F02_put_of_well_typed_hash_does_not_create_origin`

### E09

tests/test_issue70_rwp05_transfer.py:

- `test_F07_clone_and_fetch_timeouts_require_real_termination`
- `test_F02_generic_nonzero_git_exit_is_not_transfer_evidence`
- `test_F02_timeout_without_confirmed_termination_cannot_block`

### E10

tests/test_issue70_rwp05_composition.py:

- `test_F07_ack_metadata_503_is_transient`
- `test_F07_precise_metadata_and_storage_read_timeouts`
- `test_F10_unknown_upload_resolves_only_after_complete_original_packet`
- `test_F10_unknown_upload_read_failure_and_post_metadata_download_failure_priority`
- `test_F08_four_concrete_completed_verification_controls`
- `test_F10_unknown_upload_divergence_remains_upload_unknown`
- `test_F10_unknown_upload_complete_absent_or_ambiguous_listing_can_block_unknown`
- `test_F02_F23_guards_are_not_catalog_observations_even_after_unknown_upload`
- `test_F10_ack_absent_expired_ambiguous_or_upload_refused_do_not_create_catalog_failure`

### E11

tests/test_issue70_rwp05_git_boundaries.py:

- `test_F12_positive_consumed_blocked_choice_completes_all_git_edges`
- `test_F12_head_movement_after_each_blob_tree_commit_stops_next_http_effect`
- `test_F13_last_identity_observation_cannot_authorize_stale_update_refs`
- `test_F13_emitted_graphql_permission_error_is_not_source_permanence_or_success`

### E12

tests/test_issue70_rwp05_inflight.py:

- `test_F14_acquisition_process_started_before_failure_can_finish_without_next_launch`
- `test_F14_reference_response_can_return_but_following_transport_is_fenced`
- `test_F14_first_persistence_write_finishes_then_next_write_and_publication_are_fenced`

### E13

tests/test_issue70_rwp05_journal.py:

- `test_F17_unknown_and_error_responses_never_retry_or_claim_blocked`
- `test_F17_interruption_before_after_application_preserves_pending_without_retry`
- `test_F18_attributed_mutation_delayed_or_stale_read_eventually_reconciles_read_only`
- `test_F18_recognized_expected_old_rejection_is_preserved_by_failure_orchestrator`
- `test_F18_identical_visible_blocked_without_writer_attribution_stays_unresolved`
- `test_F06_F23_interruption_after_choice_before_git_creation_never_restores_ticket`
- `test_F21_blocked_decoder_preserves_v2_and_rejects_incoherent_history`
- `test_F15_blocked_and_permanent_against_prepared_both_orders`
- `test_F16_identical_and_different_failure_proposals_one_attributed_winner`

### E14

tests/test_issue70_rwp05_local_decision.py:

- `test_F06_F10_final_failure_and_prepared_choices_both_orders_after_resolved_unknown_upload`

### E15

tests/test_issue70_rwp05_cold.py:

- `test_F19_transient_and_unknown_same_original_ids_time_after_worker_disappearance`
- `test_F20_F21_lost_rejected_cause_and_untrusted_history_do_not_mutate`

### E16

tests/test_issue70_rwp05_observers.py:

- `test_F22_blocked_and_permanent_rediscovery_or_new_worker_has_zero_new_effects`
- `test_F05_copied_failure_result_is_not_a_successful_remote_handoff`
- `test_F11_prepared_entry_unknown_or_committed_never_falls_back_to_failure`

tests/test_issue70_rwp05_preparation_fence.py:

- `test_F22_failed_control_is_rejected_before_authorized_git_or_legacy_packet_writes`

### E17

tests/test_issue70_rwp05_interruptions.py:

- `test_F23_all_source_packet_phase_cuts_without_catalog_evidence_never_block`
- `test_F23_upload_download_extract_and_remote_verify_cuts_do_not_invent_cause`
- `test_F23_hard_exit_before_after_observation_conservation_does_not_commit_failure`

### E18

tests/test_issue70_rwp05_stage1.py:

- `test_Stage1_PM01_PM23_true_common_controller_to_prepared_and_cold_both_reference_variants`

### E19

tests/test_issue70_rwp05_remote_boundaries.py:

- `test_proto05_same_name_new_id_serves_identical_bytes_but_not_original_receipt`
- `test_proto06_changed_zip_and_matching_authenticated_digest_still_changes_commitment`
- `test_proto11_future_expiration_metadata_change_is_not_silently_recommitted`
- `test_proto15_proto16_remote_source_or_missing_member_with_matching_digest_refuses`

### E20

tests/test_issue70_rwp03_network_isolation.py:

- `test_01_seccomp_installation_and_kernel_state`
- `test_02_native_socket_denied`
- `test_03_python_socket_denied`
- `test_04_tcp_connect_ex_denied`
- `test_05_udp_sendto_denied`
- `test_06_native_connect_denied`
- `test_07_direct_child_inherits`
- `test_08_second_generation_after_exec_inherits`
- `test_09_complete_cold_reconstruction_under_filter`
- `test_10_missing_library_fails_closed_before_cold_import`
- `test_11_no_inherited_network_descriptors`
- `test_12_unsandboxed_linux_cold_invocation_rejected`

### E21

Corrected original-ticket witnesses in tests/test_issue70_rwp05_reconciliation.py:

- `test_R1_F17_F18_real_ref_and_matching_http_exceptions_known_and_lost_ack`
- `test_R1_F17_origin_verification_read_exception_preserves_pending`
- `test_R1_F17_reconciliation_authority_exception_keeps_already_recognized_writer`
- `test_R1_F18_recognized_rejection_evidence_survives_thrown_readback`

## Gate accounting

This matrix has 35 witnessed PASS required subcases, zero FAIL/BLOCKED required
subcases, and 30 OUT_OF_SCOPE subcases. E01–E20 have the prior CI evidence above;
E21 closes the newly exposed local witness gap with the corrected full local run.
Only fresh corrected-tree CI and GO can establish final global qualification.
No required gap is labeled OUT_OF_SCOPE. The global exact-tree CI and independent
GO gates apply to every required row. The versioned implementation report states
only evidence known before its commit; the final PR receipt supplies the later
exact-tree qualification without a self-referential documentation loop.
