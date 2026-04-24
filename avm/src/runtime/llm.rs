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

//! LLM 运行时

use crate::utils::error::{AvmError, AvmResult};
use std::collections::HashMap;

/// LLM 配置
#[derive(Debug, Clone)]
pub struct LlmConfig {
    pub provider: String,
    pub api_key: Option<String>,
    pub base_url: Option<String>,
    pub default_model: String,
    pub cache_enabled: bool,
}

impl Default for LlmConfig {
    fn default() -> Self {
        Self {
            provider: "openai".to_string(),
            api_key: None,
            base_url: None,
            default_model: "gpt-4".to_string(),
            cache_enabled: true,
        }
    }
}

/// LLM 客户端
pub struct LlmClient {
    config: LlmConfig,
    cache: HashMap<String, String>,
}

impl LlmClient {
    pub fn new(config: LlmConfig) -> Self {
        Self {
            config,
            cache: HashMap::new(),
        }
    }

    pub fn chat(&mut self, messages: &[(&str, &str)], model: Option<&str>) -> AvmResult<String> {
        let model = model.unwrap_or(&self.config.default_model);
        
        // 简化实现：模拟响应
        let last_user_msg = messages.iter()
            .rev()
            .find(|(role, _)| *role == "user")
            .map(|(_, content)| *content)
            .unwrap_or("");
        
        Ok(format!("[{}] Response to: {}", model, last_user_msg))
    }

    pub fn clear_cache(&mut self) {
        self.cache.clear();
    }

    pub fn cache_size(&self) -> usize {
        self.cache.len()
    }
}

impl Default for LlmClient {
    fn default() -> Self {
        Self::new(LlmConfig::default())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_llm_client() {
        let mut client = LlmClient::default();
        let messages = vec![("user", "Hello")];
        let result = client.chat(&messages, None).unwrap();
        assert!(result.contains("Hello"));
    }
}
