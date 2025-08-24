"""
Tests for nl2audio prep LLM functionality.
"""

from unittest.mock import Mock, patch

from nl2audio.config import AppConfig, PrepConfig
from nl2audio.prep import llm_clean_for_tts
from nl2audio.validators import validate_prep_config


class TestPrepConfig:
    """Test prep configuration validation."""

    def test_prep_config_defaults(self):
        """Test that prep config has correct defaults."""
        config = AppConfig()

        assert config.prep.enabled is False
        assert config.prep.model == "gpt-3.5-turbo"
        assert config.prep.temperature == 0.3
        assert config.prep.max_tokens == 2000

    def test_prep_config_custom_values(self):
        """Test prep config with custom values."""
        prep_config = PrepConfig(
            enabled=True, model="gpt-4o", temperature=0.7, max_tokens=3000
        )

        assert prep_config.enabled is True
        assert prep_config.model == "gpt-4o"
        assert prep_config.temperature == 0.7
        assert prep_config.max_tokens == 3000


class TestPrepValidation:
    """Test prep configuration validation."""

    def test_validate_prep_config_disabled(self, sample_config):
        """Test prep validation when prep is disabled."""
        sample_config.prep.enabled = False
        results = validate_prep_config(sample_config)

        # Should still validate config values even when disabled
        assert len(results) == 4  # model, temperature, max_tokens, status

        # All config values should pass validation (except the one we're testing)
        config_results = [
            r for r in results if r.name not in ["Prep Status", "Prep Model"]
        ]
        assert all(r.status == "pass" for r in config_results)

        # Status should show disabled
        status_result = [r for r in results if r.name == "Prep Status"][0]
        assert status_result.status == "warn"
        assert "disabled" in status_result.message

    def test_validate_prep_config_enabled(self, sample_config):
        """Test prep validation when prep is enabled."""
        sample_config.prep.enabled = True
        results = validate_prep_config(sample_config)

        assert len(results) == 4
        assert all(r.status == "pass" for r in results)

        status_result = [r for r in results if r.name == "Prep Status"][0]
        assert status_result.status == "pass"
        assert "enabled and ready to use" in status_result.message

    def test_validate_prep_config_invalid_model(self, sample_config):
        """Test prep validation with invalid model."""
        sample_config.prep.model = "invalid-model"
        results = validate_prep_config(sample_config)

        model_result = [r for r in results if r.name == "Prep Model"][0]
        assert model_result.status == "fail"
        assert "Invalid model" in model_result.message
        assert "gpt-3.5-turbo" in model_result.message
        assert "gpt-4o" in model_result.message

    def test_validate_prep_config_invalid_temperature(self, sample_config):
        """Test prep validation with invalid temperature."""
        sample_config.prep.temperature = 3.0  # Too high
        results = validate_prep_config(sample_config)

        temp_result = [r for r in results if r.name == "Prep Temperature"][0]
        assert temp_result.status == "fail"
        assert "Temperature must be between 0.0 and 2.0" in temp_result.message
        assert "got: 3.0" in temp_result.message

        # Test too low
        sample_config.prep.temperature = -0.5
        results = validate_prep_config(sample_config)

        temp_result = [r for r in results if r.name == "Prep Temperature"][0]
        assert temp_result.status == "fail"
        assert "got: -0.5" in temp_result.message

    def test_validate_prep_config_invalid_max_tokens(self, sample_config):
        """Test prep validation with invalid max_tokens."""
        sample_config.prep.max_tokens = 50  # Too low
        results = validate_prep_config(sample_config)

        tokens_result = [r for r in results if r.name == "Prep Max Tokens"][0]
        assert tokens_result.status == "fail"
        assert "Max tokens must be between 100 and 4000" in tokens_result.message
        assert "got: 50" in tokens_result.message

        # Test too high
        sample_config.prep.max_tokens = 5000
        results = validate_prep_config(sample_config)

        tokens_result = [r for r in results if r.name == "Prep Max Tokens"][0]
        assert tokens_result.status == "fail"
        assert "got: 5000" in tokens_result.message

    def test_validate_prep_config_valid_values(self, sample_config):
        """Test prep validation with all valid values."""
        sample_config.prep.enabled = True
        sample_config.prep.model = "gpt-4o"
        sample_config.prep.temperature = 0.5
        sample_config.prep.max_tokens = 1500

        results = validate_prep_config(sample_config)

        assert len(results) == 4
        assert all(r.status == "pass" for r in results)

        # Check specific values
        model_result = [r for r in results if r.name == "Prep Model"][0]
        assert "gpt-4o" in model_result.message

        temp_result = [r for r in results if r.name == "Prep Temperature"][0]
        assert "0.5" in temp_result.message

        tokens_result = [r for r in results if r.name == "Prep Max Tokens"][0]
        assert "1500" in tokens_result.message


class TestPrepModule:
    """Test the prep module functionality."""

    @patch("nl2audio.prep.check_openai_api_key")
    @patch("nl2audio.prep.OpenAI")
    def test_llm_clean_for_tts_success(
        self, mock_openai, mock_check_key, sample_config
    ):
        """Test successful LLM prep call."""
        # Mock API key check
        mock_check_key.return_value = "sk-test123"

        # Mock OpenAI client and response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "Rewritten newsletter text for better TTS quality."
        )
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 150

        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        # Test the function
        result = llm_clean_for_tts(
            text="Original newsletter text",
            model="gpt-3.5-turbo",
            temperature=0.3,
            max_tokens=2000,
        )

        # Verify result
        assert result == "Rewritten newsletter text for better TTS quality."

        # Verify OpenAI call was made correctly
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args
        assert call_args[1]["model"] == "gpt-3.5-turbo"
        assert call_args[1]["temperature"] == 0.3
        assert call_args[1]["max_tokens"] == 2000
        assert "Original newsletter text" in call_args[1]["messages"][0]["content"]

    @patch("nl2audio.prep.check_openai_api_key")
    @patch("nl2audio.prep.OpenAI")
    def test_llm_clean_for_tts_api_failure(self, mock_openai, mock_check_key):
        """Test LLM prep call when API fails."""
        # Mock API key check
        mock_check_key.return_value = "sk-test123"

        # Mock OpenAI client to raise exception
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception(
            "API rate limit exceeded"
        )
        mock_openai.return_value = mock_client

        original_text = "Original newsletter text that should be preserved"

        # Test the function
        result = llm_clean_for_tts(
            text=original_text, model="gpt-4o", temperature=0.5, max_tokens=1000
        )

        # Should return original text on failure
        assert result == original_text

    @patch("nl2audio.prep.check_openai_api_key")
    def test_llm_clean_for_tts_api_key_failure(self, mock_check_key):
        """Test LLM prep call when API key check fails."""
        # Mock API key check to fail
        mock_check_key.side_effect = Exception("Invalid API key")

        original_text = "Original newsletter text"

        # Test the function
        result = llm_clean_for_tts(
            text=original_text, model="gpt-3.5-turbo", temperature=0.3, max_tokens=2000
        )

        # Should return original text on failure
        assert result == original_text

    def test_llm_clean_for_tts_prompt_content(self, sample_config):
        """Test that the prompt contains the expected content."""
        with (
            patch("nl2audio.prep.check_openai_api_key") as mock_check_key,
            patch("nl2audio.prep.OpenAI") as mock_openai,
        ):

            mock_check_key.return_value = "sk-test123"
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Rewritten text"
            mock_response.usage = Mock()
            mock_response.usage.total_tokens = 100

            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            test_text = "Test newsletter content"

            llm_clean_for_tts(
                text=test_text, model="gpt-3.5-turbo", temperature=0.3, max_tokens=2000
            )

            # Verify prompt contains the input text
            call_args = mock_client.chat.completions.create.call_args
            prompt_content = call_args[1]["messages"][0]["content"]
            assert test_text in prompt_content
            assert "read-aloud friendly" in prompt_content
            assert "conversational" in prompt_content


class TestPrepIntegration:
    """Test prep integration with CLI commands."""

    def test_prep_config_in_sample_config(self, sample_config):
        """Test that sample config includes prep configuration."""
        assert hasattr(sample_config, "prep")
        assert isinstance(sample_config.prep, PrepConfig)
        assert sample_config.prep.enabled is False  # Default should be False
        assert sample_config.prep.model == "gpt-3.5-turbo"

    def test_prep_config_serialization(self, sample_config):
        """Test that prep config can be serialized/deserialized."""
        # This tests that the config structure is compatible with TOML
        prep_config = sample_config.prep

        # Test that all fields are accessible
        assert prep_config.enabled is False
        assert prep_config.model == "gpt-3.5-turbo"
        assert prep_config.temperature == 0.3
        assert prep_config.max_tokens == 2000

        # Test that we can modify and access values
        prep_config.enabled = True
        prep_config.model = "gpt-4o"
        assert prep_config.enabled is True
        assert prep_config.model == "gpt-4o"
