from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TesseractCliOcrOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption


def main():
    input_doc = Path("./test/docling.pdf")
    output_path = "./output/docling.md"  # 修改为你希望保存的路径

    # Set lang=["eng"] for English documents
    ocr_options = TesseractCliOcrOptions(
        lang=["eng"],  # 明确指定英文语言
        tesseract_cmd="C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
    )

    pipeline_options = PdfPipelineOptions(
        do_ocr=True, force_full_page_ocr=True, ocr_options=ocr_options
    )

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
            )
        }
    )

    doc = converter.convert(input_doc).document
    markdown_text = doc.export_to_markdown()

    # 保存到本地 Markdown 文件
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown_text)

if __name__ == "__main__":
    main()