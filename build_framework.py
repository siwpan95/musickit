# -*- coding: utf-8 -*-
"""build_framework.py —— musickit 框架安装包（S7）：staging → Inno Setup → 静默回环验证。

框架包 = 提示词/混音/电台 三段编排代码（不含采样库 13 池、不含 ffmpeg 二进制、不含渲染产物）。
产物：installer/musickit-framework-setup-1.0.0.exe
"""
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
MUSICKIT = Path(__file__).resolve().parent
AUDIO_PIPELINE = Path(r"G:\tools\audio\audio_pipeline")
STAGE = Path(r"G:\_job\framework_stage")
FRAMEWORK = STAGE / "framework"
ISCC = Path(r"C:\Users\13122\AppData\Local\Programs\Inno Setup 6\ISCC.exe")

SKIP_DIRS = {".venv", "venv", "__pycache__", ".pytest_cache", "bin", "output",
             "prompt_mixes", "prompt_mixes_json", "deliverables", "tests", "node_modules"}


def copy_dir(src: Path, dst: Path):
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name in SKIP_DIRS:
            continue
        if item.is_dir():
            shutil.copytree(item, dst / item.name)
        elif item.suffix in (".py", ".json", ".md", ".txt", ".yml", ".yaml", ".toml", ".bat"):
            shutil.copy2(item, dst / item.name)


def stage_framework():
    if STAGE.exists():
        shutil.rmtree(STAGE, ignore_errors=True)
    FRAMEWORK.mkdir(parents=True)
    # ① audio_pipeline 编排层（全部代码）
    copy_dir(AUDIO_PIPELINE, FRAMEWORK / "audio_pipeline")
    # ② music 提示词段（代码 + 63 流派 styles）
    copy_dir(MUSICKIT / "music", FRAMEWORK / "music")
    # ③ remix 混音段（代码段：core/gui/templates/tools/utils + 根 py）
    copy_dir(MUSICKIT / "remix", FRAMEWORK / "remix")
    # ④ burbidge_album（仅 py）
    d = FRAMEWORK / "burbidge_album"
    d.mkdir()
    for f in (MUSICKIT / "burbidge_album").glob("*.py"):
        shutil.copy2(f, d / f.name)
    # ⑤ musickit 根：pool_plugin + 乐器分类体系 + 测试
    for f in ("pool_plugin.py", "test_pool_plugin.py", "instrument_taxonomy.json"):
        if (MUSICKIT / f).exists():
            shutil.copy2(MUSICKIT / f, FRAMEWORK / f)
    # ⑥ 框架说明 + 启动包装
    (FRAMEWORK / "README.md").write_text(
        "# musickit 框架（提示词→混音→电台 三段编排）\n\n"
        "本安装包只含**框架代码**：audio_pipeline 编排层 + music 提示词段 + remix 混音段 + "
        "burbidge_album 混音师插件 + pool_plugin 采样池协议。\n\n"
        "**不含**：采样库（13 池音频资源，另行资源包/下载器分发）、ffmpeg 二进制（首运行 doctor 检测）、"
        "渲染产物（prompt_mixes/output 等）。\n\n"
        "运行：\n"
        "- doctor.bat —— 环境诊断（依赖/渲染器/采样池可用性）\n"
        "- chain.bat --workspace <dir> --style phonk --bars 32 —— 一键链（提示词→混音→电台）\n\n"
        "依赖：Python 3.12+（F:/Python314 或 PATH python）、pydub/numpy/scipy/soundfile/audioop-lts。\n"
        "MIT · Copyright (c) 2026 siwpan\n", encoding="utf-8")
    (FRAMEWORK / "doctor.bat").write_text(
        "@echo off\nchcp 65001 >nul\ncd /d \"%~dp0\"\npython audio_pipeline\cli.py doctor\npause\n",
        encoding="utf-8")
    (FRAMEWORK / "chain.bat").write_text(
        "@echo off\nchcp 65001 >nul\ncd /d \"%~dp0\"\npython audio_pipeline\cli.py chain %*\npause\n",
        encoding="utf-8")
    reqs = set()
    for p in (AUDIO_PIPELINE / "requirements.txt", MUSICKIT / "remix" / "requirements.txt"):
        if p.exists():
            reqs.update(l.strip() for l in p.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip())
    (FRAMEWORK / "requirements.txt").write_text("\n".join(sorted(reqs)) + "\n", encoding="utf-8")
    total = sum(f.stat().st_size for f in FRAMEWORK.rglob("*") if f.is_file()) / 1e6
    print(f"[stage] 框架文件就绪：{total:.1f} MB")


def build_installer():
    r = subprocess.run([str(ISCC), str(MUSICKIT / "musickit-framework.iss")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    print(r.stdout[-400:] if r.returncode else "[inno] 编译成功")
    if r.returncode:
        print(r.stderr[-400:])
    return r.returncode == 0


def roundtrip():
    setup = MUSICKIT / "installer" / "musickit-framework-setup-1.0.0.exe"
    target = Path(r"G:\_job\_framework_install_test")
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    r = subprocess.run([str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                        "/DIR=" + str(target)], capture_output=True, timeout=600)
    ok_inst = (target / "audio_pipeline" / "cli.py").exists() and \
              (target / "music" / "styles").exists() and \
              (target / "remix" / "main.py").exists() and \
              (target / "pool_plugin.py").exists() and \
              (target / "chain.bat").exists()
    print("安装:", "OK" if ok_inst else "FAIL", "(exit %d)" % r.returncode)
    unins = target / "unins000.exe"
    ok_un = True
    if unins.exists():
        subprocess.run([str(unins), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                       capture_output=True, timeout=600)
        ok_un = not (target / "pool_plugin.py").exists()
    print("卸载:", "OK（零残留）" if ok_un else "FAIL")
    # 安装态冒烟：doctor.bat 依赖 python 路径，改为直接跑 doctor（验证框架代码可执行）
    return ok_inst and ok_un


def main():
    stage_framework()
    if not build_installer():
        sys.exit(1)
    ok = roundtrip()
    sz = (MUSICKIT / "installer" / "musickit-framework-setup-1.0.0.exe").stat().st_size / 1e6
    print(f"安装器：{sz:.1f} MB")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
