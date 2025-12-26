# Mistral OCR PDF 处理工具

![WebUI 预览](http://blog-bucket-20240321.oss-cn-hongkong.aliyuncs.com/blog/x9trs7.png)

这个项目是一个简单但强大的工具，使用 **Mistral OCR 3**（最新版本）处理 PDF 文件。该工具能够从 PDF 文档中提取文本内容和图像，并将结果保存为 Markdown 格式。

## 功能特点

- 🚀 使用最新的 **Mistral OCR 3** 模型，识别精度更高
- 📄 自动提取文本内容并保留原始布局
- 🖼️ 提取并保存 PDF 中的图像
- 📝 生成以 PDF 原名命名的 Markdown 文件
- 🌏 支持中文等多种语言
- 🌐 **Web UI 支持**：
  - 实时进度展示
  - 最多 5 个 PDF 并发处理
  - 暂停/继续/取消任务
  - 部分完成文件支持下载
  - 下载文件带时间戳命名

## 安装要求

运行此工具需要以下依赖项：

```bash
pip install mistralai flask
```

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

通过以下命令启动 Web 界面，支持批量上传和并发处理：
```bash
python webui.py
```

浏览器访问 `http://localhost:8080` 即可使用

**功能亮点**：
- 实时进度条显示处理进度
- 最多 5 个 PDF 文件并发处理
- 支持暂停/继续/取消任务
- 任务中断时可下载已完成的文件
- 下载的 ZIP 文件自动添加时间戳

### 4. 命令行模式（可选）

如果你更喜欢命令行操作，可以使用以下命令：
```bash
python pdf_ocr.py your_document.pdf
```

指定自定义输出目录：
```bash
python pdf_ocr.py your_document.pdf -o custom_output_folder
```

如果未提供输出目录，结果将保存在 `ocr_results_[PDF文件名]` 文件夹中。

## 输出结果

脚本将根据指定的输出目录（或默认目录 `ocr_results_[PDF文件名]`）创建一个文件夹，其中包含：

- `[PDF文件名].md`: 包含所有页面内容的 Markdown 文件（以原 PDF 文件名命名）
- `images/`: 保存 PDF 中提取出的所有图像的文件夹

下载的 ZIP 文件命名格式：`ocr_results_YYYYMMDD_HHMMSS.zip`

## 注意事项

- 请确保提供的 PDF 文件路径正确且文件可访问
- API 密钥需要具有 OCR 功能的访问权限
- 如果指定的输出目录已存在，脚本仍会尝试在其中创建 `images` 子目录和对应的 `.md` 文件，现有同名文件可能会被覆盖


