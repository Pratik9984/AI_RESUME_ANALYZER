import requests
import re

def is_valid_resume(text):
    """Basic heuristic to detect resume-like content"""
    resume_keywords = ["experience", "education", "skills", "summary", "projects", "certifications"]
    matches = sum(1 for kw in resume_keywords if kw.lower() in text.lower())
    return matches >= 2  # Adjust threshold as needed

def extract_sections(content):
    """Improved section extraction using header positions"""
    section_headers = ["Strengths", "Weaknesses", "Formatting Issues", "Suggestions"]
    feedback_dict = {}

    content_lower = content.lower()
    positions = {header: content_lower.find(header.lower()) for header in section_headers}
    sorted_headers = sorted(positions.items(), key=lambda x: x[1] if x[1] != -1 else float('inf'))

    for i, (header, start) in enumerate(sorted_headers):
        if start == -1:
            feedback_dict[header] = []
            continue
        end = sorted_headers[i + 1][1] if i + 1 < len(sorted_headers) else len(content)
        section_text = content[start:end].splitlines()
        points = [line.strip("-*• ").strip() for line in section_text if line.strip()]
        feedback_dict[header] = points

    return feedback_dict

def analyze_resume(text):
    """Main resume analysis function"""
    if not is_valid_resume(text):
        return "Only Resume and CV are allowed to review", {}

    prompt = f"""
You're a professional resume reviewer. Analyze the following resume and return in clearly labeled sections:
- Score out of 100 (based on relevance, formatting, keyword density, grammar)
- Strengths (bullet points)
- Weaknesses (bullet points)
- Formatting Issues (bullet points)
- Suggestions to improve clarity and keyword relevance (bullet points)
- Review only the resume and CV. If another document is provided, say "Only Resume and CV are allowed to review."

Resume:
{text}
"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "mistral",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0}
            }
        )
        result = response.json()
        content = result.get("response", "No response received.")

        # Extract numeric score
        score_match = re.search(r"(\d{1,3})\s*/?\s*100", content)
        score = int(score_match.group(1)) if score_match else 0

        # Extract feedback sections
        feedback_dict = extract_sections(content)

        return score, feedback_dict

    except Exception as e:
        return f"Error during resume analysis: {str(e)}", {}

# 🧪 Example usage
if __name__ == "__main__":
    sample_text = "This is a sample document about quarterly sales and marketing strategy. No resume content here."

    score, feedback = analyze_resume(sample_text)

    if isinstance(score, str) and score.startswith("Only Resume"):
        print(score)
    else:
        print(f"Score: {score}")
        for section, points in feedback.items():
            print(f"\n{section}:")
            for point in points:
                print(f"- {point}")
