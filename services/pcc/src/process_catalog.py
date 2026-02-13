"""Process catalog loading, indexing, and retrieval.

Self-contained module — no external dependencies beyond python-frontmatter.
"""

import logging
import re
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import frontmatter

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

logger = logging.getLogger(__name__)


@dataclass
class ProcessStep:
    """Process step definition."""

    key: str
    label: str
    content: str
    order: int


@dataclass
class ProcessDefinition:
    """Process definition loaded from markdown."""

    process_key: str
    name: str
    domain: str | None
    intents: list[str]
    steps: list[ProcessStep]
    full_content: str


@dataclass(frozen=True)
class ProcessCatalogEntry:
    """Lightweight indexed metadata for one process markdown file."""

    process_key: str
    name: str
    domain: str | None
    intents: tuple[str, ...]
    path: Path


@dataclass(frozen=True)
class ProcessMatch:
    """Scored match candidate returned by metadata retrieval."""

    entry: ProcessCatalogEntry
    score: float


def extract_steps_from_markdown(content: str) -> list[ProcessStep]:
    """Extract process steps from markdown content."""
    steps: list[ProcessStep] = []
    step_pattern = re.compile(r"^##\s+Step\s+(\d+):\s+(.+)$", re.MULTILINE)
    matches = list(step_pattern.finditer(content))

    for i, match in enumerate(matches):
        step_num = int(match.group(1))
        step_label = match.group(2).strip()
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        step_content = content[start_pos:end_pos].strip()
        steps.append(
            ProcessStep(
                key=f"step_{step_num}",
                label=step_label,
                content=step_content,
                order=step_num,
            )
        )

    return steps


class ProcessCatalogIndexService:
    """Builds lightweight metadata index and fetches full content on demand."""

    def __init__(self, shortlist_k: int = 3, cache_size: int = 32):
        self._shortlist_k = max(1, shortlist_k)
        self._cache_size = max(1, cache_size)
        self._content_cache: OrderedDict[str, ProcessDefinition] = OrderedDict()

    async def load_index(
        self,
        process_path: Path,
        log: logging.Logger | logging.LoggerAdapter | None = None,
    ) -> dict[str, ProcessCatalogEntry]:
        """Load process metadata index without storing full markdown content."""
        log = log or logger
        entries: dict[str, ProcessCatalogEntry] = {}
        if not process_path.exists():
            log.warning("Process content path does not exist: %s", process_path)
            return entries

        for md_file in process_path.glob("*.md"):
            try:
                content = md_file.read_text()
                post = frontmatter.loads(content)
                process_key = str(post.metadata["process_key"])
                name = str(post.metadata["name"])
                domain = post.metadata.get("domain")
                intents = tuple(str(intent) for intent in post.metadata.get("intents", []))
                entries[process_key] = ProcessCatalogEntry(
                    process_key=process_key,
                    name=name,
                    domain=str(domain) if domain is not None else None,
                    intents=intents,
                    path=md_file,
                )
            except Exception as e:
                log.error("Failed to index process file %s: %s", md_file, e)

        return entries

    def shortlist(
        self,
        conversation_buffer: list[str],
        entries: dict[str, ProcessCatalogEntry],
    ) -> list[ProcessMatch]:
        """Return top metadata matches for the latest conversation window."""
        query_text = " ".join(conversation_buffer[-6:]).lower()
        query_tokens = self._tokenize(query_text)
        if not query_tokens:
            return []

        matches: list[ProcessMatch] = []
        for entry in entries.values():
            candidate_tokens = self._tokenize(
                f"{entry.process_key} {entry.name} {entry.domain or ''} {' '.join(entry.intents)}"
            )
            overlap = len(query_tokens & candidate_tokens)
            phrase_hits = sum(1 for intent in entry.intents if intent.lower() in query_text)
            score = float(overlap + (phrase_hits * 2))
            if score > 0:
                matches.append(ProcessMatch(entry=entry, score=score))

        matches.sort(key=lambda match: match.score, reverse=True)
        return matches[: self._shortlist_k]

    def confidence_from_score(self, score: float, query_text: str) -> float:
        """Map raw metadata score to a rough 0-1 confidence value."""
        token_count = len(self._tokenize(query_text))
        scale = max(3, min(12, token_count))
        return max(0.0, min(0.99, score / float(scale)))

    def load_process_definition(
        self,
        entry: ProcessCatalogEntry,
        log: logging.Logger | logging.LoggerAdapter | None = None,
    ) -> ProcessDefinition | None:
        """Load and cache full process markdown for one selected candidate."""
        log = log or logger
        cached = self._content_cache.get(entry.process_key)
        if cached:
            self._content_cache.move_to_end(entry.process_key)
            return cached

        try:
            post = frontmatter.loads(entry.path.read_text())
            content = post.content
            definition = ProcessDefinition(
                process_key=entry.process_key,
                name=entry.name,
                domain=entry.domain,
                intents=list(entry.intents),
                steps=extract_steps_from_markdown(content),
                full_content=content,
            )
            self._content_cache[entry.process_key] = definition
            if len(self._content_cache) > self._cache_size:
                self._content_cache.popitem(last=False)
            return definition
        except Exception as e:
            log.error("Failed loading process content for %s: %s", entry.process_key, e)
            return None

    def estimate_step_index(
        self,
        process: ProcessDefinition,
        conversation_buffer: list[str],
        current_step: int,
    ) -> int:
        """Estimate next process step with deterministic token overlap scoring."""
        if not process.steps:
            return current_step

        query_text = " ".join(conversation_buffer[-6:]).lower()
        query_tokens = self._tokenize(query_text)
        if not query_tokens:
            return current_step

        best_index = current_step
        best_score = 0.0
        for idx in range(current_step, len(process.steps)):
            step = process.steps[idx]
            step_tokens = self._tokenize(f"{step.label} {step.content}".lower())
            overlap = len(query_tokens & step_tokens)
            label_hit = 1 if step.label.lower() in query_text else 0
            score = float(overlap + (label_hit * 2))
            if idx == current_step:
                score += 0.25
            if score > best_score:
                best_score = score
                best_index = idx

        if best_score <= 0:
            return current_step

        return min(best_index, current_step + 1)

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return set(_TOKEN_PATTERN.findall(text.lower()))
