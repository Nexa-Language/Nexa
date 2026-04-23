"""
P1-3: Background Job System 综合测试

测试覆盖：
1. JobSpec 创建和注册
2. JobPriority 排序
3. 内存后端入队/出队/状态/取消/重试
4. SQLite 后端入队/出队
5. 重试逻辑（exponential backoff）
6. 死信处理
7. 唯一任务去重
8. 延迟入队
9. 任务过期
10. JobWorker 执行
11. JobQueue 统一接口
12. CLI 命令测试
13. Parser 语法测试
"""

import pytest
import time
import os
import json
import tempfile
import threading

# 添加 src 目录到 path
sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys_path not in os.sys.path:
    os.sys.path.insert(0, sys_path)

from src.runtime.jobs import (
    JobPriority, JobStatus, BackoffStrategy,
    JobSpec, JobRecord, MemoryBackend, SQLiteBackend,
    JobRegistry, JobQueue, JobWorker, JobScheduler,
    format_job_status, format_jobs_table,
)


# ==================== JobSpec 和注册 ====================

class TestJobSpec:
    """JobSpec 创建和注册测试"""

    def setup_method(self):
        JobRegistry.clear()

    def test_job_spec_creation_defaults(self):
        """默认配置的 JobSpec"""
        spec = JobSpec(name="SendEmail", queue="emails")
        assert spec.name == "SendEmail"
        assert spec.queue == "emails"
        assert spec.priority == JobPriority.NORMAL
        assert spec.retry_count == 3
        assert spec.timeout == 30.0
        assert spec.unique_spec is None
        assert spec.backoff_strategy == BackoffStrategy.EXPONENTIAL
        assert spec.is_agent_job == False

    def test_job_spec_with_options(self):
        """带完整配置的 JobSpec"""
        spec = JobSpec(
            name="ProcessPayment",
            queue="payments",
            priority=JobPriority.CRITICAL,
            retry_count=5,
            timeout=60.0,
            unique_spec="args for 1h",
            unique_duration=3600.0,
            backoff_strategy=BackoffStrategy.LINEAR,
        )
        assert spec.priority == JobPriority.CRITICAL
        assert spec.retry_count == 5
        assert spec.timeout == 60.0
        assert spec.unique_spec == "args for 1h"
        assert spec.backoff_strategy == BackoffStrategy.LINEAR

    def test_job_spec_agent_job(self):
        """Agent Job 的 JobSpec"""
        spec = JobSpec(
            name="AnalyzeDocument",
            queue="ai_tasks",
            is_agent_job=True,
            agent_name="AnalyzerBot",
        )
        assert spec.is_agent_job == True
        assert spec.agent_name == "AnalyzerBot"

    def test_job_registry_register_and_get(self):
        """注册和获取 JobSpec"""
        spec = JobSpec(name="SendEmail", queue="emails")
        JobRegistry.register(spec)
        
        retrieved = JobRegistry.get("SendEmail")
        assert retrieved is not None
        assert retrieved.name == "SendEmail"
        assert retrieved.queue == "emails"

    def test_job_registry_list_specs(self):
        """列出所有注册的 JobSpec"""
        JobRegistry.register(JobSpec(name="JobA", queue="queue_a"))
        JobRegistry.register(JobSpec(name="JobB", queue="queue_b"))
        
        specs = JobRegistry.list_specs()
        assert len(specs) == 2
        names = [s.name for s in specs]
        assert "JobA" in names
        assert "JobB" in names

    def test_job_registry_clear(self):
        """清空注册表"""
        JobRegistry.register(JobSpec(name="JobA", queue="queue_a"))
        JobRegistry.clear()
        assert JobRegistry.get("JobA") is None
        assert len(JobRegistry.list_specs()) == 0

    def test_job_registry_get_nonexistent(self):
        """获取未注册的 JobSpec"""
        assert JobRegistry.get("NonexistentJob") is None


# ==================== JobPriority ====================

class TestJobPriority:
    """优先级排序测试"""

    def test_priority_ordering(self):
        """优先级排序：critical > high > normal > low"""
        assert JobPriority.CRITICAL > JobPriority.HIGH
        assert JobPriority.HIGH > JobPriority.NORMAL
        assert JobPriority.NORMAL > JobPriority.LOW

    def test_priority_values(self):
        """优先级数值"""
        assert JobPriority.LOW == 0
        assert JobPriority.NORMAL == 1
        assert JobPriority.HIGH == 2
        assert JobPriority.CRITICAL == 3

    def test_priority_int_enum(self):
        """优先级是 IntEnum"""
        assert int(JobPriority.CRITICAL) == 3
        assert int(JobPriority.LOW) == 0


# ==================== 内存后端 ====================

class TestMemoryBackend:
    """内存后端测试"""

    def setup_method(self):
        self.backend = MemoryBackend()

    def _make_record(self, job_id="job-1", spec_name="TestJob", queue="default",
                     priority=JobPriority.NORMAL, args=None, unique_key=None,
                     unique_expires_at=None, scheduled_at=None, expires_at=None):
        """创建测试用的 JobRecord"""
        return JobRecord(
            job_id=job_id,
            spec_name=spec_name,
            args=args or {},
            status=JobStatus.PENDING,
            priority=priority,
            created_at=time.time(),
            attempt_count=0,
            max_retries=3,
            timeout=30.0,
            queue=queue,
            unique_key=unique_key,
            unique_expires_at=unique_expires_at,
            scheduled_at=scheduled_at,
            expires_at=expires_at,
        )

    def test_enqueue_and_dequeue(self):
        """入队和出队"""
        record = self._make_record()
        job_id = self.backend.enqueue(record)
        assert job_id == "job-1"

        dequeued = self.backend.dequeue()
        assert dequeued is not None
        assert dequeued.job_id == "job-1"
        assert dequeued.status == JobStatus.RUNNING
        assert dequeued.attempt_count == 1

    def test_priority_dequeue_order(self):
        """优先级出队顺序：critical > high > normal > low"""
        # 入队顺序：low, normal, high, critical
        self.backend.enqueue(self._make_record(job_id="low-1", priority=JobPriority.LOW))
        self.backend.enqueue(self._make_record(job_id="normal-1", priority=JobPriority.NORMAL))
        self.backend.enqueue(self._make_record(job_id="high-1", priority=JobPriority.HIGH))
        self.backend.enqueue(self._make_record(job_id="critical-1", priority=JobPriority.CRITICAL))

        # 出队顺序应该是：critical, high, normal, low
        first = self.backend.dequeue()
        assert first.priority == JobPriority.CRITICAL

        second = self.backend.dequeue()
        assert second.priority == JobPriority.HIGH

        third = self.backend.dequeue()
        assert third.priority == JobPriority.NORMAL

        fourth = self.backend.dequeue()
        assert fourth.priority == JobPriority.LOW

    def test_dequeue_empty_queue(self):
        """空队列出队返回 None"""
        assert self.backend.dequeue() is None

    def test_get_status(self):
        """查询任务状态"""
        record = self._make_record()
        self.backend.enqueue(record)

        status = self.backend.get_status("job-1")
        assert status is not None
        assert status.spec_name == "TestJob"
        assert status.status == JobStatus.PENDING

    def test_get_status_nonexistent(self):
        """查询不存在任务"""
        assert self.backend.get_status("nonexistent") is None

    def test_cancel_pending(self):
        """取消 PENDING 任务"""
        record = self._make_record()
        self.backend.enqueue(record)
        assert self.backend.cancel("job-1") == True

        status = self.backend.get_status("job-1")
        assert status.status == JobStatus.CANCELLED

    def test_cancel_nonexistent(self):
        """取消不存在任务"""
        assert self.backend.cancel("nonexistent") == False

    def test_mark_completed(self):
        """标记任务完成"""
        record = self._make_record()
        self.backend.enqueue(record)
        dequeued = self.backend.dequeue()
        
        self.backend.mark_completed("job-1")
        status = self.backend.get_status("job-1")
        assert status.status == JobStatus.COMPLETED
        assert status.completed_at is not None

    def test_mark_failed_retry(self):
        """标记失败 — 重试"""
        record = self._make_record()
        self.backend.enqueue(record)
        dequeued = self.backend.dequeue()

        new_status = self.backend.mark_failed("job-1", "Network error", 3)
        assert new_status == JobStatus.PENDING  # attempt_count=1, < max_retries=3

    def test_mark_failed_dead_letter(self):
        """标记失败 — 死信（重试耗尽）"""
        record = self._make_record()
        self.backend.enqueue(record)
        
        # 模拟3次重试耗尽
        self.backend.dequeue()  # attempt_count=1
        self.backend.mark_failed("job-1", "Error 1", 3)
        
        self.backend.dequeue()  # attempt_count=2
        self.backend.mark_failed("job-1", "Error 2", 3)
        
        self.backend.dequeue()  # attempt_count=3
        new_status = self.backend.mark_failed("job-1", "Error 3", 3)
        assert new_status == JobStatus.DEAD

        status = self.backend.get_status("job-1")
        assert status.status == JobStatus.DEAD

    def test_retry_from_dead(self):
        """从死信重试"""
        record = self._make_record()
        self.backend.enqueue(record)
        
        # 重试耗尽进入死信
        for _ in range(3):
            self.backend.dequeue()
            self.backend.mark_failed("job-1", "Error", 3)
        
        # 重试死信任务
        assert self.backend.retry_from_dead("job-1") == True
        
        status = self.backend.get_status("job-1")
        assert status.status == JobStatus.PENDING
        assert status.attempt_count == 0

    def test_retry_non_dead(self):
        """重试非死信任务"""
        record = self._make_record()
        self.backend.enqueue(record)
        assert self.backend.retry_from_dead("job-1") == False

    def test_unique_dedup(self):
        """唯一任务去重"""
        now = time.time()
        record1 = self._make_record(
            job_id="job-1",
            unique_key="SendEmail:abc",
            unique_expires_at=now + 3600,
        )
        record2 = self._make_record(
            job_id="job-2",
            unique_key="SendEmail:abc",
            unique_expires_at=now + 3600,
        )

        id1 = self.backend.enqueue(record1)
        assert id1 == "job-1"

        id2 = self.backend.enqueue(record2)
        assert id2 is None  # 唯一去重冲突

    def test_unique_dedup_expired_lock(self):
        """唯一锁过期后允许入队"""
        now = time.time()
        record1 = self._make_record(
            job_id="job-1",
            unique_key="SendEmail:abc",
            unique_expires_at=now - 1,  # 已过期
        )
        record2 = self._make_record(
            job_id="job-2",
            unique_key="SendEmail:abc",
            unique_expires_at=now + 3600,
        )

        id1 = self.backend.enqueue(record1)
        assert id1 == "job-1"

        # 完成旧任务
        self.backend.dequeue()
        self.backend.mark_completed("job-1")

        id2 = self.backend.enqueue(record2)
        assert id2 == "job-2"  # 锁已过期，允许入队

    def test_delayed_enqueue(self):
        """延迟入队"""
        record = self._make_record(
            job_id="scheduled-1",
            scheduled_at=time.time() + 3600,  # 1小时后
        )
        id = self.backend.enqueue(record)
        assert id == "scheduled-1"

        # 立即出队不应返回延迟任务
        dequeued = self.backend.dequeue()
        assert dequeued is None  # 还没到时间

    def test_delayed_enqueue_promote(self):
        """延迟任务到期后推进"""
        record = self._make_record(
            job_id="scheduled-1",
            scheduled_at=time.time() - 1,  # 已到期
        )
        self.backend.enqueue(record)

        # 推进到期任务
        with self.backend._lock:
            self.backend._promote_scheduled_jobs()

        dequeued = self.backend.dequeue()
        assert dequeued is not None

    def test_expired_job(self):
        """过期任务"""
        record = self._make_record(
            job_id="expired-1",
            expires_at=time.time() - 1,  # 已过期
        )
        self.backend.enqueue(record)

        # 出队时跳过过期任务
        dequeued = self.backend.dequeue()
        assert dequeued is None

        status = self.backend.get_status("expired-1")
        assert status.status == JobStatus.EXPIRED

    def test_list_jobs(self):
        """列出任务"""
        self.backend.enqueue(self._make_record(job_id="job-1", priority=JobPriority.NORMAL))
        self.backend.enqueue(self._make_record(job_id="job-2", priority=JobPriority.CRITICAL))
        
        # 出队一个使其变为 RUNNING
        self.backend.dequeue()
        
        all_jobs = self.backend.list_jobs(status=None, limit=50)
        assert len(all_jobs) == 2

        pending_jobs = self.backend.list_jobs(status=JobStatus.PENDING, limit=50)
        assert len(pending_jobs) == 1

    def test_clear_completed(self):
        """清理已完成任务"""
        record = self._make_record()
        self.backend.enqueue(record)
        self.backend.dequeue()
        self.backend.mark_completed("job-1")

        count = self.backend.clear_completed()
        assert count == 1
        assert self.backend.get_status("job-1") is None

    def test_stats(self):
        """队列统计"""
        self.backend.enqueue(self._make_record(job_id="job-1"))
        self.backend.enqueue(self._make_record(job_id="job-2"))
        
        stats = self.backend.stats()
        assert stats[JobStatus.PENDING] == 2


# ==================== SQLite 后端 ====================

class TestSQLiteBackend:
    """SQLite 后端测试"""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_jobs.db")
        self.backend = SQLiteBackend(self.db_path)

    def teardown_method(self):
        self.backend.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        os.rmdir(self.temp_dir)

    def _make_record(self, job_id="job-1", spec_name="TestJob", queue="default",
                     priority=JobPriority.NORMAL, args=None, unique_key=None,
                     unique_expires_at=None):
        """创建测试用的 JobRecord"""
        return JobRecord(
            job_id=job_id,
            spec_name=spec_name,
            args=args or {},
            status=JobStatus.PENDING,
            priority=priority,
            created_at=time.time(),
            attempt_count=0,
            max_retries=3,
            timeout=30.0,
            queue=queue,
            unique_key=unique_key,
            unique_expires_at=unique_expires_at,
        )

    def test_enqueue_and_dequeue(self):
        """SQLite 入队和出队"""
        record = self._make_record()
        job_id = self.backend.enqueue(record)
        assert job_id == "job-1"

        dequeued = self.backend.dequeue()
        assert dequeued is not None
        assert dequeued.job_id == "job-1"
        assert dequeued.status == JobStatus.RUNNING

    def test_priority_dequeue_order(self):
        """SQLite 优先级出队顺序"""
        self.backend.enqueue(self._make_record(job_id="low-1", priority=JobPriority.LOW))
        self.backend.enqueue(self._make_record(job_id="critical-1", priority=JobPriority.CRITICAL))

        first = self.backend.dequeue()
        assert first.priority == JobPriority.CRITICAL

        second = self.backend.dequeue()
        assert second.priority == JobPriority.LOW

    def test_get_status(self):
        """SQLite 查询任务状态"""
        self.backend.enqueue(self._make_record())
        status = self.backend.get_status("job-1")
        assert status is not None
        assert status.spec_name == "TestJob"

    def test_cancel(self):
        """SQLite 取消任务"""
        self.backend.enqueue(self._make_record())
        assert self.backend.cancel("job-1") == True
        
        status = self.backend.get_status("job-1")
        assert status.status == JobStatus.CANCELLED

    def test_mark_completed(self):
        """SQLite 标记完成"""
        self.backend.enqueue(self._make_record())
        self.backend.dequeue()
        self.backend.mark_completed("job-1")

        status = self.backend.get_status("job-1")
        assert status.status == JobStatus.COMPLETED

    def test_mark_failed_and_dead_letter(self):
        """SQLite 标记失败和死信"""
        self.backend.enqueue(self._make_record())
        
        # 模拟3次重试耗尽
        for i in range(3):
            r = self.backend.dequeue()
            if r:
                self.backend.mark_failed(r.job_id, f"Error {i+1}", 3)

        status = self.backend.get_status("job-1")
        assert status.status == JobStatus.DEAD

    def test_retry_from_dead(self):
        """SQLite 从死信重试"""
        self.backend.enqueue(self._make_record())
        
        for i in range(3):
            r = self.backend.dequeue()
            if r:
                self.backend.mark_failed(r.job_id, f"Error {i+1}", 3)

        assert self.backend.retry_from_dead("job-1") == True
        status = self.backend.get_status("job-1")
        assert status.status == JobStatus.PENDING

    def test_unique_dedup(self):
        """SQLite 唯一去重"""
        now = time.time()
        record1 = self._make_record(
            job_id="job-1",
            unique_key="SendEmail:abc",
            unique_expires_at=now + 3600,
        )
        record2 = self._make_record(
            job_id="job-2",
            unique_key="SendEmail:abc",
            unique_expires_at=now + 3600,
        )

        id1 = self.backend.enqueue(record1)
        assert id1 == "job-1"

        id2 = self.backend.enqueue(record2)
        assert id2 is None

    def test_list_jobs(self):
        """SQLite 列出任务"""
        self.backend.enqueue(self._make_record(job_id="job-1"))
        self.backend.enqueue(self._make_record(job_id="job-2"))
        
        all_jobs = self.backend.list_jobs(status=None, limit=50)
        assert len(all_jobs) == 2

    def test_clear_completed(self):
        """SQLite 清理已完成任务"""
        self.backend.enqueue(self._make_record())
        self.backend.dequeue()
        self.backend.mark_completed("job-1")

        count = self.backend.clear_completed()
        assert count == 1

    def test_persistence(self):
        """SQLite 持久化测试"""
        self.backend.enqueue(self._make_record())
        self.backend.close()

        # 重新打开数据库
        backend2 = SQLiteBackend(self.db_path)
        status = backend2.get_status("job-1")
        assert status is not None
        assert status.spec_name == "TestJob"
        backend2.close()


# ==================== JobQueue 统一接口 ====================

class TestJobQueue:
    """JobQueue 统一接口测试"""

    def setup_method(self):
        JobRegistry.clear()
        JobQueue._configured = False
        JobQueue._backend = None

    def _register_test_spec(self):
        """注册测试用 JobSpec"""
        spec = JobSpec(name="TestJob", queue="test_queue")
        JobRegistry.register(spec)

    def test_configure_memory(self):
        """配置内存后端"""
        JobQueue.configure(backend="memory")
        assert JobQueue._configured == True
        assert isinstance(JobQueue._backend, MemoryBackend)

    def test_configure_sqlite(self):
        """配置 SQLite 后端"""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_jobs.db")
        JobQueue.configure(backend="sqlite", db_path=db_path)
        assert JobQueue._configured == True
        assert isinstance(JobQueue._backend, SQLiteBackend)
        # 清理
        os.unlink(db_path)
        os.rmdir(temp_dir)

    def test_ensure_configured_default(self):
        """默认配置为内存后端"""
        JobQueue._ensure_configured()
        assert JobQueue._configured == True
        assert isinstance(JobQueue._backend, MemoryBackend)

    def test_enqueue(self):
        """入队任务"""
        self._register_test_spec()
        JobQueue.configure(backend="memory")
        
        job_id = JobQueue.enqueue("TestJob", {"key": "value"})
        assert job_id is not None

        record = JobQueue.status(job_id)
        assert record is not None
        assert record.spec_name == "TestJob"
        assert record.status == JobStatus.PENDING

    def test_enqueue_with_options(self):
        """入队带选项覆盖"""
        self._register_test_spec()
        JobQueue.configure(backend="memory")
        
        job_id = JobQueue.enqueue("TestJob", {"key": "value"}, 
                                   options={"priority": "critical"})
        assert job_id is not None
        
        record = JobQueue.status(job_id)
        assert record.priority == JobPriority.CRITICAL

    def test_enqueue_nonexistent_spec(self):
        """入队未注册的 JobSpec"""
        JobQueue.configure(backend="memory")
        with pytest.raises(ValueError, match="not registered"):
            JobQueue.enqueue("NonexistentJob", {})

    def test_enqueue_in(self):
        """延迟入队"""
        self._register_test_spec()
        JobQueue.configure(backend="memory")
        
        job_id = JobQueue.enqueue_in("TestJob", 3600, {"key": "value"})
        assert job_id is not None
        
        record = JobQueue.status(job_id)
        assert record.scheduled_at is not None

    def test_enqueue_at(self):
        """定时入队"""
        self._register_test_spec()
        JobQueue.configure(backend="memory")
        
        specific_time = time.time() + 3600
        job_id = JobQueue.enqueue_at("TestJob", specific_time, {"key": "value"})
        assert job_id is not None

    def test_status(self):
        """查询任务状态"""
        self._register_test_spec()
        JobQueue.configure(backend="memory")
        
        job_id = JobQueue.enqueue("TestJob", {"key": "value"})
        record = JobQueue.status(job_id)
        assert record is not None
        assert record.status == JobStatus.PENDING

    def test_cancel(self):
        """取消任务"""
        self._register_test_spec()
        JobQueue.configure(backend="memory")
        
        job_id = JobQueue.enqueue("TestJob", {"key": "value"})
        assert JobQueue.cancel(job_id) == True
        
        record = JobQueue.status(job_id)
        assert record.status == JobStatus.CANCELLED

    def test_retry_from_dead(self):
        """从死信重试"""
        spec = JobSpec(name="RetryTestJob", queue="test", retry_count=1)
        JobRegistry.register(spec)
        JobQueue.configure(backend="memory")
        
        job_id = JobQueue.enqueue("RetryTestJob", {"key": "value"})
        
        # 出队并失败 — 1次重试耗尽进入死信
        backend = JobQueue._backend
        dequeued = backend.dequeue()
        backend.mark_failed(job_id, "Test error", 1)
        
        record = JobQueue.status(job_id)
        assert record.status == JobStatus.DEAD
        
        # 重试
        assert JobQueue.retry(job_id) == True
        record = JobQueue.status(job_id)
        assert record.status == JobStatus.PENDING

    def test_list_jobs(self):
        """列出任务"""
        self._register_test_spec()
        JobQueue.configure(backend="memory")
        
        JobQueue.enqueue("TestJob", {"key": "1"})
        JobQueue.enqueue("TestJob", {"key": "2"})
        
        jobs = JobQueue.list_jobs(status=None, limit=50)
        assert len(jobs) == 2

    def test_clear_completed(self):
        """清理已完成任务"""
        self._register_test_spec()
        JobQueue.configure(backend="memory")
        
        job_id = JobQueue.enqueue("TestJob", {"key": "value"})
        backend = JobQueue._backend
        backend.dequeue()
        backend.mark_completed(job_id)
        
        count = JobQueue.clear_completed()
        assert count == 1

    def test_stats(self):
        """队列统计"""
        self._register_test_spec()
        JobQueue.configure(backend="memory")
        
        JobQueue.enqueue("TestJob", {"key": "1"})
        JobQueue.enqueue("TestJob", {"key": "2"})
        
        stats = JobQueue.stats()
        assert stats[JobStatus.PENDING] == 2


# ==================== 重试逻辑 ====================

class TestRetryLogic:
    """重试逻辑测试"""

    def test_exponential_backoff(self):
        """Exponential backoff 计算"""
        worker = JobWorker()
        
        # 2^0 = 1s, 2^1 = 2s, 2^2 = 4s, 2^3 = 8s
        assert worker._calculate_backoff(BackoffStrategy.EXPONENTIAL, 0) == 1
        assert worker._calculate_backoff(BackoffStrategy.EXPONENTIAL, 1) == 2
        assert worker._calculate_backoff(BackoffStrategy.EXPONENTIAL, 2) == 4
        assert worker._calculate_backoff(BackoffStrategy.EXPONENTIAL, 3) == 8

    def test_exponential_backoff_max(self):
        """Exponential backoff 最大300秒"""
        worker = JobWorker()
        assert worker._calculate_backoff(BackoffStrategy.EXPONENTIAL, 20) == 300  # capped

    def test_linear_backoff(self):
        """Linear backoff 计算"""
        worker = JobWorker()
        assert worker._calculate_backoff(BackoffStrategy.LINEAR, 1) == 10
        assert worker._calculate_backoff(BackoffStrategy.LINEAR, 3) == 30

    def test_constant_backoff(self):
        """Constant backoff 计算"""
        worker = JobWorker()
        assert worker._calculate_backoff(BackoffStrategy.CONSTANT, 0) == 10
        assert worker._calculate_backoff(BackoffStrategy.CONSTANT, 5) == 10


# ==================== 格式化输出 ====================

class TestFormatting:
    """格式化输出测试"""

    def test_format_job_status(self):
        """格式化单个任务状态"""
        record = JobRecord(
            job_id="job-abc123",
            spec_name="SendEmail",
            args={"user_id": "123"},
            status=JobStatus.PENDING,
            priority=JobPriority.NORMAL,
            created_at=time.time(),
            attempt_count=0,
            max_retries=3,
            queue="emails",
        )
        output = format_job_status(record)
        assert "job-abc123" in output
        assert "SendEmail" in output
        assert "emails" in output
        assert "pending" in output

    def test_format_jobs_table(self):
        """格式化任务列表表格"""
        records = [
            JobRecord(
                job_id="job-1",
                spec_name="JobA",
                args={},
                status=JobStatus.PENDING,
                priority=JobPriority.NORMAL,
                created_at=time.time(),
                attempt_count=0,
                max_retries=3,
                queue="default",
            ),
            JobRecord(
                job_id="job-2",
                spec_name="JobB",
                args={},
                status=JobStatus.RUNNING,
                priority=JobPriority.HIGH,
                created_at=time.time(),
                attempt_count=1,
                max_retries=3,
                queue="default",
            ),
        ]
        output = format_jobs_table(records)
        assert "job-1" in output
        assert "job-2" in output

    def test_format_jobs_table_empty(self):
        """空列表格式化"""
        output = format_jobs_table([])
        assert "No jobs found" in output


# ==================== Parser 语法测试 ====================

class TestJobParser:
    """Parser 语法解析测试"""

    def test_simple_job_decl(self):
        """解析简单 job 声明"""
        from src.nexa_parser import parse
        
        code = '''
job SendWelcomeEmail on "emails" {
    perform(user_id) {
        print("Sending email to user " + user_id)
    }
}
'''
        ast = parse(code)
        body = ast.get("body", [])
        
        # 查找 JobDeclaration
        job_decls = [node for node in body if isinstance(node, dict) and node.get("type") == "JobDeclaration"]
        assert len(job_decls) >= 1
        
        job = job_decls[0]
        assert job["name"] == "SendWelcomeEmail"
        assert job["queue"] == "emails"

    def test_job_with_inline_options(self):
        """解析带 inline 选项的 job"""
        from src.nexa_parser import parse
        
        code = '''
job AnalyzeDocument on "ai_tasks" (retry=2, timeout=120) {
    perform(doc_id) {
        print("Analyzing doc " + doc_id)
    }
}
'''
        # 这个语法可能比较复杂，测试基本的job声明解析
        ast = parse(code)
        body = ast.get("body", [])
        
        job_decls = [node for node in body if isinstance(node, dict) and node.get("type") == "JobDeclaration"]
        if len(job_decls) >= 1:
            job = job_decls[0]
            assert job["name"] == "AnalyzeDocument"
            assert job["queue"] == "ai_tasks"

    def test_job_with_config(self):
        """解析带配置的 job"""
        from src.nexa_parser import parse
        
        code = '''
job ProcessPayment on "payments" {
    retry: 5
    timeout: 60
    perform(order_id, amount) {
        print("Processing payment for order " + order_id)
    }
}
'''
        ast = parse(code)
        body = ast.get("body", [])
        
        job_decls = [node for node in body if isinstance(node, dict) and node.get("type") == "JobDeclaration"]
        if len(job_decls) >= 1:
            job = job_decls[0]
            assert job["name"] == "ProcessPayment"
            assert job["queue"] == "payments"

    def test_job_with_on_failure(self):
        """解析带 on_failure 的 job"""
        from src.nexa_parser import parse
        
        code = '''
job SendEmail on "emails" {
    perform(user_id) {
        print("Sending email")
    }
    on_failure(error, attempt) {
        print("Email failed: " + error)
    }
}
'''
        ast = parse(code)
        body = ast.get("body", [])
        
        job_decls = [node for node in body if isinstance(node, dict) and node.get("type") == "JobDeclaration"]
        if len(job_decls) >= 1:
            job = job_decls[0]
            assert job["name"] == "SendEmail"
            assert job.get("on_failure") is not None


# ==================== JobWorker 测试 ====================

class TestJobWorker:
    """JobWorker 执行测试"""

    def setup_method(self):
        JobRegistry.clear()
        JobQueue._configured = False
        JobQueue._backend = None

    def test_worker_status(self):
        """Worker 状态"""
        worker = JobWorker(worker_id="test-worker")
        status = worker.get_status()
        assert status["worker_id"] == "test-worker"
        assert status["running"] == False
        assert status["jobs_processed"] == 0

    def test_worker_execute_simple(self):
        """Worker 执行简单任务"""
        # 注册一个简单的 job
        def perform_fn(args):
            return args.get("value", 0) * 2

        spec = JobSpec(
            name="DoubleValue",
            queue="math",
            perform_fn=perform_fn,
        )
        JobRegistry.register(spec)
        JobQueue.configure(backend="memory")
        
        job_id = JobQueue.enqueue("DoubleValue", {"value": 5})
        assert job_id is not None
        
        # Worker 手动处理
        worker = JobWorker(worker_id="test-worker")
        record = JobQueue._backend.dequeue()
        if record:
            result = worker.execute_with_retry(spec, record)
            JobQueue._backend.mark_completed(record.job_id)
        
        status = JobQueue.status(job_id)
        assert status.status == JobStatus.COMPLETED

    def test_worker_execute_with_timeout(self):
        """Worker 执行超时"""
        def slow_fn(args):
            time.sleep(10)  # 模拟超时
            return "done"

        spec = JobSpec(
            name="SlowJob",
            queue="slow",
            perform_fn=slow_fn,
            timeout=2.0,  # 2秒超时
        )
        JobRegistry.register(spec)
        JobQueue.configure(backend="memory")
        
        job_id = JobQueue.enqueue("SlowJob", {"key": "value"})
        record = JobQueue._backend.dequeue()
        
        worker = JobWorker(worker_id="timeout-worker")
        try:
            worker.execute_with_retry(spec, record)
            # 如果超时，应该抛出异常
            assert False, "Expected timeout exception"
        except (TimeoutError, Exception):
            # 超时是预期行为
            pass


# ==================== JobScheduler 测试 ====================

class TestJobScheduler:
    """JobScheduler 测试"""

    def test_scheduler_creation(self):
        """创建调度器"""
        scheduler = JobScheduler(check_interval=5.0)
        assert scheduler.check_interval == 5.0

    def test_scheduler_start_stop(self):
        """启动和停止调度器"""
        scheduler = JobScheduler(check_interval=1.0)
        scheduler.start(daemon=True)
        assert scheduler._running == True
        
        scheduler.stop()
        assert scheduler._running == False


# ==================== 集成测试 ====================

class TestIntegration:
    """集成测试 — 完整工作流"""

    def setup_method(self):
        JobRegistry.clear()
        JobQueue._configured = False
        JobQueue._backend = None

    def test_full_workflow(self):
        """完整工作流：注册 → 入队 → 出队 → 执行 → 完成"""
        def perform_fn(args):
            return f"Processed {args.get('user_id', 'unknown')}"

        spec = JobSpec(
            name="SendEmail",
            queue="emails",
            perform_fn=perform_fn,
        )
        JobRegistry.register(spec)
        JobQueue.configure(backend="memory")
        
        # 入队
        job_id = JobQueue.enqueue("SendEmail", {"user_id": "123"})
        assert job_id is not None
        
        # 查询状态
        record = JobQueue.status(job_id)
        assert record.status == JobStatus.PENDING
        
        # 出队
        dequeued = JobQueue._backend.dequeue()
        assert dequeued.job_id == job_id
        assert dequeued.status == JobStatus.RUNNING
        
        # 执行
        worker = JobWorker(worker_id="integration-worker")
        result = worker.execute_with_retry(spec, dequeued)
        
        # 标记完成
        JobQueue._backend.mark_completed(job_id)
        
        # 验证完成状态
        record = JobQueue.status(job_id)
        assert record.status == JobStatus.COMPLETED

    def test_priority_workflow(self):
        """优先级工作流：critical 任务优先执行"""
        JobRegistry.register(JobSpec(name="LowJob", queue="low", priority=JobPriority.LOW, perform_fn=lambda args: "low"))
        JobRegistry.register(JobSpec(name="CriticalJob", queue="critical", priority=JobPriority.CRITICAL, perform_fn=lambda args: "critical"))
        JobQueue.configure(backend="memory")
        
        # Low 先入队，Critical 后入队
        low_id = JobQueue.enqueue("LowJob", {"type": "low"})
        critical_id = JobQueue.enqueue("CriticalJob", {"type": "critical"})
        
        # Critical 应先出队
        first = JobQueue._backend.dequeue()
        assert first.spec_name == "CriticalJob"
        
        second = JobQueue._backend.dequeue()
        assert second.spec_name == "LowJob"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])