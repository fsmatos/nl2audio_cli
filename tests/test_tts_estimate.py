"""
Tests for nl2audio TTS estimation functionality.
"""
import pytest
from pathlib import Path
import tempfile
import json

from nl2audio.tts import estimate_tts, synthesize, chunk_text, _clean_text
from nl2audio.validation import ValidationError


class TestTTSEstimation:
    """Test TTS estimation functionality."""
    
    def test_estimate_tts_basic(self, plain_text):
        """Test basic TTS estimation."""
        estimation = estimate_tts(plain_text)
        
        # Check required fields
        assert "total_characters" in estimation
        assert "total_words" in estimation
        assert "num_chunks" in estimation
        assert "estimated_minutes" in estimation
        assert "estimated_cost_usd" in estimation
        assert "model" in estimation
        assert "voice" in estimation
        
        # Check data types
        assert isinstance(estimation["total_characters"], int)
        assert isinstance(estimation["total_words"], int)
        assert isinstance(estimation["num_chunks"], int)
        assert isinstance(estimation["estimated_minutes"], float)
        assert isinstance(estimation["estimated_cost_usd"], float)
        
        # Check values are reasonable
        assert estimation["total_characters"] > 0
        assert estimation["total_words"] > 0
        assert estimation["num_chunks"] > 0
        assert estimation["estimated_minutes"] > 0
        assert estimation["estimated_cost_usd"] > 0
    
    def test_estimate_tts_cost_calculation(self, plain_text):
        """Test that cost calculation is accurate."""
        estimation = estimate_tts(plain_text)
        
        # Cost should be based on character count
        expected_cost = (estimation["total_characters"] / 1000) * 0.00015
        assert abs(estimation["estimated_cost_usd"] - expected_cost) < 0.0001
    
    def test_estimate_tts_chunking(self, newsletter_html):
        """Test that text chunking works correctly in estimation."""
        estimation = estimate_tts(newsletter_html)
        
        # Should have multiple chunks for longer text
        assert estimation["num_chunks"] > 1
        
        # Average chunk size should be reasonable
        assert estimation["avg_chunk_size"] > 0
        assert estimation["avg_chunk_size"] <= 3500  # Max chunk size
    
    def test_estimate_tts_voice_variation(self, plain_text):
        """Test estimation with different voices."""
        estimation_alloy = estimate_tts(plain_text, voice="alloy")
        estimation_echo = estimate_tts(plain_text, voice="echo")
        
        # Character counts should be the same
        assert estimation_alloy["total_characters"] == estimation_echo["total_characters"]
        
        # Voice should be set correctly
        assert estimation_alloy["voice"] == "alloy"
        assert estimation_echo["voice"] == "echo"
    
    def test_estimate_tts_model_variation(self, plain_text):
        """Test estimation with different models."""
        estimation = estimate_tts(plain_text, model="gpt-4o-mini-tts")
        
        assert estimation["model"] == "gpt-4o-mini-tts"
    
    def test_estimate_tts_text_preview(self, plain_text):
        """Test that text preview is generated correctly."""
        estimation = estimate_tts(plain_text)
        
        assert "text_preview" in estimation
        assert isinstance(estimation["text_preview"], str)
        
        # Preview should be truncated if text is long
        if len(plain_text) > 200:
            assert estimation["text_preview"].endswith("...")
            assert len(estimation["text_preview"]) <= 203  # 200 + "..."
        else:
            assert estimation["text_preview"] == plain_text
    
    def test_estimate_tts_empty_text(self):
        """Test estimation with empty text."""
        estimation = estimate_tts("")
        
        assert estimation["total_characters"] == 0
        assert estimation["total_words"] == 0
        assert estimation["num_chunks"] == 0
        assert estimation["estimated_minutes"] == 0
        assert estimation["estimated_cost_usd"] == 0
    
    def test_estimate_tts_very_long_text(self):
        """Test estimation with very long text."""
        # Create a very long text
        long_text = "This is a test sentence. " * 1000  # ~25,000 characters
        
        estimation = estimate_tts(long_text)
        
        assert estimation["total_characters"] > 20000
        assert estimation["num_chunks"] > 5  # Should be chunked
        assert estimation["estimated_minutes"] > 1.0  # Should be over 1 minute


class TestTTSSynthesizeDryRun:
    """Test TTS synthesis in dry-run mode."""
    
    def test_synthesize_dry_run(self, plain_text, temp_dir):
        """Test synthesize function in dry-run mode."""
        out_path = temp_dir / "test.mp3"
        
        # Should not create actual audio file in dry-run mode
        result = synthesize(plain_text, "alloy", out_path, dry_run=True)
        
        # Should return estimation dict, not bytes
        assert isinstance(result, dict)
        assert "total_characters" in result
        assert "estimated_cost_usd" in result
        
        # Should not create output file
        assert not out_path.exists()
    
    def test_synthesize_dry_run_vs_estimate(self, plain_text, temp_dir):
        """Test that dry-run and estimate_tts return same results."""
        out_path = temp_dir / "test.mp3"
        
        estimation = estimate_tts(plain_text)
        dry_run_result = synthesize(plain_text, "alloy", out_path, dry_run=True)
        
        # Results should be identical
        assert estimation == dry_run_result
    
    def test_synthesize_normal_mode(self, plain_text, temp_dir, mock_openai_client):
        """Test synthesize function in normal mode (not dry-run)."""
        out_path = temp_dir / "test.mp3"
        
        # Should create actual audio file in normal mode
        result = synthesize(plain_text, "alloy", out_path, dry_run=False)
        
        # Should return bytes (audio data)
        assert isinstance(result, bytes)
        assert len(result) > 0
        
        # Should create output file
        assert out_path.exists()


class TestTTSChunking:
    """Test text chunking functionality used in estimation."""
    
    def test_chunk_text_basic(self, plain_text):
        """Test basic text chunking."""
        chunks = chunk_text(plain_text)
        
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        
        # Each chunk should be within limits
        for chunk in chunks:
            assert len(chunk) <= 3500
            assert len(chunk) > 0
    
    def test_chunk_text_strategies(self, newsletter_html):
        """Test different chunking strategies."""
        # Smart strategy (default)
        smart_chunks = chunk_text(newsletter_html, strategy="smart")
        
        # Paragraph strategy
        para_chunks = chunk_text(newsletter_html, strategy="paragraph")
        
        # Sentence strategy
        sent_chunks = chunk_text(newsletter_html, strategy="sentence")
        
        # All should produce valid chunks
        assert len(smart_chunks) > 0
        assert len(para_chunks) > 0
        assert len(sent_chunks) > 0
        
        # Different strategies may produce different numbers of chunks
        # but all should be valid
        for chunks in [smart_chunks, para_chunks, sent_chunks]:
            for chunk in chunks:
                assert len(chunk) <= 3500
                assert len(chunk) > 0
    
    def test_chunk_text_empty(self):
        """Test chunking empty text."""
        chunks = chunk_text("")
        assert chunks == []
    
    def test_chunk_text_single_word(self):
        """Test chunking single word."""
        chunks = chunk_text("Hello")
        assert len(chunks) == 1
        assert chunks[0] == "Hello"


class TestTTSCleaning:
    """Test text cleaning functionality used in estimation."""
    
    def test_clean_text_basic(self):
        """Test basic text cleaning."""
        dirty_text = "  This   has   extra   spaces  \n\n\nAnd   newlines  "
        cleaned = _clean_text(dirty_text)
        
        # Should remove excessive whitespace
        assert "   " not in cleaned
        assert "\n\n\n" not in cleaned
        
        # Should preserve content
        assert "This has extra spaces" in cleaned
        assert "And newlines" in cleaned
    
    def test_clean_text_normalization(self):
        """Test text normalization."""
        text = "  Test   text  with  spacing  "
        cleaned = _clean_text(text)
        
        # Should be trimmed and normalized
        assert cleaned == "Test text with spacing"
    
    def test_clean_text_preserves_content(self):
        """Test that cleaning preserves important content."""
        original = "This is important content with\n\nparagraphs and\n\nstructure."
        cleaned = _clean_text(original)
        
        # Should preserve words and basic structure
        assert "important content" in cleaned
        assert "paragraphs" in cleaned
        assert "structure" in cleaned


class TestTTSErrorHandling:
    """Test TTS error handling."""
    
    def test_estimate_tts_invalid_voice(self, plain_text):
        """Test estimation with invalid voice (should still work)."""
        # Invalid voice should not break estimation
        estimation = estimate_tts(plain_text, voice="invalid_voice")
        
        assert estimation["voice"] == "invalid_voice"
        assert estimation["total_characters"] > 0
    
    def test_estimate_tts_invalid_model(self, plain_text):
        """Test estimation with invalid model (should use default pricing)."""
        estimation = estimate_tts(plain_text, model="invalid_model")
        
        # Should still work with default pricing
        assert estimation["model"] == "invalid_model"
        assert estimation["estimated_cost_usd"] > 0 