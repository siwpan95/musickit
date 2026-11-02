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
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  for cand in python3 python py; do
    if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
  done
fi
if [ -z "$PY" ]; then
  echo "❌ 找不到 python，可用 PYTHON=/path/to/python 指定" >&2
  exit 2
fi
echo "== Python: $PY =="
"$PY" -V || exit 2

# ---- 依赖自检（缺 pydub 直接硬失败，否则后面报错难懂）----
if ! "$PY" -c "import pydub, numpy, soundfile" 2>/dev/null; then
  echo "❌ 缺少依赖（pydub / numpy / soundfile）。请先：$PY -m pip install -r remix/requirements.txt" >&2
  exit 2
fi

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

# ---- 2) 冒烟测试（纯逻辑，不需素材/编解码）----
# 某些机器装了会炸的 pytest 第三方插件（如 hydra → antlr4 → typing.io），
# 插件自加载阶段就 ImportError，一个用例都跑不起来 —— 那与「测试失败」是两回事。
# 因此：先正常跑；只有当失败原因看起来是插件/导入层，才关掉 autoload 重试一次，
# 并在输出里明确说明「这属于本机环境问题，不是测试失败」。
echo
echo "== pytest -m smoke =="
_run_smoke() {
  ( cd remix || exit 2; "$PY" -m pytest tests -q -m smoke "$@" )
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
  ( cd remix && "$PY" -m pytest tests -q ) || exit 1
fi

echo
echo "✅ 冒烟检查通过"
exit 0
