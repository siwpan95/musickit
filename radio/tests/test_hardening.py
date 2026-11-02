"""radio 子进程调用加固的回归测试。

覆盖两条关键不变量：
1. `_bundled_bin` 在找不到二进制时返回 None（绝不返回裸名），找到时返回绝对路径；
2. `_kill_stale_hls` 收尸时只通过绝对路径调用外部命令，且二进制缺失时根本不调用
   subprocess（避免 Windows cwd 优先搜索导致的同名 exe 劫持）。
"""
import os
import sys

# radio/ 项目目录加入 path，使 `import radio` 解析到 radio/radio/ 包
_PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT not in sys.path:
    sys.path.insert(0, _PROJECT)

from radio import config, hls


class _FakeResult:
    """极简 subprocess.CompletedProcess 替身。"""

    def __init__(self):
        self.returncode = 0


def test_bundled_bin_returns_none_when_missing(monkeypatch):
    """找不到二进制时返回 None，而不是裸名 "ffmpeg"（裸名会被 cwd 劫持）。"""
    import tempfile
    d = tempfile.mkdtemp()
    monkeypatch.setattr(config, "FFMPEG_DIR", d)
    monkeypatch.setattr(config.shutil, "which", lambda name: None)
    assert config._bundled_bin("ffmpeg") is None
    assert config._bundled_bin("ffprobe") is None


def test_bundled_bin_returns_abspath_when_present(monkeypatch):
    """项目自带目录里有 exe 时返回绝对路径。"""
    import tempfile
    d = tempfile.mkdtemp()
    exe = os.path.join(d, "ffmpeg.exe")
    with open(exe, "w", encoding="utf-8") as f:
        f.write("")
    monkeypatch.setattr(config, "FFMPEG_DIR", d)
    monkeypatch.setattr(config.shutil, "which", lambda name: None)
    got = config._bundled_bin("ffmpeg")
    assert got is not None
    assert os.path.isabs(got)
    assert got == exe


def test_kill_stale_skips_when_binary_missing(monkeypatch):
    """二进制缺失时根本不调用 subprocess（且不传裸名）。"""
    calls = []
    monkeypatch.setattr(hls.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        hls.subprocess, "run",
        lambda *a, **k: (calls.append((a, k)) or _FakeResult()),
    )
    hls.reap_orphans()
    assert calls == [], "二进制缺失时不应调用任何外部命令"


def test_kill_stale_uses_absolute_path(monkeypatch):
    """二进制存在时，传给 subprocess 的是绝对路径，且显式传了 cwd=。"""
    calls = []
    abs_tool = r"C:\bin\tool.exe"  # 任意绝对路径即可，验证「绝不传裸名」

    def fake_run(*a, **k):
        calls.append((a, k))
        return _FakeResult()

    monkeypatch.setattr(hls.shutil, "which", lambda name: abs_tool)
    monkeypatch.setattr(hls.subprocess, "run", fake_run)
    hls.reap_orphans()
    assert calls, "应调用一次收尸命令"
    args, kwargs = calls[0]
    # 可执行文件必须是绝对路径（不是裸名）
    assert os.path.isabs(args[0][0])
    # 必须显式传 cwd，避免 cwd 被当作搜索路径
    assert "cwd" in kwargs
