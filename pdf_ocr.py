from mistralai import Mistral
from pathlib import Path
import os
import base64
from mistralai import DocumentURLChunk
from mistralai.models import OCRResponse

def replace_images_in_markdown(markdown_str: str, images_dict: dict) -> str:
    for img_name, img_path in images_dict.items():
        markdown_str = markdown_str.replace(f"![{img_name}]({img_name})", f"![{img_name}]({img_path})")
    return markdown_str

def save_ocr_results(ocr_response: OCRResponse, output_dir: str) -> None:
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
    
    # 保存完整markdown
    with open(os.path.join(output_dir, "complete.md"), 'w', encoding='utf-8') as f:
        f.write("\n\n".join(all_markdowns))

def process_pdf(pdf_path: str, api_key: str) -> None:
    # 初始化客户端
    client = Mistral(api_key=api_key)
    
    # 确认PDF文件存在
    pdf_file = Path(pdf_path)
    if not pdf_file.is_file():
        raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
    
    # 创建输出目录名称
    output_dir = f"ocr_results_{pdf_file.stem}"
    
    # 上传并处理PDF
    uploaded_file = client.files.upload(
        file={
            "file_name": pdf_file.stem,
            "content": pdf_file.read_bytes(),
        },
        purpose="ocr",
    )
    
    signed_url = client.files.get_signed_url(file_id=uploaded_file.id, expiry=1)
    pdf_response = client.ocr.process(
        document=DocumentURLChunk(document_url=signed_url.url), 
        model="mistral-ocr-latest", 
        include_image_base64=True
    )
    
    # 保存结果
    save_ocr_results(pdf_response, output_dir)
    print(f"OCR处理完成。结果保存在: {output_dir}")

if __name__ == "__main__":
    # 使用示例
    API_KEY = "your key"
    PDF_PATH = "zh.pdf"
    
    process_pdf(PDF_PATH, API_KEY)