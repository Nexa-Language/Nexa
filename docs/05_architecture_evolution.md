# Nexa 架构演进规划 (Architecture Evolution)

> 本文档记录 Nexa 语言未来架构演进的技术规划和设计蓝图

## 1. Rust AVM 底座 (Agent Virtual Machine)

### 1.1 设计目标

从 Python 脚本解释转译模式跨越至基于 Rust 编写的独立编译型 Agent Virtual Machine (AVM)。

### 1.2 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    Nexa AVM Architecture                     │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Nexa       │  │  AST        │  │  Bytecode           │  │
│  │  Compiler   │→ │  Generator  │→ │  Generator          │  │
│  │  (Rust)     │  │  (Rust)     │  │  (Rust)             │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│                              ↓                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    AVM Runtime (Rust)                    │ │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────┐ │ │
│  │  │ Scheduler │ │ Memory    │ │ Tool      │ │ Sandbox │ │ │
│  │  │           │ │ Manager   │ │ Registry  │ │ (WASM)  │ │ │
│  │  └───────────┘ └───────────┘ └───────────┘ └─────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 核心组件

#### 编译器前端
- **语言**: Rust
- **词法分析**: 使用 `logos` crate 进行高性能词法分析
- **语法解析**: 使用 `lalrpop` 或手写递归下降解析器
- **AST**: 类型安全的抽象语法树表示

#### 字节码设计
```rust
// Nexa 字节码指令集
enum NexaOpcode {
    // Agent 操作
    AgentCreate { name: StringId },
    AgentRun { agent_id: u32 },
    AgentClone { agent_id: u32 },
    
    // 流程控制
    Pipeline { stages: Vec<u32> },
    Fork { agents: Vec<u32> },
    Merge { strategy: MergeStrategy },
    
    // 记忆操作
    MemStore { key: StringId, scope: MemoryScope },
    MemLoad { key: StringId },
    
    // 工具调用
    ToolCall { tool_id: u32, args: Vec<Value> },
    
    // 控制流
    Jump { offset: i32 },
    JumpIf { condition: bool, offset: i32 },
    SemanticIf { pattern: StringId },
    
    // LLM 调用
    LLMCall { model: StringId },
    LLMStream { model: StringId },
}
```

#### AVM 运行时
- **调度器**: 基于 Tokio 的异步任务调度
- **内存管理**: 零拷贝消息传递，arena 分配器
- **工具注册**: 动态加载 WASM 模块
- **安全沙盒**: WASMI 集成，资源限制

### 1.4 性能目标

| 指标 | Python 转译器 | Rust AVM |
|------|--------------|----------|
| 编译时间 | ~100ms | ~5ms |
| 启动时间 | ~500ms | ~10ms |
| 内存占用 | ~100MB | ~10MB |
| 并发 Agents | ~100 | ~10000 |

### 1.5 迁移路径

1. **Phase 1**: 用 Rust 重写编译器前端，生成 Python 代码（当前）
2. **Phase 2**: 实现字节码编译器和简单 VM
3. **Phase 3**: 迁移核心运行时到 Rust
4. **Phase 4**: 完全独立的 AVM，Python 作为 FFI 扩展

---

## 2. WASM 安全沙盒

### 2.1 设计目标

在 AVM 中引入 WebAssembly，对外部 `tool` 执行提供强隔离与跨平台兼容性。

### 2.2 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    WASM Sandbox Architecture                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    Host Interface                      │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐  │  │
│  │  │ stdin/stdout│ │ filesystem  │ │ network (HTTP)  │  │  │
│  │  └─────────────┘ └─────────────┘ └─────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                              ↓ WASI                         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    WASM Runtime                        │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │  Tool 1 (WASM)  │  Tool 2 (WASM)  │  Tool N     │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  资源限制: CPU时间 | 内存 | 文件系统 | 网络访问              │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 安全策略

```rust
// WASM 资源限制配置
struct WasmResourceLimits {
    max_memory_pages: u32,      // 最大内存页数
    max_table_elements: u32,    // 最大表元素数
    max_cpu_time_ms: u64,       // 最大 CPU 时间
    max_file_size: u64,         // 最大文件大小
    allowed_paths: Vec<PathBuf>, // 允许访问的路径
    allowed_hosts: Vec<String>,  // 允许访问的主机
    network_enabled: bool,       // 是否允许网络
}

impl Default for WasmResourceLimits {
    fn default() -> Self {
        Self {
            max_memory_pages: 256,    // 16MB
            max_table_elements: 1024,
            max_cpu_time_ms: 5000,    // 5秒
            max_file_size: 10 * 1024 * 1024, // 10MB
            allowed_paths: vec![],
            allowed_hosts: vec![],
            network_enabled: false,
        }
    }
}
```

### 2.4 工具开发 SDK

```rust
// WASM 工具开发 SDK
use nexa_wasm_sdk::*;

#[nexa_tool(
    name = "calculator",
    description = "Perform mathematical calculations"
)]
fn calculate(
    #[param(description = "Mathematical expression")] expression: String
) -> ToolResult<f64> {
    // 工具实现
    let result = eval_expression(&expression)?;
    Ok(result)
}
```

---

## 3. 可视化 DAG 编辑器

### 3.1 设计目标

提供基于 Web 的节点拖拽界面，支持逆向生成 Nexa 代码。

### 3.2 技术栈

- **前端**: React + TypeScript
- **图形库**: React Flow / X6
- **后端**: Rust (Axum) + WebSocket
- **实时同步**: CRDT for collaborative editing

### 3.3 节点类型设计

```typescript
// DAG 节点类型定义
interface DAGNode {
  id: string;
  type: 'agent' | 'tool' | 'condition' | 'fork' | 'merge' | 'transform';
  position: { x: number; y: number };
  data: {
    label: string;
    config: Record<string, any>;
    inputs: Port[];
    outputs: Port[];
  };
}

// 端口定义
interface Port {
  id: string;
  name: string;
  type: 'string' | 'object' | 'stream';
  required: boolean;
}

// 边定义
interface DAGEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle: string;
  targetHandle: string;
  label?: string;
}
```

### 3.4 代码生成

```typescript
// DAG 到 Nexa 代码生成
function generateNexaCode(dag: DAGGraph): string {
  const agents = dag.nodes.filter(n => n.type === 'agent');
  const edges = dag.edges;
  
  let code = '';
  
  // 生成 Agent 声明
  for (const agent of agents) {
    code += generateAgentDeclaration(agent);
  }
  
  // 生成 Flow
  code += 'flow main {\n';
  code += generateFlowBody(dag);
  code += '}\n';
  
  return code;
}
```

### 3.5 功能规划

1. **Phase 1**: 基础编辑器，支持节点拖拽和连接
2. **Phase 2**: 实时预览和代码生成
3. **Phase 3**: 协作编辑和版本控制
4. **Phase 4**: 调试和性能分析集成

---

## 4. 智能调度器 (Smart Scheduler)

### 4.1 设计目标

在 AVM 层基于系统负载、Agent 优先级动态分配并发资源。

### 4.2 调度策略

```rust
// 调度器配置
struct SchedulerConfig {
    max_concurrent_agents: usize,
    priority_levels: u8,
    time_slice_ms: u64,
    load_balance_strategy: LoadBalanceStrategy,
}

enum LoadBalanceStrategy {
    RoundRobin,
    LeastLoaded,
    WeightedFair,      // 基于权重的公平调度
    PriorityBased,     // 优先级调度
    Adaptive,          // 自适应调度
}

// Agent 调度信息
struct AgentScheduleInfo {
    agent_id: AgentId,
    priority: u8,
    weight: f32,
    estimated_duration_ms: u64,
    dependencies: Vec<AgentId>,
    resource_requirements: ResourceRequirements,
}
```

### 4.3 调度算法

```rust
impl Scheduler {
    // 自适应调度决策
    fn schedule(&mut self, agents: Vec<AgentScheduleInfo>) -> SchedulePlan {
        // 1. 构建依赖图
        let dep_graph = self.build_dependency_graph(&agents);
        
        // 2. 拓扑排序
        let order = dep_graph.topological_sort();
        
        // 3. 并行度分析
        let parallel_groups = self.analyze_parallelism(&order);
        
        // 4. 资源分配
        let allocation = self.allocate_resources(&parallel_groups);
        
        // 5. 生成调度计划
        SchedulePlan {
            stages: parallel_groups,
            allocation,
            estimated_total_time: self.estimate_completion_time(&allocation),
        }
    }
    
    // 动态负载均衡
    fn rebalance(&mut self, current_load: &SystemLoad) -> Vec<ScheduleAdjustment> {
        let adjustments = Vec::new();
        
        // 检测过载节点
        for node in &current_load.nodes {
            if node.utilization > 0.8 {
                // 迁移部分任务到低负载节点
                adjustments.extend(self.migrate_tasks(node));
            }
        }
        
        adjustments
    }
}
```

---

## 5. 向量虚存分页 (Context Paging)

### 5.1 设计目标

AVM 接管内存，自动执行对话历史的向量化置换与透明加载。

### 5.2 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                  Context Paging Architecture                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Active Memory (RAM)                     │    │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────────────┐  │    │
│  │  │ Context   │ │ Working   │ │ Vector           │  │    │
│  │  │ Window    │ │ Memory    │ │ Index (Hot)      │  │    │
│  │  └───────────┘ └───────────┘ └───────────────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
│                          ↑↓ Swap                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Paged Storage (Disk/Vector DB)          │    │
│  │  ┌───────────────────────────────────────────────┐  │    │
│  │  │  Page 1   │  Page 2   │  Page 3   │  ...     │  │    │
│  │  │  (vec)    │  (vec)    │  (vec)    │          │  │    │
│  │  └───────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 分页策略

```rust
// 分页配置
struct PagingConfig {
    page_size: usize,           // 每页消息数
    max_active_pages: usize,    // 最大活跃页数
    embedding_model: String,    // 嵌入模型
    similarity_threshold: f32,  // 相似度阈值
    eviction_policy: EvictionPolicy,
}

enum EvictionPolicy {
    LRU,           // 最近最少使用
    LFU,           // 最不常用
    Relevance,     // 基于相关性
    Hybrid,        // 混合策略
}

// 内存页
struct MemoryPage {
    id: PageId,
    messages: Vec<Message>,
    embedding: Vec<f32>,      // 页面摘要嵌入
    last_accessed: Instant,
    access_count: u64,
    relevance_score: f32,
}
```

### 5.4 页面加载

```rust
impl ContextPager {
    // 智能页面加载
    async fn load_relevant_pages(&mut self, query: &str) -> Vec<MemoryPage> {
        // 1. 计算查询嵌入
        let query_embedding = self.embed(query).await;
        
        // 2. 向量检索找到相关页面
        let relevant = self.vector_index
            .search(&query_embedding, self.config.max_active_pages)
            .await;
        
        // 3. 加载页面到活跃内存
        let mut pages = Vec::new();
        for page_id in relevant {
            if !self.is_active(page_id) {
                let page = self.load_page(page_id).await;
                pages.push(page);
            }
        }
        
        // 4. 必要时驱逐旧页面
        self.ensure_capacity();
        
        pages
    }
    
    // 页面驱逐
    fn ensure_capacity(&mut self) {
        while self.active_pages.len() > self.config.max_active_pages {
            let to_evict = self.select_eviction_candidate();
            self.swap_out(to_evict);
        }
    }
}
```

---

## 6. 实施路线图

### 2024 Q1-Q2: 基础架构
- [ ] Rust 编译器前端原型
- [ ] WASM 运行时集成
- [ ] 基础调度器实现

### 2024 Q3-Q4: 核心功能
- [ ] 字节码编译器
- [ ] 可视化编辑器 MVP
- [ ] 向量分页原型

### 2025 Q1-Q2: 生产就绪
- [ ] AVM 稳定版发布
- [ ] 完整安全沙盒
- [ ] 编辑器正式版

### 2025 Q3-Q4: 生态扩展
- [ ] 插件系统
- [ ] 云端部署
- [ ] 企业级功能

---

*此文档将随项目进展持续更新*