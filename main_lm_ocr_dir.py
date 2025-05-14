import logging
import os
from pathlib import Path
import litellm
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    ApiVlmOptions,
    ResponseFormat,
    VlmPipelineOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.pipeline.vlm_pipeline import VlmPipeline
import threading
import queue
import time

# 加载环境变量
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()


# 创建一个自定义的 API 服务器模拟器
class GeminiAPIServer:
    def __init__(self):
        self.is_running = False
        self.server_thread = None
        self.model_cache = {}

    def start(self):
        """启动 API 服务器"""
        import http.server
        import socketserver
        import json
        from urllib.parse import parse_qs, urlparse

        class CustomHandler(http.server.SimpleHTTPRequestHandler):
            server_obj = self

            def do_POST(self):
                if self.path == '/v1/chat/completions':
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)

                    try:
                        request_data = json.loads(post_data.decode('utf-8'))
                        response = self.handle_completion(request_data)

                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps(response).encode())
                    except Exception as e:
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        error_response = {"error": str(e)}
                        self.wfile.write(json.dumps(error_response).encode())
                else:
                    self.send_response(404)
                    self.end_headers()

            def handle_completion(self, request_data):
                model = request_data.get("model", "gemini-2.5-pro-preview-05-06")
                messages = request_data.get("messages", [])

                # 使用 liteLLM 进行实际调用
                try:
                    response = litellm.completion(
                        model=f"gemini/{model}",
                        messages=messages,
                        temperature=request_data.get("temperature", 0.1),
                        max_tokens=request_data.get("max_tokens", 65536)
                    )

                    # 确保响应格式符合 OpenAI 标准
                    return {
                        "id": response.id,
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": response.choices[0].message.content
                                },
                                "finish_reason": "stop"
                            }
                        ],
                        "usage": response.usage.dict() if response.usage else {}
                    }
                except Exception as e:
                    raise e

            def log_message(self, format, *args):
                pass  # 减少日志输出

        def run_server():
            with socketserver.TCPServer(("", 4000), CustomHandler) as httpd:
                httpd.timeout = 1  # 设置超时，便于优雅关闭
                self.httpd = httpd
                while self.is_running:
                    httpd.handle_request()

        self.is_running = True
        self.server_thread = threading.Thread(target=run_server)
        self.server_thread.start()
        time.sleep(2)  # 等待服务器启动

    def stop(self):
        """停止 API 服务器"""
        self.is_running = False
        if self.server_thread:
            self.server_thread.join(timeout=5)
        logging.info("API 服务器已停止")

# 全局 API 服务器实例
api_server = GeminiAPIServer()

def gemini_vlm_options(model: str, prompt: str, timeout: int = 300):
    """配置 Gemini 的 VLM 选项"""
    options = ApiVlmOptions(
        url="http://localhost:4000/v1/chat/completions",
        params=dict(
            model=model,
            max_tokens=65536,
            temperature=1,
        ),
        prompt=prompt,
        timeout=timeout,
        scale=1.0, # 图片缩放比例
        response_format=ResponseFormat.MARKDOWN,
    )
    return options

def process_single_pdf(pdf_path: Path, output_dir: Path, model_name: str = "gemini-2.5-pro-preview-05-06"):
    """处理单个PDF文件"""
    logging.info(f"正在处理: {pdf_path.name}")

    # 配置VLM流水线
    pipeline_options = VlmPipelineOptions(
        enable_remote_services=True
    )

    pipeline_options.vlm_options = gemini_vlm_options(
        model=model_name,
        prompt="OCR the full page to markdown.",
        timeout=300
    )

    # 创建文档转换器
    doc_converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
                pipeline_cls=VlmPipeline,
            )
        }
    )

    try:
        # 执行转换
        result = doc_converter.convert(pdf_path)

        # 保存结果
        markdown_content = result.document.export_to_markdown()
        output_file = output_dir / f"{pdf_path.stem}_content.md"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        logging.info(f"转换完成，结果已保存到: {output_file}")
        return True, output_file

    except Exception as e:
        logging.error(f"处理 {pdf_path.name} 时出错: {e}")
        return False, None

def process_pdf_folder(input_folder: str, output_folder: str = "./output", model_name: str = "gemini-2.5-pro-preview-05-06"):
    """处理指定文件夹中的所有PDF文件"""

    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # 检查环境变量
    if not os.getenv("GEMINI_API_KEY"):
        logging.error("未设置 GEMINI_API_KEY 环境变量")
        logging.error("请设置你的 Gemini API 密钥: export GEMINI_API_KEY='your-api-key'")
        return

    # 初始化 liteLLM
    os.environ["LITELLM_LOG"] = "ERROR"  # 减少日志输出

    # 启动本地 API 服务器
    logging.info("=== 启动本地 API 服务器 ===")
    try:
        api_server.start()
        logging.info("API 服务器启动成功")
    except Exception as e:
        logging.error(f"无法启动 API 服务器: {e}")
        return

    # 检查输入文件夹
    input_path = Path(input_folder)
    if not input_path.exists():
        logging.error(f"输入文件夹不存在: {input_folder}")
        api_server.stop()
        return

    # 创建输出文件夹
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        # 查找所有PDF文件
        pdf_files = list(input_path.glob("*.pdf"))
        if not pdf_files:
            logging.warning(f"在 {input_folder} 中未找到PDF文件")
            return

        logging.info(f"找到 {len(pdf_files)} 个PDF文件")

        # 处理每个PDF文件
        success_count = 0
        failed_files = []

        for i, pdf_file in enumerate(pdf_files, 1):
            logging.info(f"\n=== 处理第 {i}/{len(pdf_files)} 个文件 ===")
            success, output_file = process_single_pdf(pdf_file, output_path, model_name)

            if success:
                success_count += 1
                # 显示部分内容预览
                with open(output_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    print(f"\n--- {pdf_file.name} 转换结果预览 ---")
                    print(content[:200] + "..." if len(content) > 200 else content)
            else:
                failed_files.append(pdf_file.name)

        # 输出处理结果统计
        logging.info(f"\n=== 处理完成 ===")
        logging.info(f"成功处理: {success_count}/{len(pdf_files)} 个文件")
        if failed_files:
            logging.warning(f"失败文件: {', '.join(failed_files)}")

    finally:
        # 停止服务器
        api_server.stop()

def main():
    """主函数"""
    # 设置输入文件夹
    input_folder = "./test"  # 修改为你的PDF文件夹路径

    # 设置输出文件夹
    output_folder = "./output"  # 结果保存位置

    # 设置模型名称
    model_name = "gemini-2.5-pro-preview-05-06"  # 使用 Gemini 2.5 Pro Preview

    # 处理指定文件夹中的所有PDF
    process_pdf_folder(input_folder, output_folder, model_name)

if __name__ == "__main__":
    main()
