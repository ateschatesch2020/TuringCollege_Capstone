import logging
import json
import os
import uuid
from langchain_core.tools import tool
from dotenv import load_dotenv
load_dotenv()
import serpapi

logger = logging.getLogger(__name__)

_GENERATED_FILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_files")
_API_BASE_URL = "http://localhost:8001"


def _ensure_generated_dir():
    os.makedirs(_GENERATED_FILES_DIR, exist_ok=True)


@tool
def web_search(query: str) -> str:
    """Search the web for current information using Google Search.
    Use this for any question requiring up-to-date information not available in uploaded documents.
    query: search query in any language
    Returns top search results with title, snippet, and link.
    """
    client = serpapi.Client(api_key=os.getenv("SERPAPI_KEY"))
    try:
        raw = client.search({"engine": "google", "q": query, "num": 5})
    except serpapi.exceptions.HTTPError as e:
        logger.warning("web_search: SerpAPI error for '%s': %s", query, e)
        return f"Web search unavailable: {e}"
    results = raw.get("organic_results", [])
    if not results:
        return "No results found."
    lines = []
    for r in results[:5]:
        lines.append(f"**{r.get('title', '')}**\n{r.get('snippet', '')}\n{r.get('link', '')}")
    return "\n\n".join(lines)


@tool
def generate_presentation(title: str, slides_json: str) -> str:
    """Create a PowerPoint presentation (.pptx) file and return a download link.
    Use this when the user asks to create a presentation or slideshow.
    title: presentation title
    slides_json: JSON array of slides, e.g.:
                 '[{"title": "Introduction", "content": "Point 1\\nPoint 2\\nPoint 3"}]'
                 Each slide must have a 'title' and 'content' (newline-separated bullet points).
    Returns a download URL for the generated .pptx file.
    """
    from pptx import Presentation

    try:
        slides_data = json.loads(slides_json)
    except json.JSONDecodeError as e:
        return f"Invalid slides_json: {e}. Expected JSON array like [{{\"title\": \"...\", \"content\": \"...\"}}]"

    prs = Presentation()

    title_slide = prs.slides.add_slide(prs.slide_layouts[0])
    title_slide.shapes.title.text = title
    if len(title_slide.placeholders) > 1:
        title_slide.placeholders[1].text = ""

    for slide_data in slides_data:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = slide_data.get("title", "")
        tf = slide.placeholders[1].text_frame
        tf.clear()
        bullet_lines = [l.strip() for l in slide_data.get("content", "").split("\n") if l.strip()]
        for i, line in enumerate(bullet_lines):
            if i == 0:
                tf.paragraphs[0].text = line
            else:
                tf.add_paragraph().text = line

    _ensure_generated_dir()
    filename = f"{uuid.uuid4().hex}.pptx"
    prs.save(os.path.join(_GENERATED_FILES_DIR, filename))
    logger.info("generate_presentation: created %s", filename)
    return f"Presentation created successfully.\n\n[Download {title}.pptx]({_API_BASE_URL}/files/{filename})"


@tool
def generate_word_document(title: str, content: str) -> str:
    """Create a Word document (.docx) file and return a download link.
    Use this when the user asks to create a Word document, report, summary, checklist, or price list as a file.
    title: document title (used as the main heading)
    content: document body. Supports markdown-like formatting:
             - Lines starting with # / ## / ### are headings (level 1/2/3)
             - Lines starting with - or * are bullet list items
             - Lines with | delimiters are table rows (consecutive | rows become one table)
             - All other lines are normal paragraphs
    Returns a download URL for the generated .docx file.
    """
    from docx import Document

    doc = Document()
    doc.add_heading(title, level=0)

    lines = content.split("\n")
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        if stripped.startswith("|"):
            table_rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = lines[i].strip()
                if not all(c in "-| :" for c in row):
                    table_rows.append([c.strip() for c in row.strip("|").split("|")])
                i += 1
            if table_rows:
                max_cols = max(len(r) for r in table_rows)
                tbl = doc.add_table(rows=len(table_rows), cols=max_cols)
                tbl.style = "Table Grid"
                for r_idx, cells in enumerate(table_rows):
                    for c_idx, text in enumerate(cells):
                        if c_idx < max_cols:
                            tbl.rows[r_idx].cells[c_idx].text = text
            continue

        if not stripped:
            i += 1
            continue

        if stripped.startswith("### "):
            doc.add_heading(stripped[4:], level=3)
        elif stripped.startswith("## "):
            doc.add_heading(stripped[3:], level=2)
        elif stripped.startswith("# "):
            doc.add_heading(stripped[2:], level=1)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            doc.add_paragraph(stripped[2:], style="List Bullet")
        else:
            doc.add_paragraph(stripped)
        i += 1

    _ensure_generated_dir()
    filename = f"{uuid.uuid4().hex}.docx"
    doc.save(os.path.join(_GENERATED_FILES_DIR, filename))
    logger.info("generate_word_document: created %s", filename)
    return f"Word document created successfully.\n\n[Download {title}.docx]({_API_BASE_URL}/files/{filename})"


@tool
def generate_pdf_document(title: str, content: str) -> str:
    """Create a PDF document and return a download link.
    Use this when the user asks to create a PDF report, price list, or summary as a file.
    title: document title
    content: document body. Supports:
             - Lines starting with # / ## / ### for headings
             - Lines starting with - or * for bullet points
             - Blank lines for paragraph spacing
    Returns a download URL for the generated .pdf file.
    """
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Helvetica", "B", 18)
    pdf.multi_cell(0, 10, title, align="C")
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 11)

    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            pdf.ln(3)
        elif stripped.startswith("### "):
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(0, 7, stripped[4:])
            pdf.set_font("Helvetica", "", 11)
        elif stripped.startswith("## "):
            pdf.set_font("Helvetica", "B", 13)
            pdf.multi_cell(0, 8, stripped[3:])
            pdf.set_font("Helvetica", "", 11)
        elif stripped.startswith("# "):
            pdf.set_font("Helvetica", "B", 14)
            pdf.multi_cell(0, 9, stripped[2:])
            pdf.set_font("Helvetica", "", 11)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            pdf.multi_cell(0, 7, f"  - {stripped[2:]}")
        else:
            pdf.multi_cell(0, 7, stripped)

    _ensure_generated_dir()
    filename = f"{uuid.uuid4().hex}.pdf"
    pdf.output(os.path.join(_GENERATED_FILES_DIR, filename))
    logger.info("generate_pdf_document: created %s", filename)
    return f"PDF document created successfully.\n\n[Download {title}.pdf]({_API_BASE_URL}/files/{filename})"


def make_document_search_tool(retriever):
    @tool
    def search_documents(query: str) -> str:
        """Search uploaded company documents for information, policies, procedures, and guidelines.
        Use this for ANY question about content in uploaded documents — product details, pricing,
        procedures, company policies, project information, or any other document content.
        Always search documents before answering questions about company-specific information.
        """
        docs = retriever.invoke(query)
        return "\n\n".join(d.page_content for d in docs) if docs else "No relevant information found in uploaded documents."
    return search_documents


class Tools:
    tools = [web_search, generate_presentation, generate_word_document, generate_pdf_document]
