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
pip install mistralai flask
```

## 使用方法

1.  **设置环境变量**:
    *   获取您的 Mistral AI API 密钥。
    *   设置 `MISTRAL_API_KEY` 环境变量。例如，在 Linux 或 macOS 上：
        ```bash
        export MISTRAL_API_KEY="your_actual_api_key"
        ```
        在 Windows 上，您可以在 PowerShell 中使用:
        ```powershell
        $Env:MISTRAL_API_KEY="your_actual_api_key"
        ```
        或者通过系统属性设置。

2.  **运行脚本**:
    *   使用以下命令运行脚本，将 `your_document.pdf` 替换为您的 PDF 文件的实际路径：
        ```bash
        python pdf_ocr.py your_document.pdf
        ```
    *   您可以选择使用 `-o` 或 `--output_dir` 参数指定自定义输出目录：
        ```bash
        python pdf_ocr.py your_document.pdf -o custom_output_folder
        ```
        如果未提供输出目录，结果将保存在名为 `ocr_results_[PDF文件名]` 的文件夹中，该文件夹将在脚本运行的目录中创建。

3.  **启动 Web UI**:
    * 通过以下命令启动简易 Web 界面，可一次上传并处理多个 PDF 文件：
        ```bash
        python webui.py
        ```
    * 浏览器访问 `http://localhost:8080` 即可使用。上传的文件必须是 PDF，处理完成后会提供打包好的 ZIP 下载。
    * 新版界面使用 Bootstrap 样式，美观且易用。

## 输出结果

脚本将根据指定的输出目录（或默认目录 `ocr_results_[PDF文件名]`）创建一个文件夹，其中包含：

- `complete.md`: 包含所有页面内容的 Markdown 文件
- `images/`: 保存 PDF 中提取出的所有图像的文件夹


## 注意事项

- 请确保提供的 PDF 文件路径正确且文件可访问。
- API 密钥需要具有 OCR 功能的访问权限。
- 如果指定的输出目录已存在，脚本仍会尝试在其中创建 `images` 子目录和 `complete.md` 文件。现有同名文件可能会被覆盖。


