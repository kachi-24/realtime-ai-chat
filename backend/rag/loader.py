from pathlib import Path
from pypdf import PdfReader


def load_pdf(file_path: str) -> str:
    """
    Extract text from every page of a PDF.
    """

    reader = PdfReader(file_path)

    pages = []

    for page in reader.pages:
        text = page.extract_text()

        if text:
            pages.append(text)

    return "\n".join(pages)


def load_text(file_path: str) -> str:
    """
    Read a plain text file.
    """

    return Path(file_path).read_text(
        encoding="utf-8"
    )


def load_document(file_path: str) -> str:
    """
    Determine the file type and extract its text.
    """

    extension = Path(file_path).suffix.lower()

    if extension == ".pdf":
        return load_pdf(file_path)

    if extension == ".txt":
        return load_text(file_path)

    raise ValueError(
        f"Unsupported file type: {extension}"
    )