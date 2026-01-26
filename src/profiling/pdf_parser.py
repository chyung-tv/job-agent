import fitz  # PyMuPDF
from rapidocr_onnxruntime import RapidOCR
from pathlib import Path
import numpy as np
from PIL import Image
import io

class PDFParser:
    """A robust PDF parser for extracting text from PDFs using PyMuPDF and RapidOCR.
    
    Handles both text-layer extraction and OCR fallback for scanned documents or
    PDFs with non-standard font encodings. Optimized for CJK (Chinese, Japanese, Korean)
    characters but works with any language.
    """

    def __init__(self):
        # RapidOCR defaults to Chinese (Simplified + Traditional) + English
        self.ocr_engine = RapidOCR()

    def parse(self, pdf_path: str | Path) -> str:
        """Parse a PDF file and return the extracted text.
        
        Args:
            pdf_path: Path to the PDF file to parse
            
        Returns:
            Extracted text content as a string
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Step 1: Try direct text extraction with PyMuPDF
        doc = fitz.open(str(pdf_path))
        extracted_text = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text().strip()
            
            # Check if the extracted text is "meaningful"
            # We look for a reasonable ratio of printable characters or Chinese characters
            if self._is_text_valid(text):
                extracted_text.append(text)
            else:
                # Step 2: Fallback to RapidOCR for this page
                # Convert page to image for OCR
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # Higher resolution for better OCR
                img = Image.open(io.BytesIO(pix.tobytes()))
                
                # RapidOCR expects an image as numpy array or path
                ocr_result, _ = self.ocr_engine(np.array(img))
                
                if ocr_result:
                    # ocr_result is a list of [box, text, score]
                    page_text = "\n".join([line[1] for line in ocr_result])
                    extracted_text.append(page_text)
        
        doc.close()
        return "\n\n".join(extracted_text)

    def _is_text_valid(self, text: str) -> bool:
        """
        Check if the extracted text looks like actual content or meaningless symbols.
        
        Validates text by checking for:
        - Non-empty content
        - Presence of meaningful characters (letters, CJK characters, numbers)
        - Low ratio of control/special characters
        
        Args:
            text: The extracted text to validate
            
        Returns:
            True if text appears valid, False if it should trigger OCR fallback
        """
        if not text or len(text.strip()) == 0:
            return False
        
        # Count meaningful characters (letters, CJK, numbers)
        meaningful_chars = 0
        total_chars = len(text)
        
        for char in text:
            # Check for letters (any language), CJK characters, or numbers
            if char.isalnum() or ('\u4e00' <= char <= '\u9fff'):  # CJK range
                meaningful_chars += 1
        
        # If less than 30% of characters are meaningful, likely garbled
        if total_chars > 0 and meaningful_chars / total_chars < 0.3:
            return False
        
        # If we have at least some meaningful content, consider it valid
        # This works for both English and CJK documents
        return meaningful_chars > 0

if __name__ == "__main__":
    # Quick test
    import sys
    if len(sys.argv) > 1:
        parser = PDFParser()
        print(parser.parse(sys.argv[1]))
