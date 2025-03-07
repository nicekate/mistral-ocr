# Mistral OCR PDF 处理工具

这个项目是一个简单但强大的工具，用于使用 Mistral AI 的 OCR (光学字符识别) 功能处理 PDF 文件。该工具能够从 PDF 文档中提取文本内容和图像，并将结果保存为 Markdown 格式。

## 功能特点

- 使用 Mistral AI 的 OCR 能力处理 PDF 文件
- 自动提取文本内容并保留原始布局
- 提取并保存 PDF 中的图像
- 生成包含完整内容的 Markdown 文件
- 支持中文等多种语言

## 安装要求

运行此工具需要以下依赖项：

```bash
pip install mistralai
```

## 使用方法

1. 获取 Mistral AI API 密钥
2. 修改 `pdf_ocr.py` 中的 API 密钥和 PDF 文件路径
3. 运行脚本处理 PDF 文件

```python
# 在 pdf_ocr.py 中设置
API_KEY = "your_mistral_api_key"
PDF_PATH = "your_pdf_file.pdf"

# 然后运行脚本
python pdf_ocr.py
```

## 输出结果

脚本将在工作目录下创建一个名为 `ocr_results_[PDF文件名]` 的文件夹，其中包含：

- `complete.md`: 包含所有页面内容的 Markdown 文件
- `images/`: 保存 PDF 中提取出的所有图像的文件夹


## 注意事项

- 请确保 PDF 文件路径正确
- API 密钥需要具有 OCR 功能的访问权限


