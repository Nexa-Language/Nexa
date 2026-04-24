# ========================================================================
# Copyright (C) 2026 Nexa-Language
# This file is part of Nexa Project.
# 
# Nexa is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# Nexa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with Nexa.  If not, see <https://www.gnu.org/licenses/>.
# ========================================================================

"""
Nexa Background Job System — 语言原生后台任务系统

核心特性：
- 优先级队列（low/normal/high/critical）+ Worker bands
- 唯一任务去重（unique: args for 1h）
- 重试（默认3次）+ exponential backoff + 超时
- 死信处理 + on_failure hooks
- 速率限制 + 并发控制
- 任务过期 + 幂等性检查
- 定时调度（enqueue_in / enqueue_at）
- 内存后端（零配置）+ SQLite后端（持久化）
- Agent Job — 使用Agent执行后台LLM任务（Nexa独有）

Usage:
    from src.runtime.jobs import JobQueue, JobRegistry, JobWorker, JobScheduler
    JobQueue.configure(backend="memory")
    JobRegistry.register(spec)
    JobQueue.enqueue("SendEmail", {"user_id": "123"})
"""

import uuid
import time
import json
import threading
import sqlite3
import hashlib
import os
from enum import IntEnum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple
from collections import deque
from datetime import datetime, timezone


# ==================== 枚举定义 ====================

class JobPriority(IntEnum):
    """Job 优先级 — 数值越大优先级越高"""
    LOW = 0       # 日志清理、统计
    NORMAL = 1    # 默认（邮件发送等）
    HIGH = 2      # 通知推送
    CRITICAL = 3  # 支付处理、安全操作


class JobStatus(str):
    """Job 状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"        # 死信 — 重试耗尽
    CANCELLED = "cancelled"
    EXPIRED = "expired"  # 超时未执行


class BackoffStrategy(str):
    """重试退避策略"""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"


# ==================== 数据类 ====================

@dataclass
class JobSpec:
    """Job 规格定义 — 对应 Nexa 语法中的 job 声明"""
    name: str
    queue: str                              # 队列名（如 "emails", "payments"）
    priority: JobPriority = JobPriority.NORMAL
    retry_count: int = 3                    # 默认重试3次
    timeout: float = 30.0                   # 超时秒数
    unique_spec: Optional[str] = None       # 唯一规格（如 "args for 1h"）
    unique_duration: float = 3600.0         # 唯一锁持续时间（秒）
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    perform_fn: Optional[Callable] = None   # 执行函数
    on_failure_fn: Optional[Callable] = None  # 失败回调
    is_agent_job: bool = False              # 是否为 Agent Job（Nexa独有）
    agent_name: Optional[str] = None        # Agent名称（is_agent_job=True时）
    perform_body_source: Optional[str] = None  # perform 体源码（用于代码生成）
    on_failure_body_source: Optional[str] = None  # on_failure 体源码


@dataclass
class JobRecord:
    """Job 执行记录 — 入队后创建"""
    job_id: str
    spec_name: str
    args: Dict[str, Any]
    status: str = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    attempt_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None
    expires_at: Optional[float] = None     # 过期时间
    unique_key: Optional[str] = None       # 唯一去重键
    unique_expires_at: Optional[float] = None  # 唯一锁过期时间
    scheduled_at: Optional[float] = None   # 定时执行时间（延迟入队）
    timeout: float = 30.0                  # 单次执行超时
    queue: str = "default"                 # 所属队列


# ==================== 后端实现 ====================

class MemoryBackend:
    """内存后端 — 零配置，开发和小规模使用
    
    使用4个优先级deque实现优先级队列，
    出队时从最高优先级开始扫描。
    """

    def __init__(self):
        # 4级优先级队列
        self._queues: Dict[JobPriority, deque] = {
            JobPriority.LOW: deque(),
            JobPriority.NORMAL: deque(),
            JobPriority.HIGH: deque(),
            JobPriority.CRITICAL: deque(),
        }
        # 任务记录存储
        self._records: Dict[str, JobRecord] = {}
        # 死信队列
        self._dead_letter: Dict[str, JobRecord] = {}
        # 延迟任务队列（按时间排序的列表）
        self._scheduled: List[JobRecord] = []
        # 唯一任务锁（unique_key → job_id）
        self._unique_locks: Dict[str, str] = {}
        # 线程锁保证并发安全
        self._lock = threading.Lock()

    def enqueue(self, record: JobRecord) -> Optional[str]:
        """入队一个任务，返回 job_id；如果唯一去重冲突则返回 None"""
        with self._lock:
            # 检查唯一去重
            if record.unique_key:
                existing_id = self._unique_locks.get(record.unique_key)
                if existing_id:
                    existing = self._records.get(existing_id)
                    if existing and existing.status in (JobStatus.PENDING, JobStatus.RUNNING):
                        # 唯一锁未过期，拒绝入队
                        if existing.unique_expires_at and time.time() < existing.unique_expires_at:
                            return None
                        # 锁已过期，释放旧锁
                        del self._unique_locks[record.unique_key]

            # 如果是延迟任务，放入 scheduled 队列
            if record.scheduled_at and record.scheduled_at > time.time():
                self._scheduled.append(record)
                self._scheduled.sort(key=lambda r: r.scheduled_at)
                self._records[record.job_id] = record
                if record.unique_key:
                    self._unique_locks[record.unique_key] = record.job_id
                return record.job_id

            # 正常入队
            self._queues[record.priority].append(record.job_id)
            self._records[record.job_id] = record
            if record.unique_key:
                self._unique_locks[record.unique_key] = record.job_id
            return record.job_id

    def dequeue(self, timeout: float = 0) -> Optional[JobRecord]:
        """从最高优先级队列中出队一个任务
        
        按优先级顺序扫描：CRITICAL > HIGH > NORMAL > LOW
        """
        with self._lock:
            # 首先检查延迟队列中到期任务
            self._promote_scheduled_jobs()

            for priority in [JobPriority.CRITICAL, JobPriority.HIGH, JobPriority.NORMAL, JobPriority.LOW]:
                if self._queues[priority]:
                    job_id = self._queues[priority].popleft()
                    record = self._records.get(job_id)
                    if record:
                        # 检查是否过期
                        if record.expires_at and time.time() > record.expires_at:
                            record.status = JobStatus.EXPIRED
                            continue
                        # 检查是否已取消
                        if record.status == JobStatus.CANCELLED:
                            continue
                        record.status = JobStatus.RUNNING
                        record.started_at = time.time()
                        record.attempt_count += 1
                        return record
            return None

    def get_status(self, job_id: str) -> Optional[JobRecord]:
        """查询任务状态"""
        with self._lock:
            return self._records.get(job_id)

    def update_record(self, record: JobRecord):
        """更新任务记录"""
        with self._lock:
            self._records[record.job_id] = record
            # 如果任务完成或进入死信，释放唯一锁
            if record.status in (JobStatus.COMPLETED, JobStatus.DEAD, JobStatus.CANCELLED, JobStatus.EXPIRED):
                if record.unique_key and record.unique_key in self._unique_locks:
                    # 只有当锁指向此任务时才释放
                    if self._unique_locks[record.unique_key] == record.job_id:
                        del self._unique_locks[record.unique_key]

    def cancel(self, job_id: str) -> bool:
        """取消任务"""
        with self._lock:
            record = self._records.get(job_id)
            if record and record.status in (JobStatus.PENDING, JobStatus.RUNNING):
                record.status = JobStatus.CANCELLED
                record.completed_at = time.time()
                # 从队列中移除
                for priority_queue in self._queues.values():
                    try:
                        priority_queue.remove(job_id)
                    except ValueError:
                        pass
                # 释放唯一锁
                if record.unique_key and record.unique_key in self._unique_locks:
                    if self._unique_locks[record.unique_key] == job_id:
                        del self._unique_locks[record.unique_key]
                return True
            return False

    def retry_from_dead(self, job_id: str) -> bool:
        """从死信队列重试任务"""
        with self._lock:
            record = self._records.get(job_id)
            if record and record.status == JobStatus.DEAD:
                record.status = JobStatus.PENDING
                record.attempt_count = 0
                record.last_error = None
                record.started_at = None
                record.completed_at = None
                self._queues[record.priority].append(job_id)
                if record.unique_key:
                    self._unique_locks[record.unique_key] = job_id
                return True
            return False

    def mark_completed(self, job_id: str):
        """标记任务完成"""
        with self._lock:
            record = self._records.get(job_id)
            if record:
                record.status = JobStatus.COMPLETED
                record.completed_at = time.time()

    def mark_failed(self, job_id: str, error: str, max_retries: int = 3) -> str:
        """标记任务失败，返回新状态
        
        如果未耗尽重试次数 → PENDING（重新入队）
        如果耗尽重试次数 → DEAD（进入死信队列）
        """
        with self._lock:
            record = self._records.get(job_id)
            if record:
                record.last_error = error
                if record.attempt_count >= max_retries:
                    record.status = JobStatus.DEAD
                    record.completed_at = time.time()
                    return JobStatus.DEAD
                else:
                    record.status = JobStatus.PENDING
                    record.started_at = None
                    # 重新入队
                    self._queues[record.priority].append(job_id)
                    return JobStatus.PENDING
            return JobStatus.FAILED

    def list_jobs(self, status: Optional[str] = None, limit: int = 50) -> List[JobRecord]:
        """列出任务"""
        with self._lock:
            records = list(self._records.values())
            if status:
                records = [r for r in records if r.status == status]
            # 按创建时间排序
            records.sort(key=lambda r: r.created_at, reverse=True)
            return records[:limit]

    def clear_completed(self) -> int:
        """清理已完成/过期/取消的任务"""
        with self._lock:
            to_remove = [
                job_id for job_id, record in self._records.items()
                if record.status in (JobStatus.COMPLETED, JobStatus.EXPIRED, JobStatus.CANCELLED)
            ]
            for job_id in to_remove:
                record = self._records[job_id]
                if record.unique_key and record.unique_key in self._unique_locks:
                    if self._unique_locks[record.unique_key] == job_id:
                        del self._unique_locks[record.unique_key]
                del self._records[job_id]
            return len(to_remove)

    def _promote_scheduled_jobs(self):
        """将到期的延迟任务移入主队列"""
        now = time.time()
        while self._scheduled and self._scheduled[0].scheduled_at <= now:
            record = self._scheduled.pop(0)
            record.status = JobStatus.PENDING
            self._queues[record.priority].append(record.job_id)

    def stats(self) -> Dict[str, int]:
        """返回队列统计"""
        with self._lock:
            stats = {}
            for status in [JobStatus.PENDING, JobStatus.RUNNING, JobStatus.COMPLETED,
                           JobStatus.FAILED, JobStatus.DEAD, JobStatus.CANCELLED, JobStatus.EXPIRED]:
                stats[status] = len([r for r in self._records.values() if r.status == status])
            stats["scheduled"] = len(self._scheduled)
            return stats


class SQLiteBackend:
    """SQLite 后端 — 单机持久化，中等规模
    
    使用 sqlite3 模块实现持久化存储，
    事务保证原子性操作。
    """

    def __init__(self, db_path: str = "nexa_jobs.db"):
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_tables()

    def _init_tables(self):
        """创建数据库表"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nexa_jobs (
                    id TEXT PRIMARY KEY,
                    spec_name TEXT NOT NULL,
                    args TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    priority INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    started_at REAL,
                    completed_at REAL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    last_error TEXT,
                    expires_at REAL,
                    unique_key TEXT,
                    unique_expires_at REAL,
                    scheduled_at REAL,
                    timeout REAL NOT NULL DEFAULT 30.0,
                    queue TEXT NOT NULL DEFAULT 'default'
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON nexa_jobs(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_priority ON nexa_jobs(priority DESC, created_at ASC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_unique ON nexa_jobs(unique_key)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_scheduled ON nexa_jobs(scheduled_at)
            """)
            self._conn.commit()

    def _record_from_row(self, row: sqlite3.Row) -> JobRecord:
        """从数据库行转换为 JobRecord"""
        return JobRecord(
            job_id=row["id"],
            spec_name=row["spec_name"],
            args=json.loads(row["args"]),
            status=row["status"],
            priority=JobPriority(row["priority"]),
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            attempt_count=row["attempt_count"],
            max_retries=row["max_retries"],
            last_error=row["last_error"],
            expires_at=row["expires_at"],
            unique_key=row["unique_key"],
            unique_expires_at=row["unique_expires_at"],
            scheduled_at=row["scheduled_at"],
            timeout=row["timeout"],
            queue=row["queue"],
        )

    def enqueue(self, record: JobRecord) -> Optional[str]:
        """入队一个任务"""
        with self._lock:
            # 检查唯一去重
            if record.unique_key:
                cursor = self._conn.cursor()
                cursor.execute(
                    "SELECT id, status, unique_expires_at FROM nexa_jobs WHERE unique_key = ?",
                    (record.unique_key,)
                )
                existing = cursor.fetchone()
                if existing:
                    now = time.time()
                    if existing["status"] in (JobStatus.PENDING, JobStatus.RUNNING):
                        if existing["unique_expires_at"] and now < existing["unique_expires_at"]:
                            return None
                        # 锁已过期，删除旧记录
                        cursor.execute("DELETE FROM nexa_jobs WHERE id = ?", (existing["id"],))

            # 插入新任务
            cursor = self._conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO nexa_jobs (id, spec_name, args, status, priority, created_at,
                        started_at, completed_at, attempt_count, max_retries, last_error,
                        expires_at, unique_key, unique_expires_at, scheduled_at, timeout, queue)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.job_id, record.spec_name, json.dumps(record.args),
                    record.status, int(record.priority), record.created_at,
                    record.started_at, record.completed_at, record.attempt_count,
                    record.max_retries, record.last_error, record.expires_at,
                    record.unique_key, record.unique_expires_at, record.scheduled_at,
                    record.timeout, record.queue,
                ))
                self._conn.commit()
                return record.job_id
            except sqlite3.IntegrityError:
                # 唯一约束冲突
                self._conn.rollback()
                return None

    def dequeue(self, timeout: float = 0) -> Optional[JobRecord]:
        """出队最高优先级的任务"""
        with self._lock:
            # 先推进到期的延迟任务
            self._promote_scheduled_jobs()

            cursor = self._conn.cursor()
            # 按优先级降序、创建时间升序选择
            now = time.time()
            cursor.execute("""
                SELECT * FROM nexa_jobs 
                WHERE status = 'pending' AND (scheduled_at IS NULL OR scheduled_at <= ?)
                AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
            """, (now, now))
            row = cursor.fetchone()
            if row:
                record = self._record_from_row(row)
                # 更新状态为 running
                cursor.execute("""
                    UPDATE nexa_jobs SET status = 'running', started_at = ?, attempt_count = attempt_count + 1
                    WHERE id = ?
                """, (now, record.job_id))
                self._conn.commit()
                record.status = JobStatus.RUNNING
                record.started_at = now
                record.attempt_count += 1
                return record
            return None

    def get_status(self, job_id: str) -> Optional[JobRecord]:
        """查询任务状态"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT * FROM nexa_jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if row:
                return self._record_from_row(row)
            return None

    def update_record(self, record: JobRecord):
        """更新任务记录"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                UPDATE nexa_jobs SET status = ?, started_at = ?, completed_at = ?,
                    attempt_count = ?, last_error = ?
                WHERE id = ?
            """, (
                record.status, record.started_at, record.completed_at,
                record.attempt_count, record.last_error, record.job_id,
            ))
            self._conn.commit()

    def cancel(self, job_id: str) -> bool:
        """取消任务"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT status FROM nexa_jobs WHERE id = ?", (job_id,)
            )
            row = cursor.fetchone()
            if row and row["status"] in (JobStatus.PENDING, JobStatus.RUNNING):
                cursor.execute("""
                    UPDATE nexa_jobs SET status = 'cancelled', completed_at = ?
                    WHERE id = ?
                """, (time.time(), job_id))
                self._conn.commit()
                return True
            return False

    def retry_from_dead(self, job_id: str) -> bool:
        """从死信重试"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT status FROM nexa_jobs WHERE id = ?", (job_id,)
            )
            row = cursor.fetchone()
            if row and row["status"] == JobStatus.DEAD:
                cursor.execute("""
                    UPDATE nexa_jobs SET status = 'pending', attempt_count = 0,
                        last_error = NULL, started_at = NULL, completed_at = NULL
                    WHERE id = ?
                """, (job_id,))
                self._conn.commit()
                return True
            return False

    def mark_completed(self, job_id: str):
        """标记完成"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                UPDATE nexa_jobs SET status = 'completed', completed_at = ?
                WHERE id = ?
            """, (time.time(), job_id))
            self._conn.commit()

    def mark_failed(self, job_id: str, error: str, max_retries: int = 3) -> str:
        """标记失败，返回新状态"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT attempt_count FROM nexa_jobs WHERE id = ?", (job_id,)
            )
            row = cursor.fetchone()
            if row:
                attempt_count = row["attempt_count"]
                if attempt_count >= max_retries:
                    cursor.execute("""
                        UPDATE nexa_jobs SET status = 'dead', last_error = ?, completed_at = ?
                        WHERE id = ?
                    """, (error, time.time(), job_id))
                    self._conn.commit()
                    return JobStatus.DEAD
                else:
                    cursor.execute("""
                        UPDATE nexa_jobs SET status = 'pending', last_error = ?, started_at = NULL
                        WHERE id = ?
                    """, (error, job_id))
                    self._conn.commit()
                    return JobStatus.PENDING
            return JobStatus.FAILED

    def list_jobs(self, status: Optional[str] = None, limit: int = 50) -> List[JobRecord]:
        """列出任务"""
        with self._lock:
            cursor = self._conn.cursor()
            if status:
                cursor.execute(
                    "SELECT * FROM nexa_jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM nexa_jobs ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
            return [self._record_from_row(row) for row in cursor.fetchall()]

    def clear_completed(self) -> int:
        """清理已完成/过期/取消的任务"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                DELETE FROM nexa_jobs WHERE status IN ('completed', 'expired', 'cancelled')
            """)
            count = cursor.rowcount
            self._conn.commit()
            return count

    def _promote_scheduled_jobs(self):
        """推进到期的延迟任务"""
        now = time.time()
        cursor = self._conn.cursor()
        cursor.execute("""
            UPDATE nexa_jobs SET scheduled_at = NULL
            WHERE scheduled_at IS NOT NULL AND scheduled_at <= ? AND status = 'pending'
        """, (now,))
        self._conn.commit()

    def stats(self) -> Dict[str, int]:
        """返回队列统计"""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT status, COUNT(*) as count FROM nexa_jobs GROUP BY status
            """)
            stats = {}
            for row in cursor.fetchall():
                stats[row["status"]] = row["count"]
            cursor.execute("""
                SELECT COUNT(*) as count FROM nexa_jobs 
                WHERE scheduled_at IS NOT NULL AND scheduled_at > ? AND status = 'pending'
            """, (time.time(),))
            scheduled_row = cursor.fetchone()
            stats["scheduled"] = scheduled_row["count"] if scheduled_row else 0
            return stats

    def close(self):
        """关闭数据库连接"""
        with self._lock:
            self._conn.close()


# ==================== Job 注册表 ====================

class JobRegistry:
    """Job 规格注册表 — 存储所有已定义的 JobSpec"""
    
    _specs: Dict[str, JobSpec] = {}
    _lock = threading.Lock()

    @classmethod
    def register(cls, spec: JobSpec):
        """注册一个 Job 规格"""
        with cls._lock:
            cls._specs[spec.name] = spec

    @classmethod
    def get(cls, spec_name: str) -> Optional[JobSpec]:
        """获取 Job 规格"""
        with cls._lock:
            return cls._specs.get(spec_name)

    @classmethod
    def list_specs(cls) -> List[JobSpec]:
        """列出所有 Job 规格"""
        with cls._lock:
            return list(cls._specs.values())

    @classmethod
    def clear(cls):
        """清空注册表"""
        with cls._lock:
            cls._specs.clear()


# ==================== Job 队列统一接口 ====================

class JobQueue:
    """Job 队列统一接口 — 提供入队、出队、状态查询等操作
    
    支持内存后端和 SQLite 后端。
    """
    
    _backend: Optional[Any] = None
    _configured = False
    _lock = threading.Lock()

    @classmethod
    def configure(cls, backend: str = "memory", db_path: str = "nexa_jobs.db"):
        """配置后端
        
        Args:
            backend: "memory" | "sqlite" | "redis"
            db_path: SQLite数据库路径（仅sqlite后端使用）
        """
        with cls._lock:
            if backend == "memory":
                cls._backend = MemoryBackend()
            elif backend == "sqlite":
                cls._backend = SQLiteBackend(db_path)
            elif backend == "redis":
                # Redis后端暂未实现，使用内存后端
                print("⚠️ Redis backend not yet implemented, falling back to memory backend")
                cls._backend = MemoryBackend()
            else:
                raise ValueError(f"Unknown backend: {backend}")
            cls._configured = True

    @classmethod
    def _ensure_configured(cls):
        """确保后端已配置，默认使用内存后端"""
        if not cls._configured:
            cls.configure(backend="memory")

    @classmethod
    def enqueue(cls, spec_name: str, args: Dict[str, Any], options: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """入队一个任务
        
        Args:
            spec_name: Job规格名称
            args: 任务参数
            options: 覆盖选项（priority, unique等）
        
        Returns:
            job_id 或 None（唯一去重冲突时）
        """
        cls._ensure_configured()
        
        spec = JobRegistry.get(spec_name)
        if not spec:
            raise ValueError(f"Job spec '{spec_name}' not registered")

        # 计算唯一键
        unique_key = None
        unique_expires_at = None
        if spec.unique_spec or (options and options.get("unique")):
            # 唯一键 = spec_name + args的hash
            args_hash = hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()[:16]
            unique_key = f"{spec_name}:{args_hash}"
            duration = spec.unique_duration
            if options and "unique_duration" in options:
                duration = options["unique_duration"]
            unique_expires_at = time.time() + duration

        # 确定优先级
        priority = spec.priority
        if options and "priority" in options:
            priority_str = options["priority"]
            priority = JobPriority[priority_str.upper()]

        # 确定超时
        timeout = spec.timeout
        if options and "timeout" in options:
            timeout = options["timeout"]

        # 确定过期时间
        expires_at = None
        if options and "expires_in" in options:
            expires_at = time.time() + options["expires_in"]

        # 创建记录
        record = JobRecord(
            job_id=str(uuid.uuid4()),
            spec_name=spec_name,
            args=args,
            status=JobStatus.PENDING,
            priority=priority,
            created_at=time.time(),
            max_retries=spec.retry_count,
            expires_at=expires_at,
            unique_key=unique_key,
            unique_expires_at=unique_expires_at,
            timeout=timeout,
            queue=spec.queue,
        )

        return cls._backend.enqueue(record)

    @classmethod
    def enqueue_in(cls, spec_name: str, delay_seconds: float, args: Dict[str, Any], 
                    options: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """延迟入队
        
        Args:
            spec_name: Job规格名称
            delay_seconds: 延迟秒数
            args: 任务参数
            options: 覆盖选项
        """
        cls._ensure_configured()
        
        spec = JobRegistry.get(spec_name)
        if not spec:
            raise ValueError(f"Job spec '{spec_name}' not registered")

        scheduled_at = time.time() + delay_seconds

        # 计算唯一键
        unique_key = None
        unique_expires_at = None
        if spec.unique_spec or (options and options.get("unique")):
            args_hash = hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()[:16]
            unique_key = f"{spec_name}:{args_hash}"
            duration = spec.unique_duration
            if options and "unique_duration" in options:
                duration = options["unique_duration"]
            unique_expires_at = time.time() + duration

        priority = spec.priority
        if options and "priority" in options:
            priority_str = options["priority"]
            priority = JobPriority[priority_str.upper()]

        timeout = spec.timeout
        if options and "timeout" in options:
            timeout = options["timeout"]

        expires_at = None
        if options and "expires_in" in options:
            expires_at = time.time() + options["expires_in"]

        record = JobRecord(
            job_id=str(uuid.uuid4()),
            spec_name=spec_name,
            args=args,
            status=JobStatus.PENDING,
            priority=priority,
            created_at=time.time(),
            max_retries=spec.retry_count,
            expires_at=expires_at,
            unique_key=unique_key,
            unique_expires_at=unique_expires_at,
            scheduled_at=scheduled_at,
            timeout=timeout,
            queue=spec.queue,
        )

        return cls._backend.enqueue(record)

    @classmethod
    def enqueue_at(cls, spec_name: str, specific_time: float, args: Dict[str, Any],
                    options: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """指定时间入队
        
        Args:
            spec_name: Job规格名称
            specific_time: Unix timestamp
            args: 任务参数
            options: 覆盖选项
        """
        return cls.enqueue_in(spec_name, specific_time - time.time(), args, options)

    @classmethod
    def status(cls, job_id: str) -> Optional[JobRecord]:
        """查询任务状态"""
        cls._ensure_configured()
        return cls._backend.get_status(job_id)

    @classmethod
    def cancel(cls, job_id: str) -> bool:
        """取消任务"""
        cls._ensure_configured()
        return cls._backend.cancel(job_id)

    @classmethod
    def retry(cls, job_id: str) -> bool:
        """重试死信任务"""
        cls._ensure_configured()
        return cls._backend.retry_from_dead(job_id)

    @classmethod
    def list_jobs(cls, status: Optional[str] = None, limit: int = 50) -> List[JobRecord]:
        """列出任务"""
        cls._ensure_configured()
        return cls._backend.list_jobs(status=status, limit=limit)

    @classmethod
    def clear_completed(cls) -> int:
        """清理已完成任务"""
        cls._ensure_configured()
        return cls._backend.clear_completed()

    @classmethod
    def stats(cls) -> Dict[str, int]:
        """返回队列统计"""
        cls._ensure_configured()
        return cls._backend.stats()


# ==================== Job Worker ====================

class JobWorker:
    """Job Worker — 从队列取任务并执行
    
    支持优先级出队、重试逻辑、exponential backoff、
    超时控制、死信处理和 on_failure hooks。
    """

    def __init__(self, worker_id: str = "worker-1", poll_interval: float = 1.0):
        self.worker_id = worker_id
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._heartbeat_time: Optional[float] = None
        self._jobs_processed = 0
        self._errors_count = 0

    def start(self, daemon: bool = True):
        """启动worker线程"""
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=daemon, name=self.worker_id)
        self._thread.start()

    def stop(self):
        """停止worker"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run_loop(self):
        """Worker主循环"""
        while self._running:
            self.send_heartbeat()
            record = JobQueue._backend.dequeue()
            if record:
                self._process_job(record)
            else:
                time.sleep(self.poll_interval)

    def _process_job(self, record: JobRecord):
        """处理一个任务"""
        spec = JobRegistry.get(record.spec_name)
        if not spec:
            JobQueue._backend.mark_failed(record.job_id, f"Spec '{record.spec_name}' not found", record.max_retries)
            self._errors_count += 1
            return

        try:
            result = self.execute_with_retry(spec, record)
            if result is not None:
                JobQueue._backend.mark_completed(record.job_id)
                self._jobs_processed += 1
        except Exception as e:
            self._errors_count += 1

    def execute_with_retry(self, spec: JobSpec, record: JobRecord) -> Any:
        """执行任务（含重试逻辑）
        
        Returns:
            执行结果
        Raises:
            Exception: 重试耗尽后抛出最后一次异常
        """
        last_error = None
        for attempt in range(record.max_retries + 1):
            try:
                # 超时控制
                if spec.perform_fn:
                    result = self._execute_with_timeout(spec.perform_fn, record.args, record.timeout)
                    return result
                else:
                    # 无执行函数（可能由代码生成器创建）
                    raise RuntimeError(f"No perform_fn for job '{record.spec_name}'")
            except Exception as e:
                last_error = str(e)
                # 更新记录
                record.last_error = last_error
                JobQueue._backend.update_record(record)

                # 计算退避延迟
                if attempt < record.max_retries:
                    delay = self._calculate_backoff(spec.backoff_strategy, attempt)
                    time.sleep(delay)

                    # 重新标记为pending并出队
                    new_status = JobQueue._backend.mark_failed(record.job_id, last_error, record.max_retries)
                    if new_status == JobStatus.DEAD:
                        # 调用 on_failure hook
                        if spec.on_failure_fn:
                            try:
                                spec.on_failure_fn(last_error, attempt + 1)
                            except Exception:
                                pass
                        raise Exception(f"Job '{record.spec_name}' exhausted retries: {last_error}")
                    # 继续重试
                else:
                    # 重试耗尽
                    JobQueue._backend.mark_failed(record.job_id, last_error, record.max_retries)
                    if spec.on_failure_fn:
                        try:
                            spec.on_failure_fn(last_error, attempt + 1)
                        except Exception:
                            pass
                    raise Exception(f"Job '{record.spec_name}' exhausted retries: {last_error}")
        raise Exception(f"Job '{record.spec_name}' failed: {last_error}")

    def _execute_with_timeout(self, fn: Callable, args: Dict[str, Any], timeout: float) -> Any:
        """带超时的执行"""
        result_container = [None]
        error_container = [None]

        def target():
            try:
                result_container[0] = fn(args)
            except Exception as e:
                error_container[0] = e

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            # 超时
            raise TimeoutError(f"Job execution exceeded timeout of {timeout}s")

        if error_container[0]:
            raise error_container[0]

        return result_container[0]

    def _calculate_backoff(self, strategy: BackoffStrategy, attempt: int) -> float:
        """计算重试退避延迟
        
        Args:
            strategy: 退避策略
            attempt: 当前尝试次数（0-based）
        
        Returns:
            延迟秒数
        """
        if strategy == BackoffStrategy.EXPONENTIAL:
            return min(2 ** attempt, 300)  # 最大300秒
        elif strategy == BackoffStrategy.LINEAR:
            return min(attempt * 10, 300)
        elif strategy == BackoffStrategy.CONSTANT:
            return 10
        return min(2 ** attempt, 300)  # 默认 exponential

    def send_heartbeat(self):
        """发送心跳信号"""
        self._heartbeat_time = time.time()

    def get_status(self) -> Dict[str, Any]:
        """获取worker状态"""
        return {
            "worker_id": self.worker_id,
            "running": self._running,
            "heartbeat": self._heartbeat_time,
            "jobs_processed": self._jobs_processed,
            "errors_count": self._errors_count,
        }


# ==================== Job 调度器 ====================

class JobScheduler:
    """Job 调度器 — 定期检查延迟队列、过期任务、清理已完成任务"""

    def __init__(self, check_interval: float = 5.0):
        self.check_interval = check_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self, daemon: bool = True):
        """启动调度器线程"""
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=daemon, name="job-scheduler")
        self._thread.start()

    def stop(self):
        """停止调度器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run_loop(self):
        """调度器主循环"""
        while self._running:
            self.check_delayed_jobs()
            self.check_expired_jobs()
            self.cleanup_completed()
            time.sleep(self.check_interval)

    def check_delayed_jobs(self):
        """检查延迟队列，到期则移入主队列"""
        # MemoryBackend 在 dequeue 时自动推进
        # SQLiteBackend 在 dequeue 时自动推进
        # 此方法为显式检查（用于非worker场景）
        if hasattr(JobQueue._backend, '_promote_scheduled_jobs'):
            if isinstance(JobQueue._backend, MemoryBackend):
                with JobQueue._backend._lock:
                    JobQueue._backend._promote_scheduled_jobs()

    def check_expired_jobs(self):
        """检查过期任务，标记为 expired"""
        if not JobQueue._configured:
            return
        jobs = JobQueue.list_jobs(status=JobStatus.PENDING)
        now = time.time()
        for job in jobs:
            if job.expires_at and now > job.expires_at:
                JobQueue._backend.update_record(job)
                job.status = JobStatus.EXPIRED
                job.completed_at = now
                JobQueue._backend.update_record(job)

    def cleanup_completed(self):
        """定期清理已完成任务"""
        if not JobQueue._configured:
            return
        JobQueue.clear_completed()


# ==================== CLI 辅助函数 ====================

def format_job_status(record: JobRecord) -> str:
    """格式化任务状态为可读字符串"""
    created = datetime.fromtimestamp(record.created_at, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    started = ""
    if record.started_at:
        started = datetime.fromtimestamp(record.started_at, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    completed = ""
    if record.completed_at:
        completed = datetime.fromtimestamp(record.completed_at, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    lines = [
        f"Job ID:      {record.job_id}",
        f"Spec:        {record.spec_name}",
        f"Queue:       {record.queue}",
        f"Status:      {record.status}",
        f"Priority:    {record.priority.name} ({record.priority.value})",
        f"Args:        {json.dumps(record.args, ensure_ascii=False)}",
        f"Created:     {created}",
        f"Started:     {started or '-'}",
        f"Completed:   {completed or '-'}",
        f"Attempts:    {record.attempt_count}/{record.max_retries}",
        f"Last Error:  {record.last_error or '-'}",
    ]
    return "\n".join(lines)


def format_jobs_table(records: List[JobRecord]) -> str:
    """格式化任务列表为表格"""
    if not records:
        return "No jobs found."

    lines = []
    lines.append(f"{'ID':<36} {'Spec':<20} {'Status':<12} {'Priority':<10} {'Attempts':<8} {'Created':<20}")
    lines.append("-" * 106)
    
    for r in records:
        created = datetime.fromtimestamp(r.created_at, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        lines.append(
            f"{r.job_id:<36} {r.spec_name:<20} {r.status:<12} {r.priority.name:<10} "
            f"{r.attempt_count}/{r.max_retries:<7} {created:<20}"
        )
    return "\n".join(lines)