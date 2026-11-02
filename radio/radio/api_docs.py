"""API 文档：基于提交到仓库的权威 OpenAPI 规范生成在线文档。

- GET /api/openapi.json  → 返回仓库内 radio/openapi.json（与 remix/tools/mixer-stream-openapi.yaml
  为同一套规范的 8000 端口部分，二者合并即完整 API 面）。
- GET /api/docs          → Swagger UI 风格交互文档页（读取 /api/openapi.json）。

历史说明：早期版本用 API_DEFS + _build_spec() 手工拼一个只有「200 成功」的
瘦规范，漏登记了 /api/musickit、/api/docs 等真实路由、路径参数还混了零宽字符、
且无请求/响应 schema 与示例。现改为：规范以 radio/openapi.json 为单一事实源
（由 musickit-analysis/radio-openapi.yaml 生成），本模块只负责读取与渲染。
"""
import json
import os
from flask import Blueprint, jsonify, Response

docs_bp = Blueprint("docs", __name__)

# 权威规范文件（与 radio/ 同目录，由 radio-openapi.yaml 生成）
_SPEC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "openapi.json"
)


def _load_spec():
    try:
        with open(_SPEC_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


@docs_bp.route("/api/openapi.json")
def openapi_spec():
    """返回 OpenAPI 3.0 规范 JSON（仓库单一事实源）。"""
    spec = _load_spec()
    if spec is None:
        return jsonify({"error": "openapi.json not found in radio/"}), 500
    return jsonify(spec)


@docs_bp.route("/api/docs")
def api_docs():
    """渲染 API 文档页面。"""
    return _render_swagger_page()


def _render_swagger_page():
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>API 文档 - 电台</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
<style>
body{margin:0;background:#0d1117}
.swagger-ui{filter:invert(88%) hue-rotate(180deg) brightness(.9)}
.swagger-ui .topbar{display:none}
.swagger-ui .opblock-tag{font-size:18px!important}
.back-link{display:block;padding:16px 24px;color:#58a6ff;text-decoration:none;font-size:14px;position:absolute;z-index:100}
.back-link:hover{text-decoration:underline}
</style>
</head>
<body>
<a href="/" class="back-link">← 返回电台主页</a>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
SwaggerUIBundle({url:"/api/openapi.json",dom_id:"#swagger-ui",deepLinking:true,defaultModelsExpandDepth:-1})
</script>
</body>
</html>"""
