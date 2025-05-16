from pathlib import Path  
  
from docling.datamodel.base_models import InputFormat  
from docling_core.types.doc import ImageRefMode  # Correct import  
from docling.datamodel.pipeline_options import (  
    PdfPipelineOptions,  
    RapidOcrOptions,  
)  
from docling.document_converter import DocumentConverter, PdfFormatOption  
  
  
def main():  
    input_doc = Path("./test2/mixedText.pdf")  
    output_path = "./output/mixedText.md"  # 修改为你希望保存的路径  
      
    # 创建输出目录（如果不存在）  
    Path("./output").mkdir(exist_ok=True)  
  
    pipeline_options = PdfPipelineOptions(  
        do_ocr=True,   
        ocr_options=RapidOcrOptions(  
            # lang=["ch_sim"],  
            force_full_page_ocr=True,  # 启用全页OCR  
            # confidence_threshold=0.3  # 降低置信度阈值  
        ),  
        generate_page_images=True,  # 生成页面图片  
        generate_picture_images=True,  # 生成图片元素的图片  
        images_scale=2  # 提高图片质量  
    )  
  
    converter = DocumentConverter(  
        format_options={  
            InputFormat.PDF: PdfFormatOption(  
                pipeline_options=pipeline_options,  
            )  
        }  
    )  
  
    doc = converter.convert(input_doc).document  
      
    # 使用EMBEDDED模式导出Markdown  
    markdown_text = doc.export_to_markdown(image_mode=ImageRefMode.EMBEDDED)  
  
    # 保存到本地Markdown文件  
    with open(output_path, "w", encoding="utf-8") as f:  
        f.write(markdown_text)  
      
    print(f"文档已成功转换并保存到 {output_path}")  
  
if __name__ == "__main__":  
    main()