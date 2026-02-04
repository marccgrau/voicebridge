"""Supabase client for database operations."""

from functools import lru_cache

from supabase import Client, create_client

from src.config import settings


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Get or create a cached Supabase client instance."""
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )


# Convenience alias
supabase_client = get_supabase_client
