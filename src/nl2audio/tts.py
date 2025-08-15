from __future__ import annotations

import io
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from openai import OpenAI
from pydub import AudioSegment
from pydub.effects import normalize as pydub_normalize

from .logging import get_logger, log_debug, log_error, log_info, log_warning
from .validation import ValidationError, check_openai_api_key


class TTSLengthError(Exception):
    pass


# OpenAI TTS pricing (as of 2024, in USD per 1K characters)
TTS_PRICING = {"gpt-4o-mini-tts": 0.00015}  # $0.00015 per 1K characters


def estimate_tts(
    text: str, voice: str = "alloy", model: str = "gpt-4o-mini-tts"
) -> Dict[str, Any]:
    """
    Estimate TTS cost and processing details without making API calls.

    Args:
        text: Input text to estimate
        voice: Voice to use (for future pricing variations)
        model: TTS model to use

    Returns:
        Dictionary with estimation details
    """
    logger = get_logger()

    # Clean and chunk text
    cleaned_text = _clean_text(text)
    chunks = chunk_text(cleaned_text)

    # Calculate statistics
    total_chars = len(cleaned_text)
    num_chunks = len(chunks)
    avg_chunk_size = total_chars / num_chunks if num_chunks > 0 else 0

    # Estimate audio duration (rough approximation: 150 words per minute)
    words = len(cleaned_text.split())
    estimated_minutes = words / 150

    # Calculate cost
    price_per_1k = TTS_PRICING.get(model, TTS_PRICING["gpt-4o-mini-tts"])
    estimated_cost = (total_chars / 1000) * price_per_1k

    # Check if text exceeds limits
    max_chars_per_chunk = 3500
    chunks_over_limit = [chunk for chunk in chunks if len(chunk) > max_chars_per_chunk]

    estimation = {
        "total_characters": total_chars,
        "total_words": words,
        "num_chunks": num_chunks,
        "avg_chunk_size": round(avg_chunk_size, 1),
        "estimated_minutes": round(estimated_minutes, 1),
        "estimated_cost_usd": round(estimated_cost, 4),
        "model": model,
        "voice": voice,
        "chunks_over_limit": len(chunks_over_limit),
        "max_chars_per_chunk": max_chars_per_chunk,
        "text_preview": (
            cleaned_text[:200] + "..." if len(cleaned_text) > 200 else cleaned_text
        ),
    }

    logger.info(
        f"TTS estimation: {total_chars} chars, {num_chunks} chunks, "
        f"~{estimated_minutes:.1f} min, ${estimated_cost:.4f}"
    )

    return estimation


def _clean_text(text: str) -> str:
    """Clean and normalize text for better TTS processing."""
    # Remove excessive whitespace and normalize line breaks
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = re.sub(r" +", " ", text)
    text = text.strip()
    return text


def _is_sentence_end(char: str) -> bool:
    """Check if character indicates end of sentence."""
    return char in ".!?"


def _find_safe_break_point(text: str, max_chars: int, start_pos: int = 0) -> int:
    """Find the best break point within the character limit."""
    if len(text) <= max_chars:
        return len(text)

    # Look for sentence endings first
    for i in range(min(max_chars, len(text) - 1), start_pos, -1):
        if _is_sentence_end(text[i]):
            # Ensure we don't break on abbreviations (e.g., "Mr.", "Dr.", "U.S.")
            if (
                i > 0
                and text[i - 1].isupper()
                and i < len(text) - 1
                and text[i + 1].isspace()
            ):
                continue
            return i + 1

    # Look for paragraph breaks
    for i in range(min(max_chars, len(text) - 1), start_pos, -1):
        if text[i] == "\n":
            return i + 1

    # Look for natural pause points (commas, semicolons)
    for i in range(min(max_chars, len(text) - 1), start_pos, -1):
        if text[i] in ",;":
            return i + 1

    # Look for word boundaries
    for i in range(min(max_chars, len(text) - 1), start_pos, -1):
        if text[i].isspace():
            return i + 1

    # If all else fails, break at max_chars
    return max_chars


def _split_into_paragraphs(text: str) -> List[str]:
    """Split text into logical paragraphs."""
    paragraphs = []
    current_para = ""

    for line in text.split("\n"):
        line = line.strip()
        if line:
            current_para += line + " "
        elif current_para:
            paragraphs.append(current_para.strip())
            current_para = ""

    if current_para:
        paragraphs.append(current_para.strip())

    return paragraphs


def chunk_text(text: str, max_chars: int = 3500, strategy: str = "smart") -> List[str]:
    """
    Intelligently chunk text for TTS processing.

    Args:
        text: Input text to chunk
        max_chars: Maximum characters per chunk
        strategy: Chunking strategy ('smart', 'paragraph', 'sentence')

    Returns:
        List of text chunks optimized for TTS
    """
    text = _clean_text(text)

    if strategy == "paragraph":
        return _chunk_by_paragraphs(text, max_chars)
    elif strategy == "sentence":
        return _chunk_by_sentences(text, max_chars)
    else:  # smart strategy
        return _chunk_smart(text, max_chars)


def _chunk_smart(text: str, max_chars: int) -> List[str]:
    """Smart chunking that balances paragraph structure with optimal chunk sizes."""
    chunks = []
    current_chunk = ""

    # First, try to preserve paragraph structure
    paragraphs = _split_into_paragraphs(text)

    for para in paragraphs:
        # If adding this paragraph would exceed limit, process current chunk
        if len(current_chunk) + len(para) + 1 > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = ""

        # If paragraph is too long, split it
        if len(para) > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            # Split long paragraph
            while para:
                break_point = _find_safe_break_point(para, max_chars)
                chunk_part = para[:break_point]
                chunks.append(chunk_part.strip())
                para = para[break_point:].strip()
        else:
            # Add paragraph to current chunk
            if current_chunk:
                current_chunk += " " + para
            else:
                current_chunk = para

    # Add remaining chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def _chunk_by_paragraphs(text: str, max_chars: int) -> List[str]:
    """Chunk text by paragraphs, splitting long paragraphs when necessary."""
    chunks = []
    paragraphs = _split_into_paragraphs(text)

    for para in paragraphs:
        if len(para) <= max_chars:
            chunks.append(para)
        else:
            # Split long paragraph
            while para:
                break_point = _find_safe_break_point(para, max_chars)
                chunk_part = para[:break_point]
                chunks.append(chunk_part.strip())
                para = para[break_point:].strip()

    return chunks


def _chunk_by_sentences(text: str, max_chars: int) -> List[str]:
    """Chunk text by sentences, ensuring optimal chunk sizes."""
    chunks = []
    current_chunk = ""

    # Split by sentence endings, but be careful with abbreviations
    sentences = re.split(r"(?<=[.!?])\s+", text)

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        # If adding this sentence would exceed limit, start new chunk
        if len(current_chunk) + len(sentence) + 1 > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = ""

        # If sentence is too long, split it
        if len(sentence) > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            # Split long sentence
            while sentence:
                break_point = _find_safe_break_point(sentence, max_chars)
                chunk_part = sentence[:break_point]
                chunks.append(chunk_part.strip())
                sentence = sentence[break_point:].strip()
        else:
            # Add sentence to current chunk
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence

    # Add remaining chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def _optimize_chunk_size(chunks: List[str], target_chars: int = 3500) -> List[str]:
    """Optimize chunk sizes for better TTS quality."""
    if not chunks:
        return chunks

    optimized = []
    current_chunk = ""

    for chunk in chunks:
        # If current chunk is too small and next chunk would fit, combine them
        if (
            len(current_chunk) < target_chars * 0.7
            and len(current_chunk) + len(chunk) + 1 <= target_chars
        ):
            if current_chunk:
                current_chunk += " " + chunk
            else:
                current_chunk = chunk
        else:
            if current_chunk:
                optimized.append(current_chunk.strip())
            current_chunk = chunk

    # Add final chunk
    if current_chunk.strip():
        optimized.append(current_chunk.strip())

    return optimized


def synthesize(
    text: str,
    voice: str,
    out_path: Path,
    bitrate: str = "64k",
    max_minutes: int = 60,
    dry_run: bool = False,
) -> bytes:
    logger = get_logger()

    # If dry run, just return estimation
    if dry_run:
        estimation = estimate_tts(text, voice)
        logger.info("DRY RUN: TTS synthesis skipped, returning estimation only")
        return estimation

    # Validate API key before making any requests
    try:
        api_key = check_openai_api_key()
        logger.debug("OpenAI API key validated successfully")
    except ValidationError as e:
        log_error(f"TTS initialization failed: {e}")
        raise ValidationError(f"TTS initialization failed: {e}")

    client = OpenAI(api_key=api_key)
    chunks = chunk_text(text)

    logger.info(f"Processing text in {len(chunks)} chunks for voice: {voice}")
    logger.debug(f"Text length: {len(text)} characters, max chunk size: 3500")

    combined = AudioSegment.silent(duration=0)
    total_ms = 0

    for i, chunk in enumerate(chunks):
        try:
            logger.debug(f"Processing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")

            # TTS request; using gpt-4o-mini-tts model name
            resp = client.audio.speech.create(
                model="gpt-4o-mini-tts", voice=voice, input=chunk, response_format="mp3"
            )
            audio_bytes = resp.read()
            seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
            combined += seg
            total_ms += len(seg)

            logger.debug(f"Chunk {i+1} completed: {len(seg)}ms audio")

            if total_ms / 1000 / 60 > max_minutes:
                log_warning(
                    f"Audio length limit exceeded: {total_ms/1000/60:.1f} minutes > {max_minutes} minutes"
                )
                raise TTSLengthError(f"Exceeded max minutes: {max_minutes}")

            time.sleep(0.2)  # light pacing

        except Exception as e:
            log_error(f"TTS request failed for chunk {i+1}: {e}")
            raise Exception(f"TTS request failed for chunk {i+1}: {e}")

    logger.info(
        f"All chunks processed successfully. Total audio: {total_ms/1000:.1f} seconds"
    )

    # Normalize and export
    try:
        combined = pydub_normalize(combined)
        combined.export(out_path, format="mp3", bitrate=bitrate)
        logger.info(f"Audio exported to {out_path} with bitrate {bitrate}")
    except Exception as e:
        log_error(f"Failed to export audio: {e}")
        raise

    return out_path.read_bytes()
