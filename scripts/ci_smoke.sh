#!/usr/bin/env bash
# musickit 冒烟检查（T0-2）—— 本地 / CI 通用入口。
#
# 用法：
#   bash scripts/ci_smoke.sh                  # 自检 + 冒烟测试
#   PYTHON=/e/Python314/python.exe bash scripts/ci_smoke.sh
#   STRICT_MATERIAL=1 bash scripts/ci_smoke.sh   # 素材为空也判失败
#
# 退出码：0 通过 / 1 冒烟测试失败 / 2 环境硬失败
set -uo pipefail

cd "$(dirname "$0")/.." || exit 2
ROOT="$(pwd)"

# ---- 选 Python ----
# 按名字取第一个（python3 → python → py）是不够的：本机 PATH 上同名解释器有好几个
# （托管 Python 3.13.12 无 pydub 排在最前，真正的 E:\Python314 排第 4），
# 于是脚本会选中一个跑不起来的解释器。这里枚举 PATH 上**全部**同名项，逐个探测依赖。
HAVE_DEPS='import pydub, numpy, soundfile'

_candidates() {
  if [ -n "${PYTHON:-}" ]; then printf '%s\n' "$PYTHON"; return; fi
  local name
  for name in python3 python py; do
    command -v "$name" >/dev/null 2>&1 && printf '%s\n' "$name"
  done
  which -a python3 python py 2>/dev/null
}

PY=""
PY_STRICT=0
if [ -n "${PYTHON:-}" ]; then
  PY="$PYTHON"
  PY_STRICT=1          # 显式指定就只认它，缺依赖属于配置错误，直接硬失败
else
  _seen='|'
  while IFS= read -r cand; do
    [ -n "$cand" ] || continue
    case "$_seen" in *"|$cand|"*) continue ;; esac     # 去重
    _seen="$_seen$cand|"
    if "$cand" -c "$HAVE_DEPS" >/dev/null 2>&1; then PY="$cand"; break; fi
  done <<EOF
$(_candidates)
EOF
fi

if [ -z "$PY" ]; then
  echo "❌ 找不到装了 pydub / numpy / soundfile 的 Python。" >&2
  echo "   已尝试：$(_candidates | tr '\n' ' ')" >&2
  echo "   请显式指定：PYTHON=/path/to/python bash scripts/ci_smoke.sh" >&2
  exit 2
fi
echo "== Python: $PY =="
"$PY" -V || exit 2

# ---- 依赖自检（显式指定解释器时缺依赖直接硬失败，否则后面报错难懂）----
if ! "$PY" -c "$HAVE_DEPS" 2>/dev/null; then
  echo "❌ 缺少依赖（pydub / numpy / soundfile）。请先：$PY -m pip install -r remix/requirements.txt" >&2
  exit 2
fi
[ "$PY_STRICT" = "1" ] && echo "   （来自 PYTHON，依赖已确认）"

# ---- 1) 环境与素材自检 ----
echo
echo "== doctor =="
DOCTOR_ARGS=(--root "$ROOT")
[ "${STRICT_MATERIAL:-0}" = "1" ] && DOCTOR_ARGS+=(--strict)
"$PY" remix/tools/doctor.py "${DOCTOR_ARGS[@]}"
DOCTOR_RC=$?
if [ "$DOCTOR_RC" -ge 2 ]; then
  echo "❌ doctor 判定硬失败（exit $DOCTOR_RC）" >&2
  exit 2
fi

# ---- 1.5) 文档里的测试数字必须与真实收集数一致 ----
# 手写的「N passed」每加一条用例就静默过期一次，本仓已多次踩这个坑
# （`--release-safe` 守红线、`7 处写死`、125 passed 早已是 191）。
# 这里只用 pytest --collect-only 数用例，不执行，几秒内跑完。
echo
echo "== 文档数字一致性 =="
"$PY" scripts/check_doc_counts.py || exit 1

# ---- 2) 冒烟测试（纯逻辑，不需素材/编解码）----
# 覆盖两侧：remix/tests（混音引擎）+ music/tests（提示词桥接：scale / scene / elements / fusion）。
# 某些机器装了会炸的 pytest 第三方插件（如 hydra → antlr4 → typing.io），
# 插件自加载阶段就 ImportError，一个用例都跑不起来 —— 那与「测试失败」是两回事。
# 因此：先正常跑；只有当失败原因看起来是插件/导入层，才关掉 autoload 重试一次，
# 并在输出里明确说明「这属于本机环境问题，不是测试失败」。
echo
echo "== pytest -m smoke =="
_run_smoke() {
  "$PY" -m pytest remix/tests music/tests -q -m smoke "$@"
}

OUT="$(_run_smoke 2>&1)"; RC=$?
if [ "$RC" -ne 0 ] && printf '%s' "$OUT" | grep -qE "ModuleNotFoundError|ImportError while loading|plugin"; then
  echo "$OUT" | tail -6
  echo "⚠️ 检测到 pytest 插件/导入层崩溃（非测试失败），改用 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 重试"
  export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
  OUT="$(_run_smoke 2>&1)"; RC=$?
fi
printf '%s
' "$OUT" | tail -8
if [ "$RC" -ne 0 ]; then
  echo "❌ 冒烟测试失败（exit $RC）" >&2
  exit 1
fi

# ---- 3) 全量单测（可选：FULL=1）----
if [ "${FULL:-0}" = "1" ]; then
  echo
  echo "== pytest（全量） =="
  "$PY" -m pytest remix/tests music/tests -q || exit 1
fi

echo
echo "✅ 冒烟检查通过"
exit 0
