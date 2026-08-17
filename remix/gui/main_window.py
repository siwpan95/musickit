"""
混音器主窗口 — GUI 层。

只负责展示和用户交互，所有业务逻辑委托给 ``core`` 包。
使用 ``threading.Lock`` 保护文件列表的并发访问。

双标签页：
  Tab 1 — 音频混音：多轨音频混合、增益、淡入淡出、削波、归一化、滤波。
  Tab 2 — phonk 混音：随机 phonk 风格混音，支持手动调参
          （音轨数、小节数、BPM、随机种子、曲式模板、输出格式、输出目录）。
"""

from __future__ import annotations

import json
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# 依赖检查
try:
    from pydub import AudioSegment
except ImportError:
    print("错误：请安装 pydub：pip install pydub\n并确保已安装 ffmpeg", file=sys.stderr)
    sys.exit(1)

from core.audio_loader import AudioLoader
from core.audio_mixer import (
    AudioMixer,
    ClippingMode,
    NormalizeMode,
    MixEngine,
    MixConfig,
    TrackConfig,
)
from utils.progress_reporter import ProgressReporter
from utils import generate_output_name


# ======================================================================
# 辅助组件
# ======================================================================


class TrackRow(ttk.Frame):
    """文件列表中的一行：序号 + 文件名 + 音量输入。"""

    def __init__(self, parent, name: str, index: int):
        super().__init__(parent)
        self.index = index
        self.name = name

        ttk.Label(self, text=f"{index + 1}.", width=3, anchor="e").pack(side=tk.LEFT)
        ttk.Label(self, text=name, width=28, anchor="w").pack(side=tk.LEFT, padx=(4, 8))
        ttk.Label(self, text="dB:", width=3).pack(side=tk.LEFT)
        self._gain_var = tk.StringVar(value="0.0")
        self._gain_entry = ttk.Entry(
            self, textvariable=self._gain_var, width=6, justify="center"
        )
        self._gain_entry.pack(side=tk.LEFT, padx=2)

    @property
    def gain_db(self) -> float:
        try:
            return float(self._gain_var.get())
        except ValueError:
            return 0.0


class Tooltip:
    """简易悬停提示。"""

    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event=None):
        if self.tip_window:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height()
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw, text=self.text, justify=tk.LEFT,
            background="#ffffe0", relief=tk.SOLID, borderwidth=1,
            font=("Microsoft YaHei", 9)
        )
        label.pack()

    def _hide(self, _event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class _ReporterStream:
    """把 ``run_remix`` 的 print 输出逐行转发到 ProgressReporter，供 GUI 日志实时显示。"""

    def __init__(self, reporter):
        self._reporter = reporter
        self._buf = ""

    def write(self, s: str) -> None:
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self._reporter.status(line.rstrip())

    def flush(self) -> None:
        if self._buf.strip():
            self._reporter.status(self._buf.rstrip())
        self._buf = ""


# ======================================================================
# 主窗口
# ======================================================================


class MixerApp:
    """混音器主窗口 — 单标签页：音频混音（已移除视频合成）。"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Remix — 音频混音（musickit 专属版）")
        self.root.geometry("700x800")
        self.root.minsize(520, 600)

        # ---- 数据 ----
        self._audio_paths: list[str] = []
        self._audio_lock = threading.Lock()

        # ---- 业务模块 ----
        self._loader = AudioLoader()
        self._reporter = ProgressReporter(root)

        # ---- 运行状态 ----
        self._phonk_running = False

        # ---- 构建界面 ----
        self._create_notebook()
        self._start_polling()

    # ==================================================================
    # Notebook
    # ==================================================================

    def _create_notebook(self) -> None:
        self._notebook = ttk.Notebook(self.root)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # Tab 1: 音频混音
        self._audio_tab = ttk.Frame(self._notebook)
        self._notebook.add(self._audio_tab, text="  音频混音  ")
        self._build_audio_tab()

        # Tab 2: phonk 随机混音（手动调参）
        self._phonk_tab = ttk.Frame(self._notebook)
        self._notebook.add(self._phonk_tab, text="  phonk 混音  ")
        self._build_phonk_tab()

    # ==================================================================
    # Tab 1 — 音频混音
    # ==================================================================

    def _build_audio_tab(self) -> None:
        parent = self._audio_tab
        self._build_audio_file_list(parent)
        self._build_audio_toolbar(parent)
        self._build_audio_effect_panel(parent)
        self._build_audio_progress_bar(parent)
        self._build_audio_bottom_bar(parent)

    def _build_audio_file_list(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="音频轨道列表", padding=8)
        frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6, 0))

        hdr = ttk.Frame(frame)
        hdr.pack(fill=tk.X, padx=2, pady=(0, 4))
        ttk.Label(hdr, text="#", width=3, anchor="e").pack(side=tk.LEFT)
        ttk.Label(hdr, text="文件名", width=28, anchor="w").pack(side=tk.LEFT, padx=(4, 8))
        ttk.Label(hdr, text="音量(dB)", width=9).pack(side=tk.LEFT)

        canvas_frame = ttk.Frame(frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self._audio_canvas = tk.Canvas(canvas_frame, height=160, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self._audio_canvas.yview)
        self._audio_inner = ttk.Frame(self._audio_canvas)

        self._audio_inner.bind(
            "<Configure>",
            lambda e: self._audio_canvas.configure(scrollregion=self._audio_canvas.bbox("all")),
        )
        self._audio_canvas.create_window((0, 0), window=self._audio_inner, anchor="nw")
        self._audio_canvas.configure(yscrollcommand=scrollbar.set)
        self._audio_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            self._audio_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._audio_canvas.bind("<MouseWheel>", _on_mousewheel)

        self._audio_track_rows: list[TrackRow] = []

    def _build_audio_toolbar(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, padx=6, pady=4)

        ttk.Button(frame, text="添加音乐", command=self._audio_add_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(frame, text="移除末尾", command=self._audio_remove_last).pack(side=tk.LEFT, padx=2)
        ttk.Button(frame, text="清空列表", command=self._audio_clear).pack(side=tk.LEFT, padx=2)

    def _build_audio_effect_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="混音参数", padding=8)
        frame.pack(fill=tk.X, padx=6, pady=(4, 0))

        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, pady=2)

        ttk.Label(row1, text="淡入(ms):").pack(side=tk.LEFT)
        self._fade_in_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self._fade_in_var, width=6, justify="center").pack(
            side=tk.LEFT, padx=(2, 8)
        )
        ttk.Label(row1, text="淡出(ms):").pack(side=tk.LEFT)
        self._fade_out_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self._fade_out_var, width=6, justify="center").pack(
            side=tk.LEFT, padx=(2, 8)
        )
        ttk.Label(row1, text="交叉淡化(ms):").pack(side=tk.LEFT)
        self._crossfade_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self._crossfade_var, width=6, justify="center").pack(
            side=tk.LEFT, padx=2
        )

        row2 = ttk.Frame(frame)
        row2.pack(fill=tk.X, pady=4)

        ttk.Label(row2, text="削波:").pack(side=tk.LEFT, padx=(0, 2))
        self._clip_var = tk.StringVar(value="soft")
        ttk.Radiobutton(row2, text="软", variable=self._clip_var, value="soft").pack(side=tk.LEFT)
        ttk.Radiobutton(row2, text="硬", variable=self._clip_var, value="hard").pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(row2, text="归一化:").pack(side=tk.LEFT, padx=(0, 2))
        self._norm_var = tk.StringVar(value="rms")
        ttk.Radiobutton(row2, text="RMS", variable=self._norm_var, value="rms").pack(side=tk.LEFT)
        ttk.Radiobutton(row2, text="峰值", variable=self._norm_var, value="peak").pack(side=tk.LEFT)
        ttk.Radiobutton(row2, text="无", variable=self._norm_var, value="none").pack(side=tk.LEFT, padx=(0, 12))

        self._compress_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row2, text="动态压缩", variable=self._compress_var).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(row2, text="压缩阈值(dB):").pack(side=tk.LEFT)
        self._comp_thr_var = tk.StringVar(value="-20")
        ttk.Entry(row2, textvariable=self._comp_thr_var, width=5, justify="center").pack(side=tk.LEFT, padx=2)

        row3 = ttk.Frame(frame)
        row3.pack(fill=tk.X, pady=2)

        ttk.Label(row3, text="导出格式:").pack(side=tk.LEFT)
        self._audio_fmt_var = tk.StringVar(value="wav")
        fmt_combo = ttk.Combobox(
            row3, textvariable=self._audio_fmt_var,
            values=["wav", "mp3", "ogg", "flac"],
            state="readonly", width=6,
        )
        fmt_combo.pack(side=tk.LEFT, padx=(2, 12))

        ttk.Label(row3, text="高通(Hz):").pack(side=tk.LEFT)
        self._hp_var = tk.StringVar(value="0")
        ttk.Entry(row3, textvariable=self._hp_var, width=6, justify="center").pack(
            side=tk.LEFT, padx=(2, 8)
        )
        ttk.Label(row3, text="低通(Hz):").pack(side=tk.LEFT)
        self._lp_var = tk.StringVar(value="0")
        ttk.Entry(row3, textvariable=self._lp_var, width=6, justify="center").pack(side=tk.LEFT, padx=2)

    def _build_audio_progress_bar(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, padx=6, pady=4)

        self._audio_progress_var = tk.DoubleVar()
        self._audio_progress_bar = ttk.Progressbar(
            frame, orient=tk.HORIZONTAL, mode="determinate", variable=self._audio_progress_var
        )
        self._audio_progress_bar.pack(fill=tk.X, expand=True)

    def _build_audio_bottom_bar(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, padx=6, pady=(2, 6))

        self._audio_start_btn = ttk.Button(frame, text="开始混音", command=self._audio_start_mixing)
        self._audio_start_btn.pack(side=tk.LEFT, padx=5)

        self._audio_status_label = ttk.Label(frame, text="就绪")
        self._audio_status_label.pack(side=tk.LEFT, padx=10)

    # ==================================================================
    # Tab 2 — phonk 随机混音（手动调参）
    # ==================================================================

    def _build_phonk_tab(self) -> None:
        parent = self._phonk_tab

        # ---- 参数区 ----
        params = ttk.LabelFrame(parent, text="phonk 混音参数", padding=8)
        params.pack(fill=tk.X, padx=6, pady=(6, 0))

        row1 = ttk.Frame(params)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="音轨数:").pack(side=tk.LEFT)
        self._pk_count_var = tk.IntVar(value=7)
        ttk.Spinbox(row1, from_=1, to=8, textvariable=self._pk_count_var, width=5).pack(side=tk.LEFT, padx=(2, 12))

        ttk.Label(row1, text="小节数:").pack(side=tk.LEFT)
        self._pk_bars_var = tk.IntVar(value=64)
        ttk.Spinbox(row1, from_=1, to=512, textvariable=self._pk_bars_var, width=5).pack(side=tk.LEFT, padx=(2, 12))

        ttk.Label(row1, text="随机种子:").pack(side=tk.LEFT)
        self._pk_seed_var = tk.StringVar(value="")
        ttk.Entry(row1, textvariable=self._pk_seed_var, width=8, justify="center").pack(side=tk.LEFT, padx=(2, 4))
        ttk.Label(row1, text="(留空=随机)", foreground="#888888").pack(side=tk.LEFT)

        row2 = ttk.Frame(params)
        row2.pack(fill=tk.X, pady=4)
        self._pk_bpm_auto_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row2, text="随机 BPM", variable=self._pk_bpm_auto_var,
                        command=self._phonk_toggle_bpm).pack(side=tk.LEFT)

        ttk.Label(row2, text="BPM:").pack(side=tk.LEFT, padx=(12, 0))
        self._pk_bpm_var = tk.IntVar(value=140)
        self._pk_bpm_spin = ttk.Spinbox(row2, from_=60, to=220, textvariable=self._pk_bpm_var, width=5)
        self._pk_bpm_spin.pack(side=tk.LEFT, padx=(2, 12))

        ttk.Label(row2, text="曲式模板:").pack(side=tk.LEFT)
        self._pk_structure_var = tk.StringVar(value="随机")
        ttk.Combobox(row2, textvariable=self._pk_structure_var,
                     values=["随机"] + self._phonk_structures(),
                     state="readonly", width=15).pack(side=tk.LEFT, padx=(2, 12))

        ttk.Label(row2, text="格式:").pack(side=tk.LEFT)
        self._pk_fmt_var = tk.StringVar(value="wav")
        ttk.Combobox(row2, textvariable=self._pk_fmt_var,
                     values=["wav", "mp3", "ogg", "flac"],
                     state="readonly", width=6).pack(side=tk.LEFT, padx=2)

        row3 = ttk.Frame(params)
        row3.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(row3, text="输出目录:").pack(side=tk.LEFT)
        default_out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
        self._pk_out_var = tk.StringVar(value=default_out)
        ttk.Entry(row3, textvariable=self._pk_out_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 4))
        ttk.Button(row3, text="浏览...", command=self._phonk_browse_out).pack(side=tk.LEFT)

        # ---- 音轨选择区 ----
        self._phonk_load_sources()
        tracks_lf = ttk.LabelFrame(parent, text="音轨选择", padding=6)
        tracks_lf.pack(fill=tk.X, padx=6, pady=(6, 0))

        self._pk_track_mode = tk.StringVar(value="random")
        mode_row = ttk.Frame(tracks_lf)
        mode_row.pack(fill=tk.X)
        ttk.Radiobutton(mode_row, text="随机选轨（按上方音轨数）",
                        variable=self._pk_track_mode, value="random",
                        command=self._phonk_on_track_mode_changed).pack(side=tk.LEFT)
        ttk.Radiobutton(mode_row, text="手动选轨",
                        variable=self._pk_track_mode, value="manual",
                        command=self._phonk_on_track_mode_changed).pack(side=tk.LEFT, padx=(12, 0))

        # 手动选轨容器（默认隐藏）
        self._pk_manual_box = ttk.Frame(tracks_lf)
        self._pk_rows_frame = ttk.Frame(self._pk_manual_box)
        self._pk_rows_frame.pack(fill=tk.X)
        ttk.Button(self._pk_manual_box, text="＋ 添加音轨",
                   command=self._phonk_add_track_row).pack(anchor=tk.W, pady=(4, 0))
        self._pk_track_rows: list[dict] = []

        # ---- 日志区 ----
        log = ttk.LabelFrame(parent, text="运行日志", padding=6)
        log.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6, 0))
        self._pk_log = tk.Text(log, height=8, wrap="word", state=tk.DISABLED,
                               background="#1e1e1e", foreground="#d4d4d4",
                               font=("Consolas", 9))
        scroll = ttk.Scrollbar(log, orient=tk.VERTICAL, command=self._pk_log.yview)
        self._pk_log.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._pk_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ---- 进度条 ----
        prog = ttk.Frame(parent)
        prog.pack(fill=tk.X, padx=6, pady=4)
        self._pk_progress = ttk.Progressbar(prog, orient=tk.HORIZONTAL, mode="indeterminate")
        self._pk_progress.pack(fill=tk.X, expand=True)

        # ---- 底部 ----
        bottom = ttk.Frame(parent)
        bottom.pack(fill=tk.X, padx=6, pady=(2, 6))
        self._pk_start_btn = ttk.Button(bottom, text="开始生成", command=self._phonk_start)
        self._pk_start_btn.pack(side=tk.LEFT, padx=5)
        self._pk_status_label = ttk.Label(bottom, text="就绪")
        self._pk_status_label.pack(side=tk.LEFT, padx=10)

    def _phonk_structures(self) -> list[str]:
        """读取 templates/structures.json 中的曲式模板名。"""
        tp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "templates", "structures.json")
        try:
            with open(tp, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [k for k in data.keys() if not k.startswith("_")]
        except Exception:
            return ["classic_drop", "ambient_ghost", "loop_stack"]

    def _phonk_toggle_bpm(self) -> None:
        state = tk.DISABLED if self._pk_bpm_auto_var.get() else tk.NORMAL
        self._pk_bpm_spin.configure(state=state)

    # ---- 音轨选择 ----

    def _phonk_main_module(self):
        """返回 main 模块对象（GUI 由 main.py 启动时为 __main__，否则 import main）。"""
        m = sys.modules.get("__main__")
        if m is not None and hasattr(m, "run_remix"):
            return m
        import main as mod  # noqa: F401
        return mod

    def _phonk_load_sources(self) -> None:
        """加载各素材目录下的音频文件列表（basename 供下拉框显示）。"""
        m = self._phonk_main_module()
        root = getattr(m, "_MUSICKIT_ROOT", None)
        cats = getattr(m, "_SOURCE_CATEGORIES",
                       ["bass", "drum", "guita", "cowbell", "synth", "animal", "sfx"])
        collect = getattr(m, "_collect_category_files", None)
        self._phonk_cats = list(cats)
        self._phonk_cat_files: dict[str, list[str]] = {}
        for cat in self._phonk_cats:
            if root and collect:
                self._phonk_cat_files[cat] = collect(os.path.join(root, cat))
            else:
                self._phonk_cat_files[cat] = []

    def _phonk_on_track_mode_changed(self) -> None:
        if self._pk_track_mode.get() == "manual":
            self._pk_manual_box.pack(fill=tk.X, pady=(4, 0))
        else:
            self._pk_manual_box.pack_forget()

    def _phonk_add_track_row(self, cat: str | None = None, fname: str | None = None) -> None:
        if len(self._pk_track_rows) >= 8:
            messagebox.showinfo("提示", "最多支持 8 条音轨。")
            return
        row = ttk.Frame(self._pk_rows_frame)
        row.pack(fill=tk.X, pady=1)

        cat_var = tk.StringVar(value=cat or "drum")
        cat_combo = ttk.Combobox(row, textvariable=cat_var, values=self._phonk_cats,
                                 state="readonly", width=8)
        cat_combo.pack(side=tk.LEFT)

        file_var = tk.StringVar(value=fname or "")
        file_combo = ttk.Combobox(row, textvariable=file_var, values=[],
                                  state="readonly", width=42)
        file_combo.pack(side=tk.LEFT, padx=(4, 0))

        ttk.Button(row, text="×", width=3,
                   command=lambda r=row: self._phonk_remove_track_row(r)).pack(side=tk.LEFT, padx=(4, 0))

        info = {"cat_var": cat_var, "file_var": file_var,
                "cat_combo": cat_combo, "file_combo": file_combo, "frame": row}
        self._pk_track_rows.append(info)
        cat_combo.bind("<<ComboboxSelected>>", lambda _e, i=info: self._phonk_on_row_cat_changed(i))
        self._phonk_on_row_cat_changed(info)

    def _phonk_on_row_cat_changed(self, info: dict) -> None:
        cat = info["cat_var"].get()
        names = [os.path.basename(p) for p in self._phonk_cat_files.get(cat, [])]
        info["file_combo"]["values"] = names
        if info["file_var"].get() not in names:
            info["file_var"].set(names[0] if names else "")

    def _phonk_remove_track_row(self, frame: ttk.Frame) -> None:
        for i, info in enumerate(self._pk_track_rows):
            if info["frame"] is frame:
                self._pk_track_rows.pop(i)
                frame.destroy()
                break

    def _phonk_collect_tracks(self) -> list[tuple[str, str]]:
        """收集手动选轨结果 [(category, full_path), ...]。"""
        tracks: list[tuple[str, str]] = []
        for info in self._pk_track_rows:
            cat = info["cat_var"].get()
            fname = info["file_var"].get()
            if not cat or not fname:
                continue
            for p in self._phonk_cat_files.get(cat, []):
                if os.path.basename(p) == fname:
                    tracks.append((cat, p))
                    break
        return tracks

    def _phonk_browse_out(self) -> None:
        d = filedialog.askdirectory(title="选择输出目录", initialdir=self._pk_out_var.get())
        if d:
            self._pk_out_var.set(d)

    def _phonk_log(self, text: str) -> None:
        self._pk_log.configure(state=tk.NORMAL)
        self._pk_log.insert(tk.END, text + "\n")
        self._pk_log.see(tk.END)
        self._pk_log.configure(state=tk.DISABLED)

    def _phonk_start(self) -> None:
        if self._phonk_running:
            return
        if self._pk_track_mode.get() == "manual" and not self._phonk_collect_tracks():
            messagebox.showwarning("提示", "手动选轨模式下请至少添加一条音轨。")
            return
        self._phonk_running = True
        self._pk_start_btn.configure(state=tk.DISABLED)
        self._pk_status_label.config(text="正在混音...")
        self._pk_progress.start(12)
        self._phonk_log("==== 开始 phonk 混音 ====")

        params = self._phonk_build_params()
        threading.Thread(target=self._phonk_mix_work, args=(params,), daemon=True).start()

    def _phonk_build_params(self) -> dict:
        seed_text = self._pk_seed_var.get().strip()
        seed = int(seed_text) if seed_text.lstrip("-").isdigit() and seed_text else None
        structure = self._pk_structure_var.get()
        params = {
            "count": max(1, min(self._pk_count_var.get(), 8)),
            "seed": seed,
            "bars": max(1, self._pk_bars_var.get()),
            "bpm": None if self._pk_bpm_auto_var.get() else max(1, self._pk_bpm_var.get()),
            "structure": None if structure == "随机" else structure,
            "fmt": self._pk_fmt_var.get(),
            "out_dir": self._pk_out_var.get().strip() or None,
        }
        if self._pk_track_mode.get() == "manual":
            params["tracks"] = self._phonk_collect_tracks()
        return params

    def _phonk_mix_work(self, params: dict) -> None:
        import contextlib

        run_remix = self._phonk_main_module().run_remix

        stream = _ReporterStream(self._reporter)
        try:
            with contextlib.redirect_stdout(stream):
                output_path = run_remix(**params)
            stream.flush()
            self._reporter.done(output_path)
        except Exception as e:
            stream.flush()
            self._reporter.error(str(e))

    # ==================================================================
    # Tab 1 — 音频混音：文件操作
    # ==================================================================

    def _audio_add_files(self) -> None:
        files = filedialog.askopenfilenames(
            title="选择音频文件",
            filetypes=[
                ("音频文件", "*.mp3 *.wav *.ogg *.flac *.m4a"),
                ("所有文件", "*.*"),
            ],
        )
        if not files:
            return
        with self._audio_lock:
            for f in files:
                if f not in self._audio_paths:
                    idx = len(self._audio_paths)
                    self._audio_paths.append(f)
                    row = TrackRow(self._audio_inner, os.path.basename(f), idx)
                    row.pack(fill=tk.X, pady=1)
                    self._audio_track_rows.append(row)

    def _audio_remove_last(self) -> None:
        with self._audio_lock:
            if not self._audio_paths:
                return
            self._audio_paths.pop()
            row = self._audio_track_rows.pop()
            row.destroy()

    def _audio_clear(self) -> None:
        with self._audio_lock:
            self._audio_paths.clear()
            for row in self._audio_track_rows:
                row.destroy()
            self._audio_track_rows.clear()

    def _audio_get_paths(self) -> list[str]:
        with self._audio_lock:
            return list(self._audio_paths)

    # ==================================================================
    # Tab 1 — 音频混音：流程
    # ==================================================================

    def _audio_build_config(self) -> MixConfig:
        clip = ClippingMode.SOFT if self._clip_var.get() == "soft" else ClippingMode.HARD
        norm_map = {"peak": NormalizeMode.PEAK, "rms": NormalizeMode.RMS, "none": NormalizeMode.NONE}
        norm = norm_map.get(self._norm_var.get(), NormalizeMode.RMS)

        def _to_int(var, default=0):
            try: return int(var.get())
            except ValueError: return default

        def _to_float(var, default=0.0):
            try: return float(var.get())
            except ValueError: return default

        tracks = [TrackConfig(gain_db=row.gain_db) for row in self._audio_track_rows]

        return MixConfig(
            clip_mode=clip,
            normalize_mode=norm,
            engine=MixEngine.MANUAL,
            fade_in_ms=_to_int(self._fade_in_var),
            fade_out_ms=_to_int(self._fade_out_var),
            crossfade_ms=_to_int(self._crossfade_var),
            compress=self._compress_var.get(),
            compress_threshold=_to_float(self._comp_thr_var, -20.0),
            compress_ratio=4.0,
            low_pass_cutoff=_to_int(self._lp_var),
            high_pass_cutoff=_to_int(self._hp_var),
            tracks=tracks,
        )

    def _audio_start_mixing(self) -> None:
        paths = self._audio_get_paths()
        if len(paths) < 2:
            messagebox.showwarning("文件不足", "请至少添加两个音频文件")
            return
        self._audio_start_btn.configure(state=tk.DISABLED)
        self._audio_status_label.config(text="正在混音...")
        self._audio_progress_var.set(0)

        config = self._audio_build_config()
        thread = threading.Thread(
            target=self._audio_mix_work, args=(paths, config), daemon=True
        )
        thread.start()

    def _audio_mix_work(self, paths: list[str], config: MixConfig) -> None:
        try:
            segments = self._loader.load_batch(
                paths,
                on_progress=lambda msg: self._reporter.status(msg),
            )
            if not segments:
                raise RuntimeError("没有成功加载任何音频文件")

            segments = AudioLoader.unify(segments)

            if config.engine is MixEngine.OVERLAY:
                mixed = AudioMixer.mix_with_pydub(
                    segments, config=config,
                    progress_callback=lambda c, t: self._reporter.progress(int(c / t * 100)),
                )
            else:
                sample_arrays = AudioLoader.extract_samples(segments)
                seg0 = segments[0]
                mixed = AudioMixer.mix_to_segment(
                    sample_arrays,
                    sample_width=seg0.sample_width,
                    frame_rate=seg0.frame_rate,
                    channels=seg0.channels,
                    config=config,
                    progress_callback=lambda c, t: self._reporter.progress(int(c / t * 100)),
                )

            # 注：淡入淡出 / 压缩 / 滤波等后处理已在 core 层
            # （mix_to_segment / mix_with_pydub）统一完成，此处无需重复。

            fmt = self._audio_fmt_var.get()
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            output_dir = os.path.join(base_dir, "output")
            os.makedirs(output_dir, exist_ok=True)
            ext = fmt if fmt else "wav"
            output_path = os.path.join(output_dir, generate_output_name("mixed_output", "", ext))

            AudioLoader.export(mixed, output_path, fmt=fmt)
            self._reporter.done(output_path)

        except Exception as e:
            self._reporter.error(str(e))

    # ==================================================================
    # 进度轮询
    # ==================================================================

    def _start_polling(self) -> None:
        self._reporter.start_polling(
            on_status=self._on_reporter_status,
            on_progress=self._on_reporter_progress,
            on_done=self._on_reporter_done,
            on_error=self._on_reporter_error,
        )

    def _on_reporter_status(self, text: str) -> None:
        if self._phonk_running:
            self._phonk_log(text)
        else:
            self._audio_status_label.config(text=text)

    def _on_reporter_progress(self, pct: int) -> None:
        if not self._phonk_running:
            self._audio_progress_var.set(pct)

    def _on_reporter_done(self, output_path: str) -> None:
        if self._phonk_running:
            self._phonk_running = False
            self._pk_progress.stop()
            self._phonk_log(f"完成：{output_path}")
            self._pk_status_label.config(text="生成完成！")
            self._pk_start_btn.configure(state=tk.NORMAL)
            messagebox.showinfo("完成", f"phonk 混音已保存至：\n{output_path}")
        else:
            self._audio_status_label.config(text="混音完成！")
            self._audio_start_btn.configure(state=tk.NORMAL)
            messagebox.showinfo("完成", f"音频已保存至：\n{output_path}")

    def _on_reporter_error(self, msg: str) -> None:
        if self._phonk_running:
            self._phonk_running = False
            self._pk_progress.stop()
            self._phonk_log(f"错误：{msg}")
            self._pk_status_label.config(text="生成出错")
            self._pk_start_btn.configure(state=tk.NORMAL)
            messagebox.showerror("错误", f"phonk 混音出错：\n{msg}")
        else:
            self._audio_status_label.config(text="混音出错")
            self._audio_start_btn.configure(state=tk.NORMAL)
            messagebox.showerror("错误", f"混音过程出错：\n{msg}")
