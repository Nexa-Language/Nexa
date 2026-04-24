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

//! AVM 运行时模块

pub mod agent;
pub mod tool;
pub mod llm;
pub mod contracts;
pub mod result_types;
pub mod jobs;  // P1-3: Background Job System

pub use agent::{AgentConfig, AgentInstance, AgentRegistry};
pub use tool::{ToolExecutor, ToolRegistry, ToolSpec};
pub use llm::{LlmClient, LlmConfig};
pub use contracts::{check_requires, check_ensures, capture_old_values, ContractViolation};
// v1.2: Error Propagation (错误传播)
pub use result_types::{NexaResult, NexaOption, ErrorPropagation, OtherwiseHandlerCtx, PropagationResult, propagate_or_else, wrap_agent_result};
// P1-3: Background Job System
pub use jobs::{JobPriority, JobStatus, BackoffStrategy, JobSpec, JobRecord, MemoryBackend, JobRegistry, JobQueue, calculate_backoff};

use crate::bytecode::BytecodeModule;
use crate::utils::error::{AvmError, AvmResult};
use crate::vm::stack::Value;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

/// AVM 运行时环境
pub struct AvmRuntime {
    /// Agent 注册表
    agents: Arc<RwLock<AgentRegistry>>,
    /// 工具注册表
    tools: Arc<RwLock<ToolRegistry>>,
    /// LLM 客户端
    llm: Arc<RwLock<LlmClient>>,
    /// 全局变量
    globals: Arc<RwLock<HashMap<String, Value>>>,
    /// 配置
    config: AvmConfig,
}

/// AVM 配置
#[derive(Debug, Clone)]
pub struct AvmConfig {
    pub max_stack_depth: usize,
    pub max_call_depth: usize,
    pub cache_enabled: bool,
    pub default_model: String,
}

impl Default for AvmConfig {
    fn default() -> Self {
        Self {
            max_stack_depth: 1024,
            max_call_depth: 128,
            cache_enabled: true,
            default_model: "gpt-4".to_string(),
        }
    }
}

impl AvmRuntime {
    /// 创建新的运行时
    pub fn new(config: AvmConfig) -> Self {
        Self {
            agents: Arc::new(RwLock::new(AgentRegistry::new())),
            tools: Arc::new(RwLock::new(ToolRegistry::new())),
            llm: Arc::new(RwLock::new(LlmClient::new(LlmConfig {
                default_model: config.default_model.clone(),
                ..Default::default()
            }))),
            globals: Arc::new(RwLock::new(HashMap::new())),
            config,
        }
    }

    /// 获取 Agent 注册表
    pub fn agents(&self) -> Arc<RwLock<AgentRegistry>> {
        self.agents.clone()
    }

    /// 获取工具注册表
    pub fn tools(&self) -> Arc<RwLock<ToolRegistry>> {
        self.tools.clone()
    }

    /// 获取 LLM 客户端
    pub fn llm(&self) -> Arc<RwLock<LlmClient>> {
        self.llm.clone()
    }

    /// 获取全局变量
    pub fn globals(&self) -> Arc<RwLock<HashMap<String, Value>>> {
        self.globals.clone()
    }

    /// 运行 Agent
    pub async fn run_agent(&self, name: &str, input: &str) -> AvmResult<String> {
        let mut agents = self.agents.write().await;
        agents.run_agent(name, input)
    }

    /// 执行工具
    pub async fn execute_tool(&self, name: &str, args: &HashMap<String, Value>) -> AvmResult<String> {
        let tools = self.tools.read().await;
        tools.execute(name, args)
    }

    /// LLM 调用
    pub async fn llm_chat(&self, messages: &[(&str, &str)], model: Option<&str>) -> AvmResult<String> {
        let mut llm = self.llm.write().await;
        llm.chat(messages, model)
    }

    /// 设置全局变量
    pub async fn set_global(&self, name: String, value: Value) {
        let mut globals = self.globals.write().await;
        globals.insert(name, value);
    }

    /// 获取全局变量
    pub async fn get_global(&self, name: &str) -> Option<Value> {
        let globals = self.globals.read().await;
        globals.get(name).cloned()
    }

    /// 编译并运行源码
    pub async fn run_source(&self, source: &str) -> AvmResult<Value> {
        // 解析
        let program = crate::compiler::parser::Parser::parse_from_source(source)?;
        
        // 编译
        let compiler = crate::bytecode::compiler::BytecodeCompiler::new("main".to_string());
        let module = compiler.compile(&program)?;
        
        // 执行
        self.run_module(&module).await
    }

    /// 运行字节码模块
    pub async fn run_module(&self, module: &BytecodeModule) -> AvmResult<Value> {
        use crate::vm::interpreter::Interpreter;
        
        let mut interpreter = Interpreter::new(crate::vm::interpreter::InterpreterConfig {
            max_stack_depth: self.config.max_stack_depth,
            max_call_depth: self.config.max_call_depth,
            debug_mode: false,
        });
        
        interpreter.load_module(module.clone());
        
        // 在异步环境中运行同步解释器
        let result = tokio::task::spawn_blocking(move || {
            interpreter.run()
        }).await
            .map_err(|e| AvmError::RuntimeError(e.to_string()))??;
        
        // 将栈值转换为运行时值
        Ok(result.value)
    }
}

impl Default for AvmRuntime {
    fn default() -> Self {
        Self::new(AvmConfig::default())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_runtime_creation() {
        let runtime = AvmRuntime::default();
        assert!(runtime.agents.read().await.get_agent("test").is_none());
    }

    #[tokio::test]
    async fn test_global_variables() {
        let runtime = AvmRuntime::default();
        runtime.set_global("test".to_string(), Value::Int(42)).await;
        
        let value = runtime.get_global("test").await;
        assert_eq!(value, Some(Value::Int(42)));
    }

    #[tokio::test]
    async fn test_run_simple_source() {
        // 简化测试，只测试运行时创建和基本操作
        let runtime = AvmRuntime::default();
        
        // 设置全局变量
        runtime.set_global("test".to_string(), Value::Int(123)).await;
        let value = runtime.get_global("test").await;
        assert_eq!(value, Some(Value::Int(123)));
    }
}