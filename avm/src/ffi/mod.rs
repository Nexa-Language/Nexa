//! FFI 模块 (Foreign Function Interface Module)
//!
//! 提供 Python 和 C 的互操作接口

pub mod python;
pub mod c_api;

pub use python::*;
pub use c_api::*;
