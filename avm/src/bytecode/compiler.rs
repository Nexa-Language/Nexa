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

//! 字节码编译器
//! 将 AST 编译为字节码

use crate::compiler::ast::*;
use crate::utils::error::{AvmError, AvmResult};
use super::instructions::*;
use std::collections::HashMap;

/// 字节码编译器
pub struct BytecodeCompiler {
    module: BytecodeModule,
    /// 局部变量表
    locals: Vec<HashMap<String, u32>>,
    /// 全局符号表
    globals: HashMap<String, u32>,
    /// 循环栈（用于 break/continue）
    loop_stack: Vec<LoopInfo>,
    /// 常量池索引
    constant_counter: u32,
}

/// 循环信息
struct LoopInfo {
    /// 循环起始位置
    start: u32,
    /// break 跳转目标列表
    break_jumps: Vec<u32>,
}

impl BytecodeCompiler {
    pub fn new(module_name: String) -> Self {
        Self {
            module: BytecodeModule::new(module_name),
            locals: vec![HashMap::new()],
            globals: HashMap::new(),
            loop_stack: Vec::new(),
            constant_counter: 0,
        }
    }

    /// 编译程序
    pub fn compile(mut self, program: &Program) -> AvmResult<BytecodeModule> {
        // 第一遍：收集所有声明
        for decl in &program.declarations {
            self.declare_symbol(decl)?;
        }

        // 编译所有声明
        for decl in &program.declarations {
            self.compile_declaration(decl)?;
        }

        // 编译入口 flow
        if let Some(main_flow) = program.flows.first() {
            self.module.entry_point = self.module.current_offset();
            self.compile_flow(main_flow)?;
        } else {
            // 如果没有 flow，设置默认入口
            self.module.entry_point = 0;
        }

        // 编译测试
        for test in &program.tests {
            self.compile_test(test)?;
        }

        self.module.emit(OpCode::Halt, None, None);
        Ok(self.module)
    }

    /// 声明符号
    fn declare_symbol(&mut self, decl: &Declaration) -> AvmResult<()> {
        match decl {
            Declaration::Tool(tool) => {
                let idx = self.add_constant(Constant::String(tool.name.clone()));
                self.globals.insert(tool.name.clone(), idx);
            }
            Declaration::Protocol(protocol) => {
                let idx = self.add_constant(Constant::String(protocol.name.clone()));
                self.globals.insert(protocol.name.clone(), idx);
            }
            Declaration::Agent(agent) => {
                let idx = self.add_constant(Constant::String(agent.name.clone()));
                self.globals.insert(agent.name.clone(), idx);
            }
            // v1.1: TypeAlias 声明 — 注册类型别名符号
            Declaration::TypeAlias(type_alias) => {
                let idx = self.add_constant(Constant::String(type_alias.name.clone()));
                self.globals.insert(type_alias.name.clone(), idx);
            }
        }
        Ok(())
    }

    /// 编译声明
    fn compile_declaration(&mut self, decl: &Declaration) -> AvmResult<()> {
        match decl {
            Declaration::Tool(tool) => self.compile_tool(tool),
            Declaration::Protocol(protocol) => self.compile_protocol(protocol),
            Declaration::Agent(agent) => self.compile_agent(agent),
            // v1.1: TypeAlias 声明 — 暂不生成字节码（类型在 AST 级别检查）
            Declaration::TypeAlias(_) => Ok(()),
        }
    }

    /// 编译 tool
    fn compile_tool(&mut self, tool: &ToolDeclaration) -> AvmResult<()> {
        // 工具注册
        let name_idx = self.add_constant(Constant::String(tool.name.clone()));
        
        // 描述
        let desc_idx = if let Some(desc) = &tool.description {
            self.add_constant(Constant::String(desc.clone()))
        } else {
            self.add_constant(Constant::Null)
        };

        // 参数 schema
        let params_idx = if let Some(params) = &tool.parameters {
            self.add_constant(Constant::Json(params.clone()))
        } else {
            self.add_constant(Constant::Null)
        };

        self.module.emit(OpCode::PushConst, Some(Operand::U32(name_idx)), None);
        self.module.emit(OpCode::PushConst, Some(Operand::U32(desc_idx)), None);
        self.module.emit(OpCode::PushConst, Some(Operand::U32(params_idx)), None);
        self.module.emit(OpCode::RegisterTool, Some(Operand::U8(3)), None);

        Ok(())
    }

    /// 编译 protocol
    fn compile_protocol(&mut self, protocol: &ProtocolDeclaration) -> AvmResult<()> {
        let _name_idx = self.add_constant(Constant::String(protocol.name.clone()));
        // Protocol 编译逻辑（简化）
        Ok(())
    }

    /// 编译 agent
    fn compile_agent(&mut self, agent: &AgentDeclaration) -> AvmResult<()> {
        let name_idx = self.add_constant(Constant::String(agent.name.clone()));
        
        // 编译 prompt
        let prompt_idx = if let Some(prompt) = &agent.prompt {
            self.add_constant(Constant::String(prompt.clone()))
        } else {
            self.add_constant(Constant::Null)
        };

        // 编译 role
        let role_idx = if let Some(role) = &agent.role {
            self.add_constant(Constant::String(role.clone()))
        } else {
            self.add_constant(Constant::Null)
        };

        // 编译 model
        let model_idx = if let Some(model) = &agent.model {
            self.add_constant(Constant::String(model.clone()))
        } else {
            self.add_constant(Constant::Null)
        };

        // 压入参数
        self.module.emit(OpCode::PushConst, Some(Operand::U32(name_idx)), None);
        self.module.emit(OpCode::PushConst, Some(Operand::U32(prompt_idx)), None);
        self.module.emit(OpCode::PushConst, Some(Operand::U32(role_idx)), None);
        self.module.emit(OpCode::PushConst, Some(Operand::U32(model_idx)), None);
        
        // 编译工具列表
        let tool_count = agent.tools.len() as u8;
        for tool in &agent.tools {
            self.compile_expression(tool)?;
        }

        self.module.emit(OpCode::CreateAgent, Some(Operand::U8(4 + tool_count)), None);

        Ok(())
    }

    /// 编译 flow
    fn compile_flow(&mut self, flow: &FlowDeclaration) -> AvmResult<()> {
        // 进入新的作用域
        self.push_scope();

        // v1.1: 编译参数（parameters 现在是 Vec<(String, TypeExpr)>）
        for (i, (param_name, _param_type)) in flow.parameters.iter().enumerate() {
            let local_idx = self.declare_local(param_name);
            self.module.emit(OpCode::StoreLocal, Some(Operand::U32(local_idx)), None);
        }

        // 编译 body
        for stmt in &flow.body {
            self.compile_statement(stmt)?;
        }

        // 离开作用域
        self.pop_scope();

        Ok(())
    }

    /// 编译 test
    fn compile_test(&mut self, test: &TestDeclaration) -> AvmResult<()> {
        self.push_scope();
        for stmt in &test.body {
            self.compile_statement(stmt)?;
        }
        self.pop_scope();
        Ok(())
    }

    /// 编译语句
    fn compile_statement(&mut self, stmt: &Statement) -> AvmResult<()> {
        match stmt {
            Statement::Expression(expr) => {
                self.compile_expression(expr)?;
                // 表达式语句的结果弹出
                self.module.emit(OpCode::Pop, None, None);
            }
            Statement::Assignment { target, value, is_semantic: _ } => {
                self.compile_assignment(target, value)?;
            }
            Statement::TryCatch { try_body, catch_var, catch_body } => {
                self.compile_try_catch(try_body, catch_var, catch_body)?;
            }
            Statement::Assert { condition, message } => {
                self.compile_assert(condition, message)?;
            }
            Statement::SemanticIf { branches, else_body } => {
                self.compile_semantic_if(branches, else_body)?;
            }
            Statement::Loop { condition, body } => {
                self.compile_loop(condition, body)?;
            }
            Statement::Match { input, cases } => {
                self.compile_match(input, cases)?;
            }
            Statement::Return(value) => {
                if let Some(expr) = value {
                    self.compile_expression(expr)?;
                } else {
                    self.module.emit(OpCode::PushNull, None, None);
                }
                self.module.emit(OpCode::Return, None, None);
            }
            // v1.2: Error Propagation — ? 操作符和 otherwise 内联错误处理
            Statement::TryAssignment { target, expression } => {
                // x = expr? → 编译表达式，然后 try unwrap
                // 简化实现：编译表达式后检查是否为 NexaResult
                // 完整实现需要 TryUnwrap opcode
                self.compile_expression(expression)?;
                // 将结果存储到 target 变量（暂不实现 unwrap）
                if let Some(idx) = self.globals.get(target) {
                    self.module.emit(OpCode::StoreGlobal, Some(Operand::U32(*idx)), None);
                } else {
                    let idx = self.add_constant(Constant::String(target.clone()));
                    self.module.emit(OpCode::StoreGlobal, Some(Operand::U32(idx)), None);
                }
            }
            Statement::OtherwiseAssignment { target, expression, handler: _ } => {
                // x = expr otherwise handler → 编译表达式，fallback 处理
                // 简化实现：编译表达式后存储到 target
                self.compile_expression(expression)?;
                if let Some(idx) = self.globals.get(target) {
                    self.module.emit(OpCode::StoreGlobal, Some(Operand::U32(*idx)), None);
                } else {
                    let idx = self.add_constant(Constant::String(target.clone()));
                    self.module.emit(OpCode::StoreGlobal, Some(Operand::U32(idx)), None);
                }
            }
            Statement::TryExpression(expr) => {
                // expr? → 编译表达式，暂作为普通表达式处理
                self.compile_expression(expr)?;
                self.module.emit(OpCode::Pop, None, None);
            }
            Statement::Break => {
                if let Some(loop_info) = self.loop_stack.last_mut() {
                    self.module.emit(OpCode::PushNull, None, None);
                    let jump_offset = self.module.current_offset();
                    self.module.emit(OpCode::Jump, None, None);
                    loop_info.break_jumps.push(jump_offset);
                }
            }
            Statement::Continue => {
                if let Some(loop_info) = self.loop_stack.last() {
                    let offset = loop_info.start;
                    self.module.emit(OpCode::Jump, Some(Operand::U32(offset)), None);
                }
            }
        }
        Ok(())
    }

    /// 编译赋值
    fn compile_assignment(&mut self, target: &Expression, value: &Expression) -> AvmResult<()> {
        // 编译值
        self.compile_expression(value)?;

        match target {
            Expression::Identifier(name) => {
                if let Some(idx) = self.lookup_local(name) {
                    self.module.emit(OpCode::StoreLocal, Some(Operand::U32(idx)), None);
                } else if let Some(&idx) = self.globals.get(name) {
                    self.module.emit(OpCode::StoreGlobal, Some(Operand::U32(idx)), None);
                } else {
                    // 新建局部变量
                    let idx = self.declare_local(name);
                    self.module.emit(OpCode::StoreLocal, Some(Operand::U32(idx)), None);
                }
            }
            Expression::Index { object, index } => {
                self.compile_expression(object)?;
                self.compile_expression(index)?;
                self.module.emit(OpCode::SetAttr, None, None);
            }
            Expression::PropertyAccess { object, property } => {
                self.compile_expression(object)?;
                let prop_idx = self.add_constant(Constant::String(property.clone()));
                self.module.emit(OpCode::PushConst, Some(Operand::U32(prop_idx)), None);
                self.module.emit(OpCode::SetAttr, None, None);
            }
            _ => {
                return Err(AvmError::CompilationError("Invalid assignment target".to_string()));
            }
        }

        Ok(())
    }

    /// 编译 try-catch
    fn compile_try_catch(
        &mut self,
        try_body: &[Statement],
        catch_var: &str,
        catch_body: &[Statement],
    ) -> AvmResult<()> {
        // 简化的 try-catch 实现
        // 在实际实现中需要异常表
        
        let try_start = self.module.current_offset();
        
        self.push_scope();
        for stmt in try_body {
            self.compile_statement(stmt)?;
        }
        self.pop_scope();

        let try_end = self.module.current_offset();
        
        // 跳过 catch 块
        let jump_over_catch = self.module.current_offset();
        self.module.emit(OpCode::Jump, None, None);

        // Catch 块
        let catch_start = self.module.current_offset();
        
        self.push_scope();
        let var_idx = self.declare_local(catch_var);
        self.module.emit(OpCode::StoreLocal, Some(Operand::U32(var_idx)), None);
        
        for stmt in catch_body {
            self.compile_statement(stmt)?;
        }
        self.pop_scope();

        // 修复跳转
        let catch_end = self.module.current_offset();
        self.patch_jump(jump_over_catch, catch_end);

        // 记录异常处理范围（简化）
        let _ = (try_start, try_end, catch_start);

        Ok(())
    }

    /// 编译 assert
    fn compile_assert(&mut self, condition: &Expression, message: &Option<String>) -> AvmResult<()> {
        self.compile_expression(condition)?;
        
        // 反转条件，如果为假则触发断言失败
        let jump_offset = self.module.current_offset();
        self.module.emit(OpCode::JumpIfTrue, None, None);

        // 断言失败
        if let Some(msg) = message {
            let msg_idx = self.add_constant(Constant::String(msg.clone()));
            self.module.emit(OpCode::PushConst, Some(Operand::U32(msg_idx)), None);
        } else {
            self.module.emit(OpCode::PushNull, None, None);
        }
        // 触发断言错误（简化为运行时错误）
        self.module.emit(OpCode::Halt, None, None);

        // 断言通过
        let end_offset = self.module.current_offset();
        self.patch_jump(jump_offset, end_offset);

        Ok(())
    }

    /// 编译 semantic_if
    fn compile_semantic_if(
        &mut self,
        branches: &[(Expression, Vec<Statement>)],
        else_body: &[Statement],
    ) -> AvmResult<()> {
        let mut end_jumps = Vec::new();

        for (condition, body) in branches {
            // 编译条件
            self.compile_expression(condition)?;

            // 条件跳转
            let jump_offset = self.module.current_offset();
            self.module.emit(OpCode::JumpIfFalse, None, None);

            // 编译 body
            self.push_scope();
            for stmt in body {
                self.compile_statement(stmt)?;
            }
            self.pop_scope();

            // 跳转到结尾
            let end_jump = self.module.current_offset();
            self.module.emit(OpCode::Jump, None, None);
            end_jumps.push(end_jump);

            // 修复条件跳转
            let next_offset = self.module.current_offset();
            self.patch_jump(jump_offset, next_offset);
        }

        // else 分支
        if !else_body.is_empty() {
            self.push_scope();
            for stmt in else_body {
                self.compile_statement(stmt)?;
            }
            self.pop_scope();
        }

        // 修复所有结尾跳转
        let end_offset = self.module.current_offset();
        for jump in end_jumps {
            self.patch_jump(jump, end_offset);
        }

        Ok(())
    }

    /// 编译 loop
    fn compile_loop(&mut self, condition: &Expression, body: &[Statement]) -> AvmResult<()> {
        let loop_start = self.module.current_offset();

        // 创建循环信息
        let loop_info = LoopInfo {
            start: loop_start,
            break_jumps: Vec::new(),
        };
        self.loop_stack.push(loop_info);

        // 编译条件
        self.compile_expression(condition)?;

        // 如果条件为假，退出循环
        let exit_jump = self.module.current_offset();
        self.module.emit(OpCode::JumpIfFalse, None, None);

        // 编译 body
        self.push_scope();
        for stmt in body {
            self.compile_statement(stmt)?;
        }
        self.pop_scope();

        // 跳回循环开始
        self.module.emit(OpCode::Jump, Some(Operand::U32(loop_start)), None);

        // 修复退出跳转
        let loop_end = self.module.current_offset();
        self.patch_jump(exit_jump, loop_end);

        // 修复所有 break 跳转
        if let Some(loop_info) = self.loop_stack.pop() {
            for jump in loop_info.break_jumps {
                self.patch_jump(jump, loop_end);
            }
        }

        Ok(())
    }

    /// 编译 match
    fn compile_match(&mut self, input: &Expression, cases: &[MatchCase]) -> AvmResult<()> {
        // 编译输入
        self.compile_expression(input)?;

        let mut end_jumps = Vec::new();

        for case in cases {
            // 编译模式匹配
            match &case.pattern {
                Pattern::Wildcard => {
                    // 总是匹配
                }
                Pattern::Literal(lit) => {
                    self.module.emit(OpCode::Dup, None, None);
                    self.compile_expression(lit)?;
                    self.module.emit(OpCode::Eq, None, None);
                }
                Pattern::Variable(name) => {
                    // 绑定变量
                    let idx = self.declare_local(name);
                    self.module.emit(OpCode::Dup, None, None);
                    self.module.emit(OpCode::StoreLocal, Some(Operand::U32(idx)), None);
                    self.module.emit(OpCode::PushTrue, None, None);
                }
                Pattern::Constructor { name, fields } => {
                    // 简化：检查类型名
                    let name_idx = self.add_constant(Constant::String(name.clone()));
                    self.module.emit(OpCode::Dup, None, None);
                    self.module.emit(OpCode::PushConst, Some(Operand::U32(name_idx)), None);
                    self.module.emit(OpCode::Eq, None, None);
                    let _ = fields; // 忽略字段匹配
                }
            }

            // 检查匹配
            let skip_jump = self.module.current_offset();
            self.module.emit(OpCode::JumpIfFalse, None, None);

            // 匹配成功，弹出输入值
            self.module.emit(OpCode::Pop, None, None);

            // 编译 body
            self.push_scope();
            for stmt in &case.body {
                self.compile_statement(stmt)?;
            }
            self.pop_scope();

            // 跳转到结尾
            let end_jump = self.module.current_offset();
            self.module.emit(OpCode::Jump, None, None);
            end_jumps.push(end_jump);

            // 修复跳过跳转
            let next_offset = self.module.current_offset();
            self.patch_jump(skip_jump, next_offset);
        }

        // 未匹配，弹出输入值
        self.module.emit(OpCode::Pop, None, None);

        // 修复所有结尾跳转
        let end_offset = self.module.current_offset();
        for jump in end_jumps {
            self.patch_jump(jump, end_offset);
        }

        Ok(())
    }

    /// 编译表达式
    fn compile_expression(&mut self, expr: &Expression) -> AvmResult<()> {
        match expr {
            Expression::Null => {
                self.module.emit(OpCode::PushNull, None, None);
            }
            Expression::Bool(b) => {
                if *b {
                    self.module.emit(OpCode::PushTrue, None, None);
                } else {
                    self.module.emit(OpCode::PushFalse, None, None);
                }
            }
            Expression::Integer(n) => {
                let idx = self.add_constant(Constant::Integer(*n));
                self.module.emit(OpCode::PushConst, Some(Operand::U32(idx)), None);
            }
            Expression::Float(f) => {
                let idx = self.add_constant(Constant::Float(*f));
                self.module.emit(OpCode::PushConst, Some(Operand::U32(idx)), None);
            }
            Expression::String(s) => {
                let idx = self.add_constant(Constant::String(s.clone()));
                self.module.emit(OpCode::PushConst, Some(Operand::U32(idx)), None);
            }
            // v1.2: TryOp — ? 操作符表达式（错误传播）
            // 简化实现：编译内部表达式（暂不实现 unwrap opcode）
            Expression::TryOp { expression } => {
                self.compile_expression(expression)?;
            }
            Expression::Identifier(name) => {
                if let Some(idx) = self.lookup_local(name) {
                    self.module.emit(OpCode::LoadLocal, Some(Operand::U32(idx)), None);
                } else if let Some(&idx) = self.globals.get(name) {
                    self.module.emit(OpCode::LoadGlobal, Some(Operand::U32(idx)), None);
                } else {
                    // 作为字符串常量处理
                    let idx = self.add_constant(Constant::String(name.clone()));
                    self.module.emit(OpCode::PushConst, Some(Operand::U32(idx)), None);
                }
            }
            Expression::List(elements) => {
                for elem in elements {
                    self.compile_expression(elem)?;
                }
                self.module.emit(OpCode::MakeList, Some(Operand::U32(elements.len() as u32)), None);
            }
            Expression::Dict(pairs) => {
                for (key, value) in pairs {
                    let key_idx = self.add_constant(Constant::String(key.clone()));
                    self.module.emit(OpCode::PushConst, Some(Operand::U32(key_idx)), None);
                    self.compile_expression(value)?;
                }
                self.module.emit(OpCode::MakeDict, Some(Operand::U32(pairs.len() as u32)), None);
            }
            Expression::BinaryOp { left, op, right } => {
                self.compile_expression(left)?;
                self.compile_expression(right)?;
                self.compile_binary_op(op)?;
            }
            Expression::UnaryOp { op, operand } => {
                self.compile_expression(operand)?;
                self.compile_unary_op(op)?;
            }
            Expression::Pipeline { left, right } => {
                self.compile_expression(left)?;
                self.compile_expression(right)?;
                self.module.emit(OpCode::PipeAgent, None, None);
            }
            Expression::AgentCall { name, args, kwargs } => {
                // 压入参数
                for arg in args {
                    self.compile_expression(arg)?;
                }
                for (key, value) in kwargs {
                    let key_idx = self.add_constant(Constant::String(key.clone()));
                    self.module.emit(OpCode::PushConst, Some(Operand::U32(key_idx)), None);
                    self.compile_expression(value)?;
                }

                let name_idx = self.add_constant(Constant::String(name.clone()));
                self.module.emit(OpCode::PushConst, Some(Operand::U32(name_idx)), None);
                
                let total_args = args.len() as u8 + (kwargs.len() * 2) as u8 + 1;
                self.module.emit(OpCode::CallAgent, Some(Operand::U8(total_args)), None);
            }
            Expression::MethodCall { object, method, args, kwargs } => {
                self.compile_expression(object)?;
                
                for arg in args {
                    self.compile_expression(arg)?;
                }
                for (key, value) in kwargs {
                    let key_idx = self.add_constant(Constant::String(key.clone()));
                    self.module.emit(OpCode::PushConst, Some(Operand::U32(key_idx)), None);
                    self.compile_expression(value)?;
                }

                let method_idx = self.add_constant(Constant::String(method.clone()));
                self.module.emit(OpCode::PushConst, Some(Operand::U32(method_idx)), None);

                let total_args = 1 + args.len() as u8 + (kwargs.len() * 2) as u8 + 1;
                self.module.emit(OpCode::Call, Some(Operand::U8(total_args)), None);
            }
            Expression::Index { object, index } => {
                self.compile_expression(object)?;
                self.compile_expression(index)?;
                self.module.emit(OpCode::Index, None, None);
            }
            Expression::PropertyAccess { object, property } => {
                self.compile_expression(object)?;
                let prop_idx = self.add_constant(Constant::String(property.clone()));
                self.module.emit(OpCode::PushConst, Some(Operand::U32(prop_idx)), None);
                self.module.emit(OpCode::GetAttr, None, None);
            }
            Expression::JoinCall { agents, merge_strategy, merge_agent } => {
                for agent in agents {
                    self.compile_expression(agent)?;
                }
                
                let strategy_idx = self.add_constant(Constant::String(merge_strategy.clone()));
                self.module.emit(OpCode::PushConst, Some(Operand::U32(strategy_idx)), None);

                if let Some(agent_name) = merge_agent {
                    let agent_idx = self.add_constant(Constant::String(agent_name.clone()));
                    self.module.emit(OpCode::PushConst, Some(Operand::U32(agent_idx)), None);
                } else {
                    self.module.emit(OpCode::PushNull, None, None);
                }

                self.module.emit(OpCode::JoinAgents, Some(Operand::U32(agents.len() as u32)), None);
            }
            Expression::DagFork(fork) => {
                self.compile_expression(&fork.input)?;
                for target in &fork.targets {
                    self.compile_expression(target)?;
                }
                self.module.emit(OpCode::ForkAgent, Some(Operand::U32(fork.targets.len() as u32)), None);
            }
            Expression::DagMerge(merge) => {
                for input in &merge.inputs {
                    self.compile_expression(input)?;
                }
                let strategy_idx = self.add_constant(Constant::String(merge.merge_strategy.clone()));
                self.module.emit(OpCode::PushConst, Some(Operand::U32(strategy_idx)), None);
                
                if let Some(agent_name) = &merge.merge_agent {
                    let agent_idx = self.add_constant(Constant::String(agent_name.clone()));
                    self.module.emit(OpCode::PushConst, Some(Operand::U32(agent_idx)), None);
                } else {
                    self.module.emit(OpCode::PushNull, None, None);
                }

                self.module.emit(OpCode::MergeAgent, Some(Operand::U32(merge.inputs.len() as u32)), None);
            }
            Expression::DagBranch(branch) => {
                self.compile_expression(&branch.input)?;
                self.compile_expression(&branch.condition)?;
                self.compile_expression(&branch.true_branch)?;
                
                if let Some(false_branch) = &branch.false_branch {
                    self.compile_expression(false_branch)?;
                } else {
                    self.module.emit(OpCode::PushNull, None, None);
                }

                self.module.emit(OpCode::BranchAgent, None, None);
            }
        }

        Ok(())
    }

    /// 编译二元运算符
    fn compile_binary_op(&mut self, op: &str) -> AvmResult<()> {
        match op {
            "+" => self.module.emit(OpCode::Add, None, None),
            "-" => self.module.emit(OpCode::Sub, None, None),
            "*" => self.module.emit(OpCode::Mul, None, None),
            "/" => self.module.emit(OpCode::Div, None, None),
            "%" => self.module.emit(OpCode::Mod, None, None),
            "==" => self.module.emit(OpCode::Eq, None, None),
            "!=" => self.module.emit(OpCode::Ne, None, None),
            "<" => self.module.emit(OpCode::Lt, None, None),
            "<=" => self.module.emit(OpCode::Le, None, None),
            ">" => self.module.emit(OpCode::Gt, None, None),
            ">=" => self.module.emit(OpCode::Ge, None, None),
            "&&" => self.module.emit(OpCode::And, None, None),
            "||" => self.module.emit(OpCode::Or, None, None),
            "?=" => self.module.emit(OpCode::SemanticEq, None, None),
            "~=" => self.module.emit(OpCode::SemanticMatch, None, None),
            _ => return Err(AvmError::CompilationError(format!("Unknown binary operator: {}", op))),
        }
        Ok(())
    }

    /// 编译一元运算符
    fn compile_unary_op(&mut self, op: &str) -> AvmResult<()> {
        match op {
            "-" => self.module.emit(OpCode::Neg, None, None),
            "!" => self.module.emit(OpCode::Not, None, None),
            _ => return Err(AvmError::CompilationError(format!("Unknown unary operator: {}", op))),
        }
        Ok(())
    }

    // ==================== 辅助方法 ====================

    fn push_scope(&mut self) {
        self.locals.push(HashMap::new());
    }

    fn pop_scope(&mut self) {
        self.locals.pop();
    }

    fn declare_local(&mut self, name: &str) -> u32 {
        let scope = self.locals.last_mut().unwrap();
        let idx = scope.len() as u32;
        scope.insert(name.to_string(), idx);
        idx
    }

    fn lookup_local(&self, name: &str) -> Option<u32> {
        for scope in self.locals.iter().rev() {
            if let Some(&idx) = scope.get(name) {
                return Some(idx);
            }
        }
        None
    }

    fn add_constant(&mut self, constant: Constant) -> u32 {
        let idx = self.constant_counter;
        self.constant_counter += 1;
        self.module.constants.push(constant);
        idx
    }

    fn patch_jump(&mut self, offset: u32, target: u32) {
        // 简化：在实际实现中需要修改指令的操作数
        let _ = (offset, target);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compiler_creation() {
        let compiler = BytecodeCompiler::new("test".to_string());
        assert_eq!(compiler.module.name, "test");
    }

    #[test]
    fn test_compile_empty_program() {
        let program = Program::default();
        let compiler = BytecodeCompiler::new("test".to_string());
        let result = compiler.compile(&program);
        assert!(result.is_ok());
    }

    #[test]
    fn test_compile_simple_flow() {
        let program = Program {
            declarations: vec![],
            flows: vec![FlowDeclaration {
                name: "main".to_string(),
                parameters: vec![],
                body: vec![],
            }],
            tests: vec![],
        };

        let compiler = BytecodeCompiler::new("test".to_string());
        let result = compiler.compile(&program);
        assert!(result.is_ok());

        let module = result.unwrap();
        assert!(module.instructions.len() > 0);
    }

    #[test]
    fn test_compile_agent() {
        let program = Program {
            declarations: vec![Declaration::Agent(AgentDeclaration {
                name: "TestAgent".to_string(),
                prompt: Some("You are helpful".to_string()),
                role: Some("assistant".to_string()),
                model: None,
                tools: vec![],
                protocol: None,
                memory_scope: None,
                max_history_turns: None,
            })],
            flows: vec![],
            tests: vec![],
        };

        let compiler = BytecodeCompiler::new("test".to_string());
        let result = compiler.compile(&program);
        assert!(result.is_ok());
    }
}
