# ML Architecture

*Version 0.3 | Company Document 22*

Define where classical ML and neural networks add value.

## Initial Models

- Embedding model for semantic memory.
- Generic reranker for retrieval.
- Classifiers for memory type/topic/change candidates.

## Proprietary Models Later

- Memory importance ranking.
- Personal retrieval reranker.
- Preference representation.
- Belief-change classifier.
- Decision similarity/outcome features.
- Communication-style representation.
- A domain-benchmark comparator, used only to draft a Profile refinement proposal for the user's review — never to write the Profile directly.

## Framework

Python + PyTorch for neural models; scikit-learn/XGBoost for strong baselines; never use deep learning where a simpler model performs adequately.

## Working Status

This is a working document. It should evolve through founder usage, user research, product experiments, technical validation, and legal/security review.

## Basis

Grounded in the selfie.Me Strategic Framework and Business Model Canvas, the founder's clarified direction, and the Brain 1 / Brain 2 design in `Docs/FEATURES/Building_Brain1.md` and `Building_Brain2.md`, formalized in the Architecture, Functional and Technical Design Documents (V03).
