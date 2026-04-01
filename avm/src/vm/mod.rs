//! AVM 虚拟机模块 (Virtual Machine Module)
//!
//! 字节码解释执行器

pub mod context_pager;
pub mod cow_memory;
pub mod interpreter;
pub mod scheduler;
pub mod stack;

pub use context_pager::*;
pub use cow_memory::*;
pub use interpreter::*;
pub use scheduler::*;
pub use stack::*;