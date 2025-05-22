from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    RapidOcrOptions,
    PictureDescriptionVlmOptions,
    PictureDescriptionApiOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption


# DOC_SOURCE = "https://arxiv.org/pdf/2311.18481"
DOC_SOURCE = "./test3/2025-05-20.pdf"


from rich.console import Console
from rich.panel import Panel

console = Console(width=210)  # for preventing Markdown table wrapped rendering

def print_in_console(text):
    console.print(Panel(text))


# 设置 ollama 服务器
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

# 中文检测和识别，使用 RapidOCR 模型
import os
from huggingface_hub import snapshot_download
from typing import List

download_path = snapshot_download(repo_id="SWHL/RapidOCR")
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

# 设置 pipeline 选项，包括两个部分：
# 1. 图片描述
# 2. 图片生成
pipeline_options = PdfPipelineOptions(
    do_picture_description=True,
    picture_description_options=vllm_local_options("qwen2.5vl:latest"),
    enable_remote_services=True,
    images_scale=2,
    generate_page_images = True,
    generate_picture_images = True,
    ocr_options=ocr_options,
    do_picture_classification = True,
    # do_code_enrichment = True,
    # do_ocr = True,
    # do_table_structure = True,
    # accelerator_options = AcceleratorOptions(
    #     num_threads=4, device=AcceleratorDevice.AUTO
    # ),
)

# 创建 DocumentConverter 对象，完成 pdf 文件的转换
converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
)
doc = converter.convert(source=DOC_SOURCE).document


########################################################
# 处理图片
########################################################

from pydantic import AnyUrl, BaseModel
from pathlib import Path
from docling_core.types.doc import PictureItem

img_count = 0
for item, level in doc.iterate_items(with_groups=False):
    if isinstance(item, PictureItem):
        
        # 拿到识别的图片Data
        img = item.image.pil_image

        # 生成图片的hash值, 用于生成图片的唯一标识, 存入本地
        hexhash = item._image_to_hexhash()
        if hexhash is not None:
            file_name = f"image_{img_count:06}_{hexhash}.png"
            loc_path = Path("./output/images") / file_name
            img.save(loc_path)  

            # 设置图片路径  
            obj_path = Path("./images") / file_name
            item.image.uri = Path(obj_path)
    img_count += 1




from docling_core.transforms.serializer.markdown import MarkdownDocSerializer
from docling_core.transforms.chunker.hierarchical_chunker import TripletTableSerializer
from docling_core.transforms.serializer.markdown import MarkdownParams
from typing import Any, Optional

from docling_core.transforms.serializer.base import (
    BaseDocSerializer,
    SerializationResult,
)
from docling_core.transforms.serializer.common import create_ser_result
from docling_core.transforms.serializer.markdown import (
    MarkdownParams,
    MarkdownPictureSerializer,
)
from docling_core.types.doc.document import (
    DoclingDocument,
    ImageRefMode,
    PictureDescriptionData,
    PictureClassificationData,
    PictureItem,
)
from typing_extensions import override


########################################################
# 自定义PictureSerializer，完成自定义序列化
########################################################


class AnnotationPictureSerializer(MarkdownPictureSerializer):
    @override
    def serialize(
        self,
        *,
        item: PictureItem,
        doc_serializer: BaseDocSerializer,
        doc: DoclingDocument,
        separator: Optional[str] = None,
        **kwargs: Any,
    ) -> SerializationResult:
        text_parts: list[str] = []

        # reusing the existing result:
        parent_res = super().serialize(
            item=item,
            doc_serializer=doc_serializer,
            doc=doc,
            **kwargs,
        )
        text_parts.append(parent_res.text)

        # appending annotations:
        for annotation in item.annotations:
            if isinstance(annotation, PictureDescriptionData):
                # text_parts.append(f"<!-- Picture description: {annotation.text} -->")
                text_parts.append(f"> Picture Description: {annotation.text}")
            elif isinstance(annotation, PictureClassificationData):
                # predicted_class = None
                # if annotation.predicted_classes: #
                #     # 获取预测的第一个类别名称
                #     predicted_class = annotation.predicted_classes[0].class_name #

                # if predicted_class is not None:
                #     # 将图片类型信息添加到序列化文本中
                #     text_parts.append(f"> Picture Type: {predicted_class}") #
                       # 修改此部分以输出所有分类
                if annotation.predicted_classes:  # 检查是否存在预测类别列表
                    all_class_names = []
                    for predicted_class_obj in annotation.predicted_classes:
                        if predicted_class_obj.class_name: # 确保 class_name 存在且不为空
                            all_class_names.append(predicted_class_obj.class_name)
                    
                    if all_class_names: # 如果收集到了任何类别名称
                        # 将所有类别名称用逗号和空格连接起来
                        formatted_classes = ", ".join(all_class_names)
                        text_parts.append(f"Picture Types: {formatted_classes}")

        text_res = (separator or "\n").join(text_parts)
        return create_ser_result(text=text_res, span_source=item)

serializer = MarkdownDocSerializer(
    doc=doc,
    table_serializer=TripletTableSerializer(),
    picture_serializer=AnnotationPictureSerializer(),
    params=MarkdownParams(
        image_mode=ImageRefMode.REFERENCED,
        image_placeholder="",
    ),
)
ser_result = serializer.serialize()
ser_text = ser_result.text

# print_in_console(ser_text[ser_text.find(start_cue) : ser_text.find(stop_cue)])


# 保存到本地Markdown文件  
output_path = "./output/custom_serializer.md"  # 修改为你希望保存的路径  
with open(output_path, "w", encoding="utf-8") as f:  
    f.write(ser_text)  

