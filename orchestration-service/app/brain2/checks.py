from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

# Brain 2's Check step — the deterministic half (Building_Brain2.md §9.4.4).
# Every candidate reply passes through `check_reply` before the person can
# see it; a failure is never shown (FSD BR-016). These rules exist because
# each one was observed in real Brain 2 output (see
# `tests/fixtures/brain2_real_outputs_2026_10.json`), not as style taste.
# The LLM judge (Anterior Cingulate) is a later, separate layer on top.

DEFAULT_MAX_WORDS = 60
MAX_QUESTIONS = 1
REPETITION_THRESHOLD = 0.8

# Talking about her instead of to her, or narrating its own process.
_META_PHRASES = (
    'the user',
    "user's",
    'the person',
    'this person',
    'based on the information',
    'based on the available',
    'available knowledge',
    'i can respond',
    'it seems that there is',
    'no additional information',
    'the provided',
    'brain 1',
    'brain 2',
    'as an ai language model',
)

# Wording that only appears because it was copied from an instruction.
_PROMPT_ECHO_PHRASES = (
    'genuinely matter',
    'one specific reason',
    "what i'd like to know",
    'what i would like to know',
    'one concrete',
    'specific reason why',
)

# Therapy-speak and hollow flattery (MI: affirmations must be real, not inflated).
_HOLLOW_PHRASES = (
    'i want to acknowledge',
    'i would like to acknowledge',
    'huge accomplishment',
    'incredible progress',
    "you've made incredible",
    'testament to your',
    "it's amazing that",
    "it's awesome that",
    'proud of your journey',
)

_LIST_LINE_RE = re.compile(r'^\s*(?:[-*•]|\d+[.)])\s+', re.MULTILINE)
_HEADING_RE = re.compile(r'^\s*#{1,6}\s+|\*\*[^*]+\*\*', re.MULTILINE)
_NUMBER_RE = re.compile(r'\d+(?:[.,]\d+)?')
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')
_TERMINAL_CHARS = '.!?)"\'”’…'
_WEEKDAYS = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')


@dataclass
class CheckResult:
    passed: bool
    failures: list[str] = field(default_factory=list)

    def feedback(self) -> str:
        """The failures as plain instructions for a single rewrite attempt."""
        return '; '.join(self.failures)


def check_reply(
    reply: str,
    *,
    previous_replies: list[str] | None = None,
    allowed_text: str = '',
    blocked_terms: list[str] | None = None,
    max_words: int = DEFAULT_MAX_WORDS,
    max_questions: int = MAX_QUESTIONS,
) -> CheckResult:
    """Runs every deterministic rule against one candidate reply.

    `previous_replies` are Brain 2's own recent replies in this conversation
    (repetition check). `allowed_text` is everything the reply may legitimately
    draw numbers from — the Context Pack and the conversation so far.
    `blocked_terms` are privacy items (T3 without opt-in, boundaries) that must
    never appear.
    """
    text = (reply or '').strip()
    failures: list[str] = []

    if not text:
        return CheckResult(False, ['empty reply'])

    lowered = text.lower()

    if _LIST_LINE_RE.search(text) or _HEADING_RE.search(text):
        failures.append('uses a list, heading or bold text — write plain conversational sentences')

    word_count = len(text.split())
    if word_count > max_words:
        failures.append(f'too long ({word_count} words) — stay under {max_words} words')

    meta = [p for p in _META_PHRASES if p in lowered]
    if meta:
        failures.append(f'talks about her or about its own process ({meta[0]!r}) — talk to her directly')

    echo = [p for p in _PROMPT_ECHO_PHRASES if p in lowered]
    if echo:
        failures.append(f'copies instruction wording ({echo[0]!r}) — say it in your own words')

    hollow = [p for p in _HOLLOW_PHRASES if p in lowered]
    if hollow:
        failures.append(f'hollow or therapy-style phrasing ({hollow[0]!r}) — be plain and specific')

    if text.count('?') > max_questions:
        failures.append(f'asks {text.count("?")} questions — ask at most {max_questions}')

    if text[-1] not in _TERMINAL_CHARS and not _ends_with_emoji(text):
        failures.append('ends mid-sentence — finish the thought')

    invented = _invented_numbers(text, allowed_text)
    if invented:
        failures.append(f'uses numbers not in the context ({", ".join(invented)}) — never invent numbers')

    wrong_days = [day for day in _WEEKDAYS if day in lowered and day not in (allowed_text or '').lower()]
    if wrong_days:
        failures.append(f'names a day not in the context ({wrong_days[0]}) — check what day it is')

    if previous_replies:
        repeated = _repeated_sentence(text, previous_replies)
        if repeated:
            failures.append(f'repeats something already said ({repeated!r}) — say something new')

    for term in blocked_terms or []:
        if term and term.lower() in lowered:
            failures.append('mentions something private she has not opted to share here')
            break

    return CheckResult(not failures, failures)


def _invented_numbers(text: str, allowed_text: str) -> list[str]:
    allowed = set(_NUMBER_RE.findall(allowed_text or ''))
    return sorted({n for n in _NUMBER_RE.findall(text) if n not in allowed})


def _sentences(text: str) -> list[str]:
    return [s.strip().lower() for s in _SENTENCE_SPLIT_RE.split(text) if len(s.split()) >= 4]


def _repeated_sentence(text: str, previous_replies: list[str]) -> str | None:
    previous = [s for reply in previous_replies[-5:] for s in _sentences(reply)]
    for sentence in _sentences(text):
        for old in previous:
            if SequenceMatcher(None, sentence, old).ratio() >= REPETITION_THRESHOLD:
                return sentence[:80]
    return None


def _ends_with_emoji(text: str) -> bool:
    return ord(text[-1]) > 0x2000
