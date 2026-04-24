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

//! WASM 沙盒 - 安全隔离的 WebAssembly 执行环境
//!
//! 提供权限控制、资源限制和 WASI 接口支持

use crate::utils::error::{AvmError, AvmResult};
use super::runtime::{WasmModule, WasmInstance, WasmConfig, WasmValue, ExecutionStats};
use std::collections::{HashMap, HashSet};
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

/// 沙盒权限类型
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum SandboxPermission {
    /// 文件系统读取
    FsRead,
    /// 文件系统写入
    FsWrite,
    /// 网络访问
    Network,
    /// 环境变量访问
    EnvAccess,
    /// 进程创建
    ProcessSpawn,
    /// 时钟访问
    ClockAccess,
    /// 随机数生成
    RandomAccess,
    /// 线程创建
    ThreadCreate,
}

impl SandboxPermission {
    /// 获取权限名称
    pub fn name(&self) -> &'static str {
        match self {
            SandboxPermission::FsRead => "fs_read",
            SandboxPermission::FsWrite => "fs_write",
            SandboxPermission::Network => "network",
            SandboxPermission::EnvAccess => "env_access",
            SandboxPermission::ProcessSpawn => "process_spawn",
            SandboxPermission::ClockAccess => "clock_access",
            SandboxPermission::RandomAccess => "random_access",
            SandboxPermission::ThreadCreate => "thread_create",
        }
    }
    
    /// 从名称创建权限
    pub fn from_name(name: &str) -> Option<Self> {
        match name {
            "fs_read" => Some(SandboxPermission::FsRead),
            "fs_write" => Some(SandboxPermission::FsWrite),
            "network" => Some(SandboxPermission::Network),
            "env_access" => Some(SandboxPermission::EnvAccess),
            "process_spawn" => Some(SandboxPermission::ProcessSpawn),
            "clock_access" => Some(SandboxPermission::ClockAccess),
            "random_access" => Some(SandboxPermission::RandomAccess),
            "thread_create" => Some(SandboxPermission::ThreadCreate),
            _ => None,
        }
    }
}

/// 预定义权限级别
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PermissionLevel {
    /// 最严格 - 无权限
    None,
    /// 只读权限
    ReadOnly,
    /// 基础权限 (时钟、随机数)
    Basic,
    /// 标准权限 (文件读写、网络)
    Standard,
    /// 完全权限
    Full,
}

impl PermissionLevel {
    /// 获取权限集合
    pub fn permissions(&self) -> HashSet<SandboxPermission> {
        let mut perms = HashSet::new();
        
        match self {
            PermissionLevel::None => {}
            PermissionLevel::ReadOnly => {
                perms.insert(SandboxPermission::FsRead);
                perms.insert(SandboxPermission::ClockAccess);
            }
            PermissionLevel::Basic => {
                perms.insert(SandboxPermission::ClockAccess);
                perms.insert(SandboxPermission::RandomAccess);
            }
            PermissionLevel::Standard => {
                perms.insert(SandboxPermission::FsRead);
                perms.insert(SandboxPermission::FsWrite);
                perms.insert(SandboxPermission::Network);
                perms.insert(SandboxPermission::ClockAccess);
                perms.insert(SandboxPermission::RandomAccess);
            }
            PermissionLevel::Full => {
                perms.insert(SandboxPermission::FsRead);
                perms.insert(SandboxPermission::FsWrite);
                perms.insert(SandboxPermission::Network);
                perms.insert(SandboxPermission::EnvAccess);
                perms.insert(SandboxPermission::ProcessSpawn);
                perms.insert(SandboxPermission::ClockAccess);
                perms.insert(SandboxPermission::RandomAccess);
                perms.insert(SandboxPermission::ThreadCreate);
            }
        }
        
        perms
    }
}

/// 资源限制配置
#[derive(Debug, Clone)]
pub struct ResourceLimits {
    /// 最大 CPU 时间 (毫秒)
    pub max_cpu_time_ms: u64,
    /// 最大内存使用 (字节)
    pub max_memory_bytes: usize,
    /// 最大文件描述符数量
    pub max_fds: usize,
    /// 最大文件大小 (字节)
    pub max_file_size: usize,
    /// 最大网络连接数
    pub max_connections: usize,
    /// 最大线程数
    pub max_threads: usize,
    /// 最大调用栈深度
    pub max_stack_depth: usize,
}

impl Default for ResourceLimits {
    fn default() -> Self {
        // 论文声称：默认16MB内存，30s超时
        Self {
            max_cpu_time_ms: 30_000, // 30s - 匹配论文声明
            max_memory_bytes: 16 * 1024 * 1024, // 16MB - 匹配论文声明
            max_fds: 64,
            max_file_size: 1 * 1024 * 1024, // 1MB
            max_connections: 10,
            max_threads: 1,
            max_stack_depth: 1024,
        }
    }
}

impl ResourceLimits {
    /// 创建无限制配置
    pub fn unlimited() -> Self {
        Self {
            max_cpu_time_ms: u64::MAX,
            max_memory_bytes: usize::MAX,
            max_fds: usize::MAX,
            max_file_size: usize::MAX,
            max_connections: usize::MAX,
            max_threads: usize::MAX,
            max_stack_depth: usize::MAX,
        }
    }
    
    /// 创建严格限制配置
    pub fn strict() -> Self {
        Self {
            max_cpu_time_ms: 1000,
            max_memory_bytes: 4 * 1024 * 1024, // 4MB
            max_fds: 16,
            max_file_size: 64 * 1024, // 64KB
            max_connections: 2,
            max_threads: 1,
            max_stack_depth: 256,
        }
    }
}

/// 沙盒配置
#[derive(Debug, Clone)]
pub struct SandboxConfig {
    /// 权限集合
    pub permissions: HashSet<SandboxPermission>,
    /// 资源限制
    pub limits: ResourceLimits,
    /// 允许的文件路径前缀
    pub allowed_paths: Vec<PathBuf>,
    /// 允许的环境变量
    pub allowed_env_vars: Vec<String>,
    /// 是否启用审计日志
    pub audit_enabled: bool,
}

impl Default for SandboxConfig {
    fn default() -> Self {
        Self {
            permissions: PermissionLevel::Basic.permissions(),
            limits: ResourceLimits::default(),
            allowed_paths: vec![],
            allowed_env_vars: vec![],
            audit_enabled: true,
        }
    }
}

impl SandboxConfig {
    /// 创建指定权限级别的配置
    pub fn with_level(level: PermissionLevel) -> Self {
        Self {
            permissions: level.permissions(),
            limits: ResourceLimits::default(),
            allowed_paths: vec![],
            allowed_env_vars: vec![],
            audit_enabled: true,
        }
    }
    
    /// 创建只读沙盒配置
    pub fn read_only() -> Self {
        Self {
            permissions: PermissionLevel::ReadOnly.permissions(),
            limits: ResourceLimits::default(),
            allowed_paths: vec![PathBuf::from(".")],
            allowed_env_vars: vec![],
            audit_enabled: true,
        }
    }
    
    /// 添加权限
    pub fn add_permission(&mut self, permission: SandboxPermission) {
        self.permissions.insert(permission);
    }
    
    /// 移除权限
    pub fn remove_permission(&mut self, permission: &SandboxPermission) {
        self.permissions.remove(permission);
    }
    
    /// 检查权限
    pub fn has_permission(&self, permission: &SandboxPermission) -> bool {
        self.permissions.contains(permission)
    }
    
    /// 添加允许的路径
    pub fn add_allowed_path(&mut self, path: impl Into<PathBuf>) {
        self.allowed_paths.push(path.into());
    }
    
    /// 检查路径是否允许
    pub fn is_path_allowed(&self, path: &PathBuf) -> bool {
        if self.allowed_paths.is_empty() {
            return true;
        }
        
        self.allowed_paths.iter().any(|allowed| {
            path.starts_with(allowed) || path.strip_prefix(allowed).is_ok()
        })
    }
}

/// 审计事件
#[derive(Debug, Clone)]
pub struct AuditEvent {
    /// 事件时间戳
    pub timestamp: std::time::Instant,
    /// 事件类型
    pub event_type: AuditEventType,
    /// 模块名
    pub module: String,
    /// 函数名
    pub function: Option<String>,
    /// 是否成功
    pub success: bool,
    /// 消息
    pub message: String,
}

/// 审计事件类型
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AuditEventType {
    /// 模块加载
    ModuleLoad,
    /// 模块卸载
    ModuleUnload,
    /// 函数调用
    FunctionCall,
    /// 权限检查
    PermissionCheck,
    /// 资源限制
    ResourceLimit,
    /// 内存访问
    MemoryAccess,
    /// 文件操作
    FileOperation,
    /// 网络操作
    NetworkOperation,
}

/// 审计日志
#[derive(Debug, Default)]
pub struct AuditLog {
    /// 事件列表
    events: Vec<AuditEvent>,
    /// 最大事件数
    max_events: usize,
}

impl AuditLog {
    /// 创建新的审计日志
    pub fn new(max_events: usize) -> Self {
        Self {
            events: Vec::with_capacity(max_events),
            max_events,
        }
    }
    
    /// 添加事件
    pub fn add(&mut self, event: AuditEvent) {
        if self.events.len() >= self.max_events {
            self.events.remove(0);
        }
        self.events.push(event);
    }
    
    /// 获取所有事件
    pub fn events(&self) -> &[AuditEvent] {
        &self.events
    }
    
    /// 清除日志
    pub fn clear(&mut self) {
        self.events.clear();
    }
    
    /// 过滤事件
    pub fn filter(&self, event_type: AuditEventType) -> Vec<&AuditEvent> {
        self.events.iter().filter(|e| e.event_type == event_type).collect()
    }
}

/// WASM 沙盒
pub struct WasmSandbox {
    /// 沙盒配置
    config: SandboxConfig,
    /// WASM 配置
    wasm_config: WasmConfig,
    /// 审计日志
    audit_log: Arc<Mutex<AuditLog>>,
    /// 已加载的模块实例
    instances: HashMap<String, SandboxedInstance>,
    /// 资源使用追踪
    resource_usage: HashMap<String, ResourceUsage>,
}

/// 资源使用统计
#[derive(Debug, Clone, Default)]
pub struct ResourceUsage {
    /// CPU 时间使用 (纳秒)
    pub cpu_time_ns: u64,
    /// 内存使用峰值 (字节)
    pub peak_memory: usize,
    /// 调用次数
    pub call_count: u64,
    /// 文件描述符使用
    pub open_fds: usize,
    /// 网络连接使用
    pub open_connections: usize,
}

impl WasmSandbox {
    /// 创建新的沙盒
    pub fn new(config: SandboxConfig) -> Self {
        let wasm_config = WasmConfig {
            max_memory_pages: (config.limits.max_memory_bytes / 65536) as u32,
            execution_timeout_ms: config.limits.max_cpu_time_ms,
            enable_wasi: true,
            max_table_elements: 10000,
            enable_threads: config.permissions.contains(&SandboxPermission::ThreadCreate),
            enable_simd: true,
        };
        
        Self {
            wasm_config,
            audit_log: Arc::new(Mutex::new(AuditLog::new(1000))),
            instances: HashMap::new(),
            resource_usage: HashMap::new(),
            config,
        }
    }
    
    /// 获取配置
    pub fn config(&self) -> &SandboxConfig {
        &self.config
    }
    
    /// 获取审计日志
    pub fn audit_log(&self) -> &Arc<Mutex<AuditLog>> {
        &self.audit_log
    }
    
    /// 加载模块
    pub fn load_module(&self, name: &str, bytes: Vec<u8>) -> AvmResult<WasmModule> {
        // 记录审计事件
        if self.config.audit_enabled {
            if let Ok(mut log) = self.audit_log.lock() {
                log.add(AuditEvent {
                    timestamp: std::time::Instant::now(),
                    event_type: AuditEventType::ModuleLoad,
                    module: name.to_string(),
                    function: None,
                    success: true,
                    message: format!("Module '{}' loaded ({} bytes)", name, bytes.len()),
                });
            }
        }
        
        WasmModule::from_bytes(name, bytes)
    }
    
    /// 创建沙盒实例
    pub fn create_instance(&mut self, name: &str, module: WasmModule) -> AvmResult<&mut SandboxedInstance> {
        let instance = WasmInstance::new(module)?;
        let sandboxed = SandboxedInstance {
            instance,
            config: self.config.clone(),
            audit_log: self.audit_log.clone(),
            usage: ResourceUsage::default(),
        };
        
        self.instances.insert(name.to_string(), sandboxed);
        self.resource_usage.insert(name.to_string(), ResourceUsage::default());
        
        Ok(self.instances.get_mut(name).unwrap())
    }
    
    /// 获取实例
    pub fn get_instance(&mut self, name: &str) -> Option<&mut SandboxedInstance> {
        self.instances.get_mut(name)
    }
    
    /// 检查权限
    pub fn check_permission(&self, permission: SandboxPermission) -> AvmResult<()> {
        if !self.config.permissions.contains(&permission) {
            // 记录审计事件
            if self.config.audit_enabled {
                if let Ok(mut log) = self.audit_log.lock() {
                    log.add(AuditEvent {
                        timestamp: std::time::Instant::now(),
                        event_type: AuditEventType::PermissionCheck,
                        module: String::new(),
                        function: None,
                        success: false,
                        message: format!("Permission denied: {:?}", permission),
                    });
                }
            }
            
            return Err(AvmError::WasmSandboxViolation(format!(
                "Permission denied: {}",
                permission.name()
            )));
        }
        
        Ok(())
    }
    
    /// 调用函数
    pub fn call(
        &mut self,
        instance_name: &str,
        function: &str,
        args: &[WasmValue],
    ) -> AvmResult<Vec<WasmValue>> {
        // 先检查资源限制
        self.check_resource_limits(instance_name)?;
        
        // 检查实例是否存在
        if !self.instances.contains_key(instance_name) {
            return Err(AvmError::WasmError(format!("Instance '{}' not found", instance_name)));
        }
        
        // 执行调用
        let start = std::time::Instant::now();
        let instance = self.instances.get_mut(instance_name).unwrap();
        let result = instance.call(function, args);
        let elapsed = start.elapsed().as_nanos() as u64;
        
        // 更新资源使用
        if let Some(usage) = self.resource_usage.get_mut(instance_name) {
            usage.cpu_time_ns += elapsed;
            usage.call_count += 1;
        }
        
        // 记录审计
        if self.config.audit_enabled {
            if let Ok(mut log) = self.audit_log.lock() {
                log.add(AuditEvent {
                    timestamp: std::time::Instant::now(),
                    event_type: AuditEventType::FunctionCall,
                    module: instance_name.to_string(),
                    function: Some(function.to_string()),
                    success: result.is_ok(),
                    message: format!(
                        "Function '{}' called ({:.2}ms)",
                        function,
                        elapsed as f64 / 1_000_000.0
                    ),
                });
            }
        }
        
        result
    }
    
    /// 检查资源限制
    fn check_resource_limits(&self, instance_name: &str) -> AvmResult<()> {
        let default_usage = ResourceUsage::default();
        let usage = self.resource_usage.get(instance_name).unwrap_or(&default_usage);
        
        // 检查 CPU 时间
        let cpu_time_ms = usage.cpu_time_ns / 1_000_000;
        if cpu_time_ms >= self.config.limits.max_cpu_time_ms {
            return Err(AvmError::WasmSandboxViolation(format!(
                "CPU time limit exceeded: {}ms >= {}ms",
                cpu_time_ms, self.config.limits.max_cpu_time_ms
            )));
        }
        
        Ok(())
    }
    
    /// 获取资源使用统计
    pub fn resource_usage(&self, instance_name: &str) -> Option<&ResourceUsage> {
        self.resource_usage.get(instance_name)
    }
    
    /// 销毁实例
    pub fn destroy_instance(&mut self, name: &str) -> AvmResult<()> {
        self.instances.remove(name);
        self.resource_usage.remove(name);
        
        if self.config.audit_enabled {
            if let Ok(mut log) = self.audit_log.lock() {
                log.add(AuditEvent {
                    timestamp: std::time::Instant::now(),
                    event_type: AuditEventType::ModuleUnload,
                    module: name.to_string(),
                    function: None,
                    success: true,
                    message: format!("Instance '{}' destroyed", name),
                });
            }
        }
        
        Ok(())
    }
    
    /// 清理所有实例
    pub fn clear(&mut self) {
        self.instances.clear();
        self.resource_usage.clear();
        
        if let Ok(mut log) = self.audit_log.lock() {
            log.clear();
        }
    }
}

impl Default for WasmSandbox {
    fn default() -> Self {
        Self::new(SandboxConfig::default())
    }
}

/// 沙盒实例
pub struct SandboxedInstance {
    /// WASM 实例
    instance: WasmInstance,
    /// 沙盒配置
    config: SandboxConfig,
    /// 审计日志
    audit_log: Arc<Mutex<AuditLog>>,
    /// 资源使用
    usage: ResourceUsage,
}

impl SandboxedInstance {
    /// 获取执行统计
    pub fn stats(&self) -> &ExecutionStats {
        self.instance.stats()
    }
    
    /// 获取资源使用
    pub fn resource_usage(&self) -> &ResourceUsage {
        &self.usage
    }
    
    /// 获取内存大小
    pub fn memory_size(&self) -> usize {
        self.instance.memory_size()
    }
    
    /// 读取内存
    pub fn read_memory(&self, offset: usize, len: usize) -> AvmResult<Vec<u8>> {
        // 检查内存限制
        if offset + len > self.config.limits.max_memory_bytes {
            if let Ok(mut log) = self.audit_log.lock() {
                log.add(AuditEvent {
                    timestamp: std::time::Instant::now(),
                    event_type: AuditEventType::MemoryAccess,
                    module: String::new(),
                    function: None,
                    success: false,
                    message: format!("Memory access denied: {} + {} > {}", 
                        offset, len, self.config.limits.max_memory_bytes),
                });
            }
            
            return Err(AvmError::WasmSandboxViolation("Memory access denied".to_string()));
        }
        
        self.instance.read_memory(offset, len)
    }
    
    /// 写入内存
    pub fn write_memory(&mut self, offset: usize, data: &[u8]) -> AvmResult<()> {
        // 检查内存限制
        if offset + data.len() > self.config.limits.max_memory_bytes {
            return Err(AvmError::WasmSandboxViolation("Memory access denied".to_string()));
        }
        
        self.instance.write_memory(offset, data)
    }
    
    /// 调用函数
    pub fn call(&mut self, function: &str, args: &[WasmValue]) -> AvmResult<Vec<WasmValue>> {
        // 更新资源使用
        self.usage.call_count += 1;
        
        // 检查栈深度限制
        if self.usage.call_count as usize > self.config.limits.max_stack_depth {
            return Err(AvmError::WasmSandboxViolation(
                "Stack depth limit exceeded".to_string()
            ));
        }
        
        self.instance.call(function, args)
    }
    
    /// 检查权限
    pub fn check_permission(&self, permission: SandboxPermission) -> bool {
        self.config.permissions.contains(&permission)
    }
    
    /// 获取配置
    pub fn config(&self) -> &SandboxConfig {
        &self.config
    }
}

/// WASI 上下文
#[derive(Debug, Default)]
pub struct WasiContext {
    /// 标准输入
    pub stdin: Vec<u8>,
    /// 标准输出
    pub stdout: Vec<u8>,
    /// 标准错误
    pub stderr: Vec<u8>,
    /// 环境变量
    pub env: HashMap<String, String>,
    /// 预打开的目录
    pub preopens: Vec<(String, PathBuf)>,
}

impl WasiContext {
    /// 创建新的 WASI 上下文
    pub fn new() -> Self {
        Self {
            stdin: Vec::new(),
            stdout: Vec::new(),
            stderr: Vec::new(),
            env: HashMap::new(),
            preopens: Vec::new(),
        }
    }
    
    /// 设置环境变量
    pub fn set_env(&mut self, key: impl Into<String>, value: impl Into<String>) {
        self.env.insert(key.into(), value.into());
    }
    
    /// 获取环境变量
    pub fn get_env(&self, key: &str) -> Option<&String> {
        self.env.get(key)
    }
    
    /// 添加预打开目录
    pub fn add_preopen(&mut self, name: impl Into<String>, path: impl Into<PathBuf>) {
        self.preopens.push((name.into(), path.into()));
    }
    
    /// 写入标准输出
    pub fn write_stdout(&mut self, data: &[u8]) {
        self.stdout.extend_from_slice(data);
    }
    
    /// 写入标准错误
    pub fn write_stderr(&mut self, data: &[u8]) {
        self.stderr.extend_from_slice(data);
    }
    
    /// 读取标准输入
    pub fn read_stdin(&mut self, buf: &mut [u8]) -> usize {
        let len = buf.len().min(self.stdin.len());
        buf[..len].copy_from_slice(&self.stdin[..len]);
        self.stdin.drain(..len);
        len
    }
}

/// WASI 实现占位符 (实际实现需要 wasmtime-wasi)
pub struct WasiImpl {
    context: WasiContext,
}

impl WasiImpl {
    /// 创建新的 WASI 实现
    pub fn new(context: WasiContext) -> Self {
        Self { context }
    }
    
    /// 获取上下文
    pub fn context(&self) -> &WasiContext {
        &self.context
    }
    
    /// 获取可变上下文
    pub fn context_mut(&mut self) -> &mut WasiContext {
        &mut self.context
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_sandbox_permission() {
        let perm = SandboxPermission::FsRead;
        assert_eq!(perm.name(), "fs_read");
        
        let parsed = SandboxPermission::from_name("fs_read");
        assert_eq!(parsed, Some(SandboxPermission::FsRead));
        
        let invalid = SandboxPermission::from_name("invalid");
        assert_eq!(invalid, None);
    }
    
    #[test]
    fn test_permission_level() {
        let none_perms = PermissionLevel::None.permissions();
        assert!(none_perms.is_empty());
        
        let read_only = PermissionLevel::ReadOnly.permissions();
        assert!(read_only.contains(&SandboxPermission::FsRead));
        assert!(!read_only.contains(&SandboxPermission::FsWrite));
        
        let full = PermissionLevel::Full.permissions();
        assert!(full.contains(&SandboxPermission::FsRead));
        assert!(full.contains(&SandboxPermission::FsWrite));
        assert!(full.contains(&SandboxPermission::Network));
    }
    
    #[test]
    fn test_resource_limits() {
        let limits = ResourceLimits::default();
        assert_eq!(limits.max_cpu_time_ms, 5000);
        assert_eq!(limits.max_memory_bytes, 16 * 1024 * 1024);
        
        let unlimited = ResourceLimits::unlimited();
        assert_eq!(unlimited.max_cpu_time_ms, u64::MAX);
        
        let strict = ResourceLimits::strict();
        assert_eq!(strict.max_cpu_time_ms, 1000);
    }
    
    #[test]
    fn test_sandbox_config() {
        let config = SandboxConfig::default();
        assert!(!config.permissions.is_empty());
        
        let mut config = SandboxConfig::with_level(PermissionLevel::ReadOnly);
        assert!(config.has_permission(&SandboxPermission::FsRead));
        assert!(!config.has_permission(&SandboxPermission::FsWrite));
        
        config.add_permission(SandboxPermission::Network);
        assert!(config.has_permission(&SandboxPermission::Network));
        
        config.remove_permission(&SandboxPermission::FsRead);
        assert!(!config.has_permission(&SandboxPermission::FsRead));
    }
    
    #[test]
    fn test_sandbox_config_paths() {
        let mut config = SandboxConfig::default();
        config.add_allowed_path("/tmp");
        
        assert!(config.is_path_allowed(&PathBuf::from("/tmp/file.txt")));
        assert!(!config.is_path_allowed(&PathBuf::from("/home/user/file.txt")));
    }
    
    #[test]
    fn test_audit_log() {
        let mut log = AuditLog::new(10);
        
        log.add(AuditEvent {
            timestamp: std::time::Instant::now(),
            event_type: AuditEventType::FunctionCall,
            module: "test".to_string(),
            function: Some("main".to_string()),
            success: true,
            message: "Called main".to_string(),
        });
        
        assert_eq!(log.events().len(), 1);
        
        let filtered = log.filter(AuditEventType::FunctionCall);
        assert_eq!(filtered.len(), 1);
        
        log.clear();
        assert!(log.events().is_empty());
    }
    
    #[test]
    fn test_wasm_sandbox_creation() {
        let sandbox = WasmSandbox::default();
        assert!(!sandbox.config().permissions.is_empty());
    }
    
    #[test]
    fn test_wasm_sandbox_permission_check() {
        let mut config = SandboxConfig::with_level(PermissionLevel::ReadOnly);
        let sandbox = WasmSandbox::new(config.clone());
        
        // 应该通过
        assert!(sandbox.check_permission(SandboxPermission::FsRead).is_ok());
        
        // 应该失败
        config.remove_permission(&SandboxPermission::FsRead);
        let sandbox = WasmSandbox::new(config);
        assert!(sandbox.check_permission(SandboxPermission::FsRead).is_err());
    }
    
    #[test]
    fn test_wasi_context() {
        let mut ctx = WasiContext::new();
        
        ctx.set_env("PATH", "/usr/bin");
        assert_eq!(ctx.get_env("PATH"), Some(&"/usr/bin".to_string()));
        
        ctx.write_stdout(b"Hello");
        assert_eq!(&ctx.stdout, b"Hello");
        
        ctx.add_preopen("/tmp", "/tmp");
        assert_eq!(ctx.preopens.len(), 1);
    }
    
    #[test]
    fn test_resource_usage() {
        let usage = ResourceUsage::default();
        assert_eq!(usage.call_count, 0);
        assert_eq!(usage.cpu_time_ns, 0);
    }
    
    #[test]
    fn test_sandbox_instance() {
        let sandbox = WasmSandbox::default();
        
        let valid_wasm = vec![
            0x00, 0x61, 0x73, 0x6d,
            0x01, 0x00, 0x00, 0x00,
        ];
        
        let result = sandbox.load_module("test", valid_wasm);
        assert!(result.is_ok());
    }
}
