"""
PDF Processing Service
"""
import os
from typing import List, Dict
import PyPDF2
import pdfplumber


class PDFProcessor:
    """Service for processing PDF files"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """
        Initialize PDF Processor

        Args:
            chunk_size: Maximum characters per chunk
            chunk_overlap: Overlap between chunks for context continuity
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def extract_text(self, pdf_path: str) -> List[Dict[str, any]]:
        """
        Extract text from PDF with page numbers

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of dicts with 'text' and 'page_number'
        """
        pages = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text()
                    if text:
                        pages.append({
                            'text': text,
                            'page_number': page_num
                        })
        except Exception as e:
            # Fallback to PyPDF2 if pdfplumber fails
            print(f"pdfplumber failed, using PyPDF2: {e}")
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages, start=1):
                    text = page.extract_text()
                    if text:
                        pages.append({
                            'text': text,
                            'page_number': page_num
                        })

        return pages

    def chunk_text(self, pages: List[Dict[str, any]]) -> List[Dict[str, any]]:
        """
        Split text into chunks with overlap

        Args:
            pages: List of page dicts from extract_text()

        Returns:
            List of chunk dicts with 'text', 'page_number', 'chunk_index'
        """
        chunks = []
        chunk_index = 0

        for page_data in pages:
            text = page_data['text']
            page_number = page_data['page_number']

            # Split into chunks
            start = 0
            while start < len(text):
                end = start + self.chunk_size
                chunk_text = text[start:end]

                # Try to break at sentence boundary
                if end < len(text):
                    # Look for sentence ending
                    last_period = chunk_text.rfind('.')
                    last_question = chunk_text.rfind('?')
                    last_exclamation = chunk_text.rfind('!')

                    sentence_end = max(last_period, last_question, last_exclamation)

                    if sentence_end > self.chunk_size // 2:
                        chunk_text = chunk_text[:sentence_end + 1]
                        end = start + sentence_end + 1

                chunks.append({
                    'text': chunk_text.strip(),
                    'page_number': page_number,
                    'chunk_index': chunk_index
                })

                chunk_index += 1
                start = end - self.chunk_overlap

        return chunks

    def process_pdf(self, pdf_path: str) -> List[Dict[str, any]]:
        """
        Full PDF processing pipeline

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of processed chunks ready for embedding
        """
        pages = self.extract_text(pdf_path)
        chunks = self.chunk_text(pages)
        return chunks
