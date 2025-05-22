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
DOC_ALIGNMENT = "Left"
DOC_WIDTH = "700"


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
import io
import oss2
import logging
from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv()

# 从环境变量中获取OSS配置
endpoint = os.getenv('OSS_ENDPOINT')
access_key_id = os.getenv('OSS_ACCESS_KEY_ID')
access_key_secret = os.getenv('OSS_ACCESS_KEY_SECRET')
bucket_name = os.getenv('OSS_BUCKET_NAME')


auth = oss2.Auth(access_key_id, access_key_secret)
bucket = oss2.Bucket(auth, endpoint, bucket_name)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 获取OSS Bucket绑定的自定义域名
def get_custom_domain():
    try:
        # 获取Bucket绑定的所有CNAME记录
        list_result = bucket.list_bucket_cname()
        custom_domains = []
        
        # 遍历所有CNAME记录查找状态正常的域名
        for cname in list_result.cname:
            if cname.status == 'Enabled':
                custom_domains.append(cname.domain)
                logging.info(f"发现绑定的自定义域名: {cname.domain}")
        
        # 如果有绑定的域名，返回第一个
        if custom_domains:
            return custom_domains[0]
        else:
            logging.warning("未找到绑定的自定义域名，将使用默认OSS域名")
            return None
    except Exception as e:
        logging.error(f"获取自定义域名时出错: {str(e)}")
        return None

# 获取绑定的自定义域名
custom_domain = get_custom_domain()

img_count = 0
for item, level in doc.iterate_items(with_groups=False):
    if isinstance(item, PictureItem):
        
        # 拿到识别的图片Data
        img = item.image.pil_image

        # 生成图片的hash值, 用于生成图片的唯一标识
        hexhash = item._image_to_hexhash()
        if hexhash is not None:
            file_name = f"image_{img_count:06}_{hexhash}.png"
            
            # 将图片转换为字节流
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()
            
            # 上传到OSS
            oss_path = f"docling/{file_name}"
            try:
                result = bucket.put_object(oss_path, img_byte_arr)
                if result.status == 200:
                    # 根据是否有自定义域名构建OSS URL
                    if custom_domain:
                        # 使用自定义域名构建URL
                        oss_url = f"https://{custom_domain}/{oss_path}"
                    else:
                        # 使用默认OSS域名构建URL
                        oss_url = f"https://{bucket.bucket_name}.{endpoint}/{oss_path}"
                    
                    # 设置图片路径为OSS URL
                    item.image.uri = oss_url
                    logging.info(f"上传图片成功: {oss_url}")
                else:
                    logging.error(f"上传图片失败，状态码: {result.status}")
                    # 上传失败时可以选择保存到本地
                    loc_path = Path("./output/images") / file_name
                    img.save(loc_path)
                    obj_path = Path("./images") / file_name
                    item.image.uri = Path(obj_path)
            except Exception as e:
                logging.error(f"上传图片异常: {str(e)}")
                # 发生异常时保存到本地
                loc_path = Path("./output/images") / file_name
                img.save(loc_path)
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

import re 
from typing import Any, Optional # 确保导入 Optional



class AnnotationPictureSerializer(MarkdownPictureSerializer):
    @override
    def serialize(
        self,
        *,
        item: PictureItem,
        doc_serializer: BaseDocSerializer,
        doc: DoclingDocument,
        separator: Optional[str] = None, # 您代码中已有的参数
        **kwargs: Any,
    ) -> SerializationResult:
        text_parts: list[str] = []

        # 1. 调用父类的 serialize 方法获取原始的 Markdown 图片标签
        parent_res = super().serialize(
            item=item,
            doc_serializer=doc_serializer,
            doc=doc,
            **kwargs, # 根据您的代码保留
        )
        original_markdown_tag = parent_res.text
        modified_markdown_tag = original_markdown_tag # 默认为原始标签

        # 2. 解析原始标签并替换为自定义格式
        #    正则表达式 r"!\[(.*?)\]\((.*?)\)" 用于匹配 ![alt_text](url)
        #    - 第一个捕获组 (.*?) 是 alt_text
        #    - 第二个捕获组 (.*?) 是 url
        match = re.fullmatch(r"!\[(.*?)\]\((.*?)\)", original_markdown_tag)
        
        if match:
            # original_alt_text = match.group(1) # 原始的 alt 文本 (例如 "Image")
            url = match.group(2)              # 图片的 URL

            # 定义您想要的自定义属性

            
            # 构建新的 alt 文本部分，格式为 "Image|Alignment|Width"
            # 注意：这里我们固定使用 "Image" 作为前缀，符合您的目标格式
            new_alt_text_with_attrs = f"Image|{DOC_ALIGNMENT}|{DOC_WIDTH}"
            
            # 构建新的、包含自定义属性的 Markdown 图片标签
            modified_markdown_tag = f"![{new_alt_text_with_attrs}]({url})"
        
        text_parts.append(modified_markdown_tag)

        # 3. 追加其他注解 (您现有的逻辑)
        for annotation in item.annotations: # type: ignore
            if isinstance(annotation, PictureDescriptionData):
                # text_parts.append(f"")
                text_parts.append(f"> Picture Description: {annotation.text}") # type: ignore

        # 4. 使用分隔符连接所有部分
        text_res = (separator or "\n").join(text_parts)
        
        # 5. 创建并返回序列化结果
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

# 获取序列化结果，并保存到本地Markdown文件  
ser_result = serializer.serialize()
output_path = "./output/custom_serializer.md"  # 修改为你希望保存的路径  
with open(output_path, "w", encoding="utf-8") as f:  
    f.write(ser_result.text)  

