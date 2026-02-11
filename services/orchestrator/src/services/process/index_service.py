"""Process catalog indexing and retrieval helpers for direct_call mode."""

import logging
import re
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import frontmatter

from .service import ProcessDefinition, ProcessService

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


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


class ProcessCatalogIndexService:
    """Builds lightweight metadata index and fetches full content on demand."""

    def __init__(self, shortlist_k: int = 3, cache_size: int = 32):
        self._shortlist_k = max(1, shortlist_k)
        self._cache_size = max(1, cache_size)
        self._content_cache: OrderedDict[str, ProcessDefinition] = OrderedDict()

    async def load_index(
        self,
        process_path: Path,
        logger: logging.Logger | logging.LoggerAdapter,
    ) -> dict[str, ProcessCatalogEntry]:
        """Load process metadata index without storing full markdown content."""
        entries: dict[str, ProcessCatalogEntry] = {}
        if not process_path.exists():
            logger.warning("Process content path does not exist: %s", process_path)
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
                logger.error("Failed to index process file %s: %s", md_file, e)

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
        logger: logging.Logger | logging.LoggerAdapter,
    ) -> ProcessDefinition | None:
        """Load and cache full process markdown for one selected candidate."""
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
                steps=ProcessService.extract_steps_from_markdown(content),
                full_content=content,
            )
            self._content_cache[entry.process_key] = definition
            if len(self._content_cache) > self._cache_size:
                self._content_cache.popitem(last=False)
            return definition
        except Exception as e:
            logger.error("Failed loading process content for %s: %s", entry.process_key, e)
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

        # Keep progression monotonic and avoid large jumps from one turn.
        return min(best_index, current_step + 1)

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return set(_TOKEN_PATTERN.findall(text.lower()))
