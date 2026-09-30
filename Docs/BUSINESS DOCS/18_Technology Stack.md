# Technology Stack

*Version 0.3 | Company Document 18*

Select practical technologies while preserving provider portability.

## Application

TypeScript, Next.js, Expo/React Native.

## AI/ML

Python, PyTorch, Hugging Face, scikit-learn, XGBoost/LightGBM.

## Agent Orchestration

Stateful graph/workflow framework such as LangGraph, running **one orchestrator** (Brain 2) with deterministic guardrails around its decisions — not a framework for coordinating many independent agents.

## Data

PostgreSQL, pgvector, encrypted object storage; graph representation can begin relationally and move to a graph DB if needed. Includes a Profile store (versioned, per-domain — same PostgreSQL instance as Memory/Belief).

## MLOps

MLflow, DVC; add W&B/Feast/Ray/BentoML as proprietary model complexity grows.

## Platform

GitHub, CI/CD, managed cloud hosting, observability, secrets/KMS, mobile app stores, a scheduled-job runner (cron-class) for the Scheduler, and an outbound search/knowledge-provider integration for the World Knowledge Gateway.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Two Brains / Profile implementation plan formalized in the Architecture, Functional and Technical Design Documents (V02).
