import os
from typing import List
from pathlib import Path

from huggingface_hub import snapshot_download

from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
from docling.document_converter import (
    ConversionResult,
    DocumentConverter,
    InputFormat,
    PdfFormatOption,
)

from docling_core.types.doc import ImageRefMode, PictureItem, TableItem

import time
import logging
_log = logging.getLogger(__name__)

def main():

    input_doc_path = Path("./test3/2025-05-20.pdf")
    output_dir = Path("output")

    # Download RappidOCR models from HuggingFace
    print("Downloading RapidOCR models")
    download_path = snapshot_download(repo_id="SWHL/RapidOCR")

    # Setup RapidOcrOptions for english detection
    # det_model_path = os.path.join(
    #     download_path, "PP-OCRv4", "en_PP-OCRv3_det_infer.onnx"
    # )
    # rec_model_path = os.path.join(
    #     download_path, "PP-OCRv4", "ch_PP-OCRv4_rec_server_infer.onnx"
    # )
    # cls_model_path = os.path.join(
    #     download_path, "PP-OCRv3", "ch_ppocr_mobile_v2.0_cls_train.onnx"
    # )

    # 中文检测和识别
    det_model_path = os.path.join(download_path, "PP-OCRv4", "ch_PP-OCRv4_det_infer.onnx")      # 检测模型
    rec_model_path = os.path.join(download_path, "PP-OCRv4", "ch_PP-OCRv4_rec_server_infer.onnx") # 中文识别
    cls_model_path = os.path.join(download_path, "PP-OCRv3", "ch_ppocr_mobile_v2.0_cls_train.onnx") # 方向分类
    
    lang: List[str] = ['english', 'chinese']

    ocr_options = RapidOcrOptions(
        det_model_path=det_model_path,
        rec_model_path=rec_model_path,
        cls_model_path=cls_model_path,
        lang=lang,
    )

    pipeline_options = PdfPipelineOptions(
        ocr_options=ocr_options        
        # do_ocr=True,   
        generate_page_images=True,  # 生成页面图片  
        generate_picture_images=True,  # 生成图片元素的图片  
        images_scale=2  # 提高图片质量  
    )

    start_time = time.time()

    # Convert the document
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
            ),
        },
    )

    conv_res = converter.convert(input_doc_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    doc_filename = conv_res.input.file.stem


    # Save markdown with externally referenced pictures
    md_filename = output_dir / f"{doc_filename}-rapid-ocr.md"
    conv_res.document.save_as_markdown(md_filename, image_mode=ImageRefMode.REFERENCED)


    end_time = time.time() - start_time

    _log.info(f"Document converted and figures exported in {end_time:.2f} seconds.")

if __name__ == "__main__":
    main()