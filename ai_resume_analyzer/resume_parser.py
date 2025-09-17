import pdfplumber
import docx

def extract_text(filepath):
    """Extracts text from PDF or DOCX files. Returns plain text or error message."""
    try:
        if filepath.lower().endswith('.pdf'):
            with pdfplumber.open(filepath) as pdf:
                text = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text.append(page_text)
                return "\n".join(text) if text else "No extractable text found in PDF."
        
        elif filepath.lower().endswith('.docx'):
            doc = docx.Document(filepath)
            paragraphs = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
            return "\n".join(paragraphs) if paragraphs else "No extractable text found in DOCX."
        
        else:
            return "Unsupported file format. Only PDF and DOCX are allowed."

    except Exception as e:
        return f"Error extracting text: {str(e)}"
