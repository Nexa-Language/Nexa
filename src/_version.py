# ========================================================================
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
Nexa 版本信息 — 单一版本源读取模块

版本号定义在项目根目录的 VERSION 文件中，
此模块负责读取并提供给其他模块使用。

更新版本时只需修改根目录 VERSION 文件，无需改动任何代码文件。
"""
import os
from pathlib import Path


def _read_version() -> str:
    """从项目根目录 VERSION 文件读取版本号
    
    Returns:
        纯数字版本号字符串，如 "1.3.7"
    """
    # 尝试从项目根目录的 VERSION 文件读取
    version_file = Path(__file__).resolve().parent.parent / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    # Fallback: 如果 VERSION 文件不存在（如 pip install 后）
    return "1.3.7"


# 纯数字版本号，用于 Python packaging (不带 v 前缀)
_raw_version = _read_version()

# 带 v 前缀的版本号，用于显示和 CLI
__version__ = f"v{_raw_version}"
__author__ = "Nexa Genesis Team"

# 兼容 cli.py 的命名
NEXA_VERSION = __version__