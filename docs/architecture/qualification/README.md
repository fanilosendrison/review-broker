---
okf_version: "1.0"
kind: "KnowledgeAsset"
asset_type: "verification-reference"
domain: "independent-review"
severity: "guideline"
name: "Qualified J-CH Construction References"
version: "0.1.0"
---

# Qualified J-CH construction references

The three rb91 schema resources in this folder are exact frozen construction
references from PR112 at b7316e5e8cadc718872ea56dfecfb61709c636ce. Their original
candidate titles/descriptions are retained deliberately. They are NOT the new
proposed public normative resources or runtime admission selectors.

[The provenance manifest](../../adoption/jch-qualified-inputs.json) pins these
bytes and the unchanged qualified test modules. New resources in `schemas/jch-*`
are checked against the journal/result references under an explicit fixed
$id/$ref/annotation relocation, plus executable conformance. All legacy
qualification reports already present in this folder retain their historical
scope; no old observation is upgraded by this adoption preparation.
