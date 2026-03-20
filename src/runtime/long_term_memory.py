"""
Nexa 长期记忆系统 (Long-term Memory System)
参考 Claude Code 的 CLAUDE.md 设计，为 Agent 提供持久化的长期记忆和经验存储
"""

import os
import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class MemoryEntry:
    """记忆条目"""
    id: str
    content: str
    category: str  # experience, lesson, knowledge, preference
    created_at: str
    last_accessed: str
    access_count: int = 0
    importance: float = 1.0  # 0-1, 用于优先级排序
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class LongTermMemory:
    """
    长期记忆系统
    
    特性：
    - 持久化存储：记忆保存在 markdown 文件中，易于阅读和编辑
    - 分类管理：支持经验、教训、知识、偏好等分类
    - 智能检索：基于标签和重要性排序
    - 自动学习：从对话中提取有价值的信息
    """
    
    DEFAULT_MEMORY_FILE = "MEMORY.md"
    MEMORY_CATEGORIES = ["experience", "lesson", "knowledge", "preference", "context"]
    
    # Markdown 模板
    MEMORY_TEMPLATE = '''# {agent_name} 长期记忆

> 此文件由 Nexa 长期记忆系统自动维护
> 最后更新: {last_updated}

## 📚 经验总结 (Experience)

{experience_section}

## ⚠️ 经验教训 (Lessons Learned)

{lessons_section}

## 💡 知识库 (Knowledge)

{knowledge_section}

## 🎯 用户偏好 (User Preferences)

{preference_section}

## 📋 上下文信息 (Context)

{context_section}

---
*此记忆文件帮助 Agent 在不同会话间保持一致性和学习能力*
'''
    
    ENTRY_TEMPLATE = '''
### {id}
- **创建时间**: {created_at}
- **重要性**: {importance}/10
- **标签**: {tags}
- **访问次数**: {access_count}

{content}

---
'''
    
    def __init__(self, agent_name: str, memory_file: str = None, auto_save: bool = True):
        self.agent_name = agent_name
        self.memory_file = Path(memory_file or self.DEFAULT_MEMORY_FILE)
        self.auto_save = auto_save
        
        # 内存中的记忆存储
        self.memories: Dict[str, MemoryEntry] = {}
        self.categories: Dict[str, List[str]] = {
            cat: [] for cat in self.MEMORY_CATEGORIES
        }
        
        # 加载现有记忆
        self._load()
        
    def _load(self):
        """从文件加载记忆"""
        if not self.memory_file.exists():
            return
            
        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                content = f.read()
            self._parse_markdown(content)
        except Exception as e:
            print(f"[LongTermMemory] Warning: Failed to load memory: {e}")
            
    def _parse_markdown(self, content: str):
        """解析 Markdown 格式的记忆文件"""
        # 解析各个分类下的条目
        current_category = None
        current_entry = None
        
        lines = content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 检测分类标题
            for cat in self.MEMORY_CATEGORIES:
                if f"##" in line and cat.upper() in line.upper():
                    current_category = cat
                    break
                    
            # 检测条目开始 (### 开头)
            if line.startswith("### ") and current_category:
                entry_id = line[4:].strip()
                current_entry = {
                    "id": entry_id,
                    "category": current_category
                }
                
            # 解析条目属性
            if current_entry and line.startswith("- **"):
                match = re.match(r"- \*\*(\w+)\*\*:\s*(.+)", line)
                if match:
                    key, value = match.groups()
                    if key == "创建时间":
                        current_entry["created_at"] = value
                    elif key == "重要性":
                        current_entry["importance"] = float(value.split("/")[0]) / 10
                    elif key == "标签":
                        current_entry["tags"] = [t.strip() for t in value.split(",")]
                    elif key == "访问次数":
                        current_entry["access_count"] = int(value)
                        
            # 解析条目内容
            if current_entry and not line.startswith("-") and not line.startswith("###") and not line.startswith("##") and line.strip() and not line.startswith("---"):
                if "content" not in current_entry:
                    current_entry["content"] = line
                else:
                    current_entry["content"] += "\n" + line
                    
            # 条目结束
            if line.startswith("---") and current_entry:
                if "content" in current_entry:
                    entry = MemoryEntry(
                        id=current_entry.get("id", f"entry_{len(self.memories)}"),
                        content=current_entry.get("content", ""),
                        category=current_entry.get("category", "knowledge"),
                        created_at=current_entry.get("created_at", datetime.now().isoformat()),
                        last_accessed=datetime.now().isoformat(),
                        access_count=current_entry.get("access_count", 0),
                        importance=current_entry.get("importance", 0.5),
                        tags=current_entry.get("tags", [])
                    )
                    self.memories[entry.id] = entry
                    self.categories[entry.category].append(entry.id)
                current_entry = None
                
            i += 1
            
    def add(
        self,
        content: str,
        category: str = "knowledge",
        importance: float = 0.5,
        tags: List[str] = None
    ) -> str:
        """
        添加新的记忆条目
        
        Args:
            content: 记忆内容
            category: 分类
            importance: 重要性 (0-1)
            tags: 标签列表
            
        Returns:
            条目ID
        """
        if category not in self.MEMORY_CATEGORIES:
            category = "knowledge"
            
        entry_id = f"{category}_{len(self.memories)}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        entry = MemoryEntry(
            id=entry_id,
            content=content,
            category=category,
            created_at=datetime.now().isoformat(),
            last_accessed=datetime.now().isoformat(),
            access_count=0,
            importance=min(1.0, max(0.0, importance)),
            tags=tags or []
        )
        
        self.memories[entry_id] = entry
        self.categories[category].append(entry_id)
        
        if self.auto_save:
            self.save()
            
        print(f"[LongTermMemory] Added memory: {entry_id}")
        return entry_id
        
    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """获取记忆条目"""
        entry = self.memories.get(entry_id)
        if entry:
            entry.access_count += 1
            entry.last_accessed = datetime.now().isoformat()
        return entry
        
    def search(
        self,
        query: str = None,
        category: str = None,
        tags: List[str] = None,
        min_importance: float = 0.0,
        limit: int = 10
    ) -> List[MemoryEntry]:
        """
        搜索记忆
        
        Args:
            query: 搜索关键词
            category: 分类过滤
            tags: 标签过滤
            min_importance: 最小重要性
            limit: 返回数量限制
            
        Returns:
            匹配的记忆条目列表
        """
        results = []
        
        for entry in self.memories.values():
            # 分类过滤
            if category and entry.category != category:
                continue
                
            # 重要性过滤
            if entry.importance < min_importance:
                continue
                
            # 标签过滤
            if tags and not any(t in entry.tags for t in tags):
                continue
                
            # 关键词搜索
            if query:
                query_lower = query.lower()
                if (query_lower not in entry.content.lower() and
                    query_lower not in " ".join(entry.tags).lower()):
                    continue
                    
            results.append(entry)
            
        # 按重要性和访问次数排序
        results.sort(key=lambda x: (x.importance, x.access_count), reverse=True)
        
        return results[:limit]
        
    def get_context_for_prompt(self, max_entries: int = 5) -> str:
        """
        获取用于注入到 Agent prompt 的上下文
        
        Args:
            max_entries: 最大条目数
            
        Returns:
            格式化的上下文字符串
        """
        # 获取高重要性的记忆
        all_entries = list(self.memories.values())
        all_entries.sort(key=lambda x: (x.importance, x.access_count), reverse=True)
        
        selected = all_entries[:max_entries]
        
        if not selected:
            return ""
            
        context_parts = ["[长期记忆 / Long-term Memory]"]
        
        for entry in selected:
            context_parts.append(f"- [{entry.category}] {entry.content[:200]}...")
            
        return "\n".join(context_parts)
        
    def update(self, entry_id: str, content: str = None, importance: float = None, tags: List[str] = None):
        """更新记忆条目"""
        if entry_id not in self.memories:
            return False
            
        entry = self.memories[entry_id]
        
        if content is not None:
            entry.content = content
        if importance is not None:
            entry.importance = min(1.0, max(0.0, importance))
        if tags is not None:
            entry.tags = tags
            
        if self.auto_save:
            self.save()
            
        return True
        
    def delete(self, entry_id: str) -> bool:
        """删除记忆条目"""
        if entry_id not in self.memories:
            return False
            
        entry = self.memories[entry_id]
        del self.memories[entry_id]
        
        if entry_id in self.categories[entry.category]:
            self.categories[entry.category].remove(entry_id)
            
        if self.auto_save:
            self.save()
            
        return True
        
    def save(self):
        """保存记忆到文件"""
        try:
            content = self._generate_markdown()
            
            # 确保目录存在
            self.memory_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.memory_file, "w", encoding="utf-8") as f:
                f.write(content)
                
            print(f"[LongTermMemory] Saved to {self.memory_file}")
            
        except Exception as e:
            print(f"[LongTermMemory] Error saving: {e}")
            
    def _generate_markdown(self) -> str:
        """生成 Markdown 格式的记忆文件"""
        sections = {}
        
        for cat in self.MEMORY_CATEGORIES:
            entries = [self.memories[eid] for eid in self.categories[cat] if eid in self.memories]
            entries.sort(key=lambda x: x.importance, reverse=True)
            
            if entries:
                section_content = ""
                for entry in entries:
                    section_content += self.ENTRY_TEMPLATE.format(
                        id=entry.id,
                        created_at=entry.created_at,
                        importance=int(entry.importance * 10),
                        tags=", ".join(entry.tags) if entry.tags else "无",
                        access_count=entry.access_count,
                        content=entry.content
                    )
                sections[cat] = section_content
            else:
                sections[cat] = "\n*暂无记忆*\n"
                
        return self.MEMORY_TEMPLATE.format(
            agent_name=self.agent_name,
            last_updated=datetime.now().isoformat(),
            experience_section=sections.get("experience", ""),
            lessons_section=sections.get("lesson", ""),
            knowledge_section=sections.get("knowledge", ""),
            preference_section=sections.get("preference", ""),
            context_section=sections.get("context", "")
        )
        
    def learn_from_conversation(self, messages: List[Dict], extraction_model=None):
        """
        从对话中学习并提取有价值的信息
        
        Args:
            messages: 对话消息列表
            extraction_model: 用于提取信息的模型（可选）
        """
        # 简单实现：提取关键决策和结论
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "")
            
            # 检测可能的决策或结论
            decision_patterns = [
                r"决定[：:]\s*(.+)",
                r"结论[：:]\s*(.+)",
                r"最终答案[：:]\s*(.+)",
                r"建议[：:]\s*(.+)",
                r"注意[：:]\s*(.+)",
            ]
            
            for pattern in decision_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if len(match) > 10:  # 忽略太短的内容
                        self.add(
                            content=match.strip(),
                            category="experience" if role == "assistant" else "preference",
                            importance=0.7,
                            tags=["auto-extracted", "conversation"]
                        )


class MemoryBank:
    """
    记忆银行 - 管理多个 Agent 的长期记忆
    """
    
    def __init__(self, base_dir: str = ".nexa_memory"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._agents: Dict[str, LongTermMemory] = {}
        
    def get_memory(self, agent_name: str) -> LongTermMemory:
        """获取指定 Agent 的长期记忆"""
        if agent_name not in self._agents:
            memory_file = self.base_dir / f"{agent_name}_MEMORY.md"
            self._agents[agent_name] = LongTermMemory(
                agent_name=agent_name,
                memory_file=str(memory_file)
            )
        return self._agents[agent_name]
        
    def get_shared_knowledge(self) -> str:
        """获取所有 Agent 共享的知识"""
        shared_file = self.base_dir / "SHARED_KNOWLEDGE.md"
        if shared_file.exists():
            with open(shared_file, "r", encoding="utf-8") as f:
                return f.read()
        return ""
        
    def add_shared_knowledge(self, content: str, category: str = "knowledge"):
        """添加共享知识"""
        shared_file = self.base_dir / "SHARED_KNOWLEDGE.md"
        
        existing = ""
        if shared_file.exists():
            with open(shared_file, "r", encoding="utf-8") as f:
                existing = f.read()
                
        with open(shared_file, "w", encoding="utf-8") as f:
            f.write(f"{existing}\n\n## {datetime.now().isoformat()}\n\n{content}\n")


# 全局记忆银行实例
_global_memory_bank: Optional[MemoryBank] = None


def get_memory_bank() -> MemoryBank:
    """获取全局记忆银行实例"""
    global _global_memory_bank
    if _global_memory_bank is None:
        _global_memory_bank = MemoryBank()
    return _global_memory_bank


def get_agent_memory(agent_name: str) -> LongTermMemory:
    """便捷函数：获取指定 Agent 的长期记忆"""
    return get_memory_bank().get_memory(agent_name)


__all__ = [
    'LongTermMemory', 'MemoryEntry', 'MemoryBank',
    'get_memory_bank', 'get_agent_memory'
]