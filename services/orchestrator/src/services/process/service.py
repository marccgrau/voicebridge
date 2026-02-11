"""Process catalog loading and markdown parsing."""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import frontmatter


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


class ProcessService:
    """Loads process markdown files and parses step metadata."""

    async def load_process_catalog(
        self,
        process_path: Path,
        logger: logging.Logger | logging.LoggerAdapter,
    ) -> dict[str, ProcessDefinition]:
        """Load process definitions from markdown files."""
        processes: dict[str, ProcessDefinition] = {}

        if not process_path.exists():
            logger.warning("Process content path does not exist: %s", process_path)
            return processes

        for md_file in process_path.glob("*.md"):
            try:
                content = md_file.read_text()
                post = frontmatter.loads(content)

                process_def = ProcessDefinition(
                    process_key=post.metadata["process_key"],
                    name=post.metadata["name"],
                    domain=post.metadata.get("domain"),
                    intents=post.metadata.get("intents", []),
                    steps=self.extract_steps_from_markdown(post.content),
                    full_content=post.content,
                )
                processes[process_def.process_key] = process_def
                logger.debug(
                    "Loaded process: %s (%d steps)", process_def.name, len(process_def.steps)
                )
            except Exception as e:
                logger.error("Failed to load process file %s: %s", md_file, e)

        return processes

    @staticmethod
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
