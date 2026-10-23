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

pub const DEFAULT_LLM_MODEL: &str = "minimax-m2.5";

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
            default_model: DEFAULT_LLM_MODEL.to_string(),
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
        let key = self
            .config
            .api_key
            .as_deref()
            .filter(|key| !key.is_empty())
            .ok_or_else(|| AvmError::LlmError("A provider API key is required".into()))?;
        let endpoint = self
            .config
            .base_url
            .as_deref()
            .unwrap_or("https://api.openai.com/v1");
        let client = reqwest::blocking::Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .map_err(|error| AvmError::LlmError(error.to_string()))?;
        let messages: Vec<_> = messages
            .iter()
            .map(|(role, content)| serde_json::json!({"role": role, "content": content}))
            .collect();
        let response = client
            .post(format!(
                "{}/chat/completions",
                endpoint.trim_end_matches('/')
            ))
            .bearer_auth(key)
            .json(&serde_json::json!({"model": model, "messages": messages}))
            .send()
            .map_err(|error| {
                AvmError::LlmError(format!(
                    "Provider transport failed: {}",
                    error.without_url()
                ))
            })?;
        if !response.status().is_success() {
            return Err(AvmError::LlmError(format!(
                "Provider HTTP status {}",
                response.status()
            )));
        }
        let data: serde_json::Value = response
            .json()
            .map_err(|_| AvmError::LlmError("Invalid provider JSON".into()))?;
        let choice = &data["choices"][0];
        if choice["finish_reason"] != "stop"
            || !choice["message"]["tool_calls"].is_null()
            || !choice["message"]["refusal"].is_null()
        {
            return Err(AvmError::LlmError(
                "AVM text provider requires a complete text response without tool calls".into(),
            ));
        }
        choice["message"]["content"]
            .as_str()
            .map(str::to_owned)
            .ok_or_else(|| AvmError::LlmError("Provider omitted text output".into()))
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
        assert!(client
            .chat(&messages, None)
            .unwrap_err()
            .to_string()
            .contains("API key"));
    }
}
