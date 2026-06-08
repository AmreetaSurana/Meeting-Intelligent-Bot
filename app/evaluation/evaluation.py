import json
import os
from datetime import datetime
from pathlib import Path
import mlflow
from langchain_google_genai import ChatGoogleGenerativeAI
import pandas as pd
from config.config import API_KEY as GOOGLE_API_KEY

# ------------------- CONFIG -------------------
MLFLOW_EXPERIMENT = "meeting-intelligence-eval-gemini"
GROUND_TRUTH_DIR = Path("evaluation/ground_truth")
TEST_TRANSCRIPTS_DIR = Path("evaluation/test_transcripts")


# ------------------- HELPERS -------------------
def load_json(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def compare_action_items(pred_items, gt_items):
    """Custom precision/recall for action items"""
    pred_set = {(item.get("title", "").strip().lower(), item.get("owner")) 
                for item in pred_items if item.get("title")}
    gt_set = {(item.get("title", "").strip().lower(), item.get("owner")) 
              for item in gt_items if item.get("title")}
    
    tp = len(pred_set & gt_set)
    precision = tp / len(pred_set) if pred_set else 0.0
    recall = tp / len(gt_set) if gt_set else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp}

def gemini_judge(llm, prompt: str) -> float:
    """Simple LLM-as-judge using Gemini"""
    response = llm.invoke(prompt)
    try:
        # Try to extract score from 0-1
        score_text = response.content.strip()
        score = float([s for s in score_text.split() if s.replace(".", "").replace(",", "").isdigit()][0])
        return min(max(score, 0.0), 1.0)
    except:
        return 0.5  # fallback

# ------------------- EVALUATOR CLASS -------------------
class MeetingIntelligenceEvaluator:
    def __init__(self, model_name: str = "gemini-3.5-flash"):
        mlflow.set_experiment(MLFLOW_EXPERIMENT)
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            google_api_key="GOOGLE_API_KEY"
        )
        self.model_name = model_name

    def run_evaluation(self, transcript_path: str, predicted_json_path: str, 
                       ground_truth_path: str, run_name: str = None):
        
        with mlflow.start_run(run_name=run_name or f"gemini_eval_{datetime.now().strftime('%Y%m%d_%H%M')}"):
            transcript = Path(transcript_path).read_text(encoding="utf-8")
            pred_data = load_json(predicted_json_path)
            gt_data = load_json(ground_truth_path)

            # 1. Custom Extraction Metrics
            custom_metrics = compare_action_items(
                pred_data.get("action_items", []),
                gt_data.get("action_items", [])
            )

            # 2. LLM-as-Judge: Attribution Accuracy
            attribution_prompt = f"""
            Score the owner attribution accuracy (0.0 to 1.0) for this meeting extraction.
            Compare predicted vs ground truth.
            Transcript: {transcript[:8000]}
            Predicted: {json.dumps(pred_data, indent=2)}
            Ground Truth: {json.dumps(gt_data, indent=2)}
            Return only a number between 0.0 and 1.0.
            """
            attribution_score = gemini_judge(self.llm, attribution_prompt)

            # 3. Simple Faithfulness Score
            faithfulness_prompt = f"""
            Score how faithful the extracted JSON is to the transcript (0.0-1.0).
            Check if action_items, decisions, blockers are grounded in the text.
            Transcript: {transcript[:8000]}
            JSON: {json.dumps(pred_data, indent=2)}
            Return only a number between 0.0 and 1.0.
            """
            faithfulness_score = gemini_judge(self.llm, faithfulness_prompt)

            # Log to MLflow
            mlflow.log_metric("extraction_precision", custom_metrics["precision"])
            mlflow.log_metric("extraction_recall", custom_metrics["recall"])
            mlflow.log_metric("extraction_f1", custom_metrics["f1"])
            mlflow.log_metric("attribution_accuracy", attribution_score)
            mlflow.log_metric("faithfulness", faithfulness_score)

            results_dict = {
                "timestamp": datetime.now().isoformat(),
                "model": self.model_name,
                "transcript": transcript_path,
                "metrics": {
                    **custom_metrics,
                    "attribution_accuracy": attribution_score,
                    "faithfulness": faithfulness_score
                }
            }
            
            mlflow.log_dict(results_dict, "evaluation_results.json")
            mlflow.log_artifact(predicted_json_path, "predictions")
            mlflow.log_artifact(ground_truth_path, "ground_truth")

            print(f"✅ Evaluation done. Run ID: {mlflow.active_run().info.run_id}")
            return results_dict

# ------------------- BATCH RUN -------------------
def evaluate_all_test_cases(model_name: str = "gemini-1.5-flash"):
    evaluator = MeetingIntelligenceEvaluator(model_name=model_name)
    results = []
    
    for gt_file in sorted(GROUND_TRUTH_DIR.glob("*.json")):
        base_name = gt_file.stem.replace("_gt", "")
        transcript_file = TEST_TRANSCRIPTS_DIR / f"{base_name}.txt"
        pred_file = Path("artifacts") / f"meeting_analysis_{base_name.split('_')[-1]}.json"

        if transcript_file.exists() and pred_file.exists():
            print(f"📊 Evaluating {base_name}...")
            result = evaluator.run_evaluation(
                transcript_path=str(transcript_file),
                predicted_json_path=str(pred_file),
                ground_truth_path=str(gt_file),
                run_name=f"eval_{base_name}"
            )
            results.append(result)
    
    if results:
        df = pd.DataFrame([r["metrics"] for r in results])
        print("\n=== GEMINI EVALUATION SUMMARY ===")
        print(df.mean(numeric_only=True).round(4))
        df.to_csv("evaluation_summary_gemini.csv", index=False)
        mlflow.log_artifact("evaluation_summary_gemini.csv")
        print("📁 Summary saved to evaluation_summary_gemini.csv")

if __name__ == "__main__":
    evaluate_all_test_cases()