"""Unit tests for configuration."""
import pytest
from config import Settings


class TestSettings:
    """Test settings configuration."""
    
    def test_default_values(self):
        """Test default settings values are loaded."""
        settings = Settings()
        
        # Agent Configuration
        assert settings.MAX_ITERATIONS == 10
        assert settings.CONFIDENCE_THRESHOLD == 0.7
        
        # Business Logic Thresholds
        assert settings.CLAIM_AMOUNT_THRESHOLD == 1_000_000_000
        assert settings.CLAIM_AMOUNT_TOLERANCE == 0.01
        
        # Decision Agent Thresholds
        assert settings.CRITICAL_THRESHOLD == 1
        assert settings.HIGH_THRESHOLD == 3
        assert settings.MEDIUM_THRESHOLD == 5
        assert settings.SCORE_THRESHOLD == 8
        
    def test_prior_auth_medications_list(self):
        """Test prior auth medications are parsed correctly."""
        settings = Settings()
        
        medications = settings.prior_auth_medications_list
        assert isinstance(medications, list)
        assert "morphine" in medications
        assert "warfarin" in medications
        
    def test_custom_thresholds_via_env(self, monkeypatch):
        """Test thresholds can be overridden via environment variables."""
        monkeypatch.setenv("CRITICAL_THRESHOLD", "2")
        monkeypatch.setenv("HIGH_THRESHOLD", "5")
        monkeypatch.setenv("MEDIUM_THRESHOLD", "10")
        
        # Reload settings to pick up env vars
        from importlib import reload
        import config
        reload(config)
        
        # Settings should use env values
        # Note: In actual tests, you'd need to re-instantiate
        assert config.settings.CRITICAL_THRESHOLD == 2
        assert config.settings.HIGH_THRESHOLD == 5
