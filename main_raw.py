from docling.document_converter import DocumentConverter

# source = "./test/docling.pdf"  # document per local path or URL
# output_path = "./output/docling.md"  # 修改为你希望保存的路径

source = "./test/docling.pdf"  # document per local path or URL
output_path = "./output/docling.md"  # 修改为你希望保存的路径

converter = DocumentConverter()
result = converter.convert(source)

markdown_text = result.document.export_to_markdown()

# 保存到本地 Markdown 文件
with open(output_path, "w", encoding="utf-8") as f:
    f.write(markdown_text)

print(f"Markdown 已保存到：{output_path}")
