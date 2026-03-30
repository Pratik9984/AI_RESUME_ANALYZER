import pdfplumber
from docx import Document

def extract_text(filepath):
    """
    Extracts plain text from a PDF or DOCX file.
    Returns extracted text, or a descriptive error string.
    """
    try:
        if filepath.lower().endswith('.pdf'):
            with pdfplumber.open(filepath) as pdf:
                pages = [page.extract_text() for page in pdf.pages if page.extract_text()]
                if not pages:
                    return (
                        "No extractable text found in this PDF. "
                        "It may be a scanned document. Please use a text-based PDF or a DOCX file."
                    )
                return "\n".join(pages)

        elif filepath.lower().endswith('.docx'):
            doc = Document(filepath)
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paragraphs) if paragraphs else "No extractable text found in DOCX."

        else:
            return "Unsupported file format. Only PDF and DOCX files are accepted."

    except Exception as e:
        return f"Error extracting text: {str(e)}"
