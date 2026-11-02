"""binfind / duration_ms 的解析与降级行为测试（纯逻辑，不依赖真实 ffmpeg）。"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import binfind  # noqa: E402
from core.loop_slicer import duration_ms_or  # noqa: E402

pytestmark = pytest.mark.smoke


class TestResolve:
    def test_bundled_bin_wins_over_path(self, tmp_path, monkeypatch):
        """bin/ 里存在同名文件时，必须优先用它（可锁定版本）。"""
        exe = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        bundled = tmp_path / exe
        bundled.write_bytes(b"fake")
        monkeypatch.setattr(binfind, "BIN_DIR", str(tmp_path))
        monkeypatch.setattr(binfind.shutil, "which", lambda n: "/system/" + n)

        assert binfind.resolve("ffmpeg") == str(bundled)

    def test_falls_back_to_path(self, tmp_path, monkeypatch):
        """bin/ 缺失时回退 shutil.which（系统装过 ffmpeg 就能用）。"""
        monkeypatch.setattr(binfind, "BIN_DIR", str(tmp_path))
        monkeypatch.setattr(binfind.shutil, "which", lambda n: "/system/" + n)

        assert binfind.resolve("ffmpeg") == "/system/ffmpeg"

    def test_returns_none_when_absent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(binfind, "BIN_DIR", str(tmp_path))
        monkeypatch.setattr(binfind.shutil, "which", lambda n: None)

        assert binfind.resolve("ffprobe") is None

    def test_require_message_contains_search_paths(self, tmp_path, monkeypatch):
        """require 的报错必须自带「找过哪里」，否则排障时等于没说。"""
        monkeypatch.setattr(binfind, "BIN_DIR", str(tmp_path))
        monkeypatch.setattr(binfind.shutil, "which", lambda n: None)

        with pytest.raises(binfind.BinaryNotFound) as ei:
            binfind.require("ffprobe")
        msg = str(ei.value)
        assert "ffprobe" in msg
        assert str(tmp_path) in msg  # 具体搜索目录
        assert "PATH" in msg  # 安装指引

    def test_empty_name_is_safe(self):
        assert binfind.resolve("") is None


class TestPathEnv:
    def test_ensure_path_env_is_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(binfind, "BIN_DIR", str(tmp_path))
        monkeypatch.setenv("PATH", "/usr/bin")

        binfind.ensure_path_env()
        binfind.ensure_path_env()

        parts = os.environ["PATH"].split(os.pathsep)
        assert parts.count(str(tmp_path)) == 1  # 不重复插入
        assert parts[0] == str(tmp_path)  # 必须前置（否则被系统旧版抢走）


class TestDurationFallback:
    def test_prefers_manifest_duration(self):
        """已知 manifest 时长时不应探测（0 成本路径）。"""
        assert duration_ms_or("不存在的文件.mp3", 2040) == 2040

    def test_zero_fallback_falls_through(self):
        """fallback 为 0 视为未知，走探测；文件不存在 → 0。"""
        assert duration_ms_or("不存在的文件_xyz.mp3", 0) == 0

    def test_negative_fallback_ignored(self):
        assert duration_ms_or("不存在的文件_xyz.mp3", -5) == 0
