# Docling 测试项目

这是一个使用 Docling 库进行文档处理的测试项目，主要功能包括 OCR 识别、文档转换和 LLM 处理。

## 项目结构

```
docling-test/
├── output/             # 输出文件目录
├── test/               # 测试文档目录
│   ├── docling.pdf     # 测试文档
│   └── km-test.pdf     # 测试文档
├── .env                # 环境变量配置（不包含在版本控制中）
├── .env.example        # 环境变量示例
├── main_custom.py      # 自定义文档处理示例
├── main_exrpot.py      # 文档导出示例
├── main_llm_ocr_simgle.py  # 使用 LLM 进行单文件 OCR 处理
├── main_lm_ocr_dir.py  # 使用 LLM 进行目录 OCR 处理
├── main_ocr.py         # 基本 OCR 处理示例
└── main_raw.py         # 原始文档处理示例
```

## 环境配置

1. 安装依赖：

```bash
pip install docling
```

2. 配置环境变量：

复制 `.env.example` 到 `.env` 并填入您的 API 密钥：

```bash
cp .env.example .env
```

3. 安装 Tesseract OCR（如果使用 OCR 功能）：

从 [Tesseract GitHub](https://github.com/UB-Mannheim/tesseract/wiki) 下载并安装。

## 环境变量配置

本项目使用环境变量来存储敏感配置信息，如OSS访问凭证。请按照以下步骤设置环境变量：

1. 在项目根目录创建一个名为`.env`的文件
2. 在`.env`文件中添加以下配置（替换为你自己的值）：

```
# OSS配置
OSS_ENDPOINT=oss-cn-beijing.aliyuncs.com
OSS_ACCESS_KEY_ID=your_access_key_id_here
OSS_ACCESS_KEY_SECRET=your_access_key_secret_here
OSS_BUCKET_NAME=your_bucket_name_here
```

注意：`.env`文件包含敏感信息，请不要将其提交到版本控制系统中。

## 使用方法

### 基本 OCR 处理

```bash
python main_ocr.py
```

### 使用 LLM 进行 OCR 处理

```bash
python main_llm_ocr_simgle.py
```

### 批量处理目录

```bash
python main_lm_ocr_dir.py
```

## 注意事项

- 使用 OCR 功能需要安装 Tesseract
- 使用 LLM 功能需要配置相应的 API 密钥
- 请确保 `test` 和 `output` 目录存在 