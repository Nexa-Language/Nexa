//! 语法解析器 - 递归下降解析
//! 解析 Nexa 源代码并生成 AST

use crate::compiler::ast::*;
use crate::compiler::lexer::{Token, TokenWithSpan, tokenize};
use crate::utils::error::{AvmError, AvmResult};

/// Parser 结构
pub struct Parser {
    tokens: Vec<TokenWithSpan>,
    pos: usize,
}

impl Parser {
    pub fn new(tokens: Vec<TokenWithSpan>) -> Self {
        Self { tokens, pos: 0 }
    }

    /// 从源码解析
    pub fn parse_from_source(source: &str) -> AvmResult<Program> {
        let result = tokenize(source);
        if !result.errors.is_empty() {
            return Err(AvmError::LexicalError(
                result.errors.iter()
                    .map(|(msg, _)| msg.clone())
                    .collect::<Vec<_>>()
                    .join("; ")
            ));
        }
        let mut parser = Parser::new(result.tokens);
        parser.parse()
    }

    /// 主解析函数
    pub fn parse(&mut self) -> AvmResult<Program> {
        let mut program = Program::default();

        while !self.is_at_end() {
            match self.peek_token() {
                Token::Tool => {
                    program.declarations.push(Declaration::Tool(self.parse_tool()?));
                }
                Token::Protocol => {
                    program.declarations.push(Declaration::Protocol(self.parse_protocol()?));
                }
                Token::Agent => {
                    program.declarations.push(Declaration::Agent(self.parse_agent()?));
                }
                Token::Flow => {
                    program.flows.push(self.parse_flow()?);
                }
                Token::Test => {
                    program.tests.push(self.parse_test()?);
                }
                Token::Job => {
                    program.declarations.push(Declaration::Job(self.parse_job()?));
                }
                _ => {
                    return Err(AvmError::ParseError(
                        format!("Unexpected token at top level: {:?}", self.peek_token())
                    ));
                }
            }
        }

        Ok(program)
    }

    // ==================== 声明解析 ====================

    /// 解析 tool 声明
    fn parse_tool(&mut self) -> AvmResult<ToolDeclaration> {
        self.expect(Token::Tool)?;
        let name = self.expect_identifier()?;
        
        let mut description = None;
        let mut parameters = None;
        let mut body = Vec::new();

        self.expect(Token::LBrace)?;
        
        while !self.check(Token::RBrace) && !self.is_at_end() {
            match self.peek_token() {
                Token::String(s) => {
                    description = Some(s);
                    self.advance();
                }
                Token::Identifier => {
                    let prop = self.advance_identifier()?;
                    self.expect(Token::Colon)?;
                    
                    if prop == "parameters" || prop == "params" {
                        parameters = Some(self.parse_json_value()?);
                    } else {
                        // 其他属性作为语句处理
                        body.push(self.parse_statement()?);
                    }
                }
                _ => {
                    body.push(self.parse_statement()?);
                }
            }
        }
        
        self.expect(Token::RBrace)?;
        
        Ok(ToolDeclaration {
            name,
            description,
            parameters,
            body,
        })
    }

    /// 解析 protocol 声明
    fn parse_protocol(&mut self) -> AvmResult<ProtocolDeclaration> {
        self.expect(Token::Protocol)?;
        let name = self.expect_identifier()?;
        
        let mut schema = None;
        let mut body = Vec::new();

        self.expect(Token::LBrace)?;
        
        while !self.check(Token::RBrace) && !self.is_at_end() {
            match self.peek_token() {
                Token::Identifier => {
                    let prop = self.advance_identifier()?;
                    self.expect(Token::Colon)?;
                    
                    if prop == "schema" {
                        schema = Some(self.parse_json_value()?);
                    } else {
                        body.push(self.parse_statement()?);
                    }
                }
                _ => {
                    body.push(self.parse_statement()?);
                }
            }
        }
        
        self.expect(Token::RBrace)?;
        
        Ok(ProtocolDeclaration {
            name,
            fields: Vec::new(),  // v1.1: 从 schema 提取字段（简化处理）
            schema,
            body,
        })
    }

    /// 解析 agent 声明
    fn parse_agent(&mut self) -> AvmResult<AgentDeclaration> {
        self.expect(Token::Agent)?;
        let name = self.expect_identifier()?;
        
        let mut prompt = None;
        let mut role = None;
        let mut model = None;
        let mut tools = Vec::new();
        let mut protocol = None;
        let mut memory_scope = None;
        let mut max_history_turns = None;
        let mut requires_clauses = Vec::new();
        let mut ensures_clauses = Vec::new();

        // 解析 requires/ensures 契约条款（在 { 之前）
        while self.check(Token::Requires) || self.check(Token::Ensures) {
            if self.check(Token::Requires) {
                self.advance(); // 消费 requires
                requires_clauses.push(self.parse_contract_clause("requires")?);
            } else if self.check(Token::Ensures) {
                self.advance(); // 消费 ensures
                ensures_clauses.push(self.parse_contract_clause("ensures")?);
            }
        }

        self.expect(Token::LBrace)?;
        
        while !self.check(Token::RBrace) && !self.is_at_end() {
            // 获取属性名（可能是关键字或标识符）
            let prop = match self.peek_token() {
                Token::Role => "role".to_string(),
                Token::Model => "model".to_string(),
                Token::Prompt => "prompt".to_string(),
                Token::Uses => "uses".to_string(),
                Token::Implements => "implements".to_string(),
                Token::Identifier => self.peek_text().clone(),
                _ => {
                    // 跳过非属性 token
                    self.advance();
                    continue;
                }
            };
            self.advance(); // 消费属性名 token
            self.expect(Token::Colon)?;
            
            match prop.as_str() {
                "prompt" => prompt = Some(self.parse_string_literal()?),
                "role" => role = Some(self.parse_string_literal()?),
                "model" => model = Some(self.parse_string_literal()?),
                "uses" | "tools" => tools = self.parse_expression_list()?,
                "protocol" | "implements" => protocol = Some(self.expect_identifier()?),
                "memory_scope" => memory_scope = Some(self.expect_identifier()?),
                "max_history_turns" => {
                    if let Token::Int(n) = self.peek_token() {
                        max_history_turns = Some(n as u32);
                        self.advance();
                    }
                }
                _ => {
                    // 跳过未知属性
                    self.parse_expression()?;
                }
            }
            
            // 可选的分号
            if self.check(Token::Semicolon) {
                self.advance();
            }
        }
        
        self.expect(Token::RBrace)?;
        
        // 构建 ContractSpec
        let contracts = if requires_clauses.is_empty() && ensures_clauses.is_empty() {
            None
        } else {
            Some(ContractSpec {
                requires: requires_clauses,
                ensures: ensures_clauses,
            })
        };
        
        Ok(AgentDeclaration {
            input_type: None,    // v1.1: 输入类型
            output_type: None,   // v1.1: 输出类型
            name,
            prompt,
            role,
            model,
            tools,
            protocol,
            memory_scope,
            max_history_turns,
            contracts,
        })
    }
    
    /// 解析契约条款: requires/ensures 后跟字符串（语义）或表达式（确定性）
    fn parse_contract_clause(&mut self, clause_type: &str) -> AvmResult<ContractClause> {
        // 检查是语义契约（字符串）还是确定性契约（表达式）
        if let Token::String(s) = self.peek_token() {
            // 语义契约: requires "natural language condition"
            let condition_text = s;
            self.advance();
            Ok(ContractClause {
                expression: None,
                condition_text: Some(condition_text),
                is_semantic: true,
                clause_type: clause_type.to_string(),
                message: None,
            })
        } else {
            // 硯定性契约: requires amount > 0
            // 解析为表达式字符串
            let expr_str = self.parse_comparison_expression_string()?;
            Ok(ContractClause {
                expression: Some(expr_str),
                condition_text: None,
                is_semantic: false,
                clause_type: clause_type.to_string(),
                message: None,
            })
        }
    }
    
    /// 解析比较表达式并将其转换为字符串表示
    fn parse_comparison_expression_string(&mut self) -> AvmResult<String> {
        // 左侧
        let left = self.parse_expression_term_string()?;
        
        // 比较操作符（使用 CmpOp token）
        let op = match self.peek_token() {
            Token::CmpOp => {
                let text = self.peek_text().clone();
                self.advance();
                text
            }
            _ => return Ok(left), // 没有比较操作符，返回单个表达式
        };
        
        // 右侧
        let right = self.parse_expression_term_string()?;
        
        Ok(format!("{} {} {}", left, op, right))
    }
    
    /// 解析表达式项（标识符、字面量、属性访问）并转换为字符串
    fn parse_expression_term_string(&mut self) -> AvmResult<String> {
        match self.peek_token() {
            Token::Identifier => {
                let name = self.peek_text().clone();
                self.advance();
                // 检查是否有属性访问 (如 result.field)
                if self.check(Token::Dot) {
                    self.advance();
                    let prop = self.peek_text().clone();
                    self.expect_identifier()?;
                    Ok(format!("{}.{}", name, prop))
                } else {
                    Ok(name)
                }
            }
            Token::Int(n) => {
                self.advance();
                Ok(n.to_string())
            }
            Token::Float(f) => {
                self.advance();
                Ok(f.to_string())
            }
            Token::String(s) => {
                self.advance();
                Ok(format!("\"{}\"", s))
            }
            Token::Bool(b) => {
                self.advance();
                Ok(b.to_string())
            }
            _ => Err(AvmError::ParseError(
                format!("Expected expression term in contract clause, got {:?}", self.peek_token())
            )),
        }
    }

    /// 解析 flow 声明
    fn parse_flow(&mut self) -> AvmResult<FlowDeclaration> {
        self.expect(Token::Flow)?;
        let name = self.expect_identifier()?;
        
        // v1.1: parameters 现在是 Vec<(String, TypeExpr)>
        let mut parameters: Vec<(String, TypeExpr)> = Vec::new();
        let mut requires_clauses = Vec::new();
        let mut ensures_clauses = Vec::new();
        
        // 可选参数列表 — v1.1: 支持 name: type_expr 格式
        if self.check(Token::LParen) {
            self.advance();
            if !self.check(Token::RParen) {
                loop {
                    let param_name = self.expect_identifier()?;
                    let param_type = if self.check(Token::Colon) {
                        self.advance();
                        TypeExpr::Any  // 简化：暂不解析完整类型表达式
                    } else {
                        TypeExpr::Any
                    };
                    parameters.push((param_name, param_type));
                    if !self.match_token(Token::Comma) {
                        break;
                    }
                }
            }
            self.expect(Token::RParen)?;
        }
        
        // 解析 requires/ensures 契约条款（在 { 之前）
        while self.check(Token::Requires) || self.check(Token::Ensures) {
            if self.check(Token::Requires) {
                self.advance(); // 消费 requires
                requires_clauses.push(self.parse_contract_clause("requires")?);
            } else if self.check(Token::Ensures) {
                self.advance(); // 消费 ensures
                ensures_clauses.push(self.parse_contract_clause("ensures")?);
            }
        }
        
        self.expect(Token::LBrace)?;
        let body = self.parse_block_body()?;
        self.expect(Token::RBrace)?;
        
        // 构建 ContractSpec
        let contracts = if requires_clauses.is_empty() && ensures_clauses.is_empty() {
            None
        } else {
            Some(ContractSpec {
                requires: requires_clauses,
                ensures: ensures_clauses,
            })
        };
        
        Ok(FlowDeclaration {
            return_type: None,   // v1.1: 返回类型
            name,
            parameters,
            body,
            contracts,
        })
    }

    /// 解析 test 声明
    fn parse_test(&mut self) -> AvmResult<TestDeclaration> {
        self.expect(Token::Test)?;
        let name = self.expect_identifier()?;
        
        self.expect(Token::LBrace)?;
        let body = self.parse_block_body()?;
        self.expect(Token::RBrace)?;
        
        Ok(TestDeclaration {
            name,
            body,
        })
    }

    /// P1-3: 解析 job 声明
    ///
    /// 语法: job Name on "queue" [(options)] { config* perform(params) { body } [on_failure(err, attempt) { body }] }
    fn parse_job(&mut self) -> AvmResult<JobDeclaration> {
        self.expect(Token::Job)?;
        let name = self.expect_identifier()?;
        self.expect(Token::On)?;
        let queue = self.expect_string()?;
        
        // 解析可选的 inline options: (retry: 2, timeout: 120)
        let mut options = Vec::new();
        if self.check(Token::LParen) {
            self.advance(); // consume (
            while !self.check(Token::RParen) && !self.is_at_end() {
                let key = self.expect_identifier()?;
                self.expect(Token::Assign)?;
                let value = self.parse_job_option_value()?;
                options.push(JobOption { key, value });
                if self.check(Token::Comma) {
                    self.advance();
                }
            }
            self.expect(Token::RParen)?;
        }
        
        self.expect(Token::LBrace)?;
        
        // 解析 job body: config items + perform + [on_failure]
        let mut config = Vec::new();
        let mut perform_params = Vec::new();
        let mut perform_body = Vec::new();
        let mut on_failure = None;
        
        while !self.check(Token::RBrace) && !self.is_at_end() {
            match self.peek_token() {
                Token::Perform => {
                    self.advance(); // consume perform
                    self.expect(Token::LParen)?;
                    // 解析参数列表
                    while !self.check(Token::RParen) && !self.is_at_end() {
                        perform_params.push(self.expect_identifier()?);
                        if self.check(Token::Comma) {
                            self.advance();
                        }
                    }
                    self.expect(Token::RParen)?;
                    // 解析 perform 体
                    self.expect(Token::LBrace)?;
                    perform_body = self.parse_block_body()?;
                    self.expect(Token::RBrace)?;
                }
                Token::OnFailure => {
                    self.advance(); // consume on_failure
                    self.expect(Token::LParen)?;
                    let error_param = self.expect_identifier()?;
                    self.expect(Token::Comma)?;
                    let attempt_param = self.expect_identifier()?;
                    self.expect(Token::RParen)?;
                    // 解析 on_failure 体
                    self.expect(Token::LBrace)?;
                    let on_failure_body = self.parse_block_body()?;
                    self.expect(Token::RBrace)?;
                    on_failure = Some(OnFailureDeclaration {
                        error_param,
                        attempt_param,
                        body: on_failure_body,
                    });
                }
                Token::Identifier => {
                    // config item: key: value
                    let key = self.expect_identifier()?;
                    self.expect(Token::Colon)?;
                    let value = self.parse_job_option_value()?;
                    config.push(JobOption { key, value });
                }
                _ => {
                    return Err(AvmError::ParseError(
                        format!("Unexpected token in job body: {:?}", self.peek_token())
                    ));
                }
            }
        }
        
        self.expect(Token::RBrace)?;
        
        Ok(JobDeclaration {
            name,
            queue,
            options,
            config,
            perform_params,
            perform_body,
            on_failure,
        })
    }
    
    /// P1-3: 解析 Job 选项值
    fn parse_job_option_value(&mut self) -> AvmResult<JobOptionValue> {
        match self.peek_token() {
            Token::Int(n) => {
                self.advance();
                Ok(JobOptionValue::Int(n))
            }
            Token::Float(f) => {
                self.advance();
                Ok(JobOptionValue::Float(f))
            }
            Token::String(s) => {
                self.advance();
                Ok(JobOptionValue::String(s))
            }
            Token::Identifier => {
                let id = self.expect_identifier()?;
                Ok(JobOptionValue::Identifier(id))
            }
            _ => Err(AvmError::ParseError(
                format!("Expected job option value, got: {:?}", self.peek_token())
            )),
        }
    }

    // ==================== 语句解析 ====================

    /// 解析语句块内容
    fn parse_block_body(&mut self) -> AvmResult<Vec<Statement>> {
        let mut statements = Vec::new();
        
        while !self.check(Token::RBrace) && !self.is_at_end() {
            statements.push(self.parse_statement()?);
        }
        
        Ok(statements)
    }

    /// 解析语句
    fn parse_statement(&mut self) -> AvmResult<Statement> {
        match self.peek_token() {
            Token::Try => self.parse_try_catch(),
            Token::Assert => self.parse_assert(),
            Token::SemanticIf => self.parse_semantic_if(),
            Token::Loop => self.parse_loop(),
            Token::Match => self.parse_match_stmt(),
            Token::Return => {
                self.advance();
                let value = if !self.check(Token::Semicolon) {
                    Some(self.parse_expression()?)
                } else {
                    None
                };
                self.match_token(Token::Semicolon);
                Ok(Statement::Return(value))
            }
            Token::Break => {
                self.advance();
                self.match_token(Token::Semicolon);
                Ok(Statement::Break)
            }
            Token::Continue => {
                self.advance();
                self.match_token(Token::Semicolon);
                Ok(Statement::Continue)
            }
            _ => {
                // 尝试解析赋值或表达式
                // v1.2: 支持 ? 操作符和 otherwise 内联错误处理
                let expr = self.parse_expression()?;
                
                if self.match_token(Token::Assign) {
                    let value = self.parse_expression()?;
                    
                    // v1.2: 检查 ? 操作符 — x = expr?
                    if self.check(Token::TypeQuestion) {
                        self.advance(); // 消费 ?
                        self.match_token(Token::Semicolon);
                        // target 需要从 expr 提取标识符名称
                        let target_name = self._extract_identifier_from_expr(&expr);
                        return Ok(Statement::TryAssignment {
                            target: target_name,
                            expression: value,
                        });
                    }
                    
                    // v1.2: 检查 otherwise — x = expr otherwise handler
                    if self.check(Token::Otherwise) {
                        self.advance(); // 消费 otherwise
                        let handler = self.parse_otherwise_handler()?;
                        self.match_token(Token::Semicolon);
                        let target_name = self._extract_identifier_from_expr(&expr);
                        return Ok(Statement::OtherwiseAssignment {
                            target: target_name,
                            expression: value,
                            handler,
                        });
                    }
                    
                    let is_semantic = self.match_token(Token::Identifier)
                        && self.previous_identifier().map_or(false, |s| s == "semantic");
                    self.match_token(Token::Semicolon);
                    Ok(Statement::Assignment {
                        target: expr,
                        value,
                        is_semantic,
                    })
                } else {
                    // v1.2: 检查 ? 操作符 — expr? (无赋值)
                    if self.check(Token::TypeQuestion) {
                        self.advance(); // 消费 ?
                        self.match_token(Token::Semicolon);
                        return Ok(Statement::TryExpression(expr));
                    }
                    
                    self.match_token(Token::Semicolon);
                    Ok(Statement::Expression(expr))
                }
            }
        }
    }

    /// 解析 try-catch 语句
    fn parse_try_catch(&mut self) -> AvmResult<Statement> {
        self.expect(Token::Try)?;
        self.expect(Token::LBrace)?;
        let try_body = self.parse_block_body()?;
        self.expect(Token::RBrace)?;
        
        self.expect(Token::Catch)?;
        let catch_var = self.expect_identifier()?;
        self.expect(Token::LBrace)?;
        let catch_body = self.parse_block_body()?;
        self.expect(Token::RBrace)?;
        
        Ok(Statement::TryCatch {
            try_body,
            catch_var,
            catch_body,
        })
    }

    /// 解析 assert 语句
    fn parse_assert(&mut self) -> AvmResult<Statement> {
        self.expect(Token::Assert)?;
        let condition = self.parse_expression()?;
        let message = if self.match_token(Token::Comma) {
            Some(self.parse_string_literal()?)
        } else {
            None
        };
        self.match_token(Token::Semicolon);
        
        Ok(Statement::Assert { condition, message })
    }

    /// 解析 semantic_if 语句
    fn parse_semantic_if(&mut self) -> AvmResult<Statement> {
        self.expect(Token::SemanticIf)?;
        
        let mut branches = Vec::new();
        let mut else_body = Vec::new();
        
        // 解析条件分支
        loop {
            self.expect(Token::LBrace)?;
            let body = self.parse_block_body()?;
            self.expect(Token::RBrace)?;
            
            if self.match_token(Token::Else) {
                if self.match_token(Token::LBrace) {
                    else_body = self.parse_block_body()?;
                    self.expect(Token::RBrace)?;
                    break;
                } else {
                    // 继续下一个分支
                    branches.push((Expression::Bool(true), body));
                }
            } else {
                branches.push((Expression::Bool(true), body));
                break;
            }
        }
        
        Ok(Statement::SemanticIf { branches, else_body })
    }

    /// 解析 loop 语句
    fn parse_loop(&mut self) -> AvmResult<Statement> {
        self.expect(Token::Loop)?;
        self.expect(Token::Until)?;
        let condition = self.parse_expression()?;
        self.expect(Token::LBrace)?;
        let body = self.parse_block_body()?;
        self.expect(Token::RBrace)?;
        
        Ok(Statement::Loop { condition, body })
    }

    /// 解析 match 语句
    fn parse_match_stmt(&mut self) -> AvmResult<Statement> {
        self.expect(Token::Match)?;
        self.expect(Token::Intent)?;
        let input = self.parse_expression()?;
        self.expect(Token::LBrace)?;
        
        let mut cases = Vec::new();
        
        while !self.check(Token::RBrace) && !self.is_at_end() {
            let pattern = self.parse_pattern()?;
            self.expect(Token::Arrow)?;
            self.expect(Token::LBrace)?;
            let body = self.parse_block_body()?;
            self.expect(Token::RBrace)?;
            
            cases.push(MatchCase { pattern, body });
        }
        
        self.expect(Token::RBrace)?;
        
        Ok(Statement::Match { input, cases })
    }

    /// 解析模式
    fn parse_pattern(&mut self) -> AvmResult<Pattern> {
        match self.peek_token() {
            Token::Identifier => {
                let name = self.advance_identifier()?;
                if self.check(Token::LBrace) {
                    // 构造器模式
                    self.advance();
                    let mut fields = Vec::new();
                    while !self.check(Token::RBrace) && !self.is_at_end() {
                        fields.push(self.parse_pattern()?);
                        if !self.match_token(Token::Comma) {
                            break;
                        }
                    }
                    self.expect(Token::RBrace)?;
                    Ok(Pattern::Constructor { name, fields })
                } else {
                    Ok(Pattern::Variable(name))
                }
            }
            Token::String(_) | Token::Int(_) | Token::Bool(_) => {
                let expr = self.parse_primary()?;
                Ok(Pattern::Literal(expr))
            }
            _ => Ok(Pattern::Wildcard),
        }
    }

    // ==================== 表达式解析 ====================

    /// 解析表达式
    fn parse_expression(&mut self) -> AvmResult<Expression> {
        self.parse_pipeline()
    }

    /// 解析管道表达式
    fn parse_pipeline(&mut self) -> AvmResult<Expression> {
        let mut left = self.parse_logical_or()?;
        
        loop {
            match self.peek_token() {
                Token::Pipeline => {
                    self.advance();
                    let right = self.parse_logical_or()?;
                    left = Expression::Pipeline {
                        left: Box::new(left),
                        right: Box::new(right),
                    };
                }
                Token::Fork => {
                    self.advance();
                    let targets = self.parse_expression_list()?;
                    left = Expression::DagFork(DagForkExpression {
                        input: Box::new(left),
                        targets,
                    });
                }
                Token::Merge => {
                    self.advance();
                    let strategy = if let Token::Identifier = self.peek_token() {
                        self.advance_identifier()?
                    } else {
                        "concat".to_string()
                    };
                    let merge_agent = if self.match_token(Token::Colon) {
                        Some(self.expect_identifier()?)
                    } else {
                        None
                    };
                    left = Expression::DagMerge(DagMergeExpression {
                        inputs: vec![left],
                        merge_strategy: strategy,
                        merge_agent,
                    });
                }
                Token::Branch => {
                    self.advance();
                    let condition = self.parse_expression()?;
                    self.expect(Token::Arrow)?;
                    let true_branch = self.parse_expression()?;
                    let false_branch = if self.match_token(Token::Else) {
                        Some(Box::new(self.parse_expression()?))
                    } else {
                        None
                    };
                    left = Expression::DagBranch(DagBranchExpression {
                        input: Box::new(left),
                        condition: Box::new(condition),
                        true_branch: Box::new(true_branch),
                        false_branch,
                    });
                }
                _ => break,
            }
        }
        
        Ok(left)
    }

    /// 解析逻辑或表达式
    fn parse_logical_or(&mut self) -> AvmResult<Expression> {
        let mut left = self.parse_logical_and()?;
        
        while self.match_token(Token::ParallelMerge) {
            let right = self.parse_logical_and()?;
            left = Expression::BinaryOp {
                left: Box::new(left),
                op: "||".to_string(),
                right: Box::new(right),
            };
        }
        
        Ok(left)
    }

    /// 解析逻辑与表达式
    fn parse_logical_and(&mut self) -> AvmResult<Expression> {
        let mut left = self.parse_comparison()?;
        
        while self.match_token(Token::ParallelFork) {
            let right = self.parse_comparison()?;
            left = Expression::BinaryOp {
                left: Box::new(left),
                op: "&&".to_string(),
                right: Box::new(right),
            };
        }
        
        Ok(left)
    }

    /// 解析比较表达式
    fn parse_comparison(&mut self) -> AvmResult<Expression> {
        let left = self.parse_additive()?;
        
        // 简化版本，不处理比较运算符
        Ok(left)
    }

    /// 解析加减表达式
    fn parse_additive(&mut self) -> AvmResult<Expression> {
        let mut left = self.parse_multiplicative()?;
        
        loop {
            let op = if self.check(Token::Identifier) {
                let ident = self.peek_identifier();
                if ident == Some("+"[..].into()) || ident == Some("-"[..].into()) {
                    self.advance_identifier()?
                } else {
                    break;
                }
            } else {
                break;
            };
            
            let right = self.parse_multiplicative()?;
            left = Expression::BinaryOp {
                left: Box::new(left),
                op,
                right: Box::new(right),
            };
        }
        
        Ok(left)
    }

    /// 解析乘除表达式
    fn parse_multiplicative(&mut self) -> AvmResult<Expression> {
        let left = self.parse_unary()?;
        Ok(left)
    }

    /// 解析一元表达式
    fn parse_unary(&mut self) -> AvmResult<Expression> {
        Ok(self.parse_postfix()?)
    }

    /// 解析后缀表达式
    fn parse_postfix(&mut self) -> AvmResult<Expression> {
        let mut expr = self.parse_primary()?;
        
        loop {
            match self.peek_token() {
                Token::LParen => {
                    self.advance();
                    let (args, kwargs) = self.parse_arguments()?;
                    self.expect(Token::RParen)?;
                    
                    if let Expression::Identifier(name) = expr {
                        expr = Expression::AgentCall { name, args, kwargs };
                    } else {
                        expr = Expression::MethodCall {
                            object: Box::new(expr),
                            method: "call".to_string(),
                            args,
                            kwargs,
                        };
                    }
                }
                Token::Dot => {
                    self.advance();
                    let method = self.expect_identifier()?;
                    
                    if self.check(Token::LParen) {
                        self.advance();
                        let (args, kwargs) = self.parse_arguments()?;
                        self.expect(Token::RParen)?;
                        expr = Expression::MethodCall {
                            object: Box::new(expr),
                            method,
                            args,
                            kwargs,
                        };
                    } else {
                        expr = Expression::PropertyAccess {
                            object: Box::new(expr),
                            property: method,
                        };
                    }
                }
                Token::LBracket => {
                    self.advance();
                    let index = self.parse_expression()?;
                    self.expect(Token::RBracket)?;
                    expr = Expression::Index {
                        object: Box::new(expr),
                        index: Box::new(index),
                    };
                }
                _ => break,
            }
        }
        
        Ok(expr)
    }

    /// 解析基本表达式
    fn parse_primary(&mut self) -> AvmResult<Expression> {
        match self.peek_token() {
            Token::Null => {
                self.advance();
                Ok(Expression::Null)
            }
            Token::Bool(b) => {
                let val = b;
                self.advance();
                Ok(Expression::Bool(val))
            }
            Token::Int(n) => {
                let val = n;
                self.advance();
                Ok(Expression::Integer(val))
            }
            Token::String(s) => {
                let val = s;
                self.advance();
                Ok(Expression::String(val))
            }
            Token::Identifier => {
                let name = self.advance_identifier()?;
                Ok(Expression::Identifier(name))
            }
            Token::LBracket => {
                self.advance();
                let elements = self.parse_expression_list()?;
                self.expect(Token::RBracket)?;
                Ok(Expression::List(elements))
            }
            Token::LBrace => {
                self.advance();
                let pairs = self.parse_dict_pairs()?;
                self.expect(Token::RBrace)?;
                Ok(Expression::Dict(pairs))
            }
            Token::LParen => {
                self.advance();
                let expr = self.parse_expression()?;
                self.expect(Token::RParen)?;
                Ok(expr)
            }
            _ => Err(AvmError::ParseError(
                format!("Unexpected token in expression: {:?}", self.peek_token())
            )),
        }
    }

    /// 解析参数列表
    fn parse_arguments(&mut self) -> AvmResult<(Vec<Expression>, Vec<(String, Expression)>)> {
        let mut args = Vec::new();
        let mut kwargs = Vec::new();
        
        if !self.check(Token::RParen) {
            loop {
                // 检查是否是关键字参数
                if let Token::Identifier = self.peek_token() {
                    let name = self.peek_identifier();
                    // 检查下一个是否是冒号（关键字参数）
                    if name.is_some() {
                        let saved_pos = self.pos;
                        let name = self.advance_identifier()?;
                        
                        if self.match_token(Token::Colon) {
                            let value = self.parse_expression()?;
                            kwargs.push((name, value));
                        } else {
                            // 回退，这是位置参数
                            self.pos = saved_pos;
                            args.push(self.parse_expression()?);
                        }
                    } else {
                        args.push(self.parse_expression()?);
                    }
                } else {
                    args.push(self.parse_expression()?);
                }
                
                if !self.match_token(Token::Comma) {
                    break;
                }
            }
        }
        
        Ok((args, kwargs))
    }

    /// 解析表达式列表
    fn parse_expression_list(&mut self) -> AvmResult<Vec<Expression>> {
        let mut expressions = Vec::new();
        
        if !self.check(Token::RBracket) && !self.check(Token::RBrace) && !self.check(Token::RParen) {
            loop {
                expressions.push(self.parse_expression()?);
                if !self.match_token(Token::Comma) {
                    break;
                }
            }
        }
        
        Ok(expressions)
    }

    /// 解析字典键值对
    fn parse_dict_pairs(&mut self) -> AvmResult<Vec<(String, Expression)>> {
        let mut pairs = Vec::new();
        
        if !self.check(Token::RBrace) {
            loop {
                let key = if let Token::String(s) = self.peek_token() {
                    let k = s.clone();
                    self.advance();
                    k
                } else if let Token::Identifier = self.peek_token() {
                    self.advance_identifier()?
                } else {
                    return Err(AvmError::ParseError("Expected dictionary key".to_string()));
                };
                
                self.expect(Token::Colon)?;
                let value = self.parse_expression()?;
                pairs.push((key, value));
                
                if !self.match_token(Token::Comma) {
                    break;
                }
            }
        }
        
        Ok(pairs)
    }

    /// 解析 JSON 值
    fn parse_json_value(&mut self) -> AvmResult<serde_json::Value> {
        match self.peek_token() {
            Token::String(s) => {
                let val = serde_json::Value::String(s.clone());
                self.advance();
                Ok(val)
            }
            Token::Int(n) => {
                let val = serde_json::Value::Number(n.into());
                self.advance();
                Ok(val)
            }
            Token::Bool(b) => {
                let val = serde_json::Value::Bool(b);
                self.advance();
                Ok(val)
            }
            Token::Null => {
                self.advance();
                Ok(serde_json::Value::Null)
            }
            Token::LBrace => {
                self.advance();
                let mut map = serde_json::Map::new();
                
                while !self.check(Token::RBrace) && !self.is_at_end() {
                    let key = if let Token::String(s) = self.peek_token() {
                        let k = s.clone();
                        self.advance();
                        k
                    } else {
                        return Err(AvmError::ParseError("Expected string key in JSON object".to_string()));
                    };
                    
                    self.expect(Token::Colon)?;
                    let value = self.parse_json_value()?;
                    map.insert(key, value);
                    
                    if !self.match_token(Token::Comma) {
                        break;
                    }
                }
                
                self.expect(Token::RBrace)?;
                Ok(serde_json::Value::Object(map))
            }
            Token::LBracket => {
                self.advance();
                let mut arr = Vec::new();
                
                while !self.check(Token::RBracket) && !self.is_at_end() {
                    arr.push(self.parse_json_value()?);
                    if !self.match_token(Token::Comma) {
                        break;
                    }
                }
                
                self.expect(Token::RBracket)?;
                Ok(serde_json::Value::Array(arr))
            }
            _ => Err(AvmError::ParseError(
                format!("Unexpected token in JSON value: {:?}", self.peek_token())
            )),
        }
    }

    // ==================== 辅助方法 ====================

    fn parse_string_literal(&mut self) -> AvmResult<String> {
        if let Token::String(s) = self.peek_token() {
            let val = s.clone();
            self.advance();
            Ok(val)
        } else {
            Err(AvmError::ParseError("Expected string literal".to_string()))
        }
    }

    fn is_at_end(&self) -> bool {
        self.pos >= self.tokens.len()
    }

    fn peek_token(&self) -> Token {
        if self.is_at_end() {
            Token::Identifier // 用 Identifier 作为 EOF 标记
        } else {
            self.tokens[self.pos].token.clone()
        }
    }

    fn peek_identifier(&self) -> Option<String> {
        if self.is_at_end() {
            return None;
        }
        match &self.tokens[self.pos].token {
            Token::Identifier => Some(self.tokens[self.pos].text.clone()),
            _ => None,
        }
    }

    fn peek_text(&self) -> String {
        if self.is_at_end() {
            return String::new();
        }
        self.tokens[self.pos].text.clone()
    }

    fn previous_identifier(&self) -> Option<String> {
        if self.pos == 0 {
            return None;
        }
        match &self.tokens[self.pos - 1].token {
            Token::Identifier => Some(self.tokens[self.pos - 1].text.clone()),
            _ => None,
        }
    }

    fn advance(&mut self) -> Token {
        if !self.is_at_end() {
            self.pos += 1;
        }
        self.previous_token()
    }

    fn advance_identifier(&mut self) -> AvmResult<String> {
        if let Token::Identifier = self.peek_token() {
            let text = self.tokens[self.pos].text.clone();
            self.pos += 1;
            Ok(text)
        } else {
            Err(AvmError::ParseError("Expected identifier".to_string()))
        }
    }

    fn previous_token(&self) -> Token {
        if self.pos == 0 {
            Token::Identifier
        } else {
            self.tokens[self.pos - 1].token.clone()
        }
    }

    fn check(&self, token: Token) -> bool {
        std::mem::discriminant(&self.peek_token()) == std::mem::discriminant(&token)
    }

    fn match_token(&mut self, token: Token) -> bool {
        if self.check(token.clone()) {
            self.advance();
            true
        } else {
            false
        }
    }

    fn expect(&mut self, token: Token) -> AvmResult<()> {
        if self.check(token.clone()) {
            self.advance();
            Ok(())
        } else {
            Err(AvmError::ParseError(
                format!("Expected {:?}, got {:?}", token, self.peek_token())
            ))
        }
    }

    fn expect_identifier(&mut self) -> AvmResult<String> {
        if let Token::Identifier = self.peek_token() {
            let text = self.tokens[self.pos].text.clone();
            self.pos += 1;
            Ok(text)
        } else {
            Err(AvmError::ParseError(
                format!("Expected identifier, got {:?}", self.peek_token())
            ))
        }
    }
    // ==================== v1.2: Error Propagation 辅助方法 ====================
    
    /// 解析 otherwise handler
    ///
    /// otherwise handler 可以是:
    /// - Agent 调用: AgentName.run(args) 或 AgentName.run_result(args)
    /// - 字符串值: "fallback value"
    /// - 变量引用: fallback_var
    /// - 代码块: { stmt1; stmt2; }
    fn parse_otherwise_handler(&mut self) -> AvmResult<OtherwiseHandler> {
        match self.peek_token() {
            // Agent 调用作为 fallback — IDENTIFIER.run(args)
            Token::Identifier => {
                let agent_name = self.peek_text().clone();
                // 检查是否是 Agent 方法调用 (IDENTIFIER.run 或 IDENTIFIER.run_result)
                if self.pos + 1 < self.tokens.len()
                    && self.tokens[self.pos + 1].token == Token::Dot {
                    self.advance(); // 消费 Agent 名称
                    self.advance(); // 消费 .
                    let method = self.peek_text().clone();
                    self.advance(); // 消费方法名
                    
                    let mut args = Vec::new();
                    if self.check(Token::LParen) {
                        self.advance();
                        if !self.check(Token::RParen) {
                            loop {
                                args.push(self.parse_expression()?);
                                if !self.match_token(Token::Comma) {
                                    break;
                                }
                            }
                        }
                        self.expect(Token::RParen)?;
                    }
                    
                    Ok(OtherwiseHandler::AgentCall { agent_name, args })
                } else {
                    // 变量引用作为 fallback
                    self.advance();
                    Ok(OtherwiseHandler::Variable(agent_name))
                }
            }
            // 字符串值作为 fallback
            Token::String(s) => {
                let value = s.clone();
                self.advance();
                Ok(OtherwiseHandler::Value(value))
            }
            // 代码块作为 fallback
            Token::LBrace => {
                self.advance();
                let statements = self.parse_block_body()?;
                self.expect(Token::RBrace)?;
                Ok(OtherwiseHandler::Block(statements))
            }
            _ => Err(AvmError::ParseError(
                format!("Expected otherwise handler (Agent call, value, variable, or block), got {:?}", self.peek_token())
            )),
        }
    }
    
    /// 从 Expression 中提取标识符名称
    ///
    /// 用于 TryAssignment 和 OtherwiseAssignment 的 target 字段
    fn _extract_identifier_from_expr(&self, expr: &Expression) -> String {
        match expr {
            Expression::Identifier(name) => name.clone(),
            Expression::PropertyAccess { object, property } => {
                let obj_str = self._extract_identifier_from_expr(object);
                format!("{}.{}", obj_str, property)
            }
            _ => "_".to_string(), // 默认值，不应发生
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parser_creation() {
        let result = Parser::parse_from_source("");
        assert!(result.is_ok());
    }

    #[test]
    fn test_parse_agent() {
        let source = r#"agent TestAgent {
            role: "assistant"
            prompt: "You are a helpful assistant"
        }"#;
        
        let result = Parser::parse_from_source(source);
        assert!(result.is_ok());
        
        let program = result.unwrap();
        assert_eq!(program.declarations.len(), 1);
        
        if let Declaration::Agent(agent) = &program.declarations[0] {
            assert_eq!(agent.name, "TestAgent");
            assert_eq!(agent.role, Some("assistant".to_string()));
            assert_eq!(agent.prompt, Some("You are a helpful assistant".to_string()));
        } else {
            panic!("Expected Agent declaration");
        }
    }

    #[test]
    fn test_parse_tool() {
        let source = r#"tool my_tool {
            "A simple tool"
        }"#;
        
        let result = Parser::parse_from_source(source);
        assert!(result.is_ok());
        
        let program = result.unwrap();
        assert_eq!(program.declarations.len(), 1);
        
        if let Declaration::Tool(tool) = &program.declarations[0] {
            assert_eq!(tool.name, "my_tool");
            assert_eq!(tool.description, Some("A simple tool".to_string()));
        } else {
            panic!("Expected Tool declaration");
        }
    }

    #[test]
    fn test_parse_flow() {
        let source = r#"flow main {
            agent1 >> agent2 >> agent3
        }"#;
        
        let result = Parser::parse_from_source(source);
        assert!(result.is_ok());
        
        let program = result.unwrap();
        assert_eq!(program.flows.len(), 1);
        assert_eq!(program.flows[0].name, "main");
    }

    #[test]
    fn test_parse_pipeline() {
        let source = r#"agent A { role: "test" }
agent B { role: "test" }
flow main {
    A >> B
}"#;
        
        let result = Parser::parse_from_source(source);
        assert!(result.is_ok());
        
        let program = result.unwrap();
        assert_eq!(program.declarations.len(), 2);
        assert_eq!(program.flows.len(), 1);
    }
}
