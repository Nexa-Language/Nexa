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