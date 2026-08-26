# -*- coding: utf-8 -*-
"""style_plugin.py —— 风格池插件协议（musickit S3 · 2026-08-25）

把 music/styles/ 的 63 个流派 JSON 升级为正式插件协议（与 S2 mixer_plugin 同构）：
- 插件 = 一个风格 JSON（数据即插件；扩展方式不变：styles/ 新增 JSON 即注册）；
- 注册即回滚：register/unregister 全量可逆；
- 校验 fail-loud：key/label/bpm/subgenres 必填，key 唯一；
- 独立更新：每个 JSON 可带 "version"（缺省 1.0.0），新增流派 = 加一个 JSON 不动其他；
- 日志即事实源：pick/resolve 事件写 JSONL（与 WorldLog/pipelog 同构）。

审计 CLI：python style_plugin.py --dump [--json] / --check
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

STYLES_DIR = Path(__file__).resolve().parent / "styles"
REQUIRED = ["key", "label", "bpm", "subgenres"]
REGISTRY_VERSION = "1.0.0"
DEFAULT_LOG = Path(__file__).resolve().parent.parent / "data" / "prompt_events.log"

__all__ = ["StyleRegistry", "validate_style", "REGISTRY_VERSION", "STYLES_DIR"]


def validate_style(style: dict) -> list:
    """校验单个风格插件，返回问题列表（空 = 通过）。"""
    errs = []
    for k in REQUIRED:
        if k not in style or style[k] in (None, ""):
            errs.append(f"missing required field: {k}")
    if "key" in style and style["key"] and not str(style["key"]).strip():
        errs.append("key 不能为空")
    return errs


class StyleRegistry:
    """风格池插件注册表：装配/回滚/审计（数据源 = styles/*.json）。"""

    def __init__(self, styles_dir: Path | str = STYLES_DIR, log_path: Path | str | None = None):
        self._styles_dir = Path(styles_dir)
        self._styles: dict = {}
        self._log_path = Path(log_path) if log_path is not None else None
        self._seq = 0

    # ---- 装配（注册即回滚） ----
    def register(self, style: dict) -> str:
        errs = validate_style(style)
        if errs:
            raise ValueError(f"风格插件 '{style.get('key', '?')}' 校验失败: {'; '.join(errs)}")
        key = style["key"]
        if key in self._styles:
            raise ValueError(f"风格 key 重复: {key}")
        self._styles[key] = {**style, "version": style.get("version", "1.0.0")}
        return key

    def load_all(self) -> int:
        """从 styles/ 目录加载全部 JSON（= 插件目录扫描）。"""
        for fp in sorted(self._styles_dir.glob("*.json")):
            with open(fp, encoding="utf-8") as f:
                self.register(json.load(f))
        return len(self._styles)

    def unregister(self, key: str) -> dict | None:
        return self._styles.pop(key, None)

    # ---- 审计 ----
    def dump(self) -> list:
        out = []
        for key in sorted(self._styles):
            s = self._styles[key]
            out.append({
                "key": key, "label": s.get("label"), "bpm": s.get("bpm"),
                "version": s.get("version", "1.0.0"),
                "subgenres": len(s.get("subgenres", [])),
            })
        return out

    @property
    def keys(self) -> list:
        return sorted(self._styles)

    def has(self, key: str) -> bool:
        return key in self._styles

    def __len__(self) -> int:
        return len(self._styles)

    # ---- 选用事件日志 ----
    def set_log(self, path: Path | str):
        self._log_path = Path(path)

    def log_pick(self, key: str, source: str = "pick", **payload):
        if self._log_path is None:
            return
        self._seq += 1
        entry = {"seq": self._seq,
                 "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                 "type": "style_pick",
                 "key": key,
                 "source": source}
        entry.update(payload)
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_path, "a", encoding="utf-8") as fp:
                fp.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass  # 写失败静默（pipelog 同纪律）


def _main(argv) -> int:
    p = argparse.ArgumentParser(prog="python style_plugin.py", description="风格池插件注册表审计")
    p.add_argument("--dump", action="store_true", help="打印风格池插件清单")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    p.add_argument("--check", action="store_true", help="校验全部插件（exit 0=全通过）")
    args = p.parse_args(argv)

    reg = StyleRegistry()
    problems = []
    try:
        reg.load_all()
    except ValueError as e:
        problems.append(str(e))

    if args.json:
        print(json.dumps({"version": REGISTRY_VERSION, "count": len(reg),
                          "styles": reg.dump(), "problems": problems},
                         ensure_ascii=False, indent=2))
        return 1 if problems else 0
    if args.check:
        for d in reg.dump():
            print(f"  {d['key']:22} v{d['version']}  {d['bpm']:12} {d['label']}  ({d['subgenres']} 子类)")
        print(f"[check] {'通过' if not problems else '失败'}：{len(reg)} 插件" + (f"，问题：{problems}" if problems else ""))
        return 1 if problems else 0
    if args.dump:
        for d in reg.dump():
            print(f"  {d['key']:22} v{d['version']}  {d['bpm']:12} {d['label']}  ({d['subgenres']} 子类)")
        print(f"共 {len(reg)} 个风格插件（注册表 v{REGISTRY_VERSION}）")
        return 0
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
