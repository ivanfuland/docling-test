import logging
import time
from pathlib import Path

from docling_core.types.doc import ImageRefMode, PictureItem, TableItem

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, PictureDescriptionApiOptions
from docling.document_converter import DocumentConverter, PdfFormatOption


_log = logging.getLogger(__name__)

IMAGE_RESOLUTION_SCALE = 2.0



def vllm_local_options(model: str):
    options = PictureDescriptionApiOptions(
        url="http://localhost:11434/v1/chat/completions",
        params=dict(
            model=model,
            seed=42,
            max_completion_tokens=200,
        ),
        prompt="Describe the image in three sentences. Be consise and accurate.",
        timeout=90,
    )
    return options

def main():
    logging.basicConfig(level=logging.INFO)

    input_doc_path = Path("./test3/2025-05-20.pdf")
    output_dir = Path("output")

    # 采用ollama的vllm模型
    pipeline_options = PdfPipelineOptions(
        enable_remote_services=True  # <-- this is required!
    )
    pipeline_options.do_picture_description = True
    pipeline_options.picture_description_options = vllm_local_options("qwen2.5vl:latest")


    # 生成图片
    pipeline_options.images_scale = IMAGE_RESOLUTION_SCALE
    pipeline_options.generate_page_images = True
    pipeline_options.generate_picture_images = True


    doc_converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )

    # 开始转化记录花费的时间
    start_time = time.time()    
    result = doc_converter.convert(input_doc_path)
    end_time = time.time() - start_time

    # 打印图片的描述
    for element, _level in result.document.iterate_items():
        if isinstance(element, PictureItem):
            print(
                f"Picture {element.self_ref}\n"
                f"Caption: {element.caption_text(doc=result.document)}\n"
                f"Annotations: {element.annotations}"
            )

    # # 存md文件
    # output_dir.mkdir(parents=True, exist_ok=True)
    # doc_filename = result.input.file.stem
    # md_filename = output_dir / f"{doc_filename}.md"
    # result.document.save_as_markdown(md_filename, image_mode=ImageRefMode.REFERENCED)


if __name__ == "__main__":
    main()