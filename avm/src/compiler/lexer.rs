//! Nexa Lexer - 词法分析器
//! 使用 logos crate 实现高性能词法分析

use logos::Lexer;
use std::fmt;

/// Nexa Token 类型
#[derive(Debug, Clone, PartialEq, logos::Logos)]
pub enum Token {
    // 关键字
    #[token("agent")]
    Agent,
    #[token("tool")]
    Tool,
    #[token("flow")]
    Flow,
    #[token("protocol")]
    Protocol,
    #[token("test")]
    Test,
    #[token("include")]
    Include,
    
    // Agent 属性
    #[token("role")]
    Role,
    #[token("model")]
    Model,
    #[token("prompt")]
    Prompt,
    #[token("uses")]
    Uses,
    #[token("implements")]
    Implements,
    
    // 控制流
    #[token("match")]
    Match,
    #[token("intent")]
    Intent,
    #[token("semantic_if")]
    SemanticIf,
    #[token("fast_match")]
    FastMatch,
    #[token("against")]
    Against,
    #[token("loop")]
    Loop,
    #[token("until")]
    Until,
    #[token("try")]
    Try,
    #[token("catch")]
    Catch,
    #[token("else")]
    Else,
    #[token("fallback")]
    Fallback,
    
    // 控制流关键字
    #[token("assert")]
    Assert,
    #[token("return")]
    Return,
    #[token("break")]
    Break,
    #[token("continue")]
    Continue,
    
    // 操作符
    #[token(">>")]
    Pipeline,
    #[token("|>>")]
    Fork,
    #[token("&>>")]
    Merge,
    #[token("??")]
    Branch,
    #[token("||")]
    ParallelFork,
    #[token("&&")]
    ParallelMerge,
    
    // 分隔符
    #[token("{")]
    LBrace,
    #[token("}")]
    RBrace,
    #[token("[")]
    LBracket,
    #[token("]")]
    RBracket,
    #[token("(")]
    LParen,
    #[token(")")]
    RParen,
    #[token(":")]
    Colon,
    #[token(";")]
    Semicolon,
    #[token(",")]
    Comma,
    #[token(".")]
    Dot,
    #[token("=>")]
    Arrow,
    #[token("=")]
    Assign,
    #[token("@")]
    At,
    
    // 字面量
    #[token("null")]
    Null,
    
    #[token("true", |_| true)]
    #[token("false", |_| false)]
    Bool(bool),
    
    #[regex(r#""[^"]*""#, |lex| {
        let s = lex.slice();
        // 移除首尾引号
        s[1..s.len()-1].to_string()
    })]
    String(String),
    
    #[regex(r"[0-9]+", |lex| lex.slice().parse().ok())]
    Int(i64),
    
    #[regex(r"[a-zA-Z_][a-zA-Z0-9_]*")]
    Identifier,
    
    // 注释和空白
    #[regex(r"//[^\n]*")]
    Comment,
    
    #[regex(r"/\*([^*]|\*[^/])*\*/")]
    BlockComment,
    
    #[regex(r"[ \t\n\r\f]+")]
    Whitespace,
}

/// Token 位置信息
#[derive(Debug, Clone)]
pub struct Span {
    pub start: usize,
    pub end: usize,
}

/// 带位置的 Token
#[derive(Debug, Clone)]
pub struct TokenWithSpan {
    pub token: Token,
    pub span: Span,
    pub text: String,
}

impl Token {
    /// 获取 token 的名称
    pub fn name(&self) -> &'static str {
        match self {
            Token::Agent => "agent",
            Token::Tool => "tool",
            Token::Flow => "flow",
            Token::Protocol => "protocol",
            Token::Test => "test",
            Token::Include => "include",
            Token::Role => "role",
            Token::Model => "model",
            Token::Prompt => "prompt",
            Token::Uses => "uses",
            Token::Implements => "implements",
            Token::Match => "match",
            Token::Intent => "intent",
            Token::SemanticIf => "semantic_if",
            Token::FastMatch => "fast_match",
            Token::Against => "against",
            Token::Loop => "loop",
            Token::Until => "until",
            Token::Try => "try",
            Token::Catch => "catch",
            Token::Else => "else",
            Token::Fallback => "fallback",
            Token::Assert => "assert",
            Token::Return => "return",
            Token::Break => "break",
            Token::Continue => "continue",
            Token::Pipeline => ">>",
            Token::Fork => "|>>",
            Token::Merge => "&>>",
            Token::Branch => "??",
            Token::ParallelFork => "||",
            Token::ParallelMerge => "&&",
            Token::LBrace => "{",
            Token::RBrace => "}",
            Token::LBracket => "[",
            Token::RBracket => "]",
            Token::LParen => "(",
            Token::RParen => ")",
            Token::Colon => ":",
            Token::Semicolon => ";",
            Token::Comma => ",",
            Token::Dot => ".",
            Token::Arrow => "=>",
            Token::Assign => "=",
            Token::At => "@",
            Token::String(_) => "string",
            Token::Int(_) => "int",
            Token::Bool(_) => "bool",
            Token::Null => "null",
            Token::Identifier => "identifier",
            Token::Comment => "comment",
            Token::BlockComment => "block_comment",
            Token::Whitespace => "whitespace",
        }
    }
}

impl fmt::Display for Token {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Token::String(s) => write!(f, "\"{}\"", s),
            Token::Int(n) => write!(f, "{}", n),
            Token::Bool(b) => write!(f, "{}", b),
            Token::Null => write!(f, "null"),
            _ => write!(f, "{}", self.name()),
        }
    }
}

/// 词法分析结果
pub struct LexerResult {
    pub tokens: Vec<TokenWithSpan>,
    pub errors: Vec<(String, Span)>,
}

/// 词法分析
pub fn tokenize(source: &str) -> LexerResult {
    let mut lexer = Lexer::<Token>::new(source);
    let mut tokens = Vec::new();
    let mut errors = Vec::new();
    
    while let Some(result) = lexer.next() {
        let span = Span {
            start: lexer.span().start,
            end: lexer.span().end,
        };
        let text = lexer.slice().to_string();
        
        match result {
            Ok(token) => {
                match token {
                    Token::Whitespace | Token::Comment | Token::BlockComment => {
                        // 跳过空白和注释
                    }
                    _ => {
                        tokens.push(TokenWithSpan {
                            token,
                            span,
                            text,
                        });
                    }
                }
            }
            Err(_) => {
                errors.push((format!("Unexpected token: {}", text), span));
            }
        }
    }
    
    LexerResult { tokens, errors }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_tokenize_keywords() {
        let source = "agent flow tool";
        let result = tokenize(source);
        
        assert_eq!(result.tokens.len(), 3);
        assert_eq!(result.tokens[0].token, Token::Agent);
        assert_eq!(result.tokens[1].token, Token::Flow);
        assert_eq!(result.tokens[2].token, Token::Tool);
    }
    
    #[test]
    fn test_tokenize_operators() {
        let source = ">> |>> &>> ??";
        let result = tokenize(source);
        
        assert_eq!(result.tokens.len(), 4);
        assert_eq!(result.tokens[0].token, Token::Pipeline);
        assert_eq!(result.tokens[1].token, Token::Fork);
        assert_eq!(result.tokens[2].token, Token::Merge);
        assert_eq!(result.tokens[3].token, Token::Branch);
    }
    
    #[test]
    fn test_tokenize_string() {
        let source = r#""hello world""#;
        let result = tokenize(source);
        
        assert_eq!(result.tokens.len(), 1);
        assert!(matches!(result.tokens[0].token, Token::String(_)));
    }
    
    #[test]
    fn test_tokenize_agent_declaration() {
        let source = r#"agent TestAgent { role: "test" }"#;
        let result = tokenize(source);
        
        assert!(result.errors.is_empty());
        assert!(result.tokens.len() > 0);
    }
}