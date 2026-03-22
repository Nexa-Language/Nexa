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