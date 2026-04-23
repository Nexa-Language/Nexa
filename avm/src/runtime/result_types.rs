//! Nexa Result Types — Error Propagation Infrastructure
//!
//! v1.2: 实现 ? 操作符和 otherwise 内联错误处理的核心类型
//!
//! 设计参考: NTNT 的 ? 操作符和 otherwise 语句
//! - NexaResult: 类似 Rust Result<T, E>，成功(ok)或失败(err)
//! - NexaOption: 类似 Rust Option<T>，有值(some)或无值(none)
//! - ErrorPropagation: ? 操作符触发的内部异常，用于 early-return
//!
//! 关键设计原则:
//! 1. Agent 优先: ? 和 otherwise 首先为 Agent.run() 结果设计
//! 2. 向后兼容: 字符串结果自动包装为 NexaResult::ok
//! 3. ErrorPropagation 是内部机制，不是用户可见的异常类型

use crate::vm::stack::Value;
use std::fmt;

/// ? 操作符触发的错误传播异常，用于 early-return
///
/// 这是 Nexa 内部机制，不是用户可见的异常类型。
/// 当 ? 操作符遇到 NexaResult::err 或 NexaOption::none 时，
/// 触发 ErrorPropagation，flow 函数的外层会捕获并转换为错误返回。
#[derive(Debug, Clone)]
pub struct ErrorPropagation {
    pub error: Value,
}

impl fmt::Display for ErrorPropagation {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "ErrorPropagation: {}", self.error)
    }
}

/// Nexa 结果包装器，类似 Rust 的 Result<T, E>
///
/// 表示一个可能成功或失败的操作结果：
/// - NexaResult::ok(value) — 操作成功，包含返回值
/// - NexaResult::err(error) — 操作失败，包含错误信息
#[derive(Debug, Clone)]
pub enum NexaResult {
    Ok(Value),
    Err(Value),
}

impl NexaResult {
    /// 创建成功结果
    pub fn ok(value: Value) -> Self {
        NexaResult::Ok(value)
    }

    /// 创建失败结果
    pub fn err(error: Value) -> Self {
        NexaResult::Err(error)
    }

    /// 是否成功
    pub fn is_ok(&self) -> bool {
        matches!(self, NexaResult::Ok(_))
    }

    /// 是否失败
    pub fn is_err(&self) -> bool {
        matches!(self, NexaResult::Err(_))
    }

    /// ? 操作符的核心：成功返回值，失败则触发 ErrorPropagation
    ///
    /// 类似 Rust 的 ? 操作符工作机制：
    /// - Ok → 继续执行（返回内部值）
    /// - Err → 触发 ErrorPropagation → flow 函数捕获 → 返回错误
    pub fn unwrap(&self) -> Result<Value, ErrorPropagation> {
        match self {
            NexaResult::Ok(value) => Ok(value.clone()),
            NexaResult::Err(error) => Err(ErrorPropagation { error: error.clone() }),
        }
    }

    /// otherwise 的核心：成功返回值，失败返回默认值
    pub fn unwrap_or(&self, default: Value) -> Value {
        match self {
            NexaResult::Ok(value) => value.clone(),
            NexaResult::Err(_) => default,
        }
    }

    /// otherwise 的函数版本：成功返回值，失败执行 handler
    pub fn unwrap_or_else<F>(&self, handler: F) -> Value
    where
        F: FnOnce(&Value) -> Value,
    {
        match self {
            NexaResult::Ok(value) => value.clone(),
            NexaResult::Err(error) => handler(error),
        }
    }

    /// 映射成功值
    pub fn map<F>(&self, f: F) -> NexaResult
    where
        F: FnOnce(&Value) -> Value,
    {
        match self {
            NexaResult::Ok(value) => NexaResult::Ok(f(value)),
            NexaResult::Err(error) => NexaResult::Err(error.clone()),
        }
    }

    /// 映射错误值
    pub fn map_err<F>(&self, f: F) -> NexaResult
    where
        F: FnOnce(&Value) -> Value,
    {
        match self {
            NexaResult::Ok(value) => NexaResult::Ok(value.clone()),
            NexaResult::Err(error) => NexaResult::Err(f(error)),
        }
    }
}

impl fmt::Display for NexaResult {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            NexaResult::Ok(value) => write!(f, "NexaResult::Ok({})", value),
            NexaResult::Err(error) => write!(f, "NexaResult::Err({})", error),
        }
    }
}

/// Nexa 可选值包装器，类似 Rust 的 Option<T>
///
/// 表示一个可能有值或无值的结果：
/// - NexaOption::some(value) — 有值
/// - NexaOption::none() — 无值
#[derive(Debug, Clone)]
pub enum NexaOption {
    Some(Value),
    None,
}

impl NexaOption {
    /// 创建有值的 Option
    pub fn some(value: Value) -> Self {
        NexaOption::Some(value)
    }

    /// 创建无值的 Option
    pub fn none() -> Self {
        NexaOption::None
    }

    /// 是否有值
    pub fn is_some(&self) -> bool {
        matches!(self, NexaOption::Some(_))
    }

    /// 是否无值
    pub fn is_none(&self) -> bool {
        matches!(self, NexaOption::None)
    }

    /// ? 操作符的核心：有值返回值，无值则触发 ErrorPropagation
    pub fn unwrap(&self) -> Result<Value, ErrorPropagation> {
        match self {
            NexaOption::Some(value) => Ok(value.clone()),
            NexaOption::None => Err(ErrorPropagation { error: Value::Null }),
        }
    }

    /// otherwise 的核心：有值返回值，无值返回默认值
    pub fn unwrap_or(&self, default: Value) -> Value {
        match self {
            NexaOption::Some(value) => value.clone(),
            NexaOption::None => default,
        }
    }

    /// 映射有值情况
    pub fn map<F>(&self, f: F) -> NexaOption
    where
        F: FnOnce(&Value) -> Value,
    {
        match self {
            NexaOption::Some(value) => NexaOption::Some(f(value)),
            NexaOption::None => NexaOption::None,
        }
    }

    /// 转换为 NexaResult：有值→ok，无值→err
    pub fn to_result(&self, error: Value) -> NexaResult {
        match self {
            NexaOption::Some(value) => NexaResult::Ok(value.clone()),
            NexaOption::None => NexaResult::Err(error),
        }
    }
}

impl fmt::Display for NexaOption {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            NexaOption::Some(value) => write!(f, "NexaOption::Some({})", value),
            NexaOption::None => write!(f, "NexaOption::None"),
        }
    }
}

/// 统一处理 ? 和 otherwise 逻辑
///
/// 当只有 result 参数时（? 操作符模式）：
/// - 成功 → 返回值
/// - 失败 → 返回 ErrorPropagation
///
/// 当有 otherwise_handler 参数时（otherwise 模式）：
/// - 成功 → 返回值
/// - 失败 → 执行 otherwise_handler
pub fn propagate_or_else(result: &NexaResult, otherwise_handler: Option<&OtherwiseHandlerCtx>) -> PropagationResult {
    if result.is_ok() {
        // 成功 → 返回值
        PropagationResult::Ok(match result {
            NexaResult::Ok(value) => value.clone(),
            NexaResult::Err(_) => Value::Null, // 不应到达这里
        })
    } else {
        // 失败 → 根据是否有 otherwise handler 决定行为
        match otherwise_handler {
            Some(handler) => {
                // otherwise 模式：执行 handler
                PropagationResult::Fallback(handler.handle(result))
            }
            None => {
                // ? 操作符模式：触发 ErrorPropagation
                PropagationResult::Propagate(ErrorPropagation {
                    error: match result {
                        NexaResult::Err(error) => error.clone(),
                        NexaResult::Ok(_) => Value::Null, // 不应到达这里
                    }
                })
            }
        }
    }
}

/// otherwise handler 上下文
///
/// 描述 otherwise 语句右侧的处理器类型
#[derive(Debug, Clone)]
pub enum OtherwiseHandlerCtx {
    /// Agent 调用作为 fallback
    AgentCall { agent_name: String },
    /// 值作为默认 fallback
    Value(Value),
    /// 变量引用作为 fallback
    Variable(String),
    /// 代码块作为 fallback（包含语句列表）
    Block,
}

impl OtherwiseHandlerCtx {
    /// 处理 otherwise handler
    pub fn handle(&self, result: &NexaResult) -> Value {
        match self {
            OtherwiseHandlerCtx::AgentCall { agent_name } => {
                // Agent fallback: 在解释器层面处理
                Value::String(format!("fallback_agent:{}", agent_name))
            }
            OtherwiseHandlerCtx::Value(value) => value.clone(),
            OtherwiseHandlerCtx::Variable(name) => {
                Value::String(format!("fallback_var:{}", name))
            }
            OtherwiseHandlerCtx::Block => {
                // 代码块 fallback: 在解释器层面处理
                match result {
                    NexaResult::Err(error) => error.clone(),
                    _ => Value::Null,
                }
            }
        }
    }
}

/// 错误传播结果
#[derive(Debug, Clone)]
pub enum PropagationResult {
    /// 成功 → 继续执行
    Ok(Value),
    /// otherwise → 使用 fallback 值继续
    Fallback(Value),
    /// ? → 触发 ErrorPropagation (early-return)
    Propagate(ErrorPropagation),
}

/// 将原始 Agent 执行结果包装为 NexaResult
///
/// 向后兼容策略：
/// - Value::String → NexaResult::Ok(string)
/// - 其他值 → NexaResult::Ok(value)
pub fn wrap_agent_result(raw_result: Value) -> NexaResult {
    NexaResult::Ok(raw_result)
}

/// 将 NexaOption 转换为 NexaResult
pub fn option_to_result(opt: &NexaOption, error: Value) -> NexaResult {
    opt.to_result(error)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_nexa_result_ok() {
        let result = NexaResult::ok(Value::String("success".to_string()));
        assert!(result.is_ok());
        assert!(!result.is_err());
        
        let unwrapped = result.unwrap();
        assert!(unwrapped.is_ok());
        assert_eq!(unwrapped.unwrap(), Value::String("success".to_string()));
    }

    #[test]
    fn test_nexa_result_err() {
        let result = NexaResult::err(Value::String("error".to_string()));
        assert!(result.is_err());
        assert!(!result.is_ok());
        
        let unwrapped = result.unwrap();
        assert!(unwrapped.is_err());
        let propagation = unwrapped.unwrap_err();
        assert_eq!(propagation.error, Value::String("error".to_string()));
    }

    #[test]
    fn test_nexa_result_unwrap_or() {
        let ok_result = NexaResult::ok(Value::String("success".to_string()));
        let err_result = NexaResult::err(Value::String("error".to_string()));
        
        assert_eq!(ok_result.unwrap_or(Value::String("default".to_string())), 
                   Value::String("success".to_string()));
        assert_eq!(err_result.unwrap_or(Value::String("default".to_string())), 
                   Value::String("default".to_string()));
    }

    #[test]
    fn test_nexa_option_some() {
        let opt = NexaOption::some(Value::String("value".to_string()));
        assert!(opt.is_some());
        assert!(!opt.is_none());
        
        let unwrapped = opt.unwrap();
        assert!(unwrapped.is_ok());
        assert_eq!(unwrapped.unwrap(), Value::String("value".to_string()));
    }

    #[test]
    fn test_nexa_option_none() {
        let opt = NexaOption::none();
        assert!(opt.is_none());
        assert!(!opt.is_some());
        
        let unwrapped = opt.unwrap();
        assert!(unwrapped.is_err());
    }

    #[test]
    fn test_propagate_or_else_ok() {
        let result = NexaResult::ok(Value::String("success".to_string()));
        let propagation = propagate_or_else(&result, None);
        assert!(matches!(propagation, PropagationResult::Ok(_)));
    }

    #[test]
    fn test_propagate_or_else_err_with_handler() {
        let result = NexaResult::err(Value::String("error".to_string()));
        let handler = OtherwiseHandlerCtx::Value(Value::String("fallback".to_string()));
        let propagation = propagate_or_else(&result, Some(&handler));
        assert!(matches!(propagation, PropagationResult::Fallback(Value::String(_))));
    }

    #[test]
    fn test_propagate_or_else_err_no_handler() {
        let result = NexaResult::err(Value::String("error".to_string()));
        let propagation = propagate_or_else(&result, None);
        assert!(matches!(propagation, PropagationResult::Propagate(_)));
    }

    #[test]
    fn test_wrap_agent_result() {
        let raw = Value::String("agent output".to_string());
        let result = wrap_agent_result(raw);
        assert!(result.is_ok());
    }
}