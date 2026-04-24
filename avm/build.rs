/*
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
//! Build script — 从项目根目录 VERSION 文件读取版本号，
//! 设置 NEXA_VERSION 环境变量供 Rust 代码使用。
//!
//! 更新版本时只需修改根目录 VERSION 文件，无需改动任何 Rust 代码。

use std::fs;
use std::path::Path;

fn main() {
    // 从项目根目录 VERSION 文件读取版本号
    let version_file = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join("VERSION");

    let version = if version_file.exists() {
        fs::read_to_string(&version_file)
            .unwrap()
            .trim()
            .to_string()
    } else {
        // Fallback: 使用 Cargo.toml 中的版本
        env!("CARGO_PKG_VERSION").to_string()
    };

    // 设置 NEXA_VERSION 环境变量，供 Rust 代码通过 env!("NEXA_VERSION") 使用
    println!("cargo:rustc-env=NEXA_VERSION={}", version);
}