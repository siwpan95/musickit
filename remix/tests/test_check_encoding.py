# -*- coding: utf-8 -*-
"""check_encoding 门禁的判别力测试。

为什么要有这组用例：这个门禁会进 CI，一旦它「对正常代码报错」，没人愿意维护，
久了就会被绕过。所以门禁本身必须被测 —— 而且要测的是**判别力**：
- 该报的必须报（文本模式缺 encoding）
- 不该报的一个都不能报（二进制模式、已有 encoding、判不出来的情况）

用例数会随本文件变化，注意 README / music/README / ONBOARDING 里的数字要同步
（用 `python scripts/check_doc_counts.py --fix`）。
"""
import importlib.util
import os
import sys

import pytest

pytestmark = pytest.mark.smoke

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SCRIPT = os.path.join(ROOT, "scripts", "check_encoding.py")


def _load_checker():
    """按路径加载 scripts/check_encoding.py（scripts/ 不是包，不能直接 import）。"""
    spec = importlib.util.spec_from_file_location("check_encoding_mod", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def checker():
    if not os.path.isfile(_SCRIPT):
        pytest.skip(f"门禁脚本不存在：{_SCRIPT}")
    return _load_checker()


def _hits(checker, src):
    return checker.scan_source(src, filename="<t>")


# ---- 该报的：文本模式缺 encoding ----

def test_flags_text_mode_write(checker):
    hits = _hits(checker, 'open("x", "w")\n')
    assert len(hits) == 1, hits
    assert hits[0][0] == 1


def test_flags_text_mode_read(checker):
    assert len(_hits(checker, 'open("x", "r")\n')) == 1


def test_flags_default_mode(checker):
    """不给 mode 时默认是 'r'（文本），同样要查。"""
    assert len(_hits(checker, 'open("x")\n')) == 1


def test_flags_append_mode(checker):
    assert len(_hits(checker, 'open("x", "a")\n')) == 1


def test_flags_update_mode(checker):
    """'r+' 是文本模式（+ 不带 b）。"""
    assert len(_hits(checker, 'open("x", "r+")\n')) == 1


def test_flags_keyword_mode(checker):
    assert len(_hits(checker, 'open("x", mode="w")\n')) == 1


def test_flags_write_text(checker):
    assert len(_hits(checker, 'Path("x").write_text("hi")\n')) == 1


def test_flags_path_open(checker):
    """Path.open 的 mode 是第一个位置参数。"""
    assert len(_hits(checker, 'Path("x").open("w")\n')) == 1


def test_flags_inside_with(checker):
    src = 'with open("x", "w") as f:\n    f.write("hi")\n'
    assert len(_hits(checker, src)) == 1


def test_flags_json_dump_target(checker):
    """json.dump(x, open(p, "w")) —— 写成内联实参，同样要查。"""
    src = 'json.dump(d, open("m.json", "w"), ensure_ascii=False)\n'
    assert len(_hits(checker, src)) == 1


# ---- 不该报的：二进制 / 已有 encoding / 判不出来 ----

@pytest.mark.parametrize("mode", ["rb", "wb", "ab", "rb+", "r+b", "wb+", "ab+"])
def test_ignores_binary_modes(checker, mode):
    assert _hits(checker, f'open("x", "{mode}")\n') == []


def test_ignores_when_encoding_present(checker):
    assert _hits(checker, 'open("x", "w", encoding="utf-8")\n') == []


def test_ignores_read_with_encoding(checker):
    assert _hits(checker, 'open("x", "r", encoding="utf-8")\n') == []


def test_ignores_write_text_with_encoding(checker):
    assert _hits(checker, 'Path("x").write_text("hi", encoding="utf-8")\n') == []


def test_ignores_non_literal_mode(checker):
    """mode 是变量时判不出来 —— 宁可漏报也不误报。"""
    assert _hits(checker, 'open("x", mode)\n') == []


def test_ignores_unrelated_open_methods(checker):
    """ZipFile.open / wave.open 等不是文件 open，别误伤。"""
    assert _hits(checker, 'zf.open(name)\n') == []
    assert _hits(checker, 'wave.open(path, "rb")\n') == []
    assert _hits(checker, 'urllib.request.urlopen(req)\n') == []


def test_ignores_syntax_error(checker):
    """语法错误交给别的工具报，本门禁不重复报、也不崩。"""
    assert _hits(checker, 'def broken(:\n') == []


# ---- 真实仓库必须干净 ----

def test_repo_is_clean(checker):
    """remix/ 与 music/ 下的文本模式 open() 全部已显式指定 encoding。"""
    bad = []
    for top in ("remix", "music"):
        for path in checker.iter_py_files(ROOT, top):
            for lineno, why in checker.scan_file(path):
                rel = os.path.relpath(path, ROOT).replace("\\", "/")
                bad.append(f"{rel}:{lineno}: {why}")
    assert not bad, "以下文件缺 encoding=：\n" + "\n".join(bad)


def test_scanner_finds_expected_file_count(checker):
    """防止 iter_py_files 悄悄扫不到文件（比如路径分隔符写错 → 扫到 0 个也『通过』）。"""
    files = checker.iter_py_files(ROOT, "remix") + checker.iter_py_files(ROOT, "music")
    assert len(files) > 50, f"只扫到 {len(files)} 个 .py，扫描路径可能坏了"
