#!/usr/bin/env python3
import argparse
import json
import re
import sys

def extract_video_id(url_or_id):
    """
    Extracts the 11-character YouTube video ID from various URL formats.
    """
    url_or_id = url_or_id.strip()
    if len(url_or_id) == 11 and re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id

    patterns = [
        r'(?:v=|\/embed\/|\/shorts\/|\/live\/|\/v\/)([a-zA-Z0-9_-]{11})',
        r'youtu\.be\/([a-zA-Z0-9_-]{11})',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return None

def format_timestamp(seconds):
    """
    Formats seconds into HH:MM:SS or MM:SS.
    """
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def main():
    parser = argparse.ArgumentParser(description="Fetch transcripts from YouTube videos.")
    parser.add_argument("url", help="YouTube video URL or 11-character video ID.")
    parser.add_argument("--text-only", action="store_true", help="Print plain text only.")
    parser.add_argument("--timestamps", action="store_true", help="Include timestamps in output.")
    parser.add_argument("--language", help="Comma-separated language codes to try (e.g., 'en,tr').")
    args = parser.parse_args()

    video_id = extract_video_id(args.url)
    if not video_id:
        print(f"Error: Could not extract video ID from '{args.url}'", file=sys.stderr)
        sys.exit(1)

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        print("Error: youtube-transcript-api is not installed. Run 'pip install youtube-transcript-api'", file=sys.stderr)
        sys.exit(1)

    languages = [lang.strip() for lang in args.language.split(",")] if args.language else None

    try:
        if languages:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
        else:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
    except Exception as e:
        print(f"Error: Failed to fetch transcript for video ID {video_id}. {e}", file=sys.stderr)
        sys.exit(1)

    if args.text_only:
        if args.timestamps:
            for entry in transcript:
                time_str = format_timestamp(entry["start"])
                print(f"[{time_str}] {entry['text']}")
        else:
            for entry in transcript:
                print(entry["text"])
    else:
        # Default JSON format
        output = {
            "video_id": video_id,
            "transcript": [
                {
                    "text": entry["text"],
                    "start": entry["start"],
                    "duration": entry["duration"],
                    "timestamp": format_timestamp(entry["start"])
                }
                for entry in transcript
            ]
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
