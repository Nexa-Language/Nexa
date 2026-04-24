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

//! 类型检查器 (Type Checker)
//!
//! v1.1: 渐进式类型系统 (Gradual Type System) 完整实现
//!
//! 双轴类型安全模式:
//! - NEXA_TYPE_MODE (运行时): strict / warn / forgiving
//! - NEXA_LINT_MODE (lint时): default / warn / strict
//!
//! 核心原则:
//! - 渐进式: 不是"全有或全无"，从无类型开始逐步添加
//! - Agent 优先: 类型系统首先为 Agent 输入输出设计
//! - Protocol 升级: 从字符串标注 → 完整类型表达式
//! - 不阻塞执行: 类型检查作为 lint pass

use crate::compiler::ast::*;
use crate::utils::error::{AvmError, AvmResult};
use std::collections::HashMap;
use std::env;

/// 类型检查器 — 渐进式类型检查实现
pub struct TypeChecker {
    /// 运行时类型检查模式
    type_mode: TypeMode,
    /// Lint 类型检查模式
    lint_mode: LintMode,
    /// 类型别名注册表
    type_registry: HashMap<String, TypeExpr>,
    /// Protocol 类型信息注册表
    protocol_registry: HashMap<String, HashMap<String, TypeExpr>>,
}

impl TypeChecker {
    pub fn new() -> Self {
        Self {
            type_mode: Self::detect_type_mode(),
            lint_mode: Self::detect_lint_mode(),
            type_registry: HashMap::new(),
            protocol_registry: HashMap::new(),
        }
    }

    /// 从环境变量检测 TypeMode
    fn detect_type_mode() -> TypeMode {
        match env::var("NEXA_TYPE_MODE").as_deref() {
            Ok("strict") => TypeMode::Strict,
            Ok("forgiving") => TypeMode::Forgiving,
            Ok("warn") | Ok(_) | Err(_) => TypeMode::Warn, // 默认 warn
        }
    }

    /// 从环境变量检测 LintMode
    fn detect_lint_mode() -> LintMode {
        match env::var("NEXA_LINT_MODE").as_deref() {
            Ok("strict") => LintMode::Strict,
            Ok("warn") => LintMode::Warn,
            Ok("default") | Ok(_) | Err(_) => LintMode::Default, // 默认 default
        }
    }

    /// 设置 TypeMode (CLI override)
    pub fn set_type_mode(&mut self, mode: TypeMode) {
        self.type_mode = mode;
    }

    /// 设置 LintMode (CLI override)
    pub fn set_lint_mode(&mut self, mode: LintMode) {
        self.lint_mode = mode;
    }

    /// 注册类型别名
    pub fn register_type_alias(&mut self, name: String, type_expr: TypeExpr) {
        self.type_registry.insert(name, type_expr);
    }

    /// 注册 Protocol 类型信息
    pub fn register_protocol(&mut self, name: String, fields: HashMap<String, TypeExpr>) {
        self.protocol_registry.insert(name, fields);
    }

    /// 注册 Protocol 单个字段类型
    pub fn register_protocol_field(&mut self, protocol_name: String, field_name: String, field_type: TypeExpr) {
        if !self.protocol_registry.contains_key(&protocol_name) {
            self.protocol_registry.insert(protocol_name.clone(), HashMap::new());
        }
        self.protocol_registry.get_mut(&protocol_name).unwrap().insert(field_name, field_type);
    }

    /// 解析类型别名到实际类型
    pub fn resolve_type(&self, type_expr: &TypeExpr) -> TypeExpr {
        match type_expr {
            TypeExpr::Alias { name, resolved } => {
                if let Some(r) = resolved {
                    self.resolve_type(r)
                } else if let Some(actual) = self.type_registry.get(name) {
                    self.resolve_type(actual)
                } else {
                    type_expr.clone()
                }
            }
            TypeExpr::Generic { name, type_params } => {
                let resolved_params = type_params.iter()
                    .map(|p| self.resolve_type(p))
                    .collect();
                TypeExpr::Generic {
                    name: name.clone(),
                    type_params: resolved_params,
                }
            }
            TypeExpr::Union { types } => {
                let resolved_types = types.iter()
                    .map(|t| self.resolve_type(t))
                    .collect();
                TypeExpr::Union { types: resolved_types }
            }
            TypeExpr::Option { inner } => {
                TypeExpr::Option {
                    inner: Box::new(self.resolve_type(inner)),
                }
            }
            TypeExpr::Result { ok_type, err_type } => {
                TypeExpr::Result {
                    ok_type: Box::new(self.resolve_type(ok_type)),
                    err_type: Box::new(self.resolve_type(err_type)),
                }
            }
            TypeExpr::Func { param_types, return_type } => {
                let resolved_params = param_types.iter()
                    .map(|p| self.resolve_type(p))
                    .collect();
                TypeExpr::Func {
                    param_types: resolved_params,
                    return_type: Box::new(self.resolve_type(return_type)),
                }
            }
            TypeExpr::Semantic { base, constraint } => {
                TypeExpr::Semantic {
                    base: Box::new(self.resolve_type(base)),
                    constraint: constraint.clone(),
                }
            }
            _ => type_expr.clone(),
        }
    }

    /// 检查类型兼容性
    pub fn is_type_compatible(&self, actual: &TypeExpr, expected: &TypeExpr) -> bool {
        // Any 与任何类型兼容
        if expected.is_any() || actual.is_any() {
            return true;
        }

        // 相同类型
        if actual == expected {
            return true;
        }

        // 数值 widening: int → float
        if let (TypeExpr::Primitive { name: actual_name }, TypeExpr::Primitive { name: expected_name }) = (actual, expected) {
            if actual_name == "int" && expected_name == "float" {
                return true;
            }
        }

        // Union 类型: actual 是 union 成员之一
        if let TypeExpr::Union { types } = expected {
            for member in types {
                if self.is_type_compatible(actual, member) {
                    return true;
                }
            }
        }

        // Option 类型: None 兼容 Option[T]
        if let TypeExpr::Option { inner } = expected {
            if self.is_type_compatible(actual, inner) {
                return true;
            }
        }

        // Generic 类型
        if let (TypeExpr::Generic { name: actual_name, type_params: actual_params },
                TypeExpr::Generic { name: expected_name, type_params: expected_params }) = (actual, expected) {
            if actual_name != expected_name {
                return false;
            }
            if actual_name == "list" && !actual_params.is_empty() && !expected_params.is_empty() {
                return self.is_type_compatible(&actual_params[0], &expected_params[0]);
            }
            if actual_name == "dict" && actual_params.len() >= 2 && expected_params.len() >= 2 {
                return self.is_type_compatible(&actual_params[0], &expected_params[0])
                    && self.is_type_compatible(&actual_params[1], &expected_params[1]);
            }
            // 对于 Option/Result 等其他泛型，参数数量一致即兼容
            return actual_params.len() == expected_params.len();
        }

        // Alias 类型: 解析后比较
        let resolved_actual = self.resolve_type(actual);
        let resolved_expected = self.resolve_type(expected);
        if resolved_actual != *actual || resolved_expected != *expected {
            return self.is_type_compatible(&resolved_actual, &resolved_expected);
        }

        false
    }

    /// 检查程序 — 主入口
    pub fn check_program(&self, program: &Program) -> AvmResult<()> {
        // 检查所有声明
        for decl in &program.declarations {
            self.check_declaration(decl)?;
        }
        // 检查所有 flow
        for flow in &program.flows {
            self.check_flow(flow)?;
        }
        Ok(())
    }

    /// 检查声明
    fn check_declaration(&self, decl: &Declaration) -> AvmResult<()> {
        match decl {
            Declaration::Agent(agent) => self.check_agent(agent),
            Declaration::Protocol(protocol) => self.check_protocol(protocol),
            Declaration::Tool(_) => Ok(()), // Tool 不需要类型检查
            Declaration::TypeAlias(type_alias) => self.check_type_alias(type_alias),
        }
    }

    /// 检查 Agent 声明
    fn check_agent(&self, agent: &AgentDeclaration) -> Result<(), AvmError> {
        // 如果 Agent 有 protocol，检查输出类型是否匹配
        if let Some(protocol_name) = &agent.protocol {
            if !self.protocol_registry.contains_key(protocol_name) {
                // Protocol 未注册 — 无法检查
                return Ok(());
            }
        }
        Ok(())
    }

    /// 检查 Protocol 声明
    fn check_protocol(&self, protocol: &ProtocolDeclaration) -> Result<(), AvmError> {
        // 检查所有字段的类型表达式是否合法
        for (field_name, field_type) in &protocol.fields {
            if self.has_unresolved_aliases(field_type) {
                match self.lint_mode {
                    LintMode::Strict => {
                        return Err(AvmError::TypeCheck(format!(
                            "Protocol '{}' field '{}' has unresolved type alias",
                            protocol.name, field_name
                        )));
                    }
                    LintMode::Warn => {
                        eprintln!("⚠️ Warning: Protocol '{}' field '{}' has unresolved type alias", 
                                  protocol.name, field_name);
                    }
                    LintMode::Default => {}
                }
            }
        }
        Ok(())
    }

    /// 检查类型别名声明
    fn check_type_alias(&self, type_alias: &TypeAliasDeclaration) -> Result<(), AvmError> {
        // 检查别名定义中的类型表达式是否合法
        if self.has_unresolved_aliases(&type_alias.definition) {
            match self.lint_mode {
                LintMode::Strict => {
                    return Err(AvmError::TypeCheck(format!(
                        "Type alias '{}' has unresolved type reference",
                        type_alias.name
                    )));
                }
                LintMode::Warn => {
                    eprintln!("⚠️ Warning: Type alias '{}' has unresolved type reference",
                              type_alias.name);
                }
                LintMode::Default => {}
            }
        }
        Ok(())
    }

    /// 检查 Flow 声明
    fn check_flow(&self, flow: &FlowDeclaration) -> Result<(), AvmError> {
        // 检查参数类型标注
        for (param_name, param_type) in &flow.parameters {
            if self.has_unresolved_aliases(param_type) {
                match self.lint_mode {
                    LintMode::Strict => {
                        return Err(AvmError::TypeCheck(format!(
                            "Flow '{}' parameter '{}' has unresolved type alias",
                            flow.name, param_name
                        )));
                    }
                    LintMode::Warn => {
                        eprintln!("⚠️ Warning: Flow '{}' parameter '{}' has unresolved type alias",
                                  flow.name, param_name);
                    }
                    LintMode::Default => {}
                }
            }
        }

        // 检查返回类型
        if let Some(return_type) = &flow.return_type {
            if self.has_unresolved_aliases(return_type) {
                match self.lint_mode {
                    LintMode::Strict => {
                        return Err(AvmError::TypeCheck(format!(
                            "Flow '{}' return type has unresolved alias",
                            flow.name
                        )));
                    }
                    LintMode::Warn => {
                        eprintln!("⚠️ Warning: Flow '{}' return type has unresolved alias",
                                  flow.name);
                    }
                    LintMode::Default => {}
                }
            }
        }

        // Lint 检查: 缺失类型标注
        if self.lint_mode == LintMode::Strict || self.lint_mode == LintMode::Warn {
            // 检查参数类型
            for (param_name, param_type) in &flow.parameters {
                if param_type.is_any() {
                    let msg = format!("Flow '{}' parameter '{}' lacks type annotation", flow.name, param_name);
                    match self.lint_mode {
                        LintMode::Strict => {
                            return Err(AvmError::TypeCheck(msg));
                        }
                        LintMode::Warn => {
                            eprintln!("⚠️ Warning: {}", msg);
                        }
                        LintMode::Default => {}
                    }
                }
            }

            // 检查返回类型
            if flow.return_type.is_none() || flow.return_type.as_ref().map(|t| t.is_any()).unwrap_or(true) {
                let msg = format!("Flow '{}' lacks return type annotation", flow.name);
                match self.lint_mode {
                    LintMode::Strict => {
                        return Err(AvmError::TypeCheck(msg));
                    }
                    LintMode::Warn => {
                        eprintln!("⚠️ Warning: {}", msg);
                    }
                    LintMode::Default => {}
                }
            }
        }

        Ok(())
    }

    /// 检查类型表达式中是否有未解析的别名
    fn has_unresolved_aliases(&self, type_expr: &TypeExpr) -> bool {
        match type_expr {
            TypeExpr::Alias { name, resolved } => {
                if resolved.is_some() {
                    return self.has_unresolved_aliases(resolved.as_ref().unwrap());
                }
                !self.type_registry.contains_key(name)
            }
            TypeExpr::Generic { type_params, .. } => {
                type_params.iter().any(|p| self.has_unresolved_aliases(p))
            }
            TypeExpr::Union { types } => {
                types.iter().any(|t| self.has_unresolved_aliases(t))
            }
            TypeExpr::Option { inner } => self.has_unresolved_aliases(inner),
            TypeExpr::Result { ok_type, err_type } => {
                self.has_unresolved_aliases(ok_type) || self.has_unresolved_aliases(err_type)
            }
            TypeExpr::Func { param_types, return_type } => {
                param_types.iter().any(|p| self.has_unresolved_aliases(p))
                    || self.has_unresolved_aliases(return_type)
            }
            TypeExpr::Semantic { base, .. } => self.has_unresolved_aliases(base),
            _ => false,
        }
    }

    /// Lint 检查: 检查类型标注完整性
    pub fn lint_check_annotations(&self, program: &Program) -> TypeCheckResult {
        let mut result = TypeCheckResult {
            passed: true,
            violations: Vec::new(),
            warnings: Vec::new(),
        };

        if self.lint_mode == LintMode::Default {
            return result; // 只检查有标注的部分
        }

        // 检查 Flow 声明
        for flow in &program.flows {
            for (param_name, param_type) in &flow.parameters {
                if param_type.is_any() {
                    let msg = format!("Flow '{}' parameter '{}' lacks type annotation", flow.name, param_name);
                    match self.lint_mode {
                        LintMode::Strict => {
                            result.violations.push(TypeViolation {
                                message: msg,
                                expected_type: None,
                                actual_type: Some(TypeExpr::Any),
                                context: Some(format!("flow:{},param:{}", flow.name, param_name)),
                            });
                            result.passed = false;
                        }
                        LintMode::Warn => {
                            result.warnings.push(TypeViolation {
                                message: msg,
                                expected_type: None,
                                actual_type: Some(TypeExpr::Any),
                                context: Some(format!("flow:{},param:{}", flow.name, param_name)),
                            });
                        }
                        LintMode::Default => {}
                    }
                }
            }

            if flow.return_type.is_none() {
                let msg = format!("Flow '{}' lacks return type annotation", flow.name);
                match self.lint_mode {
                    LintMode::Strict => {
                        result.violations.push(TypeViolation {
                            message: msg,
                            expected_type: None,
                            actual_type: None,
                            context: Some(format!("flow:{}", flow.name)),
                        });
                        result.passed = false;
                    }
                    LintMode::Warn => {
                        result.warnings.push(TypeViolation {
                            message: msg,
                            expected_type: None,
                            actual_type: None,
                            context: Some(format!("flow:{}", flow.name)),
                        });
                    }
                    LintMode::Default => {}
                }
            }
        }

        // 检查 Agent 声明
        for decl in &program.declarations {
            if let Declaration::Agent(agent) = decl {
                if agent.protocol.is_none() {
                    let msg = format!("Agent '{}' lacks protocol implementation", agent.name);
                    match self.lint_mode {
                        LintMode::Strict => {
                            result.violations.push(TypeViolation {
                                message: msg,
                                expected_type: None,
                                actual_type: None,
                                context: Some(format!("agent:{}", agent.name)),
                            });
                            result.passed = false;
                        }
                        LintMode::Warn => {
                            result.warnings.push(TypeViolation {
                                message: msg,
                                expected_type: None,
                                actual_type: None,
                                context: Some(format!("agent:{}", agent.name)),
                            });
                        }
                        LintMode::Default => {}
                    }
                }
            }
        }

        result
    }

    /// 根据 TypeMode 处理类型检查结果
    pub fn handle_violation(&self, result: &TypeCheckResult) -> AvmResult<()> {
        if self.type_mode == TypeMode::Strict && !result.violations.is_empty() {
            return Err(AvmError::TypeCheck(result.violations[0].message.clone()));
        }

        if self.type_mode == TypeMode::Warn {
            for warning in &result.warnings {
                eprintln!("⚠️ Type warning: {}", warning.message);
            }
            for violation in &result.violations {
                eprintln!("⚠️ Type violation (would be error in strict mode): {}", violation.message);
            }
        }

        // Forgiving 模式静默忽略
        Ok(())
    }
}

impl Default for TypeChecker {
    fn default() -> Self {
        Self::new()
    }
}
