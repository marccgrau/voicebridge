"""Process catalog loading for LLM tool calling.

Loads process definitions from markdown files and exposes functions
suitable as LLM tool handlers.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import frontmatter

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


class ProcessCatalog:
    """Loads process definitions from markdown files and provides tool handler data."""

    def __init__(self, process_content_path: str):
        self._path = Path(process_content_path)
        self._definitions: dict[str, ProcessDefinition] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all process definitions from markdown files."""
        if self._loaded:
            return

        if not self._path.exists():
            logger.warning("Process content path does not exist: %s", self._path)
            self._loaded = True
            return

        for md_file in self._path.glob("*.md"):
            try:
                content = md_file.read_text()
                post = frontmatter.loads(content)
                process_key = str(post.metadata["process_key"])
                name = str(post.metadata["name"])
                domain = post.metadata.get("domain")
                intents = [str(i) for i in post.metadata.get("intents", [])]
                steps = extract_steps_from_markdown(post.content)

                self._definitions[process_key] = ProcessDefinition(
                    process_key=process_key,
                    name=name,
                    domain=str(domain) if domain is not None else None,
                    intents=intents,
                    steps=steps,
                    full_content=post.content,
                )
            except Exception as e:
                logger.error("Failed to load process file %s: %s", md_file, e)

        self._loaded = True
        logger.info("Loaded %d process definitions", len(self._definitions))

    def get_catalog_summary(self) -> str:
        """Return a summary of all processes for the LLM to browse."""
        self.load()
        if not self._definitions:
            return "No processes available in the catalog."

        lines = []
        for defn in self._definitions.values():
            intents_str = ", ".join(defn.intents[:5])
            lines.append(
                f"- {defn.process_key}: {defn.name} "
                f"(domain: {defn.domain or 'general'}, "
                f"intents: {intents_str})"
            )
        return "Available processes:\n" + "\n".join(lines)

    def get_process_definition(self, process_key: str) -> str:
        """Return full process definition for a specific process."""
        self.load()
        defn = self._definitions.get(process_key)
        if not defn:
            return f"Process '{process_key}' not found in catalog."

        steps_str = "\n".join(
            f"  Step {s.order}: {s.label}" for s in defn.steps
        )
        return (
            f"Process: {defn.name} ({defn.process_key})\n"
            f"Domain: {defn.domain or 'general'}\n"
            f"Steps:\n{steps_str}\n\n"
            f"Full Content:\n{defn.full_content}"
        )

    def get_definition(self, process_key: str) -> ProcessDefinition | None:
        """Return the ProcessDefinition object for a given key."""
        self.load()
        return self._definitions.get(process_key)
