import logging
import time
from pathlib import Path

from docling_core.types.doc import ImageRefMode, PictureItem, TableItem

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

_log = logging.getLogger(__name__)

DOC_SOURCE = "https://arxiv.org/pdf/2311.18481"

# we set some start-stop cues for defining an excerpt to print
start_cue = "Copyright © 2024"
stop_cue = "Application of NLP to ESG"


from rich.console import Console
from rich.panel import Panel

console = Console(width=210)  # for preventing Markdown table wrapped rendering

def print_in_console(text):
    console.print(Panel(text))

from docling.document_converter import DocumentConverter

converter = DocumentConverter()
doc = converter.convert(source=DOC_SOURCE).document

# from docling_core.transforms.serializer.html import HTMLDocSerializer

# serializer = HTMLDocSerializer(doc=doc)
# ser_result = serializer.serialize()
# ser_text = ser_result.text

# # we here only print an excerpt to keep the output brief:
# print_in_console(ser_text[ser_text.find(start_cue) : ser_text.find(stop_cue)])

########################################################

# from docling_core.transforms.serializer.markdown import MarkdownDocSerializer

# serializer = MarkdownDocSerializer(doc=doc)
# ser_result = serializer.serialize()
# ser_text = ser_result.text

# print_in_console(ser_text[ser_text.find(start_cue) : ser_text.find(stop_cue)])

########################################################

from docling_core.transforms.serializer.markdown import MarkdownDocSerializer
from docling_core.transforms.chunker.hierarchical_chunker import TripletTableSerializer
from docling_core.transforms.serializer.markdown import MarkdownParams

serializer = MarkdownDocSerializer(
    doc=doc,
    table_serializer=TripletTableSerializer(),
    params=MarkdownParams(
        image_placeholder="<!-- demo picture placeholder -->",
        # ...
    ),
)
ser_result = serializer.serialize()
ser_text = ser_result.text

print_in_console(ser_text[ser_text.find(start_cue) : ser_text.find(stop_cue)])