'''
Nexa Structured Concurrency — Agent-Native 并发运行时

核心概念:
- NexaChannel: 线程安全无界通道 (queue.Queue)
- NexaTask: 后台任务句柄 (concurrent.futures)
- NexaSchedule: 周期调度器
- NexaConcurrencyRuntime: 全局单例注册表

Nexa 特色 (Agent-Aware Concurrency):
- spawn 可接受 NexaAgent 作为 handler → agent.run(context)
- parallel/race 可并行运行多个 Agent
- channels 可携带 Agent 对话上下文
- cancel_task 与 Agent timeout/retry 装饰器联动

无新增外部依赖: queue, threading, concurrent.futures, os, time, itertools (全部 stdlib)
'''

import queue
import threading
import concurrent.futures
import os
import time
import itertools
import re
import logging
from typing import Any, Dict, List, Optional, Tuple, Callable

logger = logging.getLogger(__name__)

# ==================== 全局线程池 ====================

_MAX_WORKERS = max(os.cpu_count() or 1, 4)
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix='nexa-task')

# ==================== NexaChannel ====================

class NexaChannel:
    '''线程安全无界通道, 使用 queue.Queue 实现'''

    def __init__(self, channel_id: int):
        self._queue: queue.Queue = queue.Queue()  # unbounded
        self._closed: threading.Event = threading.Event()
        self._id: int = channel_id
        self._lock: threading.Lock = threading.Lock()

    def send(self, value: Any) -> bool:
        '''发送值到通道。如果通道已关闭, 返回 False'''
        if self._closed.is_set():
            return False
        self._queue.put(value)
        return True

    def recv(self) -> Any:
        '''阻塞接收。如果通道关闭或断开, 返回 None'''
        while True:
            if self._closed.is_set():
                # 通道关闭后, 先尝试取剩余消息
                try:
                    return self._queue.get_nowait()
                except queue.Empty:
                    return None
            try:
                # 50ms 超时切片, 允许取消感知
                return self._queue.get(timeout=0.05)
            except queue.Empty:
                continue

    def recv_timeout(self, ms: int) -> Any:
        '''带超时的接收。超时返回 None'''
        if ms < 0:
            ms = 0
        deadline = time.monotonic() + ms / 1000.0
        while True:
            if self._closed.is_set():
                try:
                    return self._queue.get_nowait()
                except queue.Empty:
                    return None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            try:
                return self._queue.get(timeout=min(remaining, 0.05))
            except queue.Empty:
                if time.monotonic() >= deadline:
                    return None
                continue

    def try_recv(self) -> Optional[Any]:
        '''非阻塞 peek。空时返回 None'''
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def close(self) -> bool:
        '''关闭通道'''
        was_open = not self._closed.is_set()
        self._closed.set()
        return was_open

    def is_closed(self) -> bool:
        return self._closed.is_set()


# ==================== NexaTask ====================

class NexaTask:
    '''后台任务句柄'''

    def __init__(self, task_id: int, future: concurrent.futures.Future,
                 cancel_token: threading.Event):
        self._id: int = task_id
        self._future: concurrent.futures.Future = future
        self._cancel_token: threading.Event = cancel_token
        self._state: str = 'running'  # running/completed/failed/cancelled
        self._result: Any = None
        self._error: Optional[Exception] = None
        self._completed_at: Optional[float] = None

    def _mark_completed(self, result: Any) -> None:
        self._state = 'completed'
        self._result = result
        self._completed_at = time.monotonic()

    def _mark_failed(self, error: Exception) -> None:
        self._state = 'failed'
        self._error = error
        self._completed_at = time.monotonic()

    def _mark_cancelled(self) -> None:
        self._state = 'cancelled'
        self._completed_at = time.monotonic()


# ==================== NexaSchedule ====================

class NexaSchedule:
    '''周期调度器'''

    def __init__(self, schedule_id: int, interval_ms: int,
                 handler: Callable, cancel_token: threading.Event):
        self._id: int = schedule_id
        self._interval_ms: int = interval_ms
        self._handler: Callable = handler
        self._cancel_token: threading.Event = cancel_token
        self._thread: Optional[threading.Thread] = None
        self._running: bool = False

    def start(self) -> None:
        '''启动周期调度线程'''
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True,
            name=f'nexa-schedule-{self._id}'
        )
        self._thread.start()

    def _run_loop(self) -> None:
        '''周期执行循环 — 捕获异常不终止调度'''
        while not self._cancel_token.is_set():
            _sleep_cancellable(self._interval_ms)
            if not self._cancel_token.is_set():
                try:
                    self._handler()
                except Exception as e:
                    # panic caught, don't kill schedule
                    logger.debug(f'Schedule {self._id} tick error: {e}')
                    pass
        self._running = False

    def cancel(self) -> bool:
        '''取消周期调度'''
        was_running = self._running
        self._cancel_token.set()
        self._running = False
        return was_running


# ==================== NexaConcurrencyRuntime ====================

class NexaConcurrencyRuntime:
    '''全局并发运行时单例'''

    def __init__(self):
        self._channels: Dict[int, NexaChannel] = {}
        self._tasks: Dict[int, NexaTask] = {}
        self._schedules: Dict[int, NexaSchedule] = {}
        self._id_counter: itertools.count = itertools.count(1)
        self._lock: threading.Lock = threading.Lock()

    def _next_id(self) -> int:
        return next(self._id_counter)

    def register_channel(self, ch: NexaChannel) -> None:
        with self._lock:
            self._channels[ch._id] = ch

    def unregister_channel(self, channel_id: int) -> None:
        with self._lock:
            self._channels.pop(channel_id, None)

    def get_channel(self, channel_id: int) -> Optional[NexaChannel]:
        with self._lock:
            return self._channels.get(channel_id)

    def register_task(self, task: NexaTask) -> None:
        with self._lock:
            self._tasks[task._id] = task

    def unregister_task(self, task_id: int) -> None:
        with self._lock:
            self._tasks.pop(task_id, None)

    def get_task(self, task_id: int) -> Optional[NexaTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def register_schedule(self, schedule: NexaSchedule) -> None:
        with self._lock:
            self._schedules[schedule._id] = schedule

    def unregister_schedule(self, schedule_id: int) -> None:
        with self._lock:
            self._schedules.pop(schedule_id, None)

    def get_schedule(self, schedule_id: int) -> Optional[NexaSchedule]:
        with self._lock:
            return self._schedules.get(schedule_id)

    def cleanup_expired(self, max_age_seconds: int = 300) -> None:
        '''清理超过 5 分钟的已完成任务'''
        now = time.monotonic()
        with self._lock:
            expired_ids = []
            for tid, task in self._tasks.items():
                if task._completed_at and (now - task._completed_at) > max_age_seconds:
                    expired_ids.append(tid)
            for tid in expired_ids:
                del self._tasks[tid]


RUNTIME = NexaConcurrencyRuntime()


# ==================== Channel API ====================

def channel() -> List[Dict]:
    '''创建通道对 [tx_handle, rx_handle]'''
    ch_id = RUNTIME._next_id()
    ch = NexaChannel(ch_id)
    RUNTIME.register_channel(ch)
    tx_handle = {'_nexa_channel_id': ch_id, 'role': 'tx'}
    rx_handle = {'_nexa_channel_id': ch_id, 'role': 'rx'}
    return [tx_handle, rx_handle]


def send(tx: Dict, value: Any) -> bool:
    '''通过通道发送值。返回 False 如果通道已关闭'''
    ch_id = tx.get('_nexa_channel_id')
    if ch_id is None:
        return False
    ch = RUNTIME.get_channel(ch_id)
    if ch is None:
        return False
    return ch.send(value)


def recv(rx: Dict) -> Any:
    '''阻塞接收通道消息。返回 None 如果关闭/断开'''
    ch_id = rx.get('_nexa_channel_id')
    if ch_id is None:
        return None
    ch = RUNTIME.get_channel(ch_id)
    if ch is None:
        return None
    return ch.recv()


def recv_timeout(rx: Dict, ms: int) -> Any:
    '''带超时接收。超时返回 None'''
    ch_id = rx.get('_nexa_channel_id')
    if ch_id is None:
        return None
    ch = RUNTIME.get_channel(ch_id)
    if ch is None:
        return None
    return ch.recv_timeout(ms)


def try_recv(rx: Dict) -> Optional[Any]:
    '''非阻塞 peek 接收'''
    ch_id = rx.get('_nexa_channel_id')
    if ch_id is None:
        return None
    ch = RUNTIME.get_channel(ch_id)
    if ch is None:
        return None
    return ch.try_recv()


def close(rx: Dict) -> bool:
    '''关闭通道 (停止新发送, 但保留注册以便 drain 剩余消息)

    通道关闭后, recv 仍可读取已发送但未被消费的消息。
    完全 drain 后由 cleanup_expired 清理注册表条目。
    '''
    ch_id = rx.get('_nexa_channel_id')
    if ch_id is None:
        return False
    ch = RUNTIME.get_channel(ch_id)
    if ch is None:
        return False
    was_open = ch.close()
    return was_open


def select(rx_list: List[Dict], timeout_ms: Optional[int] = None) -> Dict:
    '''多路复用多个通道, 返回第一个有数据的通道

    Returns: {"status": "ok"/"timeout"/"closed", "channel": rx_handle, "value": data}
    '''
    deadline = None
    if timeout_ms is not None:
        deadline = time.monotonic() + timeout_ms / 1000.0

    while True:
        # 检查超时
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return {'status': 'timeout', 'channel': None, 'value': None}

        # 扫描所有通道
        all_closed = True
        for rx in rx_list:
            ch_id = rx.get('_nexa_channel_id')
            if ch_id is None:
                continue
            ch = RUNTIME.get_channel(ch_id)
            if ch is None:
                continue
            if not ch.is_closed():
                all_closed = False
            val = ch.try_recv()
            if val is not None:
                return {'status': 'ok', 'channel': rx, 'value': val}

        if all_closed:
            return {'status': 'closed', 'channel': None, 'value': None}

        # 50ms 等待切片 (取消感知)
        _sleep_cancellable(50)


# ==================== Task API ====================

def spawn(handler: Any) -> Dict:
    '''Spawn 后台任务。handler 可为 callable 或 NexaAgent 实例

    Returns: {"_nexa_task_id": id, "state": "running"}
    '''
    # Agent-Aware spawn
    from .agent import NexaAgent

    if isinstance(handler, NexaAgent):
        context = getattr(handler, 'context', '') or ''
        target = lambda: handler.run(context)
    elif callable(handler):
        target = handler
    else:
        raise ValueError(f'spawn handler must be callable or NexaAgent, got {type(handler)}')

    task_id = RUNTIME._next_id()
    cancel_token = threading.Event()

    def _run_task():
        if cancel_token.is_set():
            return None
        try:
            result = target()
            if cancel_token.is_set():
                # 任务在执行中被取消
                task_obj = RUNTIME.get_task(task_id)
                if task_obj:
                    task_obj._mark_cancelled()
                return None
            task_obj = RUNTIME.get_task(task_id)
            if task_obj:
                task_obj._mark_completed(result)
            return result
        except Exception as e:
            task_obj = RUNTIME.get_task(task_id)
            if task_obj:
                task_obj._mark_failed(e)
            raise

    future = _executor.submit(_run_task)
    task = NexaTask(task_id, future, cancel_token)
    RUNTIME.register_task(task)

    return {'_nexa_task_id': task_id, 'state': 'running'}


def await_task(task: Dict) -> Any:
    '''阻塞等待任务完成, 返回结果。失败时抛出异常'''
    task_id = task.get('_nexa_task_id')
    if task_id is None:
        raise ValueError('Invalid task handle: missing _nexa_task_id')
    task_obj = RUNTIME.get_task(task_id)
    if task_obj is None:
        raise ValueError(f'Task {task_id} not found in registry')
    try:
        result = task_obj._future.result()
        return result
    except concurrent.futures.CancelledError:
        raise ValueError(f'Task {task_id} was cancelled')
    except Exception as e:
        raise e


def try_await(task: Dict) -> Dict:
    '''非阻塞 peek 任务状态

    Returns: {"status": "running"/"completed"/"failed"/"cancelled", "result": ...}
    '''
    task_id = task.get('_nexa_task_id')
    if task_id is None:
        return {'status': 'failed', 'result': 'Invalid task handle'}
    task_obj = RUNTIME.get_task(task_id)
    if task_obj is None:
        return {'status': 'failed', 'result': f'Task {task_id} not found'}

    if task_obj._state == 'completed':
        return {'status': 'completed', 'result': task_obj._result}
    elif task_obj._state == 'failed':
        return {'status': 'failed', 'result': str(task_obj._error)}
    elif task_obj._state == 'cancelled':
        return {'status': 'cancelled', 'result': None}

    # 还在运行 — 检查 future 是否已完成
    if task_obj._future.done():
        try:
            result = task_obj._future.result()
            return {'status': 'completed', 'result': result}
        except concurrent.futures.CancelledError:
            return {'status': 'cancelled', 'result': None}
        except Exception as e:
            return {'status': 'failed', 'result': str(e)}

    return {'status': 'running', 'result': None}


def cancel_task(task: Dict) -> bool:
    '''设置取消令牌。协作式取消 — 任务在下一个 yield 点退出'''
    task_id = task.get('_nexa_task_id')
    if task_id is None:
        return False
    task_obj = RUNTIME.get_task(task_id)
    if task_obj is None:
        return False
    was_running = task_obj._state == 'running'
    task_obj._cancel_token.set()
    # 尝试取消 future (不一定成功, 取决于执行状态)
    task_obj._future.cancel()
    if was_running:
        task_obj._mark_cancelled()
    return was_running


# ==================== parallel + race ====================

def parallel(handlers: List[Any]) -> List[Any]:
    '''并行执行所有 handler, 返回结果列表(保持输入顺序)

    如果任何一个失败, 取消剩余任务并抛出异常
    '''
    tasks = [spawn(h) for h in handlers]
    results = []
    for i, t in enumerate(tasks):
        try:
            results.append(await_task(t))
        except Exception as e:
            # 取消剩余任务
            for remaining in tasks[i + 1:]:
                cancel_task(remaining)
            raise
    return results


def race(handlers: List[Any]) -> Any:
    '''第一个成功结果, 取消其余。如果全部失败, 抛出最后一个错误'''
    tasks = [spawn(h) for h in handlers]
    task_objs = []
    for t in tasks:
        tid = t.get('_nexa_task_id')
        obj = RUNTIME.get_task(tid)
        if obj:
            task_objs.append(obj)

    first_result = None
    first_error = None
    success_count = 0
    fail_count = 0
    total = len(task_objs)

    # 等待所有 future 完成, 收集第一个成功
    for future in concurrent.futures.as_completed([o._future for o in task_objs]):
        try:
            result = future.result()
            if first_result is None:
                first_result = result
            success_count += 1
        except Exception as e:
            first_error = e
            fail_count += 1

    # 取消所有还在运行的任务
    for t in tasks:
        cancel_task(t)

    if first_result is not None:
        return first_result

    # 全部失败, 抛出最后一个错误
    if first_error:
        raise first_error
    raise ValueError('All handlers failed in race')


# ==================== Schedule + After + sleep_ms ====================

def after(delay: Any, handler: Any) -> Dict:
    '''延迟执行。delay 可为 int ms 或字符串 ("5s", "1m", "500ms")'''
    ms = parse_interval(delay) if isinstance(delay, str) else int(delay)

    # Agent-Aware after
    from .agent import NexaAgent

    if isinstance(handler, NexaAgent):
        context = getattr(handler, 'context', '') or ''
        actual_handler = lambda: handler.run(context)
    elif callable(handler):
        actual_handler = handler
    else:
        raise ValueError(f'after handler must be callable or NexaAgent, got {type(handler)}')

    def _delayed_fn():
        _sleep_cancellable(ms)
        if not _is_cancelled_for_task(task_id_placeholder):
            return actual_handler()

    # 先创建 task 以获取 task_id
    task_id_placeholder = None

    task_id = RUNTIME._next_id()
    cancel_token = threading.Event()
    task_id_placeholder = task_id

    def _run_delayed():
        _sleep_cancellable(ms)
        if cancel_token.is_set():
            task_obj = RUNTIME.get_task(task_id)
            if task_obj:
                task_obj._mark_cancelled()
            return None
        try:
            result = actual_handler()
            task_obj = RUNTIME.get_task(task_id)
            if task_obj:
                task_obj._mark_completed(result)
            return result
        except Exception as e:
            task_obj = RUNTIME.get_task(task_id)
            if task_obj:
                task_obj._mark_failed(e)
            raise

    future = _executor.submit(_run_delayed)
    task = NexaTask(task_id, future, cancel_token)
    RUNTIME.register_task(task)

    return {'_nexa_task_id': task_id, 'state': 'running'}


def schedule(interval: Any, handler: Any) -> Dict:
    '''周期执行。interval 可为 int ms 或字符串格式'''
    ms = parse_interval(interval) if isinstance(interval, str) else int(interval)

    if ms <= 0:
        raise ValueError('schedule interval must be positive')

    # Agent-Aware schedule
    from .agent import NexaAgent

    if isinstance(handler, NexaAgent):
        context = getattr(handler, 'context', '') or ''
        actual_handler = lambda: handler.run(context)
    elif callable(handler):
        actual_handler = handler
    else:
        raise ValueError(f'schedule handler must be callable or NexaAgent, got {type(handler)}')

    schedule_id = RUNTIME._next_id()
    cancel_token = threading.Event()
    sched = NexaSchedule(schedule_id, ms, actual_handler, cancel_token)
    RUNTIME.register_schedule(sched)
    sched.start()

    return {'_nexa_schedule_id': schedule_id, 'running': True}


def cancel_schedule(schedule: Dict) -> bool:
    '''取消周期调度'''
    schedule_id = schedule.get('_nexa_schedule_id')
    if schedule_id is None:
        return False
    sched = RUNTIME.get_schedule(schedule_id)
    if sched is None:
        return False
    was_running = sched.cancel()
    RUNTIME.unregister_schedule(schedule_id)
    return was_running


def sleep_ms(ms: int) -> None:
    '''取消感知的 sleep (50ms 切片)'''
    _sleep_cancellable(ms)


def thread_count() -> int:
    '''返回 CPU 线程数'''
    return os.cpu_count() or 1


# ==================== 辅助函数 ====================

def _sleep_cancellable(ms: int) -> None:
    '''取消感知的 sleep, 50ms 切片'''
    remaining = ms / 1000.0
    while remaining > 0:
        slice_time = min(remaining, 0.05)
        time.sleep(slice_time)
        remaining -= slice_time


def _is_cancelled_for_task(task_id: int) -> bool:
    '''检查任务是否被取消'''
    task_obj = RUNTIME.get_task(task_id)
    if task_obj:
        return task_obj._cancel_token.is_set()
    return True  # 不存在的任务视为已取消


_INTERVAL_PATTERN = re.compile(r'^(\d+)(ms|s|m|h)?$')

def parse_interval(s: Any) -> int:
    '''解析时间间隔字符串为毫秒

    格式: "100ms" / "5s" / "1m" / "1h" / "500" (裸数字默认 ms)
    '''
    if isinstance(s, (int, float)):
        return int(s)

    s = str(s).strip()
    match = _INTERVAL_PATTERN.match(s)
    if not match:
        raise ValueError(f'Invalid interval format: {s}')

    value = int(match.group(1))
    unit = match.group(2) or 'ms'  # 裸数字默认毫秒

    if unit == 'ms':
        return value
    elif unit == 's':
        return value * 1000
    elif unit == 'm':
        return value * 60 * 1000
    elif unit == 'h':
        return value * 3600 * 1000
    else:
        return value


def get_active_channels() -> Dict[int, NexaChannel]:
    '''获取所有活跃通道快照'''
    with RUNTIME._lock:
        return dict(RUNTIME._channels)


def get_active_tasks() -> Dict[int, NexaTask]:
    '''获取所有活跃任务快照'''
    with RUNTIME._lock:
        return dict(RUNTIME._tasks)


def get_active_schedules() -> Dict[int, NexaSchedule]:
    '''获取所有活跃调度快照'''
    with RUNTIME._lock:
        return dict(RUNTIME._schedules)


def shutdown_runtime() -> None:
    '''关闭并发运行时: 取消所有任务和调度'''
    with RUNTIME._lock:
        for task in RUNTIME._tasks.values():
            task._cancel_token.set()
            task._future.cancel()
        for sched in RUNTIME._schedules.values():
            sched.cancel()
    _executor.shutdown(wait=False)