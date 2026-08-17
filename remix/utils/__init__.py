import os
import datetime

from .progress_reporter import ProgressReporter


def generate_output_name(base_name: str, suffix: str, ext: str) -> str:
    """生成带时间戳的输出文件名，避免新旧内容覆盖。
    
    Args:
        base_name: 基础名称（如 "mixed_output"、"video_name_audio"）
        suffix: 额外后缀（如 "_extracted"、"_mixed"、""，会被放在时间戳前面）
        ext:   文件扩展名（如 "wav"、"mp4"，不带点）
    
    Returns:
        完整文件名，格式为 "{base_name}{suffix}_{YYYYMMDD_HHMMSS}.{ext}"
        例如: "mixed_output_20260804_154530.wav"
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}{suffix}_{timestamp}.{ext}"


def make_unique_path(output_dir: str, base_name: str, suffix: str = "", ext: str = "wav") -> str:
    """生成带时间戳且不与现有文件冲突的完整输出路径。

    同秒冲突自动追加 _1/_2 递增，杜绝两次快速运行互相覆盖
    （generate_output_name 仅到秒级，不检查存在性）。

    Args:
        output_dir: 输出目录路径（不存在会自动创建）
        base_name: 基础名称（如 "mixed_output"、"phonk_remix"）
        suffix:   额外后缀（如 "_mixed"，会被放在时间戳前面）
        ext:      文件扩展名（不带点）

    Returns:
        不与现有文件冲突的完整输出路径
    """
    os.makedirs(output_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"{base_name}{suffix}_{stamp}"
    i = 0
    while True:
        name = f"{stem}.{ext}" if i == 0 else f"{stem}_{i}.{ext}"
        path = os.path.join(output_dir, name)
        if not os.path.exists(path):
            return path
        i += 1


def resolve_output_path(output_dir: str, base_name: str, suffix: str = "", ext: str = "wav") -> str:
    """生成带时间戳的完整输出路径（同秒冲突自动递增，确保不覆盖旧产物）。"""
    return make_unique_path(output_dir, base_name, suffix, ext)


__all__ = ["ProgressReporter", "generate_output_name", "make_unique_path", "resolve_output_path"]
