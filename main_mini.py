import logging
import time
from pathlib import Path

from docling_core.types.doc import ImageRefMode, PictureItem, TableItem

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

_log = logging.getLogger(__name__)

IMAGE_RESOLUTION_SCALE = 2.0

def main():
    logging.basicConfig(level=logging.INFO)

    input_doc_path = Path("./test/docling.pdf")
    output_dir = Path("output")

    # Important: For operating with page images, we must keep them, otherwise the DocumentConverter
    # will destroy them for cleaning up memory.
    # This is done by setting PdfPipelineOptions.images_scale, which also defines the scale of images.
    # scale=1 correspond of a standard 72 DPI image
    # The PdfPipelineOptions.generate_* are the selectors for the document elements which will be enriched
    # with the image field
    pipeline_options = PdfPipelineOptions()


    doc_converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )

    start_time = time.time()

    conv_res = doc_converter.convert(input_doc_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    doc_filename = conv_res.input.file.stem



    # Save markdown with externally referenced pictures
    md_filename = output_dir / f"{doc_filename}-mini.md"
    conv_res.document.save_as_markdown(md_filename)



    end_time = time.time() - start_time

    _log.info(f"Document converted and figures exported in {end_time:.2f} seconds.")

if __name__ == "__main__":
    main()