"""Tests for the Supabase database client."""

from unittest.mock import MagicMock, patch

from src.db.client import get_supabase_client, supabase_client


class TestGetSupabaseClient:
    """Tests for get_supabase_client function."""

    @patch("src.db.client.create_client")
    @patch("src.db.client.settings")
    def test_creates_client_with_settings(self, mock_settings, mock_create_client):
        """Test that client is created with correct settings."""
        # Clear the LRU cache before test
        get_supabase_client.cache_clear()

        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_service_role_key = "test-key"
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        client = get_supabase_client()

        # Verify create_client was called with correct arguments
        mock_create_client.assert_called_once_with(
            "https://test.supabase.co",
            "test-key",
        )
        assert client is mock_client

    @patch("src.db.client.create_client")
    @patch("src.db.client.settings")
    def test_returns_cached_client(self, mock_settings, mock_create_client):
        """Test that subsequent calls return cached client (singleton)."""
        # Clear the LRU cache before test
        get_supabase_client.cache_clear()

        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_service_role_key = "test-key"
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Call twice
        client1 = get_supabase_client()
        client2 = get_supabase_client()

        # Should only create once due to @lru_cache
        mock_create_client.assert_called_once()
        assert client1 is client2

    @patch("src.db.client.create_client")
    @patch("src.db.client.settings")
    def test_cache_info_reflects_caching(self, mock_settings, mock_create_client):
        """Test that cache_info shows cache is working."""
        # Clear the LRU cache before test
        get_supabase_client.cache_clear()

        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_service_role_key = "test-key"
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # First call - cache miss
        get_supabase_client()
        cache_info = get_supabase_client.cache_info()
        assert cache_info.hits == 0
        assert cache_info.misses == 1
        assert cache_info.currsize == 1

        # Second call - cache hit
        get_supabase_client()
        cache_info = get_supabase_client.cache_info()
        assert cache_info.hits == 1
        assert cache_info.misses == 1
        assert cache_info.currsize == 1

    @patch("src.db.client.create_client")
    @patch("src.db.client.settings")
    def test_cache_clear_resets_client(self, mock_settings, mock_create_client):
        """Test that cache_clear allows creating new client."""
        get_supabase_client.cache_clear()

        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_service_role_key = "test-key"
        mock_client1 = MagicMock()
        mock_client2 = MagicMock()
        mock_create_client.side_effect = [mock_client1, mock_client2]

        # First call
        client1 = get_supabase_client()
        assert client1 is mock_client1

        # Clear cache
        get_supabase_client.cache_clear()

        # Second call should create new client
        client2 = get_supabase_client()
        assert client2 is mock_client2
        assert mock_create_client.call_count == 2


class TestSupabaseClientAlias:
    """Tests for the supabase_client alias."""

    def test_alias_points_to_same_function(self):
        """Test that supabase_client is an alias for get_supabase_client."""
        assert supabase_client is get_supabase_client

    @patch("src.db.client.create_client")
    @patch("src.db.client.settings")
    def test_alias_returns_same_client(self, mock_settings, mock_create_client):
        """Test that calling via alias returns same cached client."""
        get_supabase_client.cache_clear()

        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_service_role_key = "test-key"
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Call via function and alias
        client1 = get_supabase_client()
        client2 = supabase_client()

        # Should be same cached instance
        assert client1 is client2
        mock_create_client.assert_called_once()
