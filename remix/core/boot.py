"""boot —— 全仓唯一的 main.py 加载入口。

## 为什么需要这个文件

混音引擎 `remix/main.py` 曾被 **5 种方式**加载，模块标识各不相同：

| 入口 | 加载方式 | sys.modules 里的名字 |
|---|---|---|
| `python main.py` | 直接执行 | `__main__` |
| `remix/gui/main_window.py` | `import main` | `main` |
| `remix/tools/hourly_remix.py` | `spec_from_file_location` | `musickit_remix_main` |
| `remix/tools/rerender_from_index.py` | 同上 | `musickit_remix_main_rr` |
| `music/prompt_driven_remix.py` | 同上，**但没注册 sys.modules** | （不登记，谁也不知道它存在） |

后果不是"重复了几行代码"，而是**同一进程里能同时存在好几份 main 模块对象**：
模块级状态各算各的 —— `AudioSegment.converter` 指哪份 ffmpeg、`_MUSICKIT_ROOT`
取的哪个根、`_PATH` 前置了几次，都取决于你是从哪个入口进来的。于是
「测试通过」不等于「生产可用」，A 处改了状态 B 处也看不见。
（PATH 重复叠加就是这么来的：每加载一次执行一遍模块级语句。）

## 这个文件做的事

把"加载 main"收敛成一个函数：**整个进程只解析出一个 main 模块对象**，
标识固定为 `main`，重复调用直接返回同一个。

    from core.boot import load_main
    remix = load_main()
    remix.run_remix(...)

优先级：
1. 本函数已经解析过 → 直接返回缓存。
2. 进程是以 `python main.py` 启动的（`__main__` 就是它）→ 把 `__main__`
   **别名**成 `main`。这样后续 `import main` 拿到的是同一个对象，不会再执行
   一遍模块级代码。
3. `sys.modules["main"]` 已经是它 → 用它。
4. 都没有 → 按路径加载一次，注册进 `sys.modules["main"]` 并缓存。

判断"是不是它"看两点：有 `run_remix` 属性，且 `__file__` 指向同一个 main.py。
只看名字会被同名的无关模块骗到。
"""
from __future__ import annotations

import importlib.util
import os
import sys

# core/boot.py -> core -> remix
REMIX_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PATH = os.path.join(REMIX_DIR, "main.py")

# 固定用它。不要再引入第二个名字 —— 那正是这个文件要消除的问题。
MODULE_NAME = "main"

_cached = None


def _same_file(a: str | None, b: str) -> bool:
    if not a:
        return False
    try:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))
    except (OSError, ValueError):
        return False


def _is_remix_main(mod) -> bool:
    """既要有 run_remix，又必须真的是这个 main.py（防同名模块）。"""
    if mod is None or not hasattr(mod, "run_remix"):
        return False
    return _same_file(getattr(mod, "__file__", None), MAIN_PATH)


def ensure_import_path() -> None:
    """把 remix/ 放进 sys.path，让 `from core...` / `import mixer_styles` 之类能解析。"""
    if REMIX_DIR not in sys.path:
        sys.path.insert(0, REMIX_DIR)


def load_main():
    """返回全进程唯一的 remix/main.py 模块对象。"""
    global _cached

    if _is_remix_main(_cached):
        return _cached

    # 2) 以脚本方式启动（python main.py）：__main__ 就是它，别名过来，别再执行一遍
    entry = sys.modules.get("__main__")
    if _is_remix_main(entry):
        sys.modules[MODULE_NAME] = entry      # 覆盖掉可能存在的重复副本
        _cached = entry
        return entry

    # 3) 已经按正式名字加载过
    existing = sys.modules.get(MODULE_NAME)
    if _is_remix_main(existing):
        _cached = existing
        return existing

    # 4) 首次加载
    ensure_import_path()
    spec = importlib.util.spec_from_file_location(MODULE_NAME, MAIN_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法从 {MAIN_PATH} 构造模块规格")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = mod          # 先注册再执行：模块内部的循环导入才看得见自己
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(MODULE_NAME, None)  # 失败别留下半成品
        raise
    _cached = mod
    return mod


def reset_cache() -> None:
    """仅供测试：清掉本模块的缓存（不动 sys.modules）。"""
    global _cached
    _cached = None
