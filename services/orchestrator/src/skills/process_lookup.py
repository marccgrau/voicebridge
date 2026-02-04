"""Process lookup skill for searching the process catalog.

This skill performs full-text search against the process_catalog table
and returns matching processes with relevance scores.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

from supabase import Client

from src.db import get_supabase_client

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    """A single process lookup result."""

    process_key: str
    name: str
    domain: str
    version: str
    score: float
    process_text: str
    steps_json: list[dict[str, Any]] | None = None


@dataclass
class ProcessLookupOutput:
    """Output from process lookup."""

    results: list[ProcessResult]
    query_time_ms: float


class ProcessLookupSkill:
    """Skill for searching the process catalog using full-text search.

    This skill is designed to be used as an LLM tool for process selection.
    It queries the process_catalog table using Postgres full-text search
    combined with trigram similarity for fuzzy matching.
    """

    def __init__(self, client: Client | None = None):
        """Initialize the skill.

        Args:
            client: Optional Supabase client. If not provided, uses the default.
        """
        self._client = client

    @property
    def client(self) -> Client:
        """Get the Supabase client."""
        if self._client is None:
            self._client = get_supabase_client()
        return self._client

    def search(
        self,
        query: str,
        *,
        locale: str = "en",
        domain: str | None = None,
        queue_tag: str | None = None,
        limit: int = 5,
    ) -> ProcessLookupOutput:
        """Search for processes matching the query.

        Args:
            query: Search query text (customer's question/issue)
            locale: Locale to filter by (default: "en")
            domain: Optional domain filter
            queue_tag: Optional queue tag filter
            limit: Maximum number of results (default: 5)

        Returns:
            ProcessLookupOutput with matching processes and timing info
        """
        start_time = time.perf_counter()

        logger.info(
            "Process lookup: query=%r, locale=%s, domain=%s, queue_tag=%s",
            query,
            locale,
            domain,
            queue_tag,
        )

        # Call the search_processes RPC function
        response = self.client.rpc(
            "search_processes",
            {
                "search_query": query,
                "search_locale": locale,
                "search_domain": domain,
                "search_queue_tag": queue_tag,
                "result_limit": limit,
            },
        ).execute()

        query_time_ms = (time.perf_counter() - start_time) * 1000

        results = [
            ProcessResult(
                process_key=row["process_key"],
                name=row["name"],
                domain=row["domain"],
                version=row["version"],
                score=float(row["rank"]),
                process_text=row["process_text"],
                steps_json=row.get("steps_json"),
            )
            for row in (response.data or [])
        ]

        logger.info(
            "Process lookup complete: found %d results in %.2fms",
            len(results),
            query_time_ms,
        )

        # Log results for auditability
        for i, result in enumerate(results):
            logger.debug(
                "Result %d: %s (score=%.3f)",
                i + 1,
                result.process_key,
                result.score,
            )

        return ProcessLookupOutput(results=results, query_time_ms=query_time_ms)

    def get_tool_definition(self) -> dict[str, Any]:
        """Get the tool definition for LLM function calling.

        Returns:
            Tool definition dict compatible with Anthropic's tool use format.
        """
        return {
            "name": "process_lookup",
            "description": (
                "Search the process catalog to find relevant customer service processes "
                "based on what the customer is asking about. Use this to identify which "
                "process/workflow applies to the customer's issue or request."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query describing what the customer needs help with. "
                            "Include key terms from the customer's request."
                        ),
                    },
                    "domain": {
                        "type": "string",
                        "description": (
                            "Optional domain filter (e.g., 'billing', 'orders', 'technical')"
                        ),
                    },
                },
                "required": ["query"],
            },
        }

    def format_for_llm(self, output: ProcessLookupOutput) -> str:
        """Format lookup results for LLM consumption.

        Args:
            output: The lookup output to format

        Returns:
            Formatted string for including in LLM context
        """
        if not output.results:
            return "No matching processes found."

        lines = ["Found the following relevant processes:\n"]
        for i, result in enumerate(output.results, 1):
            lines.append(f"{i}. **{result.name}** (`{result.process_key}`)")
            lines.append(f"   Domain: {result.domain}")
            lines.append(f"   Score: {result.score:.2f}")
            lines.append(f"   Description: {result.process_text[:200]}...")
            if result.steps_json:
                step_names = [s.get("label", s.get("key")) for s in result.steps_json]
                lines.append(f"   Steps: {' → '.join(step_names)}")
            lines.append("")

        return "\n".join(lines)


# Module-level convenience function
def process_lookup(
    query: str,
    *,
    locale: str = "en",
    domain: str | None = None,
    queue_tag: str | None = None,
    limit: int = 5,
    client: Client | None = None,
) -> ProcessLookupOutput:
    """Search for processes matching the query.

    This is a convenience function that creates a ProcessLookupSkill
    and performs a search. For repeated use, instantiate ProcessLookupSkill
    directly.

    Args:
        query: Search query text
        locale: Locale to filter by (default: "en")
        domain: Optional domain filter
        queue_tag: Optional queue tag filter
        limit: Maximum number of results
        client: Optional Supabase client

    Returns:
        ProcessLookupOutput with matching processes
    """
    skill = ProcessLookupSkill(client=client)
    return skill.search(
        query,
        locale=locale,
        domain=domain,
        queue_tag=queue_tag,
        limit=limit,
    )
