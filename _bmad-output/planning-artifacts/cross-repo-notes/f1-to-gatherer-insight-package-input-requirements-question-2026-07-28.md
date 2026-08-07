# F1 to Gatherer: Insight Package Input Requirements Question

```yaml
direction: outbound
date: "2026-07-28"
source_project: f1_analytics
receiving_project: gatherer
note_type: question
purpose_label: insight_package_input_requirements_for_next_function
source_paths:
  - outputs/reports/question_workflow_surfaces.md
  - outputs/tables/question_workflow_surfaces.csv
requested_action: >
  Gatherer should name the concrete input shape (fields, format, minimum
  content) its next function actually needs to run against a real analysis,
  rather than f1 assuming today's Insight Package structure is sufficient.
response_expectation: >
  Please reply via a note in this same exchange naming what your next
  function requires as input, or confirming the current Insight Package
  fields (decision_question, data_contract, validation_status, story_assets,
  output_location, producer_version_or_run_identifier, consumer_guidance)
  are sufficient as-is.
```

## Summary

F1 has a first real analysis project it can point to: a per-question Insight
Package, generated locally, covering five 2026 F1 questions. Before f1
declares or authorizes any observable path, f1 wants to confirm what
Gatherer's next function actually needs as input to do real work against it —
not just to validate that registry wiring itself is functional.

## Question

What input does Gatherer's next function require to actually run against a
real f1 analysis?

- What fields or shape does it need — is the current Insight Package
  structure (one record per question, with a decision question, a data
  contract, a validation status, and story assets) enough, or does it need
  something else?
- Does it need fully computed answers, or can it exercise itself against a
  record that is honestly still source-blocked/pending, as most of f1's
  current records are?

## Boundary

This is a question only. F1 is not declaring these paths as authorized for
Gatherer to observe, not asking Gatherer to build anything, and not treating
any prior exchange as a commitment on either side. F1 will decide what to
authorize once Gatherer names what its next function actually needs.
