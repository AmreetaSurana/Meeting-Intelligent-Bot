"""
evaluation.py  —  app/evaluation/evaluation.py

Compares every file in  app/evaluation/created_json/
against its reference in  app/evaluation/given_json/
using an LLM-as-judge and prints a full report to the terminal.

Run AFTER generate_json.py has populated created_json/:
    python app/evaluation/evaluation.py
"""

import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config.config import API_KEY, API_MODEL  # noqa: E402

JUDGE_MODEL = API_MODEL

try:
    from google import genai
    from google.genai import types
    judge_client = genai.Client(api_key=API_KEY)
except ImportError:
    print("❌  google-genai not installed. Run: pip install google-genai")
    sys.exit(1)

# ---------------------------------------------------------------------------

class MeetingEvaluator:
    """Compare created_json/ files against given_json/ reference files via LLM judge."""

    def __init__(self, base_dir: str = "app/evaluation", batch_size: int = 3):
        self.base_dir         = Path(base_dir)
        self.ref_json_dir     = self.base_dir / "given_json"
        self.created_json_dir = self.base_dir / "created_json"
        self.batch_size       = batch_size
        self.results: List[Dict] = []

    # ------------------------------------------------------------------
    def find_json_pairs(self) -> List[Tuple[str, Path, Path]]:
        if not self.ref_json_dir.exists():
            print(f"❌ Reference JSON dir not found: {self.ref_json_dir.resolve()}")
            return []
        if not self.created_json_dir.exists():
            print(f"❌ Created JSON dir not found: {self.created_json_dir.resolve()}")
            return []

        ref_jsons     = sorted(self.ref_json_dir.glob("*.json"))
        created_jsons = sorted(self.created_json_dir.glob("*.json"))

        print(f"\n   📂 Reference JSONs ({len(ref_jsons)}):  {[f.name for f in ref_jsons]}")
        print(f"   📂 Created JSONs   ({len(created_jsons)}):  {[f.name for f in created_jsons]}")

        ref_map: Dict[str, Path] = {}
        for f in ref_jsons:
            m = re.search(r"(\d+)", f.stem)
            if m:
                ref_map[m.group(1)] = f

        created_map: Dict[str, Path] = {}
        for f in created_jsons:
            m = re.search(r"(\d+)", f.stem)
            if m:
                created_map[m.group(1)] = f

        pairs = []
        for num in sorted(ref_map.keys(), key=int):
            if num in created_map:
                pairs.append((num, created_map[num], ref_map[num]))
            else:
                print(f"   ⚠️  No created JSON for reference meeting {num} — skipping.")

        print(f"\n✅ Matched {len(pairs)} pair(s) for evaluation.")
        return pairs

    # ------------------------------------------------------------------
    def load_json(self, path: Path) -> Optional[Dict]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"   ❌ Error reading {path.name}: {e}")
            return None

    # ------------------------------------------------------------------
    def llm_as_judge(
        self, generated: Dict, reference: Dict, meeting_id: str
    ) -> Dict:
        if not reference:
            return {"overall_score": 0, "missing_information": ["No reference JSON"]}

        prompt = f"""
You are a strict JSON evaluator.

Reference JSON (Ground Truth):
{json.dumps(reference, indent=2)}

Generated JSON:
{json.dumps(generated, indent=2)}

Compare them carefully. Identify what important information is missing or incorrect
in the Generated JSON compared to the Reference.

Return ONLY valid JSON (no markdown fences, no extra text):
{{
  "overall_score": <integer 0-100>,
  "missing_information": ["specific missing item 1", "specific missing item 2"],
  "strengths": ["good thing 1", "good thing 2"],
  "weaknesses": ["issue 1", "issue 2"],
  "reasoning": "brief overall summary"
}}
"""
        print(f"   ⚖️  Judging meeting {meeting_id} with {JUDGE_MODEL}...")
        try:
            response = judge_client.models.generate_content(
                model=JUDGE_MODEL,
                config=types.GenerateContentConfig(
                    system_instruction="You are a precise evaluator. Always return valid JSON only."
                ),
                contents=prompt,
            )
            text  = response.text.strip()
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise ValueError("No JSON object found in judge response.")
        except Exception as e:
            print(f"   ❌ Judge error: {e}")
            return {
                "overall_score": 0,
                "missing_information": [f"Judge call failed: {e}"],
                "strengths": [],
                "weaknesses": [],
                "reasoning": "Judge LLM call failed.",
            }

    # ------------------------------------------------------------------
    def run(self):
        print("\n🚀 Starting Evaluation: Created JSON vs Reference JSON")
        pairs = self.find_json_pairs()

        if not pairs:
            print("Nothing to evaluate. Exiting.")
            return

        for i, (num, created_path, ref_path) in enumerate(pairs, 1):
            print(f"\n{'─'*60}")
            print(f"→ Meeting {num}  ({i}/{len(pairs)})")
            print(f"{'─'*60}")

            generated = self.load_json(created_path)
            reference = self.load_json(ref_path)

            if not generated:
                print("   ⚠️  Could not load created JSON — skipping.")
                continue

            comparison = self.llm_as_judge(generated, reference, num)

            self.results.append({
                "meeting_id":          num,
                "overall_score":       comparison.get("overall_score", 0),
                "missing_information": comparison.get("missing_information", []),
                "strengths":           comparison.get("strengths", []),
                "weaknesses":          comparison.get("weaknesses", []),
                "reasoning":           comparison.get("reasoning", ""),
                "comparison":          comparison,
            })

            if i % self.batch_size == 0 and i < len(pairs):
                print(f"\n⏳ Rate-limit pause — waiting 60 s before next batch...")
                time.sleep(60)

        self.print_report()

    # ------------------------------------------------------------------
    def print_report(self):
        SEP = "=" * 100
        print(f"\n{SEP}")
        print("🤖  FINAL EVALUATION REPORT — GENERATED vs REFERENCE")
        print(SEP)

        total_score = 0
        for r in self.results:
            score = r["overall_score"]
            total_score += score
            grade = "✅" if score >= 80 else ("⚠️ " if score >= 60 else "❌")

            print(f"\n📍 Meeting {r['meeting_id']}")
            print(f"   {grade} Overall Score    : {score}/100")
            print(f"   💬 Reasoning        : {r['reasoning']}")

            if r["strengths"]:
                print("   ✔  Strengths        :")
                for s in r["strengths"]:
                    print(f"        • {s}")

            if r["weaknesses"]:
                print("   ✘  Weaknesses       :")
                for w in r["weaknesses"]:
                    print(f"        • {w}")

            if r["missing_information"]:
                print("   ⚡ Missing Info      :")
                for item in r["missing_information"][:10]:
                    print(f"        – {item}")

        avg = round(total_score / len(self.results), 1) if self.results else 0

        print(f"\n{SEP}")
        print("📊  AGGREGATE")
        print(f"   Meetings Evaluated : {len(self.results)}")
        print(f"   Average Score      : {avg}/100")
        print(SEP)

        results_file = self.base_dir / "evaluation_results.json"
        results_file.write_text(
            json.dumps(self.results, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\n💾 Full results saved → {results_file}\n")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    evaluator = MeetingEvaluator(base_dir="app/evaluation", batch_size=3)
    evaluator.run()
