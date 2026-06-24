from pathlib import Path
import os
import base64
import sys
import argparse

# mistralai 2.x 优先，回退到 1.x
try:
    from mistralai.client import Mistral
    from mistralai.client.models import DocumentURLChunk, ImageURLChunk, OCRResponse
    from mistralai.client.errors import SDKError, MistralError, NoResponseError

    MistralAPIException = SDKError
    MistralConnectionException = NoResponseError
    MistralException = MistralError
except ImportError:
    from mistralai import Mistral, DocumentURLChunk, ImageURLChunk
    from mistralai.models import OCRResponse
    try:
        from mistralai.models.sdkerror import SDKError
        from mistralai.models.mistralerror import MistralError

        MistralAPIException = SDKError
        MistralConnectionException = Exception
        MistralException = MistralError
    except ImportError:
        MistralAPIException = MistralConnectionException = MistralException = Exception


SUPPORTED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tiff', '.tif'}
SUPPORTED_PDF_EXTENSIONS = {'.pdf'}
SUPPORTED_EXTENSIONS = SUPPORTED_PDF_EXTENSIONS | SUPPORTED_IMAGE_EXTENSIONS

IMAGE_MIME_TYPES = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.webp': 'image/webp',
    '.gif': 'image/gif',
    '.bmp': 'image/bmp',
    '.tiff': 'image/tiff',
    '.tif': 'image/tiff',
}


class OCRProcessingError(Exception):
    """Raised when an OCR processing step fails."""


def is_supported_file(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def is_image_file(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS


def image_to_data_url(image_path: Path) -> str:
    mime = IMAGE_MIME_TYPES.get(image_path.suffix.lower(), 'image/jpeg')
    encoded = base64.b64encode(image_path.read_bytes()).decode()
    return f"data:{mime};base64,{encoded}"


def replace_images_in_markdown(markdown_str: str, images_dict: dict) -> str:
    for img_name, img_path in images_dict.items():
        markdown_str = markdown_str.replace(f"![{img_name}]({img_name})", f"![{img_name}]({img_path})")
    return markdown_str


def save_ocr_results(ocr_response: OCRResponse, output_dir: str, source_name: str = None) -> None:
    os.makedirs(output_dir, exist_ok=True)
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    all_markdowns = []
    for page in ocr_response.pages:
        page_images = {}
        for img in page.images:
            img_data = base64.b64decode(img.image_base64.split(',')[1])
            img_path = os.path.join(images_dir, f"{img.id}.png")
            with open(img_path, 'wb') as f:
                f.write(img_data)
            page_images[img.id] = f"images/{img.id}.png"

        page_markdown = replace_images_in_markdown(page.markdown, page_images)
        all_markdowns.append(page_markdown)

    md_filename = f"{source_name}.md" if source_name else "complete.md"
    with open(os.path.join(output_dir, md_filename), 'w', encoding='utf-8') as f:
        f.write("\n\n".join(all_markdowns))


def _create_client() -> Mistral:
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("MISTRAL_API_KEY 环境变量未设置。")
    return Mistral(api_key=api_key)


def _run_ocr(client: Mistral, document) -> OCRResponse:
    print("OCR处理中，请稍候...")
    try:
        return client.ocr.process(
            document=document,
            model="mistral-ocr-latest",
            include_image_base64=True,
        )
    except (MistralAPIException, MistralConnectionException) as e:
        raise OCRProcessingError(f"OCR处理过程中发生API或连接错误: {e}") from e
    except MistralException as e:
        raise OCRProcessingError(f"OCR处理过程中发生Mistral相关错误: {e}") from e
    except Exception as e:
        raise OCRProcessingError(f"OCR处理过程中发生未知错误: {e}") from e


def _process_pdf_file(client: Mistral, pdf_file: Path) -> OCRResponse:
    print(f"正在上传文件: {pdf_file.name}...")
    try:
        uploaded_file = client.files.upload(
            file={
                "file_name": pdf_file.stem,
                "content": pdf_file.read_bytes(),
            },
            purpose="ocr",
        )
        print(f"文件已上传成功，文件ID: {uploaded_file.id}")
    except FileNotFoundError:
        raise FileNotFoundError(f"PDF文件 '{pdf_file}' 未找到。")
    except (MistralAPIException, MistralConnectionException) as e:
        raise OCRProcessingError(f"上传PDF文件时发生API或连接错误: {e}") from e
    except MistralException as e:
        raise OCRProcessingError(f"上传PDF文件时发生Mistral相关错误: {e}") from e
    except Exception as e:
        raise OCRProcessingError(f"上传PDF文件时发生未知错误: {e}") from e

    print("正在获取签名URL...")
    try:
        signed_url = client.files.get_signed_url(file_id=uploaded_file.id, expiry=60)
    except (MistralAPIException, MistralConnectionException) as e:
        raise OCRProcessingError(f"获取签名URL时发生API或连接错误: {e}") from e
    except MistralException as e:
        raise OCRProcessingError(f"获取签名URL时发生Mistral相关错误: {e}") from e
    except Exception as e:
        raise OCRProcessingError(f"获取签名URL时发生未知错误: {e}") from e

    return _run_ocr(client, DocumentURLChunk(document_url=signed_url.url))


def _process_image_file(client: Mistral, image_file: Path) -> OCRResponse:
    print(f"正在处理图片: {image_file.name}...")
    data_url = image_to_data_url(image_file)
    return _run_ocr(client, ImageURLChunk(image_url=data_url))


def process_document(file_path: str, output_dir_arg: str = None) -> None:
    source_file = Path(file_path)
    if not source_file.is_file():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    suffix = source_file.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        supported = ', '.join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"不支持的文件类型: {suffix}。支持: {supported}")

    if output_dir_arg:
        output_dir = output_dir_arg
    else:
        output_dir = f"ocr_results_{source_file.stem}"

    client = _create_client()

    if is_image_file(source_file):
        ocr_response = _process_image_file(client, source_file)
    else:
        ocr_response = _process_pdf_file(client, source_file)

    print("OCR处理已完成，正在保存结果...")
    save_ocr_results(ocr_response, output_dir, source_file.stem)
    print(f"OCR处理完成。结果保存在: {output_dir}")


def process_pdf(pdf_path: str, output_dir_arg: str = None) -> None:
    """兼容旧调用方式。"""
    process_document(pdf_path, output_dir_arg)


def main():
    parser = argparse.ArgumentParser(description="使用 Mistral AI OCR 处理 PDF 或图片文件。")
    parser.add_argument("file_path", help="要处理的 PDF 或图片文件路径。")
    parser.add_argument(
        "-o", "--output_dir",
        help="存储结果的输出目录。如果未提供，则默认为 'ocr_results_[文件名]'。"
    )

    args = parser.parse_args()

    try:
        process_document(args.file_path, args.output_dir)
    except (FileNotFoundError, ValueError, OCRProcessingError) as e:
        print(f"主程序错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"主程序未知错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()