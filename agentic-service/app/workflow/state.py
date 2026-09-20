from __future__ import annotations

from enum import Enum


class RunStatus(str, Enum):
    """Agent run lifecycle — matches TDD §8 / ADD §8.1."""

    CREATED = 'created'
    PLANNING = 'planning'
    READY = 'ready'
    RUNNING = 'running'
    WAITING_APPROVAL = 'waiting_approval'
    WAITING_EXTERNAL = 'waiting_external'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class StepStatus(str, Enum):
    PENDING = 'pending'
    WAITING_APPROVAL = 'waiting_approval'
    COMPLETED = 'completed'
    DENIED = 'denied'
    FAILED = 'failed'


class RiskClass(str, Enum):
    """Matches TDD §8.1's planning contract risk classes."""

    READ_ONLY = 'read_only'
    REVERSIBLE_WRITE = 'reversible_write'
    CONSEQUENTIAL_WRITE = 'consequential_write'
    HIGH_IMPACT = 'high_impact'


class PolicyDecision(str, Enum):
    ALLOW = 'allow'
    REQUIRE_APPROVAL = 'require_approval'
    DENY = 'deny'
