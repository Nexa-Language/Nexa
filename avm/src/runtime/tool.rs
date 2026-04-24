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

//! Tool 运行时

use crate::utils::error::{AvmError, AvmResult};
use crate::vm::stack::Value;
use std::collections::HashMap;

/// 工具定义
#[derive(Debug, Clone)]
pub struct ToolSpec {
    pub name: String,
    pub description: String,
    pub parameters: serde_json::Value,
}

impl ToolSpec {
    pub fn new(name: impl Into<String>, description: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            description: description.into(),
            parameters: serde_json::json!({"type": "object"}),
        }
    }
}

/// 工具执行器 trait
pub trait ToolExecutor: Send + Sync {
    fn execute(&self, args: &HashMap<String, Value>) -> AvmResult<String>;
    fn spec(&self) -> &ToolSpec;
}

/// 工具注册表
pub struct ToolRegistry {
    tools: HashMap<String, Box<dyn ToolExecutor>>,
}

impl ToolRegistry {
    pub fn new() -> Self {
        Self {
            tools: HashMap::new(),
        }
    }

    pub fn register(&mut self, name: String, executor: Box<dyn ToolExecutor>) {
        self.tools.insert(name, executor);
    }

    pub fn execute(&self, name: &str, args: &HashMap<String, Value>) -> AvmResult<String> {
        let executor = self.tools.get(name)
            .ok_or_else(|| AvmError::ToolNotFound(name.to_string()))?;
        executor.execute(args)
    }

    pub fn list_tools(&self) -> Vec<&String> {
        self.tools.keys().collect()
    }
}

impl Default for ToolRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tool_spec() {
        let spec = ToolSpec::new("test", "A test tool");
        assert_eq!(spec.name, "test");
    }
}
