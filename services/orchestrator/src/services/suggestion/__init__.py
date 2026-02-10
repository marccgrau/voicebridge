"""Suggestion service package."""

from .contracts import SuggestionServiceInput, SuggestionServiceResult
from .service import SuggestionService

__all__ = ["SuggestionServiceInput", "SuggestionServiceResult", "SuggestionService"]
