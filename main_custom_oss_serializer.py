import os
import io
import re
import logging
import oss2
from typing import List, Any, Optional
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from huggingface_hub import snapshot_download
from typing_extensions import override

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    RapidOcrOptions,
    PictureDescriptionVlmOptions,
    PictureDescriptionApiOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.transforms.serializer.markdown import MarkdownDocSerializer, MarkdownParams
from docling_core.transforms.chunker.hierarchical_chunker import TripletTableSerializer
from docling_core.transforms.serializer.base import BaseDocSerializer, SerializationResult
from docling_core.transforms.serializer.common import create_ser_result
from docling_core.transforms.serializer.markdown import MarkdownPictureSerializer
from docling_core.types.doc.document import (
    DoclingDocument,
    ImageRefMode,
    PictureDescriptionData,
    PictureClassificationData,
    PictureItem,
)
from docling_core.types.doc import PictureItem


class ConfigManager:
    """配置管理类，用于管理文档处理的基本配置"""
    def __init__(self, doc_source, doc_dst, doc_alignment="Left", doc_width="700"):
        self.doc_source = doc_source
        self.doc_dst = doc_dst
        self.doc_alignment = doc_alignment
        self.doc_width = doc_width


class ConsolePrinter:
    """控制台输出类，用于格式化输出信息"""
    def __init__(self, width=210):
        self.console = Console(width=width)  # 防止 Markdown 表格换行渲染
        
    def print_panel(self, text):
        """在面板中打印文本"""
        self.console.print(Panel(text))


class VlmConfiguration:
    """VLM配置类，处理视觉语言模型的配置"""
    @staticmethod
    def get_local_options(model):
        """获取本地VLM模型的配置选项"""
        return PictureDescriptionApiOptions(
            url="http://localhost:11434/v1/chat/completions",
            params=dict(
                model=model,
                seed=42,
                max_completion_tokens=200,
            ),
            prompt="Describe the image in three sentences. Be consise and accurate.",
            timeout=90,
        )


class OcrConfiguration:
    """OCR配置类，负责光学字符识别的配置"""
    @staticmethod
    def get_rapid_ocr_options():
        """获取RapidOCR模型的配置选项"""
        download_path = snapshot_download(repo_id="SWHL/RapidOCR")
        det_model_path = os.path.join(download_path, "PP-OCRv4", "ch_PP-OCRv4_det_infer.onnx")      # 检测模型
        rec_model_path = os.path.join(download_path, "PP-OCRv4", "ch_PP-OCRv4_rec_server_infer.onnx") # 中文识别
        cls_model_path = os.path.join(download_path, "PP-OCRv3", "ch_ppocr_mobile_v2.0_cls_train.onnx") # 方向分类

        lang: List[str] = ['english', 'chinese']

        return RapidOcrOptions(
            det_model_path=det_model_path,
            rec_model_path=rec_model_path,
            cls_model_path=cls_model_path,
            lang=lang,
        )


class OssImageUploader:
    """OSS图片上传类，处理图片上传到阿里云OSS的逻辑"""
    def __init__(self):
        # 配置日志
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # 加载.env文件中的环境变量
        load_dotenv()
        
        # 从环境变量中获取OSS配置
        self.endpoint = os.getenv('OSS_ENDPOINT')
        self.access_key_id = os.getenv('OSS_ACCESS_KEY_ID')
        self.access_key_secret = os.getenv('OSS_ACCESS_KEY_SECRET')
        self.bucket_name = os.getenv('OSS_BUCKET_NAME')
        
        # 初始化OSS客户端
        self.auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        self.bucket = oss2.Bucket(self.auth, self.endpoint, self.bucket_name)
        
        # 获取自定义域名
        self.custom_domain = self._get_custom_domain()
    
    def _get_custom_domain(self):
        """获取OSS Bucket绑定的自定义域名"""
        try:
            # 获取Bucket绑定的所有CNAME记录
            list_result = self.bucket.list_bucket_cname()
            custom_domains = []
            
            # 遍历所有CNAME记录查找状态正常的域名
            for cname in list_result.cname:
                if cname.status == 'Enabled':
                    custom_domains.append(cname.domain)
                    self.logger.info(f"发现绑定的自定义域名: {cname.domain}")
            
            # 如果有绑定的域名，返回第一个
            if custom_domains:
                return custom_domains[0]
            else:
                self.logger.warning("未找到绑定的自定义域名，将使用默认OSS域名")
                return None
        except Exception as e:
            self.logger.error(f"获取自定义域名时出错: {str(e)}")
            return None
    
    def upload_image(self, image, image_hash, img_count):
        """上传图片到OSS，返回URL或本地路径"""
        file_name = f"image_{img_count:06}_{image_hash}.png"
        
        # 将图片转换为字节流
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        # 上传到OSS
        oss_path = f"docling/{file_name}"
        try:
            result = self.bucket.put_object(oss_path, img_byte_arr)
            if result.status == 200:
                # 根据是否有自定义域名构建OSS URL
                if self.custom_domain:
                    # 使用自定义域名构建URL
                    oss_url = f"https://{self.custom_domain}/{oss_path}"
                else:
                    # 使用默认OSS域名构建URL
                    oss_url = f"https://{self.bucket.bucket_name}.{self.endpoint}/{oss_path}"
                
                self.logger.info(f"上传图片成功: {oss_url}")
                return oss_url
            else:
                self.logger.error(f"上传图片失败，状态码: {result.status}")
                # 上传失败时保存到本地
                local_path = self._save_locally(image, file_name)
                return local_path
        except Exception as e:
            self.logger.error(f"上传图片异常: {str(e)}")
            # 发生异常时保存到本地
            local_path = self._save_locally(image, file_name)
            return local_path
    
    def _save_locally(self, image, file_name):
        """将图片保存到本地，返回路径"""
        # 确保输出目录存在
        output_dir = Path("./output/images")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        loc_path = output_dir / file_name
        image.save(loc_path)
        return Path("./images") / file_name


class AnnotationPictureSerializer(MarkdownPictureSerializer):
    """自定义图片序列化器，添加图片自定义属性和描述"""
    def __init__(self, doc_alignment, doc_width):
        super().__init__()
        self.doc_alignment = doc_alignment
        self.doc_width = doc_width
        
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

        # 1. 调用父类的 serialize 方法获取原始的 Markdown 图片标签
        parent_res = super().serialize(
            item=item,
            doc_serializer=doc_serializer,
            doc=doc,
            **kwargs,
        )
        original_markdown_tag = parent_res.text
        modified_markdown_tag = original_markdown_tag

        # 2. 解析原始标签并替换为自定义格式
        match = re.fullmatch(r"!\[(.*?)\]\((.*?)\)", original_markdown_tag)
        
        if match:
            url = match.group(2)
            new_alt_text_with_attrs = f"Image|{self.doc_alignment}|{self.doc_width}"
            modified_markdown_tag = f"![{new_alt_text_with_attrs}]({url})"
        
        text_parts.append(modified_markdown_tag)

        # 3. 追加其他注解
        for annotation in item.annotations:
            if isinstance(annotation, PictureDescriptionData):
                text_parts.append(f"> Picture Description: {annotation.text}")

        # 4. 使用分隔符连接所有部分
        text_res = (separator or "\n").join(text_parts)
        
        # 5. 创建并返回序列化结果
        return create_ser_result(text=text_res, span_source=item)


class DocumentProcessor:
    """文档处理类，负责整个文档处理流程"""
    def __init__(self, config_manager):
        self.config = config_manager
        self.oss_uploader = OssImageUploader()
    
    def setup_pipeline_options(self):
        """设置文档处理管道选项"""
        return PdfPipelineOptions(
            do_picture_description=True,
            picture_description_options=VlmConfiguration.get_local_options("qwen2.5vl:latest"),
            enable_remote_services=True,
            images_scale=2,
            generate_page_images=True,
            generate_picture_images=True,
            ocr_options=OcrConfiguration.get_rapid_ocr_options(),
            do_picture_classification=True,
        )
    
    def convert_document(self):
        """转换文档为内部表示"""
        pipeline_options = self.setup_pipeline_options()
        
        converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )
        
        return converter.convert(source=self.config.doc_source).document
    
    def process_images(self, doc):
        """处理文档中的图片，上传到OSS或保存到本地"""
        img_count = 0
        for item, level in doc.iterate_items(with_groups=False):
            if isinstance(item, PictureItem):
                # 拿到识别的图片Data
                img = item.image.pil_image

                # 生成图片的hash值
                hexhash = item._image_to_hexhash()
                if hexhash is not None:
                    uri = self.oss_uploader.upload_image(img, hexhash, img_count)
                    item.image.uri = uri
            img_count += 1
        
        return doc
    
    def serialize_document(self, doc):
        """序列化文档为Markdown格式"""
        serializer = MarkdownDocSerializer(
            doc=doc,
            table_serializer=TripletTableSerializer(),
            picture_serializer=AnnotationPictureSerializer(
                self.config.doc_alignment, 
                self.config.doc_width
            ),
            params=MarkdownParams(
                image_mode=ImageRefMode.REFERENCED,
                image_placeholder="",
            ),
        )
        
        return serializer.serialize()
    
    def save_markdown(self, ser_result):
        """保存序列化结果到Markdown文件"""
        # 确保输出目录存在
        output_path = self.config.doc_dst
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ser_result.text)
        
        return output_path
    
    def process(self):
        """执行完整的文档处理流程"""
        # 1. 转换文档
        doc = self.convert_document()
        
        # 2. 处理图片
        doc = self.process_images(doc)
        
        # 3. 序列化文档
        ser_result = self.serialize_document(doc)
        
        # 4. 保存Markdown
        output_path = self.save_markdown(ser_result)
        
        return output_path


def main():
    """主函数，执行整个文档处理流程"""
    # 创建配置管理器
    doc_source = "./test3/2025-05-20.pdf"
    doc_dst = "./output/results/processed_document.md"
    config = ConfigManager(doc_source, doc_dst)
    
    # 创建文档处理器
    processor = DocumentProcessor(config)
    
    # 处理文档
    output_path = processor.process()
    
    # 打印结果
    printer = ConsolePrinter()
    printer.print_panel(f"文档处理完成，输出文件：{output_path}")


if __name__ == "__main__":
    main()

