"""The spinal cord — the one dedicated pathway between this service and the

Agentic Service (where actual reasoning happens: the model gateway, and the
cognitive agents — Thalamus, Sensory Cortex, Hippocampus, Prefrontal Cortex,
Amygdala, Broca's Area). Not a sense organ like `brain1`'s Eyes/Ears, not
Brain 2's voice like Mouth — purely internal signal relay, in both
directions, between two parts of Brain 2. No other module is allowed to
call a model provider directly; every call passes through here, same way
every nerve impulse between the brain and the rest of the body passes
through the spinal cord. A severed cord (`AgenticServiceError`) doesn't
stop Brain 2 from reasoning — it stops that reasoning from reaching or
hearing back from this side, which is exactly why callers of this client
keep an honest fallback for that case.
"""

from .agentic_client import AgenticServiceClient, AgenticServiceError

__all__ = ['AgenticServiceClient', 'AgenticServiceError']
