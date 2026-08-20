"""用户认证系统：密码登录 / 登出 / Session 保护。

- 密码哈希存储（SHA-256 + salt），不以明文落盘
- 控制面板访问控制：未登录跳转登录页
- API 写操作（POST）可选择性保护
- 支持首次运行自动设置密码

用法：
    from .auth import login_required, api_login_required, init_auth

    init_auth(app)                    # 注册 session secret key
    @login_required                   # 保护 HTML 页面路由
    @api_login_required                # 保护 API POST 路由
"""
import hashlib
import os
import secrets
import functools
from flask import session, redirect, url_for, request, jsonify, render_template_string
from . import config

# 密码哈希文件：首次运行自动创建
_PASSWD_PATH = os.path.join(config.BASE_DIR, ".station_password")

LOGIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>登录 - {station}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);
  min-height:100vh;display:flex;align-items:center;justify-content:center;
  color:#eee;
}}
.card{{
  background:rgba(255,255,255,0.08);backdrop-filter:blur(16px);
  border:1px solid rgba(255,255,255,0.1);border-radius:20px;
  padding:48px 40px;width:100%;max-width:400px;text-align:center;
}}
.card h1{{font-size:28px;margin-bottom:6px;font-weight:700}}
.card p{{color:#aaa;margin-bottom:32px;font-size:14px}}
input{{
  width:100%;padding:14px 18px;border-radius:12px;border:1px solid rgba(255,255,255,0.2);
  background:rgba(255,255,255,0.06);color:#fff;font-size:16px;outline:none;
  margin-bottom:16px;transition:border-color .2s;
}}
input:focus{{border-color:#e94560}}
input::placeholder{{color:#777}}
.btn{{
  width:100%;padding:14px;border-radius:12px;border:none;
  background:linear-gradient(135deg,#e94560,#c23152);
  color:#fff;font-size:16px;font-weight:600;cursor:pointer;
  transition:opacity .2s,transform .1s;
}}
.btn:hover{{opacity:.9}}
.btn:active{{transform:scale(0.98)}}
.error{{color:#e94560;font-size:13px;margin-bottom:12px;display:none}}
.error.show{{display:block}}
</style>
</head>
<body>
<div class="card">
  <h1>🎙️ {station}</h1>
  <p>请输入管理员密码以继续</p>
  <div class="error" id="error">{error}</div>
  <form method="POST">
    <input type="password" name="password" placeholder="管理员密码" autofocus required>
    <button type="submit" class="btn">登 录</button>
  </form>
</div>
<script>
  var e=document.getElementById("error");
  if(e.textContent.trim())e.classList.add("show");
</script>
</body>
</html>"""


def _hash_password(password: str, salt: str = "") -> tuple:
    """SHA-256 哈希密码（兼容 salt）。返回 (hash_hex, salt_hex)。"""
    if not salt:
        salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return h, salt


def init_auth(app):
    """初始化认证系统：注册 Flask secret key。"""
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))


def is_configured() -> bool:
    """是否已设置密码（.station_password 文件存在）。"""
    return os.path.isfile(_PASSWD_PATH)


def _read_password():
    """读取密码哈希文件，返回 (hash, salt) 或 (None, None)。"""
    try:
        with open(_PASSWD_PATH, "r") as f:
            h, s = f.read().strip().split(":", 1)
        return h, s
    except Exception:
        return None, None


def verify_password(password: str) -> bool:
    """验证密码是否正确。"""
    h, s = _read_password()
    if not h:
        return True   # 未设置 = 无密码模式
    return _hash_password(password, s)[0] == h


def set_password(password: str):
    """设置/修改密码（原子写）。"""
    h, s = _hash_password(password)
    tmp = _PASSWD_PATH + ".tmp"
    with open(tmp, "w") as f:
        f.write(f"{h}:{s}")
    os.replace(tmp, _PASSWD_PATH)


def login_required(view):
    """装饰器：保护 HTML 页面路由。未登录重定向到登录页。"""
    @functools.wraps(view)
    def wrapper(*a, **kw):
        if session.get("logged_in"):
            return view(*a, **kw)
        return _login_page()
    return wrapper


def api_login_required(view):
    """装饰器：保护 API 路由。未登录返回 401 JSON。"""
    @functools.wraps(view)
    def wrapper(*a, **kw):
        if session.get("logged_in"):
            return view(*a, **kw)
        return jsonify({"ok": False, "error": "请先登录"}), 401
    return wrapper


def optional_login(view):
    """装饰器：不强制登录，但把登录状态注入 kwargs（前端用）。"""
    @functools.wraps(view)
    def wrapper(*a, **kw):
        kw["_logged_in"] = session.get("logged_in", False)
        return view(*a, **kw)
    return wrapper


def _login_page(error=""):
    """渲染登录页。"""
    return render_template_string(
        LOGIN_HTML,
        station=config.STATION_NAME,
        error=error
    )


def register_routes(app):
    """在 Flask app 上注册认证相关路由。"""

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            pwd = (request.form.get("password") or "").strip()
            # 未设置密码：首次 POST 即创建密码
            if not is_configured():
                if pwd:
                    set_password(pwd)
                    session["logged_in"] = True
                    return redirect(url_for("index"))
                return _login_page("请输入新密码来创建管理员账户")
            # 已设置：验证
            if verify_password(pwd):
                session["logged_in"] = True
                return redirect(url_for("index"))
            return _login_page("密码错误")
        # GET：如果已配置密码就显示登录页；否则显示首次设置页
        if is_configured() and session.get("logged_in"):
            return redirect(url_for("index"))
        msg = "" if is_configured() else "首次使用，请设置管理员密码"
        return _login_page(msg)

    @app.route("/logout")
    def logout():
        session.pop("logged_in", None)
        return redirect(url_for("login"))

    @app.route("/api/auth/status")
    def api_auth_status():
        """返回认证状态（前端用于决定是否显示登录入口）。"""
        return jsonify({
            "ok": True,
            "configured": is_configured(),
            "logged_in": session.get("logged_in", False),
        })

    @app.route("/api/auth/password", methods=["POST"])
    def api_change_password():
        """修改密码（需已登录或首次设置）。"""
        if is_configured() and not session.get("logged_in"):
            return jsonify({"ok": False, "error": "请先登录"}), 401
        body = request.get_json(silent=True) or {}
        old = (body.get("old") or "").strip()
        new = (body.get("new") or "").strip()
        if not new or len(new) < 4:
            return jsonify({"ok": False, "error": "密码至少 4 位"}), 400
        if is_configured() and not verify_password(old):
            return jsonify({"ok": False, "error": "原密码错误"}), 403
        set_password(new)
        return jsonify({"ok": True})
