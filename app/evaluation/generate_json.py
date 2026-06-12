"""
generate_json.py  —  app/evaluation/generate_json.py

Reads every transcript from  app/evaluation/transcript/
Calls llm_for_structured_json() from the pipeline
Saves one JSON file per transcript into  app/evaluation/created_json/

Run:
    python app/evaluation/generate_json.py
"""

import json
import re
import sys
import time
from pathlib import Path
from typing import List, Tuple

# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.pipeline.llm_call import llm_for_structured_json  # noqa: E402

# ---------------------------------------------------------------------------

class JSONGenerator:
    """Batch-generate structured JSONs from meeting transcripts."""

    def __init__(self, base_dir: str = "app/evaluation", batch_size: int = 3):
        self.base_dir         = Path(base_dir)
        self.transcript_dir   = self.base_dir / "transcript"
        self.created_json_dir = self.base_dir / "created_json"
        self.batch_size       = batch_size

        self.created_json_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Output directory → {self.created_json_dir.resolve()}")

    # ------------------------------------------------------------------
    def find_transcripts(self) -> List[Tuple[str, Path]]:
        if not self.transcript_dir.exists():
            print(f"❌ Transcript directory not found: {self.transcript_dir.resolve()}")
            return []

        transcripts = sorted(self.transcript_dir.glob("*.txt"))
        print(f"\n   📂 Transcript dir : {self.transcript_dir.resolve()}")
        print(f"      Found {len(transcripts)} file(s): {[f.name for f in transcripts]}")

        result = []
        for t in transcripts:
            m = re.search(r"(\d+)", t.stem)
            if m:
                result.append((m.group(1), t))
            else:
                print(f"   ⚠️  Could not extract number from {t.name} — skipping.")

        return result

    # ------------------------------------------------------------------
    def load_transcript(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception as e:
            print(f"   ❌ Error reading {path.name}: {e}")
            return ""

    # ------------------------------------------------------------------
    def generate_and_save(self, transcript: str, meeting_id: str) -> bool:
        """Call the pipeline, clean the response, save to created_json/. Returns success."""
        print(f"   🔄 Generating JSON for meeting {meeting_id}...")
        try:
            raw   = llm_for_structured_json(transcript)
            clean = raw.strip()
            clean = re.sub(r"^```[a-z]*\s*", "", clean)
            clean = re.sub(r"\s*```$",        "", clean)
            start, end = clean.find("{"), clean.rfind("}")
            if start != -1 and end != -1:
                clean = clean[start : end + 1]

            generated = json.loads(clean)

            save_path = self.created_json_dir / f"generated_meeting_analysis_{meeting_id}.json"
            save_path.write_text(
                json.dumps(generated, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"   💾 Saved → {save_path.name}")
            return True

        except Exception as e:
            print(f"   ❌ Failed for meeting {meeting_id}: {e}")
            return False

    # ------------------------------------------------------------------
    def run(self):
        print("\n🚀 Starting JSON Generation from Transcripts")
        transcripts = self.find_transcripts()

        if not transcripts:
            print("No transcripts found. Exiting.")
            return

        success, failed = 0, 0

        for i, (num, t_path) in enumerate(transcripts, 1):
            print(f"\n{'─'*60}")
            print(f"→ Meeting {num}  ({i}/{len(transcripts)})")
            print(f"{'─'*60}")

            transcript = self.load_transcript(t_path)
            if not transcript:
                print("   ⚠️  Empty transcript — skipping.")
                failed += 1
                continue

            ok = self.generate_and_save(transcript, num)
            if ok:
                success += 1
            else:
                failed += 1

            if i % self.batch_size == 0 and i < len(transcripts):
                print(f"\n⏳ Rate-limit pause — waiting 60 s before next batch...")
                time.sleep(100)

        SEP = "=" * 100
        print(f"\n{SEP}")
        print("📊  GENERATION SUMMARY")
        print(f"   Total Transcripts : {len(transcripts)}")
        print(f"   ✅ Succeeded       : {success}")
        print(f"   ❌ Failed          : {failed}")
        print(f"   Output dir        : {self.created_json_dir.resolve()}")
        print(SEP)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    generator = JSONGenerator(base_dir="app/evaluation", batch_size=3)
    generator.run()
