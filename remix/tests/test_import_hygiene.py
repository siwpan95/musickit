"""导入卫生：PATH 前置必须幂等、入库脚本必须能导入。

两个都是真实踩过的坑：

1. `main.py` 曾在 import 时无条件 `os.environ["PATH"] = bin + sep + PATH`。
   main.py 会被 GUI、hourly_remix、测试等多处以**不同模块名**重复加载，
   每加载一次 PATH 就多一段相同的 bin/（实测 3 次加载：41 段 → 44 段）。
   现在改为调用 `binfind.ensure_path_env()`（幂等）。

2. `ingest_categories / ingest_guitar / ingest_synth` 三个脚本在定义 `_MK_ROOT`
   之前就引用了它 → 导入即 NameError，脚本从来跑不起来（`ingest_mixkit` 早先
   修过同一个 bug，另外三个漏了）。
"""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

_REMIX = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOOLS = os.path.join(_REMIX, "tools")
sys.path.insert(0, _REMIX)

from core import binfind  # noqa: E402

pytestmark = pytest.mark.smoke

_BIN = os.path.normcase(os.path.abspath(binfind.BIN_DIR))


def _bin_occurrences() -> int:
    """PATH 里出现几次 remix/bin（规范化后按完整段比较，避免子串误判）。"""
    n = 0
    for part in os.environ.get("PATH", "").split(os.pathsep):
        if part and os.path.normcase(os.path.abspath(part)) == _BIN:
            n += 1
    return n


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestPathPrependIsIdempotent:
    def test_ensure_path_env_is_idempotent(self):
        binfind.ensure_path_env()
        binfind.ensure_path_env()
        binfind.ensure_path_env()
        assert _bin_occurrences() <= 1

    def test_reloading_main_does_not_grow_path(self):
        """模拟 GUI / hourly_remix / 测试先后加载 main.py 的真实情形。"""
        before = _bin_occurrences()
        for i in range(3):
            _load(f"_path_probe_main_{i}", os.path.join(_REMIX, "main.py"))
        after = _bin_occurrences()
        assert after <= max(1, before), (
            f"重复加载 main.py 把 bin/ 叠加进了 PATH（{before} 次 → {after} 次）；"
            "应改为调用 binfind.ensure_path_env()"
        )


class TestIngestScriptsImportable:
    """入库脚本在定义 _MK_ROOT 之前就引用它 → NameError，等于完全不能用。"""

    @pytest.mark.parametrize("name", [
        "ingest_categories", "ingest_guitar", "ingest_synth", "ingest_mixkit",
    ])
    def test_imports_without_nameerror(self, name):
        mod = _load(f"_ingest_probe_{name}", os.path.join(_TOOLS, f"{name}.py"))
        assert mod._MK_ROOT.is_dir(), "_MK_ROOT 应指向存在的仓根"
        assert str(mod._BIN).endswith(os.path.join("remix", "bin"))

    def test_ingest_scripts_do_not_duplicate_path(self):
        """四个脚本的 PATH 前置都已幂等：连开四个也不该出现重复段。"""
        for name in ("ingest_categories", "ingest_guitar", "ingest_synth", "ingest_mixkit"):
            _load(f"_ingest_dup_{name}", os.path.join(_TOOLS, f"{name}.py"))
        assert _bin_occurrences() <= 1
