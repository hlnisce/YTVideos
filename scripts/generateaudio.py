#!/usr/bin/env python3
"""
generateaudio.py - Generate audio narration from narration.txt
Uses edge-tts with en-US-AnaNeural voice

Usage:
  python generateaudio.py                    # Generate all audio
  python generateaudio.py --clips 2          # Generate first 2 clips
"""

import json
import os
import sys
import re
import asyncio
import argparse
import edge_tts

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)


def load_project_config():
    """Load project configuration from project.json."""
    config_path = os.path.join(PARENT_DIR, "project.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    return {}


PROJECT_CONFIG = load_project_config()
VOICE = PROJECT_CONFIG.get("voice_model", "en-US-AnaNeural")
RATE = PROJECT_CONFIG.get("voice_rate", "-20%")


def read_narration_file(narration_path):
    """Read narration.txt and return list of sentences."""
    with open(narration_path, "r") as f:
        content = f.read()

    # Split by lines and clean
    lines = [line.strip() for line in content.split("\n") if line.strip()]

    # Remove header if present
    if lines and ("=" in lines[0] or "NARRATION" in lines[0].upper()):
        lines = lines[2:]  # Skip header and separator

    # Remove line numbers if present (e.g., "1. Once upon...")
    cleaned_lines = []
    for line in lines:
        # Remove leading numbers and dots
        cleaned = re.sub(r"^\d+\.\s*", "", line)
        if cleaned:
            cleaned_lines.append(cleaned)

    return cleaned_lines


async def generate_audio_segment(text, output_path, clip_number):
    """Generate a single audio segment using edge-tts."""
    print(f"Generating audio for clip {clip_number:02d}...")

    communicate = edge_tts.Communicate(text, VOICE, rate=RATE)
    await communicate.save(output_path)

    if os.path.exists(output_path):
        print(f"  Saved: {output_path}")
        return True
    else:
        print(f"  Failed to generate audio for clip {clip_number}")
        return False


async def main_async(args):
    # Find narration.txt
    narration_path = os.path.join(PARENT_DIR, "narration.txt")

    if not os.path.exists(narration_path):
        print(f"Error: narration.txt not found at {narration_path}")
        sys.exit(1)

    # Read narration
    sentences = read_narration_file(narration_path)
    print(f"Found {len(sentences)} sentences")

    # Limit number of clips if specified
    if args.clips:
        sentences = sentences[: args.clips]

    # Create sound directory
    sound_dir = os.path.join(PARENT_DIR, "sound")
    os.makedirs(sound_dir, exist_ok=True)

    print("=" * 60)
    print("AUDIO GENERATION PIPELINE")
    print("=" * 60)
    print(f"Sentences: {len(sentences)}")
    print(f"Voice: {VOICE}")
    print(f"Rate: {RATE}")
    print(f"Output: {sound_dir}")

    # Generate audio
    results = []
    for i, sentence in enumerate(sentences):
        print(f"\n[{i + 1}/{len(sentences)}] Processing sentence {i + 1}")

        audio_path = os.path.join(sound_dir, f"audio_{i + 1:02d}.mp3")
        success = await generate_audio_segment(sentence, audio_path, i + 1)
        results.append((i + 1, success))

        # Brief pause between generations
        await asyncio.sleep(1)

    # Summary
    print("\n" + "=" * 60)
    print("GENERATION COMPLETE!")
    print("=" * 60)

    successful = sum(1 for _, success in results if success)
    print(f"Successfully generated: {successful}/{len(sentences)} audio files")

    if successful > 0:
        print(f"\nAudio files saved to: {sound_dir}")
        print("\nNext steps:")
        print("1. Review audio files in the 'sound' folder")
        print("2. Use ffmpeg to concatenate clips with audio")
        print("3. Synchronize video clips with audio narration")


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Generate audio narration from narration.txt"
    )
    parser.add_argument(
        "--clips",
        type=int,
        default=None,
        help="Number of audio clips to generate (default: all)",
    )
    args = parser.parse_args()

    # Run async main
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
