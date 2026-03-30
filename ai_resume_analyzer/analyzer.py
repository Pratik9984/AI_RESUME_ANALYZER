import os
import requests
import json
from dotenv import load_dotenv

# This physically loads the variables from your .env file into the script
load_dotenv()

def is_valid_resume(text):
    """Heuristic check: resume-like content has multiple resume keywords and reasonable length."""
    if len(text.strip()) < 100:
        return False
    keywords = [
        "experience", "education", "skills", "summary", "projects",
        "certifications", "work history", "employment", "objective", "references"
    ]
    matches = sum(1 for kw in keywords if kw.lower() in text.lower())
    return matches >= 2


def analyze_resume(text, api_key=None):
    """
    Analyzes resume text via Groq API.
    Requests structured JSON output natively.
    Returns (score: int, feedback_dict: dict).
    """
    # Now it will successfully pull the key from your .env file
    # It checks for both uppercase and your original casing just in case
    key = api_key or os.environ.get("GROQ_API_KEY") or os.environ.get("Groq_API_KEY")
    
    if not key:
        return 0, {"Error": ["Groq API key not found. Make sure your .env file is set up correctly."]}

    if not is_valid_resume(text):
        return 0, {"Notice": ["Only Resume and CV documents are accepted for review."]}

    prompt = f"""You are a professional resume reviewer , Review the Resume very strictly. Analyze the resume below and respond ONLY with a valid JSON object. No preamble, no explanation.

Required JSON structure (all fields required, values must be arrays of strings):
{{
  "score": <integer 0-100>,
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "formatting_issues": ["...", "..."],
  "suggestions": ["...", "..."]
}}

Resume:
{text}"""

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.1-8b-instant", 
        "messages": [
            {
                "role": "system",
                "content": "You are an API that only returns valid JSON objects."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"} 
    }

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        
        raw = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = json.loads(raw)

        score = max(0, min(100, int(parsed.get("score", 0))))
        feedback_dict = {
            "Strengths":         parsed.get("strengths", []),
            "Weaknesses":        parsed.get("weaknesses", []),
            "Formatting Issues": parsed.get("formatting_issues", []),
            "Suggestions":       parsed.get("suggestions", [])
        }
        return score, feedback_dict

    except json.JSONDecodeError:
        return 0, {"Error": ["The AI returned an unexpected format. Please try again."]}
    except requests.exceptions.HTTPError as e:
        return 0, {"Error": [f"API Error: {response.status_code} - {response.text}"]}
    except requests.exceptions.ConnectionError:
        return 0, {"Error": ["Could not reach the Groq API. Please check your internet connection."]}
    except requests.exceptions.Timeout:
        return 0, {"Error": ["The analysis request timed out. Please try again."]}
    except Exception as e:
        return 0, {"Error": [f"Analysis failed: {str(e)}"]}
