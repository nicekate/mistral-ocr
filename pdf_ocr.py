from mistralai import Mistral
from pathlib import Path
import os
import base64
import sys
import argparse
from mistralai import DocumentURLChunk
from mistralai.models import OCRResponse

class OCRProcessingError(Exception):
    """Raised when an OCR processing step fails."""
try:
    from mistralai.exceptions import MistralAPIException, MistralConnectionException, MistralException
except ImportError:
    # Fallback if specific exceptions are not found
    MistralAPIException = MistralConnectionException = MistralException = Exception

def replace_images_in_markdown(markdown_str: str, images_dict: dict) -> str:
    for img_name, img_path in images_dict.items():
        markdown_str = markdown_str.replace(f"![{img_name}]({img_name})", f"![{img_name}]({img_path})")
    return markdown_str

def save_ocr_results(ocr_response: OCRResponse, output_dir: str, pdf_name: str = None) -> None:
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    
    all_markdowns = []
    for page in ocr_response.pages:
        # 保存图片
        page_images = {}
        for img in page.images:
            img_data = base64.b64decode(img.image_base64.split(',')[1])
            img_path = os.path.join(images_dir, f"{img.id}.png")
            with open(img_path, 'wb') as f:
                f.write(img_data)
            page_images[img.id] = f"images/{img.id}.png"
        
        # 处理markdown内容
        page_markdown = replace_images_in_markdown(page.markdown, page_images)
        all_markdowns.append(page_markdown)
    
    # 保存完整markdown，使用PDF原始名称
    md_filename = f"{pdf_name}.md" if pdf_name else "complete.md"
    with open(os.path.join(output_dir, md_filename), 'w', encoding='utf-8') as f:
        f.write("\n\n".join(all_markdowns))

def process_pdf(pdf_path: str, output_dir_arg: str = None) -> None:
    # 获取 API Key
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("MISTRAL_API_KEY 环境变量未设置。")

    # 初始化客户端
    client = Mistral(api_key=api_key)
    
    # 确认PDF文件存在
    pdf_file = Path(pdf_path)
    if not pdf_file.is_file():
        # This check might be redundant if argparse handles file existence,
        # but good for direct calls or future refactoring.
        raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
    
    # 确定输出目录
    if output_dir_arg:
        output_dir = output_dir_arg
    else:
        output_dir = f"ocr_results_{pdf_file.stem}"
    
    # 上传并处理PDF
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
        # Should be caught by the earlier check, but raise for safety
        raise FileNotFoundError(f"PDF文件 '{pdf_path}' 未找到。")
    except (MistralAPIException, MistralConnectionException) as e:
        raise OCRProcessingError(f"上传PDF文件时发生API或连接错误: {e}") from e
    except MistralException as e:
        raise OCRProcessingError(f"上传PDF文件时发生Mistral相关错误: {e}") from e
    except Exception as e:
        raise OCRProcessingError(f"上传PDF文件时发生未知错误: {e}") from e

    print("正在获取签名URL...")
    try:
        signed_url = client.files.get_signed_url(file_id=uploaded_file.id, expiry=60)  # Increased expiry to 60 seconds
    except (MistralAPIException, MistralConnectionException) as e:
        raise OCRProcessingError(f"获取签名URL时发生API或连接错误: {e}") from e
    except MistralException as e:
        raise OCRProcessingError(f"获取签名URL时发生Mistral相关错误: {e}") from e
    except Exception as e:
        raise OCRProcessingError(f"获取签名URL时发生未知错误: {e}") from e
    
    print("OCR处理中，请稍候...")
    try:
        pdf_response = client.ocr.process(
            document=DocumentURLChunk(document_url=signed_url.url),
            model="mistral-ocr-latest",
            include_image_base64=True
        )
    except (MistralAPIException, MistralConnectionException) as e:
        raise OCRProcessingError(f"OCR处理过程中发生API或连接错误: {e}") from e
    except MistralException as e:
        raise OCRProcessingError(f"OCR处理过程中发生Mistral相关错误: {e}") from e
    except Exception as e:
        raise OCRProcessingError(f"OCR处理过程中发生未知错误: {e}") from e
    
    print("OCR处理已完成，正在保存结果...")
    # 保存结果，使用PDF文件名作为md文件名
    save_ocr_results(pdf_response, output_dir, pdf_file.stem)
    print(f"OCR处理完成。结果保存在: {output_dir}")

def main():
    # API_KEY 将从环境变量 MISTRAL_API_KEY 读取 (process_pdf内处理)
    
    parser = argparse.ArgumentParser(description="使用 Mistral AI OCR 功能处理 PDF 文件。")
    parser.add_argument("pdf_path", help="要处理的 PDF 文件的路径。")
    parser.add_argument(
        "-o", "--output_dir",
        help="存储结果的输出目录。如果未提供，则默认为 'ocr_results_[PDF文件名]'。"
    )

    args = parser.parse_args()

    try:
        process_pdf(args.pdf_path, args.output_dir)
    except (FileNotFoundError, ValueError, OCRProcessingError) as e:
        print(f"主程序错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"主程序未知错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

