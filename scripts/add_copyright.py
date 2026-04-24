#!/usr/bin/env python3
"""
批量添加版权头脚本

给缺少版权头的 .py 和 .rs 文件自动添加 AGPL-3.0 版权声明。
已有版权头的文件会被跳过。
"""

import os
import sys
from pathlib import Path

PY_HEADER = """# ========================================================================
# Copyright (C) 2026 Nexa-Language
# This file is part of Nexa Project.
# 
# Nexa is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# Nexa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with Nexa.  If not, see <https://www.gnu.org/licenses/>.
# ========================================================================
"""

RS_HEADER = """/*
# ========================================================================
Copyright (C) 2026 Nexa-Language
This file is part of Nexa Project.

Nexa is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

Nexa is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with Nexa.  If not, see <https://www.gnu.org/licenses/>.
========================================================================
*/
"""

# 版权头标识关键词，用于检测文件是否已有版权头
COPYRIGHT_MARKER = "Copyright (C) 2026 Nexa-Language"


def has_copyright(content: str) -> bool:
    """检查文件是否已包含版权头"""
    return COPYRIGHT_MARKER in content


def add_header(filepath: Path, header: str) -> bool:
    """给文件添加版权头，如果已有则跳过"""
    content = filepath.read_text(encoding='utf-8')
    
    if has_copyright(content):
        print(f"  SKIP (已有版权头): {filepath}")
        return False
    
    # 插入版权头到文件开头
    new_content = header + "\n" + content
    filepath.write_text(new_content, encoding='utf-8')
    print(f"  DONE: {filepath}")
    return True


def main():
    project_root = Path(__file__).resolve().parent.parent
    
    # 需要处理的目录
    src_dir = project_root / "src"
    avm_dir = project_root / "avm" / "src"
    
    added = 0
    skipped = 0
    
    # 处理 Python 文件
    print("=== 处理 Python 文件 ===")
    for py_file in src_dir.rglob("*.py"):
        if add_header(py_file, PY_HEADER):
            added += 1
        else:
            skipped += 1
    
    # 处理 Rust 文件
    print("\n=== 处理 Rust 文件 ===")
    for rs_file in avm_dir.rglob("*.rs"):
        if add_header(rs_file, RS_HEADER):
            added += 1
        else:
            skipped += 1
    
    # 处理 avm/build.rs
    build_rs = project_root / "avm" / "build.rs"
    if build_rs.exists():
        if add_header(build_rs, RS_HEADER):
            added += 1
        else:
            skipped += 1
    
    # 处理 avm/benches/
    benches_dir = project_root / "avm" / "benches"
    if benches_dir.exists():
        for rs_file in benches_dir.rglob("*.rs"):
            if add_header(rs_file, RS_HEADER):
                added += 1
            else:
                skipped += 1
    
    print(f"\n=== 统计 ===")
    print(f"  添加版权头: {added} 个文件")
    print(f"  跳过(已有): {skipped} 个文件")
    print(f"  总计扫描:   {added + skipped} 个文件")


if __name__ == "__main__":
    main()