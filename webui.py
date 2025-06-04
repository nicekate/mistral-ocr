import os
import tempfile
import zipfile
import shutil
from pathlib import Path
from flask import Flask, request, render_template_string, send_file, after_this_request
from werkzeug.utils import secure_filename

from pdf_ocr import process_pdf, OCRProcessingError

app = Flask(__name__)

HTML_FORM = """
<!doctype html>
<title>Mistral OCR WebUI</title>
<h1>Upload PDF files for OCR</h1>
<form method=post enctype=multipart/form-data>
  <input type=file name=files multiple>
  <input type=submit value='Start OCR'>
</form>
"""

@app.route('/', methods=['GET', 'POST'])
def upload_and_ocr():
    if request.method == 'POST':
        uploaded_files = request.files.getlist('files')
        if not uploaded_files:
            return 'No files uploaded', 400

        work_dir = tempfile.mkdtemp(prefix='ocr_web_')
        result_dirs = []
        errors = []

        @after_this_request
        def cleanup(response):
            shutil.rmtree(work_dir, ignore_errors=True)
            return response

        for f in uploaded_files:
            if f.filename == '':
                continue
            filename = secure_filename(f.filename)
            if not filename.lower().endswith('.pdf'):
                errors.append(f"{filename}: not a PDF")
                continue
            pdf_path = os.path.join(work_dir, filename)
            f.save(pdf_path)
            out_dir = os.path.join(work_dir, f'ocr_results_{Path(filename).stem}')
            try:
                process_pdf(pdf_path, out_dir)
                result_dirs.append(out_dir)
            except (FileNotFoundError, ValueError, OCRProcessingError) as e:
                errors.append(f"{filename}: {e}")
            except Exception as e:
                errors.append(f"{filename}: 未知错误 {e}")

        if not result_dirs:
            return {'errors': errors}, 400

        zip_path = os.path.join(work_dir, 'results.zip')
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for d in result_dirs:
                for root, _, files in os.walk(d):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, work_dir)
                        zipf.write(file_path, arcname)

        return send_file(zip_path, as_attachment=True)
    return render_template_string(HTML_FORM)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

