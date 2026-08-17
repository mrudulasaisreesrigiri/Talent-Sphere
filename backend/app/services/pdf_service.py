import os
from typing import List, Dict, Any
from pypdf import PdfReader

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ModuleNotFoundError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

class PDFProcessor:
    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ".", " ", ""]
        )

    def extract_text_with_metadata(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Reads a PDF file and extracts text page by page.
        Returns a list of dicts containing page_number, content, and chunk_index.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found at {file_path}")

        reader = PdfReader(file_path)
        extracted_chunks = []
        global_chunk_idx = 0

        for page_idx, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            if not page_text.strip():
                continue

            page_number = page_idx + 1
            chunks = self.splitter.split_text(page_text)

            for chunk in chunks:
                extracted_chunks.append({
                    "chunk_index": global_chunk_idx,
                    "page_number": page_number,
                    "content": chunk.strip()
                })
                global_chunk_idx += 1

        return extracted_chunks

pdf_service = PDFProcessor()
