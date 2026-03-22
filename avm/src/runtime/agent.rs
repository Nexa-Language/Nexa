//! Agent 运行时

use crate::utils::error::{AvmError, AvmResult};
use crate::vm::stack::Value;
use std::collections::HashMap;

/// Agent 配置
#[derive(Debug, Clone)]
pub struct AgentConfig {
    pub name: String,
    pub prompt: Option<String>,
    pub role: Option<String>,
    pub model: Option<String>,
    pub tools: Vec<String>,
    pub cache_enabled: bool,
}

impl AgentConfig {
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            prompt: None,
            role: None,
            model: None,
            tools: Vec::new(),
            cache_enabled: false,
        }
    }
}

/// Agent 实例
pub struct AgentInstance {
    config: AgentConfig,
    history: Vec<String>,
}

impl AgentInstance {
    pub fn new(config: AgentConfig) -> Self {
        Self {
            config,
            history: Vec::new(),
        }
    }

    pub fn run(&mut self, input: &str) -> AvmResult<String> {
        self.history.push(input.to_string());
        Ok(format!("[{}]: {}", self.config.name, input))
    }

    pub fn config(&self) -> &AgentConfig {
        &self.config
    }

    pub fn clear_history(&mut self) {
        self.history.clear();
    }
}

/// Agent 注册表
pub struct AgentRegistry {
    agents: HashMap<String, AgentInstance>,
    templates: HashMap<String, AgentConfig>,
}

impl AgentRegistry {
    pub fn new() -> Self {
        Self {
            agents: HashMap::new(),
            templates: HashMap::new(),
        }
    }

    pub fn register_template(&mut self, config: AgentConfig) {
        self.templates.insert(config.name.clone(), config);
    }

    pub fn create_agent(&mut self, name: &str) -> AvmResult<&AgentInstance> {
        let config = self.templates.get(name).cloned()
            .ok_or_else(|| AvmError::AgentNotFound(name.to_string()))?;
        let instance = AgentInstance::new(config);
        self.agents.insert(name.to_string(), instance);
        Ok(self.agents.get(name).unwrap())
    }

    pub fn get_agent(&self, name: &str) -> Option<&AgentInstance> {
        self.agents.get(name)
    }

    pub fn run_agent(&mut self, name: &str, input: &str) -> AvmResult<String> {
        let agent = self.agents.get_mut(name)
            .ok_or_else(|| AvmError::AgentNotFound(name.to_string()))?;
        agent.run(input)
    }
}

impl Default for AgentRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_agent_config() {
        let config = AgentConfig::new("test_agent");
        assert_eq!(config.name, "test_agent");
    }

    #[test]
    fn test_agent_instance() {
        let config = AgentConfig::new("test");
        let mut agent = AgentInstance::new(config);
        let result = agent.run("Hello").unwrap();
        assert!(result.contains("test"));
    }
}
