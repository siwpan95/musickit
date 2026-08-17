#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风格池完整性自检脚本。

每次扩充 styles/ 后运行，校验所有 JSON 风格文件：
  - 是否为合法 JSON
  - 是否包含 REQUIRED_FIELDS 全部字段
  - 各列表字段是否为非空数组
  - key 是否唯一

用法：
  python validate_styles.py                 # 校验脚本同级 styles/
  python validate_styles.py -d 路径/to/styles
  python validate_styles.py --strict        # 警告也视为失败（非零退出码）

退出码：0 通过（或仅有警告），1 存在错误（非法 JSON / 缺字段 / key 重复）。
"""
import argparse
import json
import os
import sys

# 与 music_prompt_generator.py 保持一致的规范
REQUIRED_FIELDS = ["key", "label", "bpm", "subgenres",
                   "instruments", "scales", "moods", "elements", "scenes"]
LIST_FIELDS = ["subgenres", "instruments", "scales", "moods", "elements", "scenes"]


def validate(directory: str, strict: bool = False) -> int:
    if not os.path.isdir(directory):
        print(f"❌ 未找到风格池目录：{directory}")
        return 1

    errors = []
    warnings = []
    keys = {}
    files = sorted(f for f in os.listdir(directory) if f.lower().endswith(".json"))

    print(f"🔍 校验风格池：{directory}（共 {len(files)} 个文件）\n")

    for fn in files:
        path = os.path.join(directory, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            errors.append(f"  {fn}: JSON 解析失败 → {e}")
            continue

        if not isinstance(data, dict):
            errors.append(f"  {fn}: 根节点必须是 JSON 对象")
            continue

        # 必需字段检查
        missing = [f for f in REQUIRED_FIELDS if f not in data]
        if missing:
            errors.append(f"  {fn}: 缺少字段 {missing}")

        # 列表字段非空检查
        for lf in LIST_FIELDS:
            val = data.get(lf)
            if val is not None:
                if not isinstance(val, list):
                    errors.append(f"  {fn}: 字段 '{lf}' 必须是数组")
                elif len(val) == 0:
                    warnings.append(f"  {fn}: 字段 '{lf}' 为空数组")

        # subgenres 子项结构
        for i, sub in enumerate(data.get("subgenres", [])):
            if not isinstance(sub, dict) or "name" not in sub:
                errors.append(f"  {fn}: subgenres[{i}] 缺少 'name' 字段")

        # key 唯一性
        k = data.get("key", fn[:-5])
        if k in keys:
            errors.append(f"  {fn}: key '{k}' 与 {keys[k]} 重复")
        else:
            keys[k] = fn

        if missing:
            status = "❌"
        elif any(w.startswith(f"  {fn}:") for w in warnings):
            status = "⚠️"
        else:
            status = "✓"
        print(f"  {status} {fn:<22} key={k}")

    print("\n" + "=" * 56)
    if warnings:
        print(f"⚠️  警告（{len(warnings)}）：")
        for w in warnings:
            print(w)
    if errors:
        print(f"❌ 错误（{len(errors)}）：")
        for e in errors:
            print(e)
        print(f"\n结果：失败（{len(errors)} 个错误）")
        return 1

    if warnings and strict:
        print(f"\n结果：失败（strict 模式下 {len(warnings)} 个警告视为错误）")
        return 1

    print(f"✅ 校验通过：{len(files)} 个风格文件，{len(keys)} 个唯一 key，"
          f"{len(warnings)} 个警告。")
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="风格池完整性自检")
    parser.add_argument("-d", "--dir", default=os.path.join(here, "styles"),
                        help="风格池目录（默认脚本同级 styles/）")
    parser.add_argument("--strict", action="store_true",
                        help="将警告也视为失败（非零退出码）")
    args = parser.parse_args()
    sys.exit(validate(args.dir, strict=args.strict))


if __name__ == "__main__":
    main()
