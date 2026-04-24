/*
========================================================================
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
//! Nexa Agent Virtual Machine (AVM)
//!
//! A high-performance runtime for AI agent orchestration written in Rust.

pub mod compiler;
pub mod bytecode;
pub mod vm;
pub mod runtime;
pub mod utils;
pub mod wasm;
pub mod ffi;

// Re-export error types
pub use utils::error::{AvmError, AvmResult};

/// AVM version
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
