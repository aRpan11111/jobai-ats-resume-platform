import io
import pdfplumber
import docx

def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract raw text from PDF or DOCX bytes."""
    ext = filename.lower().split('.')[-1]
    
    if ext == 'pdf':
        text = ""
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        return text.strip()
        
    elif ext == 'docx':
        doc = docx.Document(io.BytesIO(file_bytes))
        return "\n".join([para.text for para in doc.paragraphs]).strip()
        
    elif ext == 'tex':
        # Decode the bytes directly to a string
        try:
            return file_bytes.decode('utf-8')
        except UnicodeDecodeError:
            return file_bytes.decode('latin-1')
            
    else:
        raise ValueError("Unsupported file format. Please upload PDF, DOCX, or TEX.")
