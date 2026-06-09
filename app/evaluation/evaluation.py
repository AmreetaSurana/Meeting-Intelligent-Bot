import os
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from difflib import SequenceMatcher

# Import config (uses app/config/config.py)
try:
    from app.config.config import GEMINI_API_KEY
except ImportError:
    GEMINI_API_KEY = None
    print("⚠️  Could not import GEMINI_API_KEY from app.config.config")

import google.generativeai as genai


class MeetingEvaluator:
    """Terminal-based LLM-as-a-Judge evaluator for Meeting Bot pipeline with rate limiting."""
    
    def __init__(self, base_dir: str = "app/evaluation", batch_size: int = 5):
        self.base_dir = Path(base_dir)
        self.transcript_dir = self.base_dir / "transcript"
        self.json_dir = self.base_dir / "json"
        self.results: List[Dict] = []
        self.batch_size = batch_size
        
        # Load API key from config
        self.api_key = GEMINI_API_KEY
        
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            print(f"✅ Gemini configured successfully via config. (Rate limit: {batch_size} req/min)")
        else:
            self.model = None
            print("⚠️  GEMINI_API_KEY not found in config. Falling back to heuristic scoring.")

    def find_transcript_json_pairs(self) -> List[Tuple[str, Path, Path]]:
        """Find matching transcript and reference JSON pairs."""
        if not self.transcript_dir.exists() or not self.json_dir.exists():
            print("❌ Directories not found!")
            print(f"Expected:\n   {self.transcript_dir}\n   {self.json_dir}")
            return []

        transcripts = sorted(self.transcript_dir.glob("meeting_transcript_*.txt"))
        json_map = {}
        for j in self.json_dir.glob("meeting_analysis_*.json"):
            match = re.search(r'(\d+)', j.stem)
            if match:
                json_map[match.group(1)] = j

        pairs = []
        for t_path in transcripts:
            match = re.search(r'meeting_transcript_(\d+)', t_path.stem)
            if match:
                num = match.group(1)
                j_path = json_map.get(num)
                if j_path:
                    pairs.append((num, t_path, j_path))
                else:
                    print(f"⚠️  No matching JSON for transcript {num}")
        
        print(f"✅ Found {len(pairs)} transcript/JSON pairs.")
        return pairs

    def load_transcript(self, path: Path) -> str:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            print(f"Error reading {path.name}: {e}")
            return ""

    def load_json(self, path: Path) -> Optional[Dict]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading {path.name}: {e}")
            return None

    def validate_schema(self, data: Dict) -> Tuple[bool, List[str]]:
        expected_fields = ["summary", "action_items", "key_decisions", 
                          "participants", "sentiment", "topics"]
        issues = []
        for field in expected_fields:
            if field not in data:
                issues.append(f"Missing field: '{field}'")
            elif field in ["action_items", "key_decisions", "participants", "topics"] and not isinstance(data[field], list):
                issues.append(f"'{field}' should be a list")
        return len(issues) == 0, issues

    def gemini_judge(self, transcript: str, ref_json: Dict, meeting_id: str) -> Dict[str, Any]:
        """Use Gemini as LLM Judge."""
        if not self.model:
            return self.heuristic_judgement(ref_json)

        prompt = f"""
You are an expert meeting analyst and strict evaluator.

Transcript:
{transcript[:15000]}

Reference Analysis JSON:
{json.dumps(ref_json, indent=2)}

Evaluate the quality of this meeting analysis on a scale of 0-100.
Focus on:
1. Summary quality and completeness
2. Action items accuracy and clarity
3. Key decisions captured
4. Participants identification
5. Overall usefulness

Return ONLY a valid JSON with this structure:
{{
  "overall_score": <number 0-100>,
  "summary_score": <number>,
  "action_items_score": <number>,
  "decisions_score": <number>,
  "participants_score": <number>,
  "strengths": ["point1", "point2"],
  "weaknesses": ["point1", "point2"],
  "reasoning": "brief explanation"
}}
"""

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                return self.heuristic_judgement(ref_json)
        except Exception as e:
            print(f"Gemini error for meeting {meeting_id}: {e}")
            return self.heuristic_judgement(ref_json)

    def heuristic_judgement(self, ref_json: Dict) -> Dict[str, Any]:
        """Fallback scoring."""
        actions = len(ref_json.get("action_items", []))
        decisions = len(ref_json.get("key_decisions", []))
        participants = len(ref_json.get("participants", []))
        summary_len = len(ref_json.get("summary", ""))

        overall = min(100, (actions * 15) + (decisions * 12) + (participants * 10) + (summary_len // 20))
        
        return {
            "overall_score": round(overall, 1),
            "summary_score": min(100, summary_len // 15),
            "action_items_score": min(100, actions * 18),
            "decisions_score": min(100, decisions * 15),
            "participants_score": min(100, participants * 20),
            "strengths": ["Good structure"],
            "weaknesses": [] if overall > 70 else ["Limited detail"],
            "reasoning": "Heuristic fallback scoring"
        }

    def evaluate_single(self, num: str, trans_path: Path, json_path: Path):
        transcript = self.load_transcript(trans_path)
        ref_json = self.load_json(json_path)

        if not transcript or not ref_json:
            self.results.append({"meeting_id": num, "overall_score": 0, "status": "LOAD_ERROR"})
            return

        is_valid, issues = self.validate_schema(ref_json)
        judgement = self.gemini_judge(transcript, ref_json, num)

        result = {
            "meeting_id": num,
            "transcript_words": len(transcript.split()),
            "json_valid": is_valid,
            "issues": issues,
            "judgement": judgement,
            "overall_score": judgement.get("overall_score", 0),
            "status": "SUCCESS"
        }
        self.results.append(result)

    def print_report(self):
        if not self.results:
            print("No results to report.")
            return

        print("\n" + "="*80)
        print("🤖 MEETING BOT - GEMINI LLM-AS-A-JUDGE EVALUATION")
        print("="*80)

        total_score = 0
        valid_count = 0

        for r in self.results:
            j = r["judgement"]
            print(f"\n📍 Meeting {r['meeting_id']}")
            print(f"   Words              : {r['transcript_words']:,}")
            print(f"   JSON Valid         : {'✅' if r['json_valid'] else '❌'}")
            print(f"   Overall Score      : {r['overall_score']}/100")
            print(f"   Strengths          : {', '.join(j.get('strengths', []))}")
            if j.get('weaknesses'):
                print(f"   Weaknesses         : {', '.join(j.get('weaknesses', []))}")
            total_score += r['overall_score']
            if r['json_valid']:
                valid_count += 1

        avg_score = round(total_score / len(self.results), 1)

        print("\n" + "="*80)
        print("📊 AGGREGATE RESULTS")
        print("="*80)
        print(f"Meetings Evaluated     : {len(self.results)}")
        print(f"Valid JSONs            : {valid_count}/{len(self.results)}")
        print(f"Average LLM Judge Score: {avg_score}/100")
        print("="*80)

        results_path = self.base_dir / "evaluation_results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2)
        print(f"💾 Detailed results saved to: {results_path}")

    def run(self):
        print("🚀 Starting Gemini LLM-as-a-Judge Evaluation (with rate limiting)...")
        pairs = self.find_transcript_json_pairs()
        
        for i, (num, t_path, j_path) in enumerate(pairs, 1):
            print(f"→ Evaluating Meeting {num}... ({i}/{len(pairs)})")
            self.evaluate_single(num, t_path, j_path)
            
            # Rate limiting: Wait 60 seconds after every batch_size evaluations
            if i % self.batch_size == 0 and i < len(pairs):
                print(f"⏳ Rate limit reached ({self.batch_size} requests). Waiting 60 seconds...")
                time.sleep(60)
        
        self.print_report()


if __name__ == "__main__":
    evaluator = MeetingEvaluator(batch_size=5)   # Change batch_size if needed
    evaluator.run()