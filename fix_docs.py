with open("docs/03_roadmap_and_vision.md", "r") as f:
    text = f.read()
if "阶段 5" not in text:
    text = text.replace("## 阶段 3: v1.0 - The Rust AVM (智能体虚拟机)", """## 阶段 3: v0.6 模块化与安全纪元 (已完成 ✅)
**定位：** 引领代码复用与原生安全防护。
* **核心特性：**
  * **密钥隔离 (.nxs)：** 原生剔除硬编码密钥，引入 `secret("KEY")` 运行时动态注入与只读加载环境。
  * **原生标准库与包导入 (.nxlib)：** 添加 `include` 关键字合并跨文件 AST，允许开发者构建定制化 Agent 插件并分发。

## 阶段 4: v0.8 MCP 与流式响应 (规划中 🌟)
**定位：** 打通生态次元壁与人机交互升级。
* **MCP (Model Context Protocol) 接入底座：** 支持一键挂载标准 MCP Server 转化为 `std` 命名空间工具，让 Nexa 瞬间拥有海量开源工具矩阵。
* **终端级原生 Streaming：** 优化底层 Runtime 打印流，适应大模型推理流性质，彻底解决执行时的黑盒盲等时间。

## 阶段 5: v1.0 - The Rust AVM (智能体虚拟机)
* **包含 NxPM (Nexa Package Manager):** 类似于 npm，基于模块化体系引入云端包管理器支持，一键安装第三方智能体。""")
    
    with open("docs/03_roadmap_and_vision.md", "w") as f:
        f.write(text)
