//! AVM 契约运行时引擎 - Design by Contract (契约式编程)
//!
//! 核心概念：
//! - requires: 前置条件（函数调用前必须满足）
//! - ensures: 后置条件（函数返回后必须满足）
//! - 确定性契约：传统逻辑条件（如 amount > 0）
//! - 语义契约：自然语言条件（如 "input contains financial data"），用 LLM 判断

use crate::compiler::ast::{ContractClause, ContractSpec};
use crate::utils::error::{AvmError, AvmResult};
use crate::vm::stack::Value;
use std::collections::HashMap;

/// 契约违反错误
#[derive(Debug, Clone)]
pub struct ContractViolation {
    pub message: String,
    pub clause_type: String, // "requires" 或 "ensures"
    pub is_semantic: bool,
    pub expression: Option<String>,
    pub condition_text: Option<String>,
}

impl std::fmt::Display for ContractViolation {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let tag = if self.is_semantic { "semantic" } else { "deterministic" };
        write!(f, "ContractViolation({}:{}) - {}", self.clause_type, tag, self.message)
    }
}

/// 评估确定性契约表达式
fn evaluate_deterministic_expression(
    expression: &str,
    context: &HashMap<String, Value>,
    result: Option<&Value>,
    old_values: &HashMap<String, Value>,
) -> bool {
    // 替换 old(expr) 为实际值
    let mut expr = expression.to_string();
    for (key, val) in old_values {
        let old_pattern = format!("old({})", key);
        let replacement = value_to_expr_string(val);
        expr = expr.replace(&old_pattern, &replacement);
    }

    // 构建评估环境
    let eval_ctx: HashMap<String, Value> = if let Some(r) = result {
        let mut ctx = context.clone();
        ctx.insert("result".to_string(), r.clone());
        ctx
    } else {
        context.clone()
    };

    evaluate_simple_comparison(&expr, &eval_ctx)
}

/// 将 Value 转换为表达式字符串表示
fn value_to_expr_string(val: &Value) -> String {
    match val {
        Value::Int(n) => n.to_string(),
        Value::Float(f) => f.to_string(),
        Value::String(s) => format!("\"{}\"", s),
        Value::Bool(b) => b.to_string(),
        Value::Null => "null".to_string(),
        _ => format!("{:?}", val),
    }
}

/// 评估简单的比较表达式
fn evaluate_simple_comparison(expr: &str, context: &HashMap<String, Value>) -> bool {
    let operators = [">=", "<=", "==", "!=", ">", "<"];
    
    for op in &operators {
        if let Some(pos) = expr.find(op) {
            let left_str = expr[..pos].trim();
            let right_str = expr[pos + op.len()..].trim();
            
            let left_val = resolve_value(left_str, context);
            let right_val = resolve_value(right_str, context);
            
            return compare_values(&left_val, &right_val, op);
        }
    }
    
    let val = resolve_value(expr.trim(), context);
    match val {
        Value::Bool(b) => b,
        Value::Null => false,
        _ => true,
    }
}

/// 从上下文中解析值
fn resolve_value(expr: &str, context: &HashMap<String, Value>) -> Value {
    if expr.starts_with('"') && expr.ends_with('"') {
        return Value::String(expr[1..expr.len()-1].to_string());
    }
    if expr == "true" {
        return Value::Bool(true);
    }
    if expr == "false" {
        return Value::Bool(false);
    }
    if expr == "null" {
        return Value::Null;
    }
    
    if let Ok(n) = expr.parse::<i64>() {
        return Value::Int(n);
    }
    if let Ok(f) = expr.parse::<f64>() {
        return Value::Float(f);
    }
    
    if expr.contains('.') {
        let parts: Vec<&str> = expr.split('.').collect();
        let mut val = context.get(parts[0]).cloned().unwrap_or(Value::Null);
        for part in &parts[1..] {
            val = match &val {
                Value::Dict(map) => map.get(*part).cloned().unwrap_or(Value::Null),
                _ => Value::Null,
            };
        }
        return val;
    }
    
    context.get(expr).cloned().unwrap_or(Value::Null)
}

/// 比较整数辅助函数
fn cmp_int(l: i64, r: i64, op: &str) -> bool {
    if op == ">=" { l >= r }
    else if op == "<=" { l <= r }
    else if op == "==" { l == r }
    else if op == "!=" { l != r }
    else if op == ">" { l > r }
    else if op == "<" { l < r }
    else { false }
}

/// 比较浮点数辅助函数
fn cmp_float(l: f64, r: f64, op: &str) -> bool {
    if op == ">=" { l >= r }
    else if op == "<=" { l <= r }
    else if op == "==" { l == r }
    else if op == "!=" { l != r }
    else if op == ">" { l > r }
    else if op == "<" { l < r }
    else { false }
}

/// 比较两个 Value
fn compare_values(left: &Value, right: &Value, op: &str) -> bool {
    match (left, right) {
        (Value::Int(l), Value::Int(r)) => cmp_int(*l, *r, op),
        (Value::Float(l), Value::Float(r)) => cmp_float(*l, *r, op),
        (Value::Int(l), Value::Float(r)) => cmp_float(*l as f64, *r, op),
        (Value::Float(l), Value::Int(r)) => cmp_float(*l, *r as f64, op),
        (Value::String(l), Value::String(r)) => {
            if op == "==" { l == r }
            else if op == "!=" { l != r }
            else { false }
        }
        (Value::Bool(l), Value::Bool(r)) => {
            if op == "==" { l == r }
            else if op == "!=" { l != r }
            else { false }
        }
        _ => false,
    }
}

/// 检查前置条件 (requires)
pub fn check_requires(
    spec: &ContractSpec,
    context: &HashMap<String, Value>,
) -> AvmResult<()> {
    for clause in &spec.requires {
        let satisfied = if clause.is_semantic {
            println!("[Contract Semantic] Requires: \"{}\" - deferred to LLM evaluation", 
                     clause.condition_text.as_deref().unwrap_or(""));
            true
        } else {
            let expr = clause.expression.as_deref().unwrap_or("");
            evaluate_deterministic_expression(expr, context, None, &HashMap::new())
        };
        
        if !satisfied {
            let desc = if clause.is_semantic {
                clause.condition_text.as_deref().unwrap_or("")
            } else {
                clause.expression.as_deref().unwrap_or("")
            };
            // Use let binding to avoid temporary value dropped while borrowed
            let default_msg = format!("Requires clause violated: {}", desc);
            let message = clause.message.as_deref().unwrap_or(&default_msg);
            let tag = if clause.is_semantic { "semantic" } else { "deterministic" };
            return Err(AvmError::RuntimeError(
                format!("ContractViolation({}:{}): {}", clause.clause_type, tag, message)
            ));
        }
    }
    Ok(())
}

/// 检查后置条件 (ensures)
pub fn check_ensures(
    spec: &ContractSpec,
    context: &HashMap<String, Value>,
    result: &Value,
    old_values: &HashMap<String, Value>,
) -> AvmResult<()> {
    for clause in &spec.ensures {
        let satisfied = if clause.is_semantic {
            println!("[Contract Semantic] Ensures: \"{}\" - deferred to LLM evaluation",
                     clause.condition_text.as_deref().unwrap_or(""));
            true
        } else {
            let expr = clause.expression.as_deref().unwrap_or("");
            evaluate_deterministic_expression(expr, context, Some(result), old_values)
        };
        
        if !satisfied {
            let desc = if clause.is_semantic {
                clause.condition_text.as_deref().unwrap_or("")
            } else {
                clause.expression.as_deref().unwrap_or("")
            };
            // Use let binding to avoid temporary value dropped while borrowed
            let default_msg = format!("Ensures clause violated: {}", desc);
            let message = clause.message.as_deref().unwrap_or(&default_msg);
            let tag = if clause.is_semantic { "semantic" } else { "deterministic" };
            return Err(AvmError::RuntimeError(
                format!("ContractViolation({}:{}): {}", clause.clause_type, tag, message)
            ));
        }
    }
    Ok(())
}

/// 从 ensures 条款中提取 old() 表达式
pub fn extract_old_expressions(spec: &ContractSpec) -> Vec<String> {
    let mut old_exprs = Vec::new();
    for clause in &spec.ensures {
        if !clause.is_semantic && clause.expression.is_some() {
            let expr = clause.expression.as_deref().unwrap();
            if let Some(start) = expr.find("old(") {
                let inner_start = start + 4;
                if let Some(end) = expr[inner_start..].find(')') {
                    let inner = expr[inner_start..inner_start + end].to_string();
                    old_exprs.push(inner);
                }
            }
        }
    }
    old_exprs
}

/// 捕获函数入口时的值
pub fn capture_old_values(
    spec: &ContractSpec,
    context: &HashMap<String, Value>,
) -> HashMap<String, Value> {
    let old_exprs = extract_old_expressions(spec);
    let mut values = HashMap::new();
    for expr in &old_exprs {
        if let Some(val) = context.get(expr) {
            values.insert(expr.clone(), val.clone());
        }
        if expr.contains('.') {
            let parts: Vec<&str> = expr.split('.').collect();
            if let Some(root) = context.get(parts[0]) {
                let mut val = root.clone();
                for part in &parts[1..] {
                    val = match &val {
                        Value::Dict(map) => map.get(*part).cloned().unwrap_or(Value::Null),
                        _ => Value::Null,
                    };
                }
                values.insert(expr.clone(), val);
            }
        }
    }
    values
}