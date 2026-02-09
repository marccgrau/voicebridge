"""Service for generating session summaries from transcripts."""

import logging
from typing import TypedDict

import anthropic

from ..config import settings

logger = logging.getLogger(__name__)


class TranscriptSegment(TypedDict):
    """Transcript segment data."""

    speaker: str
    text: str
    ts: str


class SummaryService:
    """Service for generating AI summaries from conversation transcripts."""

    def __init__(self, api_key: str | None = None, model: str = "claude-haiku-4-5-20251001"):
        """
        Initialize the summary service.

        Args:
            api_key: Anthropic API key (defaults to settings.anthropic_api_key)
            model: Model to use for summary generation
        """
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for summary generation")

        self.model = model
        self._client = anthropic.Anthropic(api_key=self.api_key)
        logger.info("SummaryService initialized with model=%s", model)

    def generate_summary(self, segments: list[TranscriptSegment], max_tokens: int = 512) -> str:
        """
        Generate a summary from transcript segments.

        Args:
            segments: List of transcript segments with speaker, text, and timestamp
            max_tokens: Maximum tokens for the summary

        Returns:
            Generated summary text

        Raises:
            ValueError: If segments list is empty
            anthropic.APIError: If API call fails
        """
        if not segments:
            raise ValueError("Cannot generate summary from empty transcript")

        # Format transcript for LLM
        transcript_text = "\n".join(f"[{seg['speaker'].upper()}] {seg['text']}" for seg in segments)

        logger.info("Generating summary for transcript with %d segments", len(segments))

        try:
            message = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Summarize the following customer service call transcript in 3-5 sentences.
                        Focus on: the customer's issue, actions taken by the agent, and the outcome/resolution.
                        Write in past tense, third person. Be concise and factual.
                        The summary should be suitable for internal use by customer support teams to quickly understand the call without reading the full transcript.
                        The conversation may have transcription errors, infer the intended meaning where possible.

                        Transcript:
                        {transcript_text}""",  # noqa: E501
                    }
                ],
            )

            summary_text = message.content[0].text.strip()
            logger.info("Summary generated successfully (%d chars)", len(summary_text))
            return summary_text

        except anthropic.APIError as e:
            logger.error("Failed to generate summary: %s", e)
            raise
