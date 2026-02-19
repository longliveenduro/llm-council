
import json
import os

SCORES_FILE = "data/model_scores.json"

initial_scores = {
  "ChatGPT 5.2": 0,
  "Gemini 3.1 Pro": 0,
  "Claude Sonnet 4.6": 0,
  "Gemini 3 Flash Preview": 0
}

try:
    with open(SCORES_FILE, "w") as f:
        json.dump(initial_scores, f, indent=2)
    print(f"Successfully reset scores in {SCORES_FILE}")
    
    # Verify
    with open(SCORES_FILE, "r") as f:
        print("Content:")
        print(f.read())
except Exception as e:
    print(f"Error: {e}")
