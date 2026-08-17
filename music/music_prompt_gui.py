#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
纯音乐风格提示词生成器 · 简易图形界面（tkinter）。

直接复用 music_prompt_generator.py 的核心函数（generate / 导出 / 风格池），
无需重复逻辑。运行方式：
    python music_prompt_gui.py
依赖：仅标准库 tkinter（Python 自带）。
"""
import contextlib
import io
import os
import random
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import music_prompt_generator as mpg
import validate_styles as vsty

BASE_DIR = mpg.BASE_DIR

# 项目字体：优设标题黑（标题黑体，中文简体、字形现代，文件位于项目根目录）；
# 缺失或加载失败时回退系统已安装的中文字体，不影响使用。
PROJ_FONT_PATH = os.path.join(BASE_DIR, "优设标题黑.ttf")


def load_project_font():
    """把项目字体文件加载为本进程可用字体，返回其真实字体族名。

    实现说明：tkinter.font.Font 不支持 file 参数（旧实现因此从未生效过，
    一直静默回退系统字体），这里改用 Windows GDI 的 AddFontResourceExW 以
    FR_PRIVATE 私有模式加载——仅本进程可见、进程退出即卸载，不污染系统
    字体表；加载后对比 tkinter 字体族列表差集获取真实族名（跳过 @ 开头
    的竖排变体）。非 Windows 平台或任何失败返回 None，由调用方回退系统字体。
    """
    if not os.path.isfile(PROJ_FONT_PATH):
        return None
    try:
        import ctypes
        from tkinter import font as tkfont
        before = set(tkfont.families())
        FR_PRIVATE = 0x10
        if ctypes.windll.gdi32.AddFontResourceExW(PROJ_FONT_PATH, FR_PRIVATE, 0) == 0:
            return None
        added = sorted(f for f in set(tkfont.families()) - before
                       if not f.startswith("@"))
        return added[0] if added else None
    except Exception:
        return None


def _first_available_system_font(*names):
    """在系统已安装字体中返回第一个可用的字体族名，都不存在则返回 None。"""
    try:
        from tkinter import font as tkfont
        families = set(tkfont.families())
        for nm in names:
            if nm in families:
                return nm
    except Exception:
        pass
    return None


def safe_random_seed(seed_var):
    """从输入框解析种子；空值则不固定（用系统熵）。"""
    raw = seed_var.get().strip()
    if raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("纯音乐风格提示词生成器")
        self.geometry("820x640")
        try:
            self.tk.call("tk", "scaling", 1.3)
        except Exception:
            pass

        self.style_keys = ["(随机)"] + list(mpg.STYLE_BY_KEY.keys())
        self.results = []  # 当前生成结果，供导出复用

        # 加载项目字体（优设标题黑，中文简体），缺失则回退系统字体
        # 回退链：项目优设标题黑 → 系统 SimHei → 系统 Microsoft YaHei → 系统默认
        self.font_family = (
            load_project_font()
            or _first_available_system_font("SimHei", "Microsoft YaHei")
            or "TkDefaultFont"
        )
        try:
            self.option_add("*Font", f"{self.font_family} 11")
        except Exception:
            pass

        self._build_widgets()
        self._refresh_status(f"已加载 {len(mpg.STYLES)} 个风格，"
                             f"{len(mpg.STYLE_BY_KEY)} 个唯一 key。")

    # ---------- 界面布局 ----------
    def _build_widgets(self):
        pad = {"padx": 8, "pady": 4}

        # 顶部：参数区
        frm_top = ttk.LabelFrame(self, text="生成参数", padding=8)
        frm_top.pack(fill="x", padx=8, pady=6)

        # 风格
        ttk.Label(frm_top, text="风格：").grid(row=0, column=0, sticky="e", **pad)
        self.style_var = tk.StringVar(value=self.style_keys[0])
        ttk.Combobox(frm_top, textvariable=self.style_var,
                     values=self.style_keys, width=22, state="readonly") \
            .grid(row=0, column=1, sticky="w", **pad)

        # 条数
        ttk.Label(frm_top, text="条数：").grid(row=0, column=2, sticky="e", **pad)
        self.num_var = tk.IntVar(value=5)
        ttk.Spinbox(frm_top, from_=1, to=200, textvariable=self.num_var,
                    width=8).grid(row=0, column=3, sticky="w", **pad)

        # 种子
        ttk.Label(frm_top, text="种子：").grid(row=0, column=4, sticky="e", **pad)
        self.seed_var = tk.StringVar(value="")
        ttk.Entry(frm_top, textvariable=self.seed_var, width=10) \
            .grid(row=0, column=5, sticky="w", **pad)

        # 复选框行
        frm_chk = ttk.Frame(frm_top)
        frm_chk.grid(row=1, column=0, columnspan=6, sticky="w", **pad)
        self.fusion_var = tk.BooleanVar(value=False)
        self.english_var = tk.BooleanVar(value=True)
        self.dedup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frm_chk, text="跨类融合", variable=self.fusion_var) \
            .pack(side="left", padx=6)
        ttk.Checkbutton(frm_chk, text="附带英文", variable=self.english_var) \
            .pack(side="left", padx=6)
        ttk.Checkbutton(frm_chk, text="批量去重", variable=self.dedup_var) \
            .pack(side="left", padx=6)

        # 按钮行
        frm_btn = ttk.Frame(self)
        frm_btn.pack(fill="x", padx=8, pady=2)
        ttk.Button(frm_btn, text="▶ 生成", command=self.on_generate) \
            .pack(side="left", padx=4)
        ttk.Button(frm_btn, text="导出 TXT", command=lambda: self.on_export("txt")) \
            .pack(side="left", padx=4)
        ttk.Button(frm_btn, text="导出 JSON", command=lambda: self.on_export("json")) \
            .pack(side="left", padx=4)
        ttk.Button(frm_btn, text="导出 CSV", command=lambda: self.on_export("csv")) \
            .pack(side="left", padx=4)
        ttk.Button(frm_btn, text="风格池自检", command=self.on_validate) \
            .pack(side="left", padx=4)
        ttk.Button(frm_btn, text="清空", command=self.on_clear) \
            .pack(side="left", padx=4)

        # 结果区
        frm_out = ttk.LabelFrame(self, text="生成结果", padding=6)
        frm_out.pack(fill="both", expand=True, padx=8, pady=4)
        self.txt = scrolledtext.ScrolledText(
            frm_out, wrap="word", font=("Consolas", 11), state="disabled")
        self.txt.pack(fill="both", expand=True)

        # 状态栏
        self.status = tk.StringVar(value="就绪")
        ttk.Label(self, textvariable=self.status, relief="sunken",
                  anchor="w", padding=4).pack(fill="x", side="bottom")

    # ---------- 业务逻辑 ----------
    def _refresh_status(self, msg):
        self.status.set(msg)

    def _append(self, text):
        self.txt.configure(state="normal")
        self.txt.insert("end", text + "\n")
        self.txt.configure(state="disabled")
        self.txt.see("end")

    def _gen_one(self, profile, fusion_with, english):
        return mpg.generate(profile, fusion_with=fusion_with, english=english)

    def on_generate(self):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.configure(state="disabled")

        n = max(1, int(self.num_var.get()))
        key = self.style_var.get()
        profile = mpg.STYLE_BY_KEY.get(key) if key != "(随机)" else None
        english = self.english_var.get()
        seed = safe_random_seed(self.seed_var)
        dedup = self.dedup_var.get()

        # 统一调用 generator 的 batch_generate（去重/融合/可复现逻辑与 CLI 一致，
        # 不再在 GUI 内重复实现生成循环，避免去重语义漂移）
        self.results = mpg.batch_generate(
            n, profile,
            dedup=dedup,
            fusion=self.fusion_var.get(),
            english=english,
            seed=seed,
        )

        # 渲染
        for i, d in enumerate(self.results):
            head = f"【#{i + 1}】" + (f"  融合:{d['fusion_with']}" if d["fusion"] else "")
            block = mpg.render(d, english) if hasattr(mpg, "render") else d["sentence"]
            self._append("=" * 56)
            self._append(head)
            self._append(block)
        self._append("=" * 56)
        self._refresh_status(f"已生成 {len(self.results)} 条"
                             + (f"（种子 {seed}）" if seed is not None else ""))

    def on_export(self, fmt):
        if not self.results:
            messagebox.showwarning("提示", "请先点击「生成」再导出。")
            return
        # 默认文件名带时间戳（与 CLI 共用 _default_export_path，单一来源），避免同名覆盖旧导出
        ext = fmt
        initial = os.path.basename(mpg._default_export_path(ext))
        path = filedialog.asksaveasfilename(
            title=f"导出为 {fmt.upper()}",
            initialdir=BASE_DIR,
            initialfile=initial,
            defaultextension=f".{ext}",
            filetypes=[(f"{fmt.upper()} 文件", f"*.{ext}"), ("所有文件", "*.*")])
        if not path:
            return
        path = os.path.abspath(path)
        if fmt == "json":
            mpg.export_json(self.results, path)
        elif fmt == "csv":
            mpg.export_csv(self.results, path)
        else:
            mpg.export_txt(self.results, path)
        self._refresh_status(f"已导出 {len(self.results)} 条 → {path}")
        messagebox.showinfo("导出成功", f"文件已保存：\n{path}")

    def on_validate(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = vsty.validate(mpg.STYLES_DIR)
        out = buf.getvalue().strip()
        self._refresh_status("风格池自检完成" + ("（有错误）" if rc else "（通过）"))
        messagebox.showinfo("风格池自检结果", out if out else "校验通过")

    def on_clear(self):
        self.results = []
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.configure(state="disabled")
        self._refresh_status("已清空")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    App().mainloop()
