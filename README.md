# Mistral OCR 文档处理工具

![WebUI 预览](http://blog-bucket-20240321.oss-cn-hongkong.aliyuncs.com/blog/x9trs7.png)

这个项目使用 `mistral-ocr-latest` 模型处理 **PDF 与图片**（当前对应 **Mistral OCR 4**），提取文本与图像并保存为 Markdown。

## 功能特点

- 🚀 使用 `mistral-ocr-latest` 模型（当前对应 Mistral OCR 4）
- 📄 支持 PDF 与图片输入（PNG、JPG、WebP、GIF、BMP、TIFF）
- 🖼️ 提取并保存文档中的图像
- 📝 生成以原文件名命名的 Markdown 文件
- 🌏 支持中文等多种语言
- 🌐 **Web UI 支持**：
  - 实时进度展示
  - 最多 5 个文件并发处理
  - 暂停/继续/取消任务
  - 部分完成文件支持下载
  - 下载文件带时间戳命名

## 安装要求

```bash
pip install "mistralai>=2" flask
```

SDK 兼容 `mistralai` 1.x / 2.x，代码优先使用 2.x；若环境仅有 1.x 也可运行。

## 使用方法

### 1. 获取 API 密钥

1. 访问 [Mistral AI Console](https://console.mistral.ai/) 注册或登录账号
2. 进入 [API Keys 页面](https://console.mistral.ai/api-keys/) 创建 API 密钥
3. 更多信息请参考 [Mistral AI 快速入门文档](https://docs.mistral.ai/getting-started/quickstart)

### 2. 设置环境变量

在 Linux 或 macOS 上：
```bash
export MISTRAL_API_KEY="your_actual_api_key"
```

在 Windows PowerShell 中：
```powershell
$Env:MISTRAL_API_KEY="your_actual_api_key"
```

### 3. 启动 Web UI（推荐）

```bash
python webui.py
```

浏览器访问 `http://localhost:8080`，可上传 PDF 或图片批量处理。

### 4. 命令行模式（可选）

```bash
python pdf_ocr.py your_document.pdf
python pdf_ocr.py photo.png
python pdf_ocr.py scan.jpg -o custom_output_folder
```

未指定输出目录时，结果保存在 `ocr_results_[文件名]` 文件夹中。

## 输出结果

每个文件会生成一个输出目录，包含：

- `[文件名].md`：OCR 识别的 Markdown 内容
- `images/`：提取出的图像（如有）

下载的 ZIP 文件命名格式：`ocr_results_YYYYMMDD_HHMMSS.zip`

## 注意事项

- 请确保文件路径正确且文件可访问
- API 密钥需要具有 OCR 功能的访问权限
- 若输出目录已存在，同名 `.md` 文件可能会被覆盖