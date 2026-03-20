"""
Nexa 知识图谱记忆管理系统 (Knowledge Graph Memory)
将 Agent 的记忆以结构化的方式存储和查询，提升推理能力和知识整合能力
"""

import os
import json
import re
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
from pathlib import Path
import hashlib


@dataclass
class Entity:
    """知识实体"""
    id: str
    name: str
    entity_type: str  # person, concept, event, object, location
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    confidence: float = 1.0
    source: str = ""  # 来源（哪个Agent或对话）
    

@dataclass
class Relation:
    """知识关系"""
    id: str
    source_id: str  # 起始实体ID
    target_id: str  # 目标实体ID
    relation_type: str  # 关系类型
    properties: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    evidence: str = ""  # 证据/来源文本
    

@dataclass
class KnowledgeTriple:
    """知识三元组 (主体, 关系, 客体)"""
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0
    source: str = ""
    

class KnowledgeGraph:
    """
    知识图谱
    
    特性：
    - 实体管理：存储和管理知识实体
    - 关系推理：支持基于关系的推理
    - 路径查询：查找实体间的关联路径
    - 知识融合：合并来自不同来源的知识
    - 知识衰减：支持知识的时效性管理
    """
    
    # 预定义关系类型
    RELATION_TYPES = {
        "is_a": "是一个",
        "has_part": "包含",
        "related_to": "相关",
        "causes": "导致",
        "follows": "跟随",
        "precedes": "先于",
        "located_at": "位于",
        "created_by": "由...创建",
        "used_for": "用于",
        "depends_on": "依赖于",
        "contradicts": "与...矛盾",
        "supports": "支持",
        "example_of": "是...的例子",
        " synonym_of": "同义于",
    }
    
    # 实体类型
    ENTITY_TYPES = ["person", "concept", "event", "object", "location", "organization", "topic"]
    
    def __init__(self, name: str = "default", storage_path: str = None):
        self.name = name
        self.storage_path = Path(storage_path or f".nexa_knowledge/{name}")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # 内存存储
        self.entities: Dict[str, Entity] = {}
        self.relations: Dict[str, Relation] = {}
        
        # 索引
        self._entity_name_index: Dict[str, str] = {}  # name -> id
        self._outgoing_index: Dict[str, List[str]] = defaultdict(list)  # entity_id -> [relation_ids]
        self._incoming_index: Dict[str, List[str]] = defaultdict(list)  # entity_id -> [relation_ids]
        self._type_index: Dict[str, Set[str]] = defaultdict(set)  # type -> {entity_ids}
        
        # 加载现有知识
        self._load()
        
    def _generate_id(self, content: str) -> str:
        """生成唯一ID"""
        return hashlib.md5(content.encode()).hexdigest()[:12]
        
    def add_entity(
        self,
        name: str,
        entity_type: str,
        properties: Dict[str, Any] = None,
        confidence: float = 1.0,
        source: str = ""
    ) -> Entity:
        """
        添加实体
        
        Args:
            name: 实体名称
            entity_type: 实体类型
            properties: 属性字典
            confidence: 置信度
            source: 来源
            
        Returns:
            创建的实体
        """
        # 检查是否已存在同名实体
        if name in self._entity_name_index:
            existing_id = self._entity_name_index[name]
            existing = self.entities[existing_id]
            # 合并属性
            if properties:
                existing.properties.update(properties)
            existing.confidence = max(existing.confidence, confidence)
            return existing
            
        entity_id = self._generate_id(f"{entity_type}:{name}")
        
        entity = Entity(
            id=entity_id,
            name=name,
            entity_type=entity_type,
            properties=properties or {},
            confidence=confidence,
            source=source
        )
        
        self.entities[entity_id] = entity
        self._entity_name_index[name] = entity_id
        self._type_index[entity_type].add(entity_id)
        
        return entity
        
    def add_relation(
        self,
        source_name: str,
        relation_type: str,
        target_name: str,
        properties: Dict[str, Any] = None,
        confidence: float = 1.0,
        evidence: str = ""
    ) -> Optional[Relation]:
        """
        添加关系
        
        Args:
            source_name: 起始实体名称
            relation_type: 关系类型
            target_name: 目标实体名称
            properties: 属性
            confidence: 置信度
            evidence: 证据文本
            
        Returns:
            创建的关系
        """
        # 确保实体存在
        if source_name not in self._entity_name_index:
            self.add_entity(source_name, "concept")
        if target_name not in self._entity_name_index:
            self.add_entity(target_name, "concept")
            
        source_id = self._entity_name_index[source_name]
        target_id = self._entity_name_index[target_name]
        
        # 检查是否已存在相同关系
        for rel_id in self._outgoing_index[source_id]:
            rel = self.relations[rel_id]
            if rel.target_id == target_id and rel.relation_type == relation_type:
                # 更新现有关系
                if properties:
                    rel.properties.update(properties)
                rel.confidence = max(rel.confidence, confidence)
                return rel
                
        relation_id = self._generate_id(f"{source_id}:{relation_type}:{target_id}")
        
        relation = Relation(
            id=relation_id,
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            properties=properties or {},
            confidence=confidence,
            evidence=evidence
        )
        
        self.relations[relation_id] = relation
        self._outgoing_index[source_id].append(relation_id)
        self._incoming_index[target_id].append(relation_id)
        
        return relation
        
    def add_triple(self, triple: KnowledgeTriple) -> Tuple[Entity, Relation, Entity]:
        """添加知识三元组"""
        source_entity = self.add_entity(triple.subject, "concept", source=triple.source)
        target_entity = self.add_entity(triple.object, "concept", source=triple.source)
        relation = self.add_relation(
            source_name=triple.subject,
            relation_type=triple.predicate,
            target_name=triple.object,
            confidence=triple.confidence,
            evidence=triple.source
        )
        return source_entity, relation, target_entity
        
    def get_entity(self, name: str) -> Optional[Entity]:
        """通过名称获取实体"""
        entity_id = self._entity_name_index.get(name)
        if entity_id:
            return self.entities[entity_id]
        return None
        
    def get_relations(
        self,
        entity_name: str,
        relation_type: str = None,
        direction: str = "both"
    ) -> List[Relation]:
        """
        获取实体的关系
        
        Args:
            entity_name: 实体名称
            relation_type: 关系类型过滤
            direction: outgoing, incoming, 或 both
            
        Returns:
            关系列表
        """
        entity_id = self._entity_name_index.get(entity_name)
        if not entity_id:
            return []
            
        relations = []
        
        if direction in ("outgoing", "both"):
            for rel_id in self._outgoing_index.get(entity_id, []):
                rel = self.relations[rel_id]
                if relation_type is None or rel.relation_type == relation_type:
                    relations.append(rel)
                    
        if direction in ("incoming", "both"):
            for rel_id in self._incoming_index.get(entity_id, []):
                rel = self.relations[rel_id]
                if relation_type is None or rel.relation_type == relation_type:
                    relations.append(rel)
                    
        return relations
        
    def find_path(
        self,
        source_name: str,
        target_name: str,
        max_depth: int = 3
    ) -> List[List[str]]:
        """
        查找两个实体之间的路径
        
        Args:
            source_name: 起始实体名称
            target_name: 目标实体名称
            max_depth: 最大搜索深度
            
        Returns:
            路径列表，每条路径是实体名称的列表
        """
        source_id = self._entity_name_index.get(source_name)
        target_id = self._entity_name_index.get(target_name)
        
        if not source_id or not target_id:
            return []
            
        if source_id == target_id:
            return [[source_name]]
            
        # BFS 搜索
        paths = []
        queue = [(source_id, [source_name])]
        visited = set()
        
        while queue and len(paths) < 5:
            current_id, path = queue.pop(0)
            
            if len(path) > max_depth:
                continue
                
            if current_id in visited:
                continue
            visited.add(current_id)
            
            # 获取相邻实体
            for rel_id in self._outgoing_index.get(current_id, []):
                rel = self.relations[rel_id]
                next_id = rel.target_id
                next_name = self.entities[next_id].name
                
                new_path = path + [f"--[{rel.relation_type}]-->", next_name]
                
                if next_id == target_id:
                    paths.append(new_path)
                else:
                    queue.append((next_id, new_path))
                    
        return paths
        
    def query(
        self,
        entity_type: str = None,
        has_relation: str = None,
        properties: Dict[str, Any] = None,
        limit: int = 10
    ) -> List[Entity]:
        """
        查询实体
        
        Args:
            entity_type: 实体类型过滤
            has_relation: 具有指定关系的实体
            properties: 属性过滤
            
        Returns:
            匹配的实体列表
        """
        results = []
        
        # 按类型筛选
        candidate_ids = set()
        if entity_type:
            candidate_ids = self._type_index.get(entity_type, set())
        else:
            candidate_ids = set(self.entities.keys())
            
        for entity_id in candidate_ids:
            entity = self.entities[entity_id]
            
            # 属性过滤
            if properties:
                match = all(
                    entity.properties.get(k) == v
                    for k, v in properties.items()
                )
                if not match:
                    continue
                    
            # 关系过滤
            if has_relation:
                rels = self.get_relations(entity.name, relation_type=has_relation)
                if not rels:
                    continue
                    
            results.append(entity)
            
            if len(results) >= limit:
                break
                
        return results
        
    def infer(self, entity_name: str, inference_type: str = "related") -> List[Entity]:
        """
        推理相关实体
        
        Args:
            entity_name: 实体名称
            inference_type: 推理类型 (related, causes, is_a, etc.)
            
        Returns:
            推理得到的实体列表
        """
        entity = self.get_entity(entity_name)
        if not entity:
            return []
            
        results = []
        
        # 直接关系
        direct_relations = self.get_relations(entity_name, relation_type=inference_type)
        for rel in direct_relations:
            if rel.source_id == self._entity_name_index[entity_name]:
                related_id = rel.target_id
            else:
                related_id = rel.source_id
            results.append(self.entities[related_id])
            
        # 传递推理 (例如 A is_a B, B is_a C => A is_a C)
        if inference_type == "is_a":
            for rel in direct_relations:
                if rel.source_id == self._entity_name_index[entity_name]:
                    parent_id = rel.target_id
                    # 递归查找父类的父类
                    parent_relations = self.get_relations(
                        self.entities[parent_id].name,
                        relation_type="is_a"
                    )
                    for parent_rel in parent_relations:
                        grandparent_id = parent_rel.target_id
                        results.append(self.entities[grandparent_id])
                        
        return results
        
    def extract_from_text(
        self,
        text: str,
        source: str = "",
        entity_types: List[str] = None
    ) -> List[KnowledgeTriple]:
        """
        从文本中提取知识三元组（简化实现）
        
        Args:
            text: 输入文本
            source: 来源标识
            entity_types: 要提取的实体类型
            
        Returns:
            提取的三元组列表
        """
        triples = []
        
        # 简单的模式匹配
        patterns = [
            # "A 是 B" -> (A, is_a, B)
            (r"(\w+)\s*是\s*(?:一个|一种)?\s*(\w+)", "is_a"),
            # "A 导致 B" -> (A, causes, B)
            (r"(\w+)\s*导致\s*(\w+)", "causes"),
            # "A 包含 B" -> (A, has_part, B)
            (r"(\w+)\s*包含\s*(\w+)", "has_part"),
            # "A 位于 B" -> (A, located_at, B)
            (r"(\w+)\s*位于\s*(\w+)", "located_at"),
            # "A 用于 B" -> (A, used_for, B)
            (r"(\w+)\s*用于\s*(\w+)", "used_for"),
            # "A 与 B 相关" -> (A, related_to, B)
            (r"(\w+)\s*与\s*(\w+)\s*相关", "related_to"),
        ]
        
        for pattern, rel_type in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) == 2:
                    subject, obj = match
                    if len(subject) > 1 and len(obj) > 1:  # 过滤单字
                        triples.append(KnowledgeTriple(
                            subject=subject,
                            predicate=rel_type,
                            object=obj,
                            confidence=0.7,
                            source=source
                        ))
                        # 添加到图谱
                        self.add_triple(triples[-1])
                        
        return triples
        
    def get_context_for_query(self, query: str, max_entities: int = 5) -> str:
        """
        根据查询获取相关上下文
        
        Args:
            query: 查询文本
            max_entities: 最大实体数
            
        Returns:
            格式化的上下文字符串
        """
        # 从查询中提取可能的实体名
        words = re.findall(r'\w+', query)
        
        relevant_entities = []
        relevant_relations = []
        
        for word in words:
            entity = self.get_entity(word)
            if entity:
                relevant_entities.append(entity)
                relations = self.get_relations(word)
                relevant_relations.extend(relations[:2])
                
        if not relevant_entities:
            return ""
            
        # 构建上下文
        context_parts = ["[知识图谱上下文 / Knowledge Graph Context]"]
        
        for entity in relevant_entities[:max_entities]:
            context_parts.append(f"- {entity.name} ({entity.entity_type})")
            for key, val in entity.properties.items():
                context_parts.append(f"  - {key}: {val}")
                
        if relevant_relations:
            context_parts.append("\n[相关关系 / Related Relations]")
            for rel in relevant_relations[:5]:
                source_name = self.entities[rel.source_id].name
                target_name = self.entities[rel.target_id].name
                context_parts.append(f"- {source_name} --[{rel.relation_type}]--> {target_name}")
                
        return "\n".join(context_parts)
        
    def save(self):
        """保存知识图谱"""
        data = {
            "name": self.name,
            "entities": {
                eid: {
                    "name": e.name,
                    "entity_type": e.entity_type,
                    "properties": e.properties,
                    "created_at": e.created_at,
                    "confidence": e.confidence,
                    "source": e.source
                }
                for eid, e in self.entities.items()
            },
            "relations": {
                rid: {
                    "source_id": r.source_id,
                    "target_id": r.target_id,
                    "relation_type": r.relation_type,
                    "properties": r.properties,
                    "confidence": r.confidence,
                    "evidence": r.evidence
                }
                for rid, r in self.relations.items()
            }
        }
        
        file_path = self.storage_path / "knowledge_graph.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    def _load(self):
        """加载知识图谱"""
        file_path = self.storage_path / "knowledge_graph.json"
        if not file_path.exists():
            return
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            for eid, e_data in data.get("entities", {}).items():
                entity = Entity(
                    id=eid,
                    name=e_data["name"],
                    entity_type=e_data["entity_type"],
                    properties=e_data.get("properties", {}),
                    created_at=e_data.get("created_at", ""),
                    confidence=e_data.get("confidence", 1.0),
                    source=e_data.get("source", "")
                )
                self.entities[eid] = entity
                self._entity_name_index[entity.name] = eid
                self._type_index[entity.entity_type].add(eid)
                
            for rid, r_data in data.get("relations", {}).items():
                relation = Relation(
                    id=rid,
                    source_id=r_data["source_id"],
                    target_id=r_data["target_id"],
                    relation_type=r_data["relation_type"],
                    properties=r_data.get("properties", {}),
                    confidence=r_data.get("confidence", 1.0),
                    evidence=r_data.get("evidence", "")
                )
                self.relations[rid] = relation
                self._outgoing_index[relation.source_id].append(rid)
                self._incoming_index[relation.target_id].append(rid)
                
        except Exception as e:
            print(f"[KnowledgeGraph] Warning: Failed to load: {e}")
            
    def export_dot(self) -> str:
        """导出为 DOT 格式（用于可视化）"""
        lines = [f'digraph "{self.name}" {{']
        lines.append('  rankdir=LR;')
        lines.append('  node [shape=box];')
        
        # 节点
        for entity in self.entities.values():
            label = f"{entity.name}\\n({entity.entity_type})"
            lines.append(f'  "{entity.id}" [label="{label}"];')
            
        # 边
        for relation in self.relations.values():
            label = relation.relation_type
            lines.append(f'  "{relation.source_id}" -> "{relation.target_id}" [label="{label}"];')
            
        lines.append('}')
        return '\n'.join(lines)
        
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "entity_count": len(self.entities),
            "relation_count": len(self.relations),
            "entity_types": {t: len(ids) for t, ids in self._type_index.items()},
            "relation_types": dict(Counter(r.relation_type for r in self.relations.values()))
        }


from collections import Counter


# 全局知识图谱实例
_global_knowledge_graph: Optional[KnowledgeGraph] = None


def get_knowledge_graph(name: str = "default") -> KnowledgeGraph:
    """获取全局知识图谱实例"""
    global _global_knowledge_graph
    if _global_knowledge_graph is None:
        _global_knowledge_graph = KnowledgeGraph(name)
    return _global_knowledge_graph


__all__ = [
    'KnowledgeGraph', 'Entity', 'Relation', 'KnowledgeTriple',
    'get_knowledge_graph'
]