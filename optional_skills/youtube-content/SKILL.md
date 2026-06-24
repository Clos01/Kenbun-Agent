---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [python, bash, youtube-transcript-api]
  discovery_required: false
---

# YouTube Content Tool

Extract transcripts from YouTube videos and convert them into structured content (chapters, summaries, threads, blog posts).

---

## When to Use
- User shares a YouTube URL or video link.
- User asks to summarize a video, extract key takeaways, or request a transcript.
- User wants to reformat YouTube video content into articles, Twitter/X threads, or blog posts.

---

## Setup
Install the necessary dependency into the Kenbun environment:
```bash
pip install youtube-transcript-api
```

---

## Helper Script
The helper script accepts any standard YouTube URL format (e.g., watch links, shortlinks `youtu.be`, shorts, embeds, live streams) or a raw 11-character video ID.

```bash
# JSON output with metadata
python3 optional_skills/youtube-content/scripts/fetch_transcript.py "https://youtube.com/watch?v=VIDEO_ID"

# Plain text (useful for piping into further processing)
python3 optional_skills/youtube-content/scripts/fetch_transcript.py "URL" --text-only

# Plain text with timestamps
python3 optional_skills/youtube-content/scripts/fetch_transcript.py "URL" --text-only --timestamps

# Specific language with fallback chain
python3 optional_skills/youtube-content/scripts/fetch_transcript.py "URL" --language tr,en
```

---

## Output Formats
After fetching the transcript, format the output based on user requests:

### 1. Chapters
Group content by topic shifts and output a timestamped list of sections.
*Example:*
```
00:00 Introduction — host opens with the problem statement
03:45 Background — prior work and why existing solutions fall short
12:20 Core method — walkthrough of the proposed approach
24:10 Results — benchmark comparisons and key takeaways
31:55 Q&A — audience questions on scalability and next steps
```

### 2. Summary
A concise 5-10 sentence overview of the entire video.

### 3. Chapter Summaries
List the video chapters alongside a brief paragraph summarizing each chapter's details.

### 4. Thread (Twitter/X)
A sequence of numbered posts (each under 280 characters) summarizing key points.

### 5. Blog Post
A fully-formed article with a title, subheadings, and key takeaways.

### 6. Quotes
Notable direct quotes from the transcript alongside their timestamps.

---

## Workflow

1. **Fetch:** Fetch the transcript using the helper script:
   ```bash
   python3 optional_skills/youtube-content/scripts/fetch_transcript.py "URL" --text-only --timestamps
   ```
2. **Validate:** Confirm the output is non-empty. If empty, retry without the `--language` parameter to fetch any available language. If it remains empty, inform the user that transcripts might be disabled for this video.
3. **Chunking (if large):** If the transcript is extremely long (exceeds ~50K characters), split the text into overlapping chunks (~40K characters with 2K overlap), summarize each chunk individually, and then combine the summaries.
4. **Transform:** Reformat the transcript text into the requested format (defaulting to a summary if none is specified).
5. **Verify:** Read through the final output to check for coherence, correct timestamp alignments, and completeness.

---

## Error Handling

- **Transcript Disabled:** Inform the user and suggest they verify if subtitles/CC are enabled on the YouTube video page.
- **Private/Unavailable Video:** Relay the error and ask the user to double check the URL.
- **No Matching Language:** Retry without `--language` to fetch any auto-generated or default transcript, then notify the user.
