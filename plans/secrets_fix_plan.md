# Secrets.nxs 解析问题修复方案

## 问题诊断

### 错误现象
运行 `nexa run 01_hello_world.nx` 时出现 OpenAI API 认证错误：
```
openai.AuthenticationError: Error code: 401 - {'error': {'message': 'Incorrect API key provided: sk-Yq-qW*************We2Q...
```

### 根本原因分析

经过代码审查，发现以下问题：

#### 1. secrets.py 的 `get()` 方法设计缺陷

**位置**: [`src/runtime/secrets.py:104-106`](src/runtime/secrets.py:104)

```python
def get(self, key: str):
    # Fallback for old secret("KEY") calls
    return os.environ.get(key, "")
```

**问题**: `get()` 方法只返回环境变量，完全不返回解析后的 config 块内容。这意味着即使 secrets.nxs 文件被正确解析，通过 `get()` 也无法获取其中的配置。

#### 2. 两种 secrets.nxs 格式不兼容

**旧格式** (根目录 `secrets.nxs`):
```
OPENAI_API_KEY = "sk-Yq-qWVwmUvF8EpJdM-We2Q"
OPENAI_API_BASE = "https://aihub.arcsysu.cn/v1"
```

**新格式** (examples 目录 `secrets.nxs`):
```
config default{
    BASE_URL = "https://aihub.arcsysu.cn/v1"
    API_KEY = "sk-YCPxyABmlYgRt7A4arm77A"
    MODEL_NAME = {
        "strong": "minimax-m2.5",
        "weak": "deepseek-chat",
        "super": "glm-5"
    }
}
```

**问题**: `_parse_nxs()` 方法只解析 `config xxx { ... }` 格式的块，旧格式无法被解析。

#### 3. agent.py 的 fallback 逻辑使用硬编码无效 key

**位置**: [`src/runtime/agent.py:59-75`](src/runtime/agent.py:59)

```python
api_key = nexa_secrets.get(f"{self.provider.upper()}_API_KEY")
base_url = nexa_secrets.get(f"{self.provider.upper()}_BASE_URL")

# Fallbacks for existing environment
if not api_key:
    api_key = "sk-lDc9yRMvfPzpxXKuuXB2LA" if self.provider in ["minimax", "deepseek"] else (nexa_secrets.get("OPENAI_API_KEY") or "sk-lDc9yRMvfPzpxXKuuXB2LA")
```

**问题**: 
- `nexa_secrets.get()` 返回空字符串
- fallback 到硬编码的 `"sk-lDc9yRMvfPzpxXKuuXB2LA"`，这个 key 可能已过期或无效

#### 4. core.py 存在硬编码配置

**位置**: [`src/runtime/core.py:4-9`](src/runtime/core.py:4)

```python
client = OpenAI(
    base_url="https://aihub.arcsysu.cn/v1",
    api_key="sk-lDc9yRMvfPzpxXKuuXB2LA"
)
```

**问题**: 全局 client 使用硬编码配置，应该从 secrets 动态获取。

#### 5. 运行目录影响

当在 `examples/` 目录运行时，`_load_secrets()` 使用 `pathlib.Path.cwd()` 查找 secrets.nxs：
- 加载的是 `examples/secrets.nxs`（新格式）
- 但解析后的配置无法通过 `get()` 方法访问

---

## 修复方案

### 方案概述

统一 secrets.nxs 格式，修复 secrets.py 的解析和访问逻辑，移除所有硬编码配置。

### 修改清单

#### 1. 重构 secrets.py

**目标**: 支持两种格式，提供正确的 `get()` 方法

**修改内容**:

```python
class NexaSecrets:
    def __init__(self):
        self._flat_configs = {}  # 旧格式: KEY -> VALUE
        self._block_configs = {}  # 新格式: config_name -> ConfigNode
        self._load_secrets()
        
    def _parse_nxs(self, content):
        """解析两种格式的 secrets.nxs"""
        # 1. 先解析 config block 格式
        blocks = self._parse_config_blocks(content)
        
        # 2. 再解析扁平格式 (KEY = VALUE，不在 config 块内)
        flat = self._parse_flat_format(content)
        
        return blocks, flat
    
    def _parse_flat_format(self, content):
        """解析旧格式: OPENAI_API_KEY = "xxx" """
        flat = {}
        # 移除 config 块内的内容，只保留块外的赋值
        # ... 实现细节
        
    def get(self, key: str, default: str = ""):
        """优先级: block_configs.default > flat_configs > 环境变量"""
        # 1. 先查 default config block
        if "default" in self._block_configs:
            val = self._block_configs["default"].get(key)
            if val:
                return val
        
        # 2. 再查 flat configs
        if key in self._flat_configs:
            return self._flat_configs[key]
        
        # 3. 最后查环境变量
        return os.environ.get(key, default)
```

#### 2. 修改 agent.py 的初始化逻辑

**目标**: 正确从 secrets 获取配置，移除硬编码 fallback

**修改内容**:

```python
# Init Client - 修改第59-75行
api_key = nexa_secrets.get(f"{self.provider.upper()}_API_KEY")
base_url = nexa_secrets.get(f"{self.provider.upper()}_BASE_URL")

# 如果 provider 特定的 key 不存在，尝试通用配置
if not api_key:
    api_key = nexa_secrets.get("API_KEY")
if not base_url:
    base_url = nexa_secrets.get("BASE_URL")

# 最后 fallback 到环境变量 (不再硬编码)
if not api_key:
    raise ValueError(f"API key not found for provider '{self.provider}'. Please configure secrets.nxs or set environment variable.")
```

#### 3. 修改 core.py

**目标**: 移除硬编码，从 secrets 动态获取

**修改内容**:

```python
from .secrets import nexa_secrets

# 动态获取配置
_base_url = nexa_secrets.get("BASE_URL") or nexa_secrets.get("OPENAI_API_BASE") or "https://api.openai.com/v1"
_api_key = nexa_secrets.get("API_KEY") or nexa_secrets.get("OPENAI_API_KEY")

if not _api_key:
    raise ValueError("API key not configured. Please create secrets.nxs with API_KEY or OPENAI_API_KEY.")

client = OpenAI(
    base_url=_base_url,
    api_key=_api_key
)

# MODEL_NAME 配置
_model_config = nexa_secrets.default.MODEL_NAME if hasattr(nexa_secrets.default, 'MODEL_NAME') else {}
STRONG_MODEL = _model_config.get("strong", "gpt-4")
WEAK_MODEL = _model_config.get("weak", "gpt-3.5-turbo")
```

#### 4. 统一 secrets.nxs 格式

**目标**: 使用统一的新格式，放在项目根目录

**建议格式**:

```
config default {
    BASE_URL = "https://aihub.arcsysu.cn/v1",
    API_KEY = "sk-YCPxyABmlYgRt7A4arm77A",
    MODEL_NAME = {
        "strong": "minimax-m2.5",
        "weak": "deepseek-chat",
        "super": "glm-5"
    }
}

// Provider-specific overrides (optional)
config openai {
    BASE_URL = "https://api.openai.com/v1",
    API_KEY = "sk-your-openai-key"
}

config deepseek {
    BASE_URL = "https://api.deepseek.com/v1",
    API_KEY = "sk-your-deepseek-key"
}
```

---

## 实施步骤

1. **修改 secrets.py**:
   - 添加 `_flat_configs` 存储
   - 实现 `_parse_flat_format()` 方法
   - 重构 `get()` 方法支持多级查找
   - 添加 `get_model_config()` 方法获取模型配置

2. **修改 agent.py**:
   - 重构 API key 获取逻辑
   - 移除硬编码 fallback
   - 添加配置缺失时的明确错误提示

3. **修改 core.py**:
   - 移除硬编码配置
   - 从 secrets 动态获取 base_url, api_key, model 配置

4. **统一 secrets.nxs**:
   - 合并根目录和 examples 目录的配置
   - 使用新格式放在根目录
   - 删除 examples/secrets.nxs (或保持同步)

5. **测试验证**:
   - 运行 `nexa run 01_hello_world.nx` 验证修复

---

## 风险评估

- **低风险**: 修改仅涉及配置加载逻辑，不影响核心业务逻辑
- **向后兼容**: 新格式支持旧格式的字段名 (OPENAI_API_KEY 等)
- **测试覆盖**: 需要添加 secrets 解析的单元测试

---

## 预期结果

修复后，运行 `nexa run 01_hello_world.nx` 应能正确：
1. 解析 secrets.nxs 中的 API_KEY 和 BASE_URL
2. 使用正确的 API key 调用 LLM
3. 不再出现 401 认证错误