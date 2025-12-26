import os
import tempfile
import zipfile
import shutil
import uuid
import json
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, Future
from flask import Flask, request, render_template_string, send_file, Response, jsonify
from werkzeug.utils import secure_filename

from pdf_ocr import process_pdf, OCRProcessingError

app = Flask(__name__)

# 任务状态管理
tasks = {}  # task_id -> TaskInfo
tasks_lock = threading.Lock()

# 并发处理器（最多5个并发）
executor = ThreadPoolExecutor(max_workers=5)


class FileStatus:
    PENDING = "pending"      # 等待中
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消


class TaskStatus:
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskInfo:
    def __init__(self, task_id: str, work_dir: str, files: list):
        self.task_id = task_id
        self.work_dir = work_dir
        self.status = TaskStatus.RUNNING
        self.files = files  # [{"name": str, "status": str, "error": str|None, "output_dir": str|None}]
        self.futures: list[Future] = []
        self.lock = threading.Lock()

    def to_dict(self):
        with self.lock:
            completed = sum(1 for f in self.files if f["status"] == FileStatus.COMPLETED)
            failed = sum(1 for f in self.files if f["status"] == FileStatus.FAILED)
            total = len(self.files)
            return {
                "task_id": self.task_id,
                "status": self.status,
                "files": self.files.copy(),
                "progress": {
                    "completed": completed,
                    "failed": failed,
                    "total": total,
                    "percent": int((completed + failed) / total * 100) if total > 0 else 0
                }
            }


def process_single_pdf(task_id: str, file_index: int, pdf_path: str, output_dir: str):
    """处理单个PDF文件"""
    with tasks_lock:
        task = tasks.get(task_id)
        if not task:
            return

    # 检查任务是否被暂停或取消
    with task.lock:
        if task.status in [TaskStatus.PAUSED, TaskStatus.CANCELLED]:
            task.files[file_index]["status"] = FileStatus.CANCELLED
            return
        task.files[file_index]["status"] = FileStatus.PROCESSING

    try:
        process_pdf(pdf_path, output_dir)
        with task.lock:
            task.files[file_index]["status"] = FileStatus.COMPLETED
            task.files[file_index]["output_dir"] = output_dir
    except (FileNotFoundError, ValueError, OCRProcessingError) as e:
        with task.lock:
            task.files[file_index]["status"] = FileStatus.FAILED
            task.files[file_index]["error"] = str(e)
    except Exception as e:
        with task.lock:
            task.files[file_index]["status"] = FileStatus.FAILED
            task.files[file_index]["error"] = f"未知错误: {e}"


def check_task_completion(task_id: str):
    """检查任务是否全部完成"""
    with tasks_lock:
        task = tasks.get(task_id)
        if not task:
            return

    with task.lock:
        if task.status in [TaskStatus.PAUSED, TaskStatus.CANCELLED]:
            return

        all_done = all(
            f["status"] in [FileStatus.COMPLETED, FileStatus.FAILED, FileStatus.CANCELLED]
            for f in task.files
        )
        if all_done:
            has_failed = any(f["status"] == FileStatus.FAILED for f in task.files)
            task.status = TaskStatus.FAILED if has_failed else TaskStatus.COMPLETED



HTML_TEMPLATE = """
<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>Mistral OCR WebUI</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
.file-item { padding: 8px 12px; border-radius: 6px; margin-bottom: 6px; background: #f8f9fa; }
.file-pending { border-left: 4px solid #6c757d; }
.file-processing { border-left: 4px solid #0d6efd; background: #e7f1ff; }
.file-completed { border-left: 4px solid #198754; background: #d1e7dd; }
.file-failed { border-left: 4px solid #dc3545; background: #f8d7da; }
.file-cancelled { border-left: 4px solid #ffc107; background: #fff3cd; }
.status-icon { margin-right: 8px; }
#progress-section { display: none; }
</style>
</head>
<body class="bg-light">
<div class="container py-5">
  <h1 class="mb-4">Mistral OCR WebUI</h1>

  <!-- 上传区域 -->
  <div id="upload-section">
    <form id="upload-form" enctype="multipart/form-data" class="mb-3">
      <div class="mb-3">
        <input type="file" class="form-control" id="file-input" name="files" multiple accept=".pdf" required>
        <small class="text-muted">支持多选PDF文件，最多同时处理5个</small>
      </div>
      <button type="submit" class="btn btn-primary" id="start-btn">开始 OCR</button>
    </form>
  </div>

  <!-- 进度区域 -->
  <div id="progress-section">
    <div class="d-flex justify-content-between align-items-center mb-2">
      <span id="progress-text">准备中...</span>
      <span id="progress-percent">0%</span>
    </div>
    <div class="progress mb-3" style="height: 24px;">
      <div class="progress-bar progress-bar-striped progress-bar-animated" id="progress-bar"
           role="progressbar" style="width: 0%"></div>
    </div>

    <!-- 文件列表 -->
    <div id="file-list" class="mb-3"></div>

    <!-- 控制按钮 -->
    <div id="control-buttons" class="mb-3">
      <button class="btn btn-warning me-2" id="pause-btn" onclick="pauseTask()">暂停</button>
      <button class="btn btn-success me-2" id="resume-btn" onclick="resumeTask()" style="display:none;">继续</button>
      <button class="btn btn-danger" id="cancel-btn" onclick="cancelTask()">取消</button>
    </div>

    <!-- 下载按钮 -->
    <div id="download-section" style="display:none;">
      <button class="btn btn-success me-2" id="download-all-btn" onclick="downloadResults()">
        下载全部结果
      </button>
      <button class="btn btn-outline-primary" id="download-partial-btn" onclick="downloadResults()" style="display:none;">
        下载已完成文件
      </button>
      <button class="btn btn-secondary" id="new-task-btn" onclick="resetUI()">新任务</button>
    </div>
  </div>

  <!-- 错误提示 -->
  <div id="error-alert" class="alert alert-danger" style="display:none;"></div>
</div>

<script>
let currentTaskId = null;
let eventSource = null;

document.getElementById('upload-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fileInput = document.getElementById('file-input');
  const files = fileInput.files;
  if (files.length === 0) return;

  const formData = new FormData();
  for (let f of files) {
    formData.append('files', f);
  }

  try {
    const resp = await fetch('/upload', { method: 'POST', body: formData });
    const data = await resp.json();
    if (data.error) {
      showError(data.error);
      return;
    }
    currentTaskId = data.task_id;
    showProgressSection();
    startSSE();
  } catch (err) {
    showError('上传失败: ' + err.message);
  }
});

function showProgressSection() {
  document.getElementById('upload-section').style.display = 'none';
  document.getElementById('progress-section').style.display = 'block';
  document.getElementById('download-section').style.display = 'none';
  document.getElementById('control-buttons').style.display = 'block';
  document.getElementById('pause-btn').style.display = 'inline-block';
  document.getElementById('resume-btn').style.display = 'none';
}

function startSSE() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource('/progress/' + currentTaskId);
  eventSource.onmessage = (e) => {
    const data = JSON.parse(e.data);
    updateProgress(data);
  };
  eventSource.onerror = () => {
    eventSource.close();
  };
}

function updateProgress(data) {
  const { status, files, progress } = data;

  // 更新进度条
  document.getElementById('progress-bar').style.width = progress.percent + '%';
  document.getElementById('progress-percent').textContent = progress.percent + '%';
  document.getElementById('progress-text').textContent =
    `已完成 ${progress.completed}/${progress.total} 个文件` +
    (progress.failed > 0 ? ` (${progress.failed} 个失败)` : '');

  // 更新文件列表
  const fileListEl = document.getElementById('file-list');
  fileListEl.innerHTML = files.map(f => {
    const statusClass = 'file-' + f.status;
    const icon = getStatusIcon(f.status);
    const errorText = f.error ? `<small class="text-danger d-block">${f.error}</small>` : '';
    return `<div class="file-item ${statusClass}">${icon} ${f.name}${errorText}</div>`;
  }).join('');

  // 根据任务状态更新UI
  if (status === 'completed' || status === 'failed') {
    taskFinished(status === 'completed');
  } else if (status === 'paused') {
    document.getElementById('pause-btn').style.display = 'none';
    document.getElementById('resume-btn').style.display = 'inline-block';
  } else if (status === 'cancelled') {
    taskFinished(false, true);
  }
}

function getStatusIcon(status) {
  const icons = {
    pending: '<span class="status-icon">○</span>',
    processing: '<span class="status-icon text-primary">⟳</span>',
    completed: '<span class="status-icon text-success">✓</span>',
    failed: '<span class="status-icon text-danger">✗</span>',
    cancelled: '<span class="status-icon text-warning">⊘</span>'
  };
  return icons[status] || '';
}

function taskFinished(allSuccess, wasCancelled = false) {
  if (eventSource) eventSource.close();
  document.getElementById('control-buttons').style.display = 'none';
  document.getElementById('download-section').style.display = 'block';

  if (allSuccess) {
    document.getElementById('download-all-btn').style.display = 'inline-block';
    document.getElementById('download-partial-btn').style.display = 'none';
  } else {
    document.getElementById('download-all-btn').style.display = 'none';
    document.getElementById('download-partial-btn').style.display = 'inline-block';
  }
}

async function pauseTask() {
  await fetch('/pause/' + currentTaskId, { method: 'POST' });
}

async function resumeTask() {
  await fetch('/resume/' + currentTaskId, { method: 'POST' });
  document.getElementById('pause-btn').style.display = 'inline-block';
  document.getElementById('resume-btn').style.display = 'none';
}

async function cancelTask() {
  await fetch('/cancel/' + currentTaskId, { method: 'POST' });
}

function downloadResults() {
  window.location.href = '/download/' + currentTaskId;
}

function resetUI() {
  currentTaskId = null;
  if (eventSource) eventSource.close();
  document.getElementById('upload-section').style.display = 'block';
  document.getElementById('progress-section').style.display = 'none';
  document.getElementById('file-input').value = '';
  document.getElementById('file-list').innerHTML = '';
  document.getElementById('progress-bar').style.width = '0%';
  document.getElementById('error-alert').style.display = 'none';
}

function showError(msg) {
  const el = document.getElementById('error-alert');
  el.textContent = msg;
  el.style.display = 'block';
}
</script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/upload', methods=['POST'])
def upload():
    """上传文件并创建任务"""
    uploaded_files = request.files.getlist('files')
    if not uploaded_files:
        return jsonify({"error": "没有上传文件"}), 400

    # 创建工作目录
    work_dir = tempfile.mkdtemp(prefix='ocr_web_')
    task_id = str(uuid.uuid4())

    # 准备文件列表
    files_info = []
    pdf_files = []

    for f in uploaded_files:
        if f.filename == '':
            continue
        filename = secure_filename(f.filename)
        if not filename.lower().endswith('.pdf'):
            continue

        pdf_path = os.path.join(work_dir, filename)
        f.save(pdf_path)
        out_dir = os.path.join(work_dir, f'ocr_results_{Path(filename).stem}')

        files_info.append({
            "name": filename,
            "status": FileStatus.PENDING,
            "error": None,
            "output_dir": None,
            "pdf_path": pdf_path,
            "out_dir": out_dir
        })
        pdf_files.append((pdf_path, out_dir))

    if not files_info:
        shutil.rmtree(work_dir, ignore_errors=True)
        return jsonify({"error": "没有有效的PDF文件"}), 400

    # 创建任务
    task = TaskInfo(task_id, work_dir, files_info)
    with tasks_lock:
        tasks[task_id] = task

    # 提交并发任务
    for i, (pdf_path, out_dir) in enumerate(pdf_files):
        future = executor.submit(process_single_pdf, task_id, i, pdf_path, out_dir)
        future.add_done_callback(lambda _, tid=task_id: check_task_completion(tid))
        task.futures.append(future)

    return jsonify({"task_id": task_id})


@app.route('/progress/<task_id>')
def progress(task_id):
    """SSE 进度推送"""
    def generate():
        while True:
            with tasks_lock:
                task = tasks.get(task_id)

            if not task:
                yield f"data: {json.dumps({'error': '任务不存在'})}\n\n"
                break

            data = task.to_dict()
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

            # 如果任务已结束，停止推送
            if data["status"] in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                break

            import time
            time.sleep(0.5)  # 每0.5秒推送一次

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/pause/<task_id>', methods=['POST'])
def pause(task_id):
    """暂停任务"""
    with tasks_lock:
        task = tasks.get(task_id)

    if not task:
        return jsonify({"error": "任务不存在"}), 404

    with task.lock:
        if task.status == TaskStatus.RUNNING:
            task.status = TaskStatus.PAUSED
            # 将等待中的文件标记为取消
            for f in task.files:
                if f["status"] == FileStatus.PENDING:
                    f["status"] = FileStatus.CANCELLED

    return jsonify({"status": "paused"})


@app.route('/resume/<task_id>', methods=['POST'])
def resume(task_id):
    """继续任务"""
    with tasks_lock:
        task = tasks.get(task_id)

    if not task:
        return jsonify({"error": "任务不存在"}), 404

    with task.lock:
        if task.status == TaskStatus.PAUSED:
            task.status = TaskStatus.RUNNING
            # 重新提交被取消的文件
            for i, f in enumerate(task.files):
                if f["status"] == FileStatus.CANCELLED:
                    f["status"] = FileStatus.PENDING
                    future = executor.submit(
                        process_single_pdf, task_id, i, f["pdf_path"], f["out_dir"]
                    )
                    future.add_done_callback(lambda _, tid=task_id: check_task_completion(tid))
                    task.futures.append(future)

    return jsonify({"status": "running"})


@app.route('/cancel/<task_id>', methods=['POST'])
def cancel(task_id):
    """取消任务"""
    with tasks_lock:
        task = tasks.get(task_id)

    if not task:
        return jsonify({"error": "任务不存在"}), 404

    with task.lock:
        task.status = TaskStatus.CANCELLED
        # 将等待中的文件标记为取消
        for f in task.files:
            if f["status"] == FileStatus.PENDING:
                f["status"] = FileStatus.CANCELLED

    return jsonify({"status": "cancelled"})


@app.route('/download/<task_id>')
def download(task_id):
    """下载已完成的结果"""
    with tasks_lock:
        task = tasks.get(task_id)

    if not task:
        return jsonify({"error": "任务不存在"}), 404

    # 收集已完成的输出目录
    completed_dirs = []
    with task.lock:
        for f in task.files:
            if f["status"] == FileStatus.COMPLETED and f.get("output_dir"):
                completed_dirs.append(f["output_dir"])

    if not completed_dirs:
        return jsonify({"error": "没有已完成的文件"}), 400

    # 创建ZIP文件
    zip_path = os.path.join(task.work_dir, 'results.zip')
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for d in completed_dirs:
            for root, _, files in os.walk(d):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, task.work_dir)
                    zipf.write(file_path, arcname)

    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(zip_path, as_attachment=True, download_name=f'ocr_results_{timestamp}.zip')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, threaded=True)