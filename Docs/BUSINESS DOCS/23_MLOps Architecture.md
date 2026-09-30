# MLOps Architecture

*Version 0.3 | Company Document 23*

Define repeatable model development and production control.

## Lifecycle

Dataset snapshot -> train -> evaluate -> register -> approve -> deploy -> monitor -> collect feedback -> retrain/rollback.

## Tooling

- MLflow for experiments/model registry.
- DVC for dataset/artifact versioning.
- Optional W&B for richer experiment analysis.
- BentoML/managed endpoints for serving.
- OpenTelemetry/model metrics for monitoring.

## Governance

Every model version records training data lineage, evaluation metrics, intended use, limitations and rollback path — including the future domain-benchmark comparator (`22_ML Architecture`), which follows the same lifecycle as every other model here.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Two Brains / Profile implementation plan formalized in the Architecture, Functional and Technical Design Documents (V02).
