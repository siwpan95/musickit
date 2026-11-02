"""core/boot 的契约：全进程只有一个 main 模块对象。

背景（真实踩过的坑）：`remix/main.py` 曾被 5 种方式加载 —— `python main.py`
（`__main__`）、`import main`、以及三个不同名字的 `spec_from_file_location`
（`musickit_remix_main` / `musickit_remix_main_rr` / 一份压根没注册 sys.modules）。
同一进程里因此可能同时存在好几份 main 对象，模块级状态各算各的：converter
指哪份 ffmpeg、MUSICKIT_ROOT 取哪个根、PATH 前置了几次，全看从哪进来的。
"""
from __future__ import annotations

import os
import sys
import types

import pytest

_REMIX = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MUSIC = os.path.join(os.path.dirname(_REMIX), "music")
sys.path.insert(0, _REMIX)

from core import boot  # noqa: E402

pytestmark = pytest.mark.smoke


class TestSingleIdentity:
    def test_repeated_calls_return_the_same_object(self):
        first = boot.load_main()
        second = boot.load_main()
        assert first is second

    def test_registers_under_fixed_name(self):
        mod = boot.load_main()
        assert sys.modules.get("main") is mod
        assert mod.__file__.endswith(os.path.join("remix", "main.py"))

    def test_no_second_copy_under_legacy_names(self):
        """老名字（musickit_remix_main*）不该再出现 —— 出现就说明有入口绕过了 boot。"""
        boot.load_main()
        legacy = [n for n in sys.modules
                  if n.startswith("musickit_remix_main")]
        assert legacy == [], f"仍有入口自己加载 main：{legacy}"


class TestScriptEntryIsAliased:
    """`python main.py` 启动时 __main__ 就是 main.py —— 必须别名，不能再执行一遍。"""

    def test_main_dunder_is_reused(self, monkeypatch):
        fake = types.ModuleType("__main__")
        fake.__file__ = boot.MAIN_PATH
        fake.run_remix = lambda *a, **k: None          # 标记"我就是它"
        monkeypatch.setitem(sys.modules, "__main__", fake)
        monkeypatch.setitem(sys.modules, "main", types.ModuleType("main"))  # 旧副本
        boot.reset_cache()

        got = boot.load_main()
        assert got is fake, "应复用 __main__，而不是重新执行一遍 main.py"
        assert sys.modules["main"] is fake, "旧副本应被覆盖"

    def test_unrelated_dunder_is_not_mistaken(self, monkeypatch):
        """pytest 进程的 __main__ 没有 run_remix，不能被误当成 main.py。"""
        fake = types.ModuleType("__main__")
        fake.__file__ = os.path.join(_REMIX, "tools", "doctor.py")
        monkeypatch.setitem(sys.modules, "__main__", fake)
        boot.reset_cache()

        got = boot.load_main()
        assert got is not fake
        assert hasattr(got, "run_remix")


class TestAllEntrypointsConverge:
    """四个入口必须拿到同一个对象 —— 这是收敛是否真的生效的唯一判据。"""

    def test_four_entrypoints_agree(self, monkeypatch):
        canonical = boot.load_main()

        # 1) remix/tools/hourly_remix.py::load_stack()
        sys.path.insert(0, os.path.join(_REMIX, "tools"))
        import hourly_remix  # noqa: E402
        monkeypatch.setattr(hourly_remix, "args_pass",
                            types.SimpleNamespace(fusion=False), raising=False)
        from_hourly, _pdr, _mpg = hourly_remix.load_stack()

        # 2) remix/tools/rerender_from_index.py::load_remix_main()
        import rerender_from_index  # noqa: E402
        from_rerender = rerender_from_index.load_remix_main()

        # 3) music/prompt_driven_remix.py 里的 _m
        if _MUSIC not in sys.path:
            sys.path.insert(0, _MUSIC)
        import prompt_driven_remix as pdr  # noqa: E402
        from_pdr = pdr._m

        assert from_hourly is canonical, "hourly_remix 拿到了另一份 main"
        assert from_rerender is canonical, "rerender_from_index 拿到了另一份 main"
        assert from_pdr is canonical, "prompt_driven_remix 拿到了另一份 main"
        assert pdr.run_remix is canonical.run_remix
        assert pdr.pick_loop_candidate is canonical.pick_loop_candidate


class TestLoadFailureLeavesNoStub:
    def test_failed_load_does_not_poison_sys_modules(self, monkeypatch, tmp_path):
        """加载失败时不能留下半成品模块，否则下次调用会拿到空壳。"""
        bad = tmp_path / "main.py"
        bad.write_text("raise RuntimeError('boom')\n", encoding="utf-8")
        monkeypatch.setattr(boot, "MAIN_PATH", str(bad))
        monkeypatch.delitem(sys.modules, "main", raising=False)
        boot.reset_cache()

        with pytest.raises(RuntimeError):
            boot.load_main()
        assert "main" not in sys.modules or sys.modules["main"].__file__ != str(bad)
