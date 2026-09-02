"""Web 音乐文件上传与管理。

功能：
- 拖拽 / 点击上传（支持批量）
- 音频格式校验（mp3/ogg/flac/wav/m4a/aac）
- 上传后自动通知电台扫描
- 文件列表 + 删除（API）
- 上传进度 SSE 推送
"""
import os
import uuid
import time
from flask import request, jsonify, Response
from . import config
from .auth import api_login_required

# 允许的音频 MIME 类型和扩展名
ALLOWED_AUDIO_TYPES = {
    "audio/mpeg", "audio/mp3",
    "audio/ogg", "audio/vorbis",
    "audio/flac", "audio/x-flac",
    "audio/wav", "audio/wave", "audio/x-wav",
    "audio/x-m4a", "audio/mp4", "audio/aac",
    "audio/webm", "audio/x-ms-wma",
}
ALLOWED_EXTENSIONS = {".mp3", ".ogg", ".flac", ".wav", ".m4a", ".aac", ".webm", ".wma", ".opus"}

UPLOAD_DIR = config.MUSIC_DIR

# 上传进度存储（简单内存字典）
_upload_progress: dict = {}  # task_id -> {"done": int, "total": int, "files": [...], "errors": [...]}


def _allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def _safe_filename(original: str) -> str:
    """生成安全文件名：保留原始名 + 去重后缀。"""
    name, ext = os.path.splitext(original)
    # 清理文件名中的危险字符
    safe = "".join(c for c in name if c.isalnum() or c in ".-_ ()（）")
    safe = safe.strip() or "audio"
    base = f"{safe}{ext}"
    # 如果已存在，加序号
    if not os.path.exists(os.path.join(UPLOAD_DIR, base)):
        return base
    for i in range(1, 1000):
        candidate = f"{safe}_{i}{ext}"
        if not os.path.exists(os.path.join(UPLOAD_DIR, candidate)):
            return candidate
    return f"{safe}_{uuid.uuid4().hex[:8]}{ext}"


def register_routes(app):
    """注册上传相关 API 路由。"""

    @app.route("/api/upload", methods=["POST"])
    @api_login_required
    def api_upload():
        """上传音乐文件（支持批量）。返回上传结果。"""
        files = request.files.getlist("files")
        if not files:
            return jsonify({"ok": False, "error": "未选择文件"}), 400

        task_id = uuid.uuid4().hex[:12]
        total = len(files)
        _upload_progress[task_id] = {
            "done": 0, "total": total,
            "files": [], "errors": [],
            "timestamp": time.time(),
        }

        # 后台批量保存（同步，文件量小时 OK）
        uploaded = []
        failed = []
        for f in files:
            fname = (f.filename or "unknown.mp3").strip()
            if not fname or not _allowed_file(fname):
                failed.append({"name": fname, "reason": "不支持的文件格式"})
                continue
            safe = _safe_filename(fname)
            try:
                os.makedirs(UPLOAD_DIR, exist_ok=True)   # music/ 可能不存在（默认用 musickit 随机渲染）
                f.save(os.path.join(UPLOAD_DIR, safe))
                uploaded.append({"name": safe, "original": fname})
            except Exception as e:
                failed.append({"name": fname, "reason": str(e)})

        # 触发电台扫描新文件
        try:
            from . import runner
            if hasattr(runner, "station") and runner.station:
                runner.station.rescan()
        except Exception:
            pass

        prog = _upload_progress[task_id]
        prog["done"] = total
        prog["files"] = uploaded
        prog["errors"] = failed

        return jsonify({
            "ok": True,
            "task_id": task_id,
            "uploaded": len(uploaded),
            "failed": len(failed),
            "files": uploaded,
            "errors": failed,
        })

    @app.route("/api/upload/progress/<task_id>")
    def api_upload_progress(task_id):
        """查询上传进度（SSE 或 JSON）。"""
        prog = _upload_progress.get(task_id)
        if not prog:
            return jsonify({"ok": False, "error": "任务不存在"}), 404

        # 支持 SSE（Server-Sent Events）用于实时进度
        if request.headers.get("Accept") == "text/event-stream":
            def generate():
                while True:
                    p = _upload_progress.get(task_id)
                    if not p:
                        break
                    data = {
                        "done": p["done"],
                        "total": p["total"],
                        "percent": int(p["done"] / max(p["total"], 1) * 100),
                        "files": [f["name"] for f in p.get("files", [])],
                        "errors": p.get("errors", []),
                    }
                    yield f"data: {__import__('json').dumps(data)}\n\n"
                    if p["done"] >= p["total"]:
                        break
                    time.sleep(0.5)
                # 发送完成事件并清理
                yield "event: done\ndata: {}\n\n"
                _upload_progress.pop(task_id, None)
            return Response(generate(), mimetype="text/event-stream")

        pct = int(prog["done"] / max(prog["total"], 1) * 100)
        return jsonify({
            "ok": True,
            "done": prog["done"],
            "total": prog["total"],
            "percent": pct,
            "files": [f["name"] for f in prog.get("files", [])],
            "errors": prog.get("errors", []),
        })

    @app.route("/api/files", methods=["GET"])
    @api_login_required
    def api_list_files():
        """列出音乐目录中所有文件（含大小、时间）。"""
        items = []
        try:
            for name in sorted(os.listdir(UPLOAD_DIR)):
                path = os.path.join(UPLOAD_DIR, name)
                if os.path.isfile(path) and _allowed_file(name):
                    stat = os.stat(path)
                    items.append({
                        "name": name,
                        "size": stat.st_size,
                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                        "modified": time.strftime(
                            "%Y-%m-%d %H:%M:%S",
                            time.localtime(stat.st_mtime)
                        ),
                    })
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
        return jsonify({"ok": True, "count": len(items), "files": items})

    @app.route("/api/files/<path:filename>", methods=["DELETE"])
    @api_login_required
    def api_delete_file(filename):
        """删除指定音乐文件。"""
        safe = os.path.basename(filename)  # 防路径遍历
        path = os.path.join(UPLOAD_DIR, safe)
        if not os.path.isfile(path):
            return jsonify({"ok": False, "error": "文件不存在"}), 404
        if not _allowed_file(safe):
            return jsonify({"ok": False, "error": "不支持的操作"}), 403
        try:
            os.remove(path)
            # 通知电台刷新
            try:
                from . import runner
                if hasattr(runner, "station") and runner.station:
                    runner.station.scan_music()
            except Exception:
                pass
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/files", methods=["GET"])
    @api_login_required
    def files_page():
        """文件管理页面。"""
        from .auth import is_configured
        need_auth = is_configured()
        return __import__("flask").current_app.send_static_file("upload.html") if False else _upload_html(need_auth)

    # 清理过期进度记录（定时任务）
    @app.before_request
    def _cleanup_stale_progress():
        now = time.time()
        stale = [k for k, v in _upload_progress.items() if now - v["timestamp"] > 3600]
        for k in stale:
            _upload_progress.pop(k, None)


_UPLOAD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>文件管理 - 电台</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0d1117;color:#c9d1d9;min-height:100vh;padding:24px}
h1{font-size:24px;margin-bottom:24px;color:#58a6ff}
.upload-zone{
  border:2px dashed #30363d;border-radius:16px;padding:48px;
  text-align:center;margin-bottom:32px;cursor:pointer;
  transition:all .2s;background:#161b22;
}
.upload-zone:hover,.upload-zone.dragover{border-color:#58a6ff;background:#1c2333}
.upload-zone p{color:#8b949e;font-size:15px}
.upload-zone .icon{font-size:48px;margin-bottom:12px}
.progress-bar{
  height:8px;background:#30363d;border-radius:4px;margin:12px 0;
  overflow:hidden;display:none;
}
.progress-bar .fill{
  height:100%;background:linear-gradient(90deg,#58a6ff,#a371f7);
  border-radius:4px;transition:width .3s;width:0%
}
.file-list{margin-top:24px}
.file-row{
  display:flex;align-items:center;justify-content:space-between;
  padding:12px 16px;border-bottom:1px solid #21262d;
  transition:background .15s;
}
.file-row:hover{background:#161b22}
.file-name{flex:1;font-size:15px}
.file-size{color:#8b949e;font-size:13px;margin:0 20px}
.file-date{color:#8b949e;font-size:13px;margin:0 12px}
.btn-del{
  background:none;border:1px solid #f85149;color:#f85149;
  padding:6px 16px;border-radius:8px;cursor:pointer;font-size:13px;
  transition:all .15s;
}
.btn-del:hover{background:#f85149;color:#fff}
#status{color:#8b949e;margin-bottom:16px;min-height:24px}
#status.success{color:#3fb950}
#status.error{color:#f85149}
.back-link{display:inline-block;margin-bottom:20px;color:#58a6ff;text-decoration:none;font-size:14px}
.back-link:hover{text-decoration:underline}
</style>
</head>
<body>
<a href="/" class="back-link">← 返回电台主页</a>
<h1>📁 音乐文件管理</h1>

<div class="upload-zone" id="dropZone">
  <div class="icon">🎵</div>
  <p>拖拽音乐文件到此处，或点击选择</p>
  <input type="file" id="fileInput" multiple accept=".mp3,.ogg,.flac,.wav,.m4a,.aac,.webm,.wma,.opus" style="display:none">
  <div class="progress-bar" id="progress"><div class="fill"></div></div>
</div>
<div id="status"></div>
<div class="file-list" id="fileList"><p style="color:#8b949e">加载中…</p></div>

<script>
var dropZone=document.getElementById("dropZone");
var fileInput=document.getElementById("fileInput");
var progress=document.getElementById("progress");
var progressFill=progress.querySelector(".fill");
var statusEl=document.getElementById("status");
var fileList=document.getElementById("fileList");

dropZone.addEventListener("click",function(){fileInput.click()});
dropZone.addEventListener("dragover",function(e){e.preventDefault();dropZone.classList.add("dragover")});
dropZone.addEventListener("dragleave",function(){dropZone.classList.remove("dragover")});
dropZone.addEventListener("drop",function(e){
  e.preventDefault();dropZone.classList.remove("dragover");
  uploadFiles(e.dataTransfer.files);
});
fileInput.addEventListener("change",function(){if(fileInput.files.length)uploadFiles(fileInput.files)});

function setStatus(msg,cls){
  statusEl.textContent=msg;statusEl.className=cls||""
}

async function uploadFiles(files){
  var fd=new FormData();
  for(var f of files)fd.append("files",f);
  progress.style.display="block";
  progressFill.style.width="0%";
  setStatus("上传中…");
  try{
    var r=await fetch("/api/upload",{method:"POST",body:fd});
    var d=await r.json();
    if(d.ok){
      progressFill.style.width="100%";
      setStatus("上传完成！成功 "+d.uploaded+" 个文件"+(d.failed?"，失败 "+d.failed+" 个":""),"success");
      if(d.errors.length)d.errors.forEach(function(e){setStatus(statusEl.textContent+" | "+e.name+": "+e.reason,"error")});
      loadFiles();
    }else{
      setStatus("上传失败: "+(d.error||"未知错误"),"error");
    }
  }catch(e){
    setStatus("上传出错: "+e.message,"error");
  }
  setTimeout(function(){progress.style.display="none"},2000);
  fileInput.value="";
}

async function loadFiles(){
  try{
    var r=await fetch("/api/files");
    var d=await r.json();
    if(!d.ok){fileList.innerHTML="<p>加载失败</p>";return}
    if(!d.files.length){fileList.innerHTML="<p style='color:#8b949e'>还没有文件，请上传音乐</p>";return}
    var h=d.files.map(function(f){
      return '<div class="file-row"><span class="file-name">🎵 '+_esc(f.name)+'</span>'
        +'<span class="file-size">'+f.size_mb+' MB</span>'
        +'<span class="file-date">'+f.modified+'</span>'
        +'<button class="btn-del" onclick="delFile(\''+_escjs(f.name)+'\')">删除</button></div>';
    }).join("");
    fileList.innerHTML=h;
  }catch(e){fileList.innerHTML="<p>加载出错</p>"}
}

async function delFile(name){
  if(!confirm("确定删除 "+name+" 吗？"))return;
  try{
    var r=await fetch("/api/files/"+encodeURIComponent(name),{method:"DELETE"});
    var d=await r.json();
    if(d.ok){setStatus("已删除: "+name,"success");loadFiles()}
    else setStatus("删除失败: "+(d.error||""),"error");
  }catch(e){setStatus("删除出错: "+e.message,"error")}
}

function _esc(s){return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
function _escjs(s){return s.replace(/'/g,"\\'").replace(/"/g,"\\\"")}

loadFiles();
</script>
</body>
</html>"""


def _upload_html(need_auth: bool):
    return _UPLOAD_HTML
