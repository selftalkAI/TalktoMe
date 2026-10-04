# Technology Stack

*Version 0.3 | Company Document 18*

Select practical technologies while preserving provider portability.

## Application

TypeScript, Next.js, Expo/React Native.

## AI/ML

Python, PyTorch, Hugging Face, scikit-learn, XGBoost/LightGBM.

## Agent Orchestration

LangGraph: Brain 1's 13 core agents each run a bounded think → act → check graph with tools; Brain 2 runs a five-step reply pipeline (Understand, Decide, Speak, Check, Remember). Deterministic guardrails (write gate, plan rules, Check) sit around every model decision. Models via a gateway: Ollama locally today, a stronger provider per step when configured.

## Data

PostgreSQL, pgvector, encrypted object storage; graph representation can begin relationally and move to a graph DB if needed. Includes a Profile store (versioned, per-domain — same PostgreSQL instance as Memory/Belief).

## MLOps

MLflow, DVC; add W&B/Feast/Ray/BentoML as proprietary model complexity grows.

## Platform

GitHub, CI/CD, managed cloud hosting, observability, secrets/KMS, mobile app stores, a scheduled-job runner (cron-class) for the Scheduler, and an outbound search/knowledge-provider integration for the World Knowledge Gateway.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Brain 1 / Brain 2 design in `Docs/FEATURES/Building_Brain1.md` and `Building_Brain2.md`, formalized in the Architecture, Functional and Technical Design Documents (V03).
