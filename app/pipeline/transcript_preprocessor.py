"""
Transcript Preprocessor
========================
Converts a raw .vtt (WebVTT) transcript into clean structured text
ready to be sent to the LLM extraction agent.

What it does
------------
1. Strips cue numbers and timestamps
2. Parses "Speaker: text" lines
3. Merges consecutive lines from the same speaker into one turn
4. Outputs a clean dialogue block + a speaker list

Usage
-----
    python transcript_preprocessor.py                              # processes built-in sample path
    python transcript_preprocessor.py sprint_planning.vtt         # your own file
"""

import re
import sys
from pathlib import Path

# ── Regex patterns ────────────────────────────────────────────────────────────

# Matches WebVTT timestamp lines: 00:00:05.800 --> 00:00:06.400
TIMESTAMP_RE = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d+ --> \d{2}:\d{2}:\d{2}\.\d+")

# Matches cue index lines: a bare integer on its own line
CUE_INDEX_RE = re.compile(r"^\d+$")

# Matches "Speaker Name: dialogue text"
SPEAKER_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z\s\-']+?):\s+(.+)$")


# ── Core parsing ──────────────────────────────────────────────────────────────

def parse_vtt(text: str) -> list[dict]:
    """
    Parse raw VTT content into a list of speaker turns.
    Each turn: {"speaker": str, "text": str}
    Consecutive cues from the same speaker are merged.
    """
    turns = []
    current_speaker = None
    current_text_parts = []

    for raw_line in text.splitlines():
        line = raw_line.strip()

        # Skip blank lines, the WEBVTT header, cue indices, and timestamps
        if not line:
            continue
        if line == "WEBVTT":
            continue
        if CUE_INDEX_RE.match(line):
            continue
        if TIMESTAMP_RE.match(line):
            continue

        # Try to match "Speaker: text"
        m = SPEAKER_LINE_RE.match(line)
        if m:
            speaker = m.group(1).strip()
            text_fragment = m.group(2).strip()

            if speaker == current_speaker:
                # Same speaker continuing — append to current turn
                current_text_parts.append(text_fragment)
            else:
                # New speaker — flush previous turn
                if current_speaker is not None:
                    turns.append({
                        "speaker": current_speaker,
                        "text": " ".join(current_text_parts)
                    })
                current_speaker = speaker
                current_text_parts = [text_fragment]
        else:
            # Continuation line with no speaker prefix — append to current turn
            if current_speaker is not None:
                current_text_parts.append(line)

    # Flush the last turn
    if current_speaker is not None and current_text_parts:
        turns.append({
            "speaker": current_speaker,
            "text": " ".join(current_text_parts)
        })

    return turns


def extract_speakers(turns: list[dict]) -> list[str]:
    """Return unique speakers in order of first appearance."""
    seen = []
    for t in turns:
        if t["speaker"] not in seen:
            seen.append(t["speaker"])
    return seen


# ── Output formatting ─────────────────────────────────────────────────────────

def format_structured_text(turns: list[dict], source_file: str = "") -> str:
    """
    Produce the clean structured text block that gets sent to the LLM.
    Format:
        [TRANSCRIPT: <filename>]
        Participants: A, B, C

        [Speaker Name]
        Text of their turn.

        [Speaker Name]
        ...
    """
    speakers = extract_speakers(turns)
    lines = []

    if source_file:
        lines.append(f"[TRANSCRIPT: {source_file}]")
    lines.append(f"Participants: {', '.join(speakers)}")
    lines.append("")

    for turn in turns:
        lines.append(f"[{turn['speaker']}]")
        lines.append(turn["text"])
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ── Entry point ───────────────────────────────────────────────────────────────

def preprocess(vtt_path: str | None = None) -> str:
    """
    Read a .vtt file, parse it, and write clean structured text.
    Returns the structured text string.
    """
    path = Path(vtt_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {vtt_path}")

    raw = path.read_text(encoding="utf-8")
    turns = parse_vtt(raw)

    if not turns:
        raise ValueError("No speaker turns found — check the VTT format.")

    structured = format_structured_text(turns, source_file=path.name)

    # Console summary
    # speakers = extract_speakers(turns)
    # print(f"\n  Preprocessed : {path.name}")
    # print(f"  Speakers     : {', '.join(speakers)}")
    # print(f"  Turns        : {len(turns)}")
    # print("─" * 60)
    # print(structured[:800] + ("…" if len(structured) > 800 else ""))
    # print("─" * 60)

    return structured


def main():
    if len(sys.argv) >= 2:
        vtt_file = sys.argv[1]
        
    else:
        # Default to the sprint planning file in the workspace
        vtt_file = "sprint_planning_incomplete_fields.vtt"
        

    structured_json = preprocess(vtt_file)
    return structured_json

if __name__ == "__main__":
    main()
