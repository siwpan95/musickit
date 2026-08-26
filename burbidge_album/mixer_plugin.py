# -*- coding: utf-8 -*-
"""mixer_plugin.py —— 混音师插件协议（musickit S2 · 2026-08-25）

把 mixer_styles.STYLES 的 24 位混音师升级为正式插件协议：
- 插件 = 一个风格 manifest dict（数据即插件；数据源仍是 mixer_styles.STYLES，零迁移）；
- 注册即回滚：register/unregister 全量可逆（Context 纪律）；
- 校验 fail-loud：必填字段缺失当场点名；
- 独立更新：新增混音师 = 加一个 manifest dict，不动其他插件；
- 日志即事实源：resolve 选用事件写 JSONL（与 WorldLog/pipelog 同构：seq/ts/type/...）。

审计 CLI：python mixer_plugin.py --dump [--json] / --check
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mixer_styles as ms

REQUIRED = ["slug", "name", "zh", "drums", "bass", "pad", "lead", "bg", "master", "reverb"]
REGISTRY_VERSION = "1.0.0"
DEFAULT_LOG = Path(__file__).resolve().parent.parent / "data" / "mixer_events.log"

__all__ = ["MixerRegistry", "validate_manifest", "REGISTRY_VERSION"]


def validate_manifest(manifest) -> list:
    """校验单个混音师插件 manifest，返回问题列表（空 = 通过）。"""
    errs = []
    for k in REQUIRED:
        if k not in manifest or manifest[k] in (None, "", []):
            errs.append(f"missing required field: {k}")
    if manifest.get("slug") and not str(manifest["slug"]).strip():
        errs.append("slug 不能为空")
    return errs


class MixerRegistry:
    """混音师插件注册表：装配/回滚/审计（数据源 = mixer_styles.STYLES）。"""

    def __init__(self, log_path: Path | str | None = None):
        self._styles: dict = {}
        self._log_path = Path(log_path) if log_path is not None else None
        self._seq = 0

    # ---- 装配（注册即回滚） ----
    def register(self, manifest: dict) -> str:
        errs = validate_manifest(manifest)
        if errs:
            raise ValueError(f"混音师插件 '{manifest.get('slug', '?')}' 校验失败: {'; '.join(errs)}")
        slug = manifest["slug"]
        self._styles[slug] = {**manifest, "version": manifest.get("version", "1.0.0")}
        return slug

    def register_all(self, styles) -> int:
        for s in styles:
            self.register(s)
        return len(self._styles)

    def unregister(self, slug: str) -> dict | None:
        """卸载插件（注册即回滚：弹出即恢复原状）。"""
        return self._styles.pop(slug, None)

    # ---- 审计 ----
    def dump(self) -> list:
        out = []
        for slug in sorted(self._styles):
            s = self._styles[slug]
            out.append({
                "slug": slug, "name": s.get("name"), "zh": s.get("zh"),
                "version": s.get("version", "1.0.0"),
                "tagline": s.get("tagline", ""),
            })
        return out

    @property
    def slugs(self) -> list:
        return sorted(self._styles)

    def __len__(self) -> int:
        return len(self._styles)

    # ---- 解析（行为与 mixer_styles.resolve_style 完全一致 + 事件日志） ----
    def set_log(self, path: Path | str):
        self._log_path = Path(path)

    def _log(self, event_type: str, **payload):
        if self._log_path is None:
            return
        self._seq += 1
        entry = {"seq": self._seq,
                 "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                 "type": event_type}
        entry.update(payload)
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_path, "a", encoding="utf-8") as fp:
                fp.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass  # 日志写失败静默不阻断混音（pipelog 同纪律）

    def resolve(self, name: str, rng=None) -> dict:
        style = ms.resolve_style(name, rng)
        self._log("mixer_resolve", style=style["slug"], name=name, zh=style.get("zh"))
        return style


def _main(argv) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="python mixer_plugin.py", description="混音师插件注册表审计")
    p.add_argument("--dump", action="store_true", help="打印插件清单")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    p.add_argument("--check", action="store_true", help="校验全部插件（exit 0=全通过）")
    args = p.parse_args(argv)

    reg = MixerRegistry()
    problems = []
    for s in ms.STYLES:
        try:
            reg.register(s)
        except ValueError as e:
            problems.append(str(e))

    if args.json:
        print(json.dumps({"version": REGISTRY_VERSION, "count": len(reg),
                          "styles": reg.dump(), "problems": problems},
                         ensure_ascii=False, indent=2))
        return 1 if problems else 0
    if args.check:
        for d in reg.dump():
            print(f"  {d['slug']:24} v{d['version']}  {d['zh']}  ({d['name']})")
        print(f"[check] {'通过' if not problems else '失败'}：{len(reg)} 插件" + (f"，问题：{problems}" if problems else ""))
        return 1 if problems else 0
    if args.dump:
        for d in reg.dump():
            print(f"  {d['slug']:24} v{d['version']}  {d['zh']}  ({d['name']})  {d['tagline']}")
        print(f"共 {len(reg)} 位混音师插件（注册表 v{REGISTRY_VERSION}）")
        return 0
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
