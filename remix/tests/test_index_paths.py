# -*- coding: utf-8 -*-
"""burbidge_album 的索引路径契约（2026-11-02 铁律 5 去符盘）。

背景（真实踩过的坑）：`burbidge_album/index.json` **是入库文件**，而它原先把
每个素材的**绝对路径**写进 `path` 字段（如 `G:\\repos\\musickit\\bass\\...`）。
后果有三：

1. **换机即失效** —— 别人 clone 下来，索引里的路径指向别人的盘，专辑管线读不到文件；
2. **违反铁律 5**（活文档/配置不烤盘符，路径写卷标识形式）；
3. **泄露本机目录结构**到公开仓库。

修法：`build_index.py` 存**相对仓库根**的路径，`build_album.py` 按自身位置推导的
仓库根还原成绝对路径再读文件。本测试守住这条契约，防止回退。

顺带守住另一条：`burbidge_album/build_index.py` 依赖仓根的 `manifest_index.json`，
缺失时会直接 FileNotFoundError（实测干净克隆必崩）—— 这里用「缺文件要给能照做的
提示」而非裸异常来检验。

本文件放在 remix/tests/ 而非 burbidge_album/：根 pytest.ini 的 testpaths 与
scripts/ci_smoke.sh 只收 remix/tests 与 music/tests，放在别处 CI 收不到。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))          # remix/tests/
_ROOT = os.path.dirname(os.path.dirname(_HERE))              # 仓库根
_ALBUM = os.path.join(_ROOT, "burbidge_album")
_BUILD_INDEX = os.path.join(_ALBUM, "build_index.py")
_BUILD_ALBUM = os.path.join(_ALBUM, "build_album.py")

pytestmark = pytest.mark.smoke


def _read_index():
    with open(os.path.join(_ALBUM, "index.json"), encoding="utf-8") as f:
        return json.load(f)


class TestIndexPathContract:
    def test_index_path_is_relative(self):
        """入库的 index.json 里不得有绝对路径（铁律 5）。"""
        idx = _read_index()
        assert idx["index"], "索引为空"
        for rec in idx["index"][:500]:
            p = rec["path"]
            assert not os.path.isabs(p), f"index.json 存了绝对路径（铁律 5 违规）：{p}"
            assert ":" not in p.split("/")[0], f"路径首段含盘符：{p}"
            assert not p.startswith("/"), f"路径以 / 开头（绝对路径）：{p}"

    def test_base_marker_is_not_a_local_path(self):
        """base 字段不得写死本机仓库根。"""
        base = _read_index()["base"]
        assert not os.path.isabs(base), f"base 存了绝对路径：{base}"
        assert ":" not in base, f"base 含盘符：{base}"

    def test_no_drive_letter_anywhere_in_index(self):
        """全量扫描：索引里不应出现任何 Windows 盘符形态。"""
        raw = open(os.path.join(_ALBUM, "index.json"), encoding="utf-8").read()
        assert ":\\" not in raw, "index.json 出现盘符路径（形如 X:\\...）"
        assert ":/" not in raw, "index.json 出现盘符路径（形如 X:/...）"


class TestAbsPathRestore:
    """build_album.abs_path 的还原逻辑（相对 → 绝对，且兼容旧版绝对路径）。"""

    def _load_abc(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("_mk_build_album", _BUILD_ALBUM)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.modules.pop(spec.name, None)
        return mod

    def test_relative_path_is_joined_to_root(self):
        mod = self._load_abc()
        out = mod.abs_path("bass/808_bass/bass (771).wav")
        assert os.path.isabs(out)
        assert out.replace("\\", "/").endswith("bass/808_bass/bass (771).wav")

    def test_absolute_path_passes_through(self):
        """兼容旧版 index.json（path 已是绝对路径）。"""
        mod = self._load_abc()
        raw = os.path.join(_ROOT, "bass", "x.wav")
        assert mod.abs_path(raw) == raw


class TestBuildIndexErrorPath:
    def test_missing_manifest_index_gives_actionable_hint(self):
        """缺 manifest_index.json 时，报错要能照做，而不是裸 FileNotFoundError。"""
        import shutil
        import tempfile

        mi = os.path.join(_ROOT, "manifest_index.json")
        if not os.path.isfile(mi):
            pytest.skip("本机无 manifest_index.json，跳过（该文件不入库）")

        with tempfile.TemporaryDirectory() as tmp:
            stub = os.path.join(tmp, "build_index.py")
            # 只复制脚本，manifest_index.json 故意缺席
            shutil.copy(_BUILD_INDEX, stub)
            env = dict(os.environ, MUSICKIT_ROOT=tmp)
            r = subprocess.run(
                [sys.executable, stub],
                capture_output=True, text=True, env=env, timeout=120,
            )
        assert r.returncode != 0, "缺 manifest_index.json 时应失败而非静默通过"
        combined = (r.stdout or "") + (r.stderr or "")
        assert "manifest_index" in combined, f"报错未提 manifest_index：{combined[-400:]}"
