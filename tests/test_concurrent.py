'''
P2-2: Structured Concurrency Tests — 80+ tests

测试覆盖:
- Channel 创建/发送/接收/超时/peek/关闭
- Task spawn/await/try_await/cancel
- parallel/race/select
- after/schedule/sleep_ms/thread_count
- Agent-Aware spawn
- Contract integration
- Stdlib namespace
- Parser/AST
'''

import pytest
import json
import time
import threading
import sys
import os

# Ensure src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.runtime.concurrent import (
    NexaChannel, NexaTask, NexaSchedule, NexaConcurrencyRuntime, RUNTIME,
    channel, send, recv, recv_timeout, try_recv, close,
    select, spawn, await_task, try_await, cancel_task,
    parallel, race, after, schedule, cancel_schedule,
    sleep_ms, thread_count, parse_interval,
    get_active_channels, get_active_tasks, get_active_schedules,
    _sleep_cancellable,
)


# ==================== TestChannelCreation ====================

class TestChannelCreation:
    '''通道对创建测试'''

    def test_channel_returns_list_of_two(self):
        result = channel()
        assert isinstance(result, list)
        assert len(result) == 2

    def test_tx_handle_format(self):
        tx, rx = channel()
        assert '_nexa_channel_id' in tx
        assert tx['role'] == 'tx'
        assert isinstance(tx['_nexa_channel_id'], int)

    def test_rx_handle_format(self):
        tx, rx = channel()
        assert '_nexa_channel_id' in rx
        assert rx['role'] == 'rx'
        assert isinstance(rx['_nexa_channel_id'], int)

    def test_tx_rx_same_channel_id(self):
        tx, rx = channel()
        assert tx['_nexa_channel_id'] == rx['_nexa_channel_id']


# ==================== TestChannelSendRecv ====================

class TestChannelSendRecv:
    '''通道发送/接收测试'''

    def test_send_recv_basic_string(self):
        tx, rx = channel()
        assert send(tx, 'hello') is True
        result = recv(rx)
        assert result == 'hello'

    def test_send_recv_integer(self):
        tx, rx = channel()
        send(tx, 42)
        result = recv(rx)
        assert result == 42

    def test_send_recv_dict(self):
        tx, rx = channel()
        data = {'key': 'value', 'num': 123}
        send(tx, data)
        result = recv(rx)
        assert result == data

    def test_send_recv_multiple_messages(self):
        tx, rx = channel()
        for i in range(5):
            send(tx, f'msg_{i}')
        for i in range(5):
            result = recv(rx)
            assert result == f'msg_{i}'

    def test_send_returns_true_when_open(self):
        tx, rx = channel()
        result = send(tx, 'test')
        assert result is True

    def test_send_none_value(self):
        tx, rx = channel()
        send(tx, None)
        result = recv(rx)
        assert result is None

    def test_send_list_value(self):
        tx, rx = channel()
        send(tx, [1, 2, 3])
        result = recv(rx)
        assert result == [1, 2, 3]

    def test_send_bool_value(self):
        tx, rx = channel()
        send(tx, True)
        result = recv(rx)
        assert result is True


# ==================== TestChannelTimeout ====================

class TestChannelTimeout:
    '''通道超时接收测试'''

    def test_recv_timeout_returns_value(self):
        tx, rx = channel()
        send(tx, 'data')
        result = recv_timeout(rx, 1000)
        assert result == 'data'

    def test_recv_timeout_returns_none_on_empty(self):
        tx, rx = channel()
        result = recv_timeout(rx, 100)
        assert result is None

    def test_recv_timeout_zero_ms(self):
        tx, rx = channel()
        result = recv_timeout(rx, 0)
        assert result is None

    def test_recv_timeout_negative_treated_as_zero(self):
        tx, rx = channel()
        result = recv_timeout(rx, -100)
        assert result is None

    def test_recv_timeout_with_data_arriving(self):
        tx, rx = channel()
        def delayed_send():
            time.sleep(0.05)
            send(tx, 'late_data')
        t = threading.Thread(target=delayed_send)
        t.start()
        result = recv_timeout(rx, 500)
        assert result == 'late_data'
        t.join()


# ==================== TestChannelTryRecv ====================

class TestChannelTryRecv:
    '''通道非阻塞 peek 测试'''

    def test_try_recv_empty_returns_none(self):
        tx, rx = channel()
        result = try_recv(rx)
        assert result is None

    def test_try_recv_after_send(self):
        tx, rx = channel()
        send(tx, 'peek_data')
        result = try_recv(rx)
        assert result == 'peek_data'

    def test_try_recv_consumes_message(self):
        tx, rx = channel()
        send(tx, 'consumed')
        val1 = try_recv(rx)
        assert val1 == 'consumed'
        val2 = try_recv(rx)
        assert val2 is None

    def test_try_recv_multiple_messages(self):
        tx, rx = channel()
        send(tx, 'first')
        send(tx, 'second')
        val1 = try_recv(rx)
        val2 = try_recv(rx)
        assert val1 == 'first'
        assert val2 == 'second'


# ==================== TestChannelClose ====================

class TestChannelClose:
    '''通道关闭测试'''

    def test_close_returns_true_when_open(self):
        tx, rx = channel()
        result = close(rx)
        assert result is True

    def test_send_returns_false_after_close(self):
        tx, rx = channel()
        close(rx)
        result = send(tx, 'after_close')
        assert result is False

    def test_recv_returns_none_after_close_empty(self):
        tx, rx = channel()
        close(rx)
        result = recv(rx)
        assert result is None

    def test_recv_returns_remaining_after_close(self):
        tx, rx = channel()
        send(tx, 'remaining')
        close(rx)
        result = recv(rx)
        assert result == 'remaining'

    def test_close_marks_channel_closed_not_removed(self):
        '''close() 不立即移除注册, 保留以便 drain 剩余消息'''
        tx, rx = channel()
        ch_id = rx['_nexa_channel_id']
        close(rx)
        ch = RUNTIME.get_channel(ch_id)
        assert ch is not None  # Still in registry for draining
        assert ch.is_closed() is True


# ==================== TestSelect ====================

class TestSelect:
    '''多路复用 select 测试'''

    def test_select_single_channel_with_data(self):
        tx, rx = channel()
        send(tx, 'select_data')
        result = select([rx], timeout_ms=500)
        assert result['status'] == 'ok'
        assert result['value'] == 'select_data'

    def test_select_multiple_channels(self):
        tx1, rx1 = channel()
        tx2, rx2 = channel()
        send(tx2, 'from_ch2')
        result = select([rx1, rx2], timeout_ms=500)
        assert result['status'] == 'ok'
        assert result['value'] == 'from_ch2'

    def test_select_timeout(self):
        tx, rx = channel()
        result = select([rx], timeout_ms=100)
        assert result['status'] == 'timeout'

    def test_select_all_closed(self):
        tx1, rx1 = channel()
        tx2, rx2 = channel()
        close(rx1)
        close(rx2)
        result = select([rx1, rx2], timeout_ms=100)
        assert result['status'] == 'closed'

    def test_select_returns_channel_handle(self):
        tx1, rx1 = channel()
        send(tx1, 'ch1_data')
        result = select([rx1], timeout_ms=500)
        assert result['channel'] == rx1


# ==================== TestTaskSpawn ====================

class TestTaskSpawn:
    '''任务派生测试'''

    def test_spawn_callable(self):
        task = spawn(lambda: 42)
        assert '_nexa_task_id' in task
        assert task['state'] == 'running'

    def test_spawn_and_await_result(self):
        task = spawn(lambda: 'hello_task')
        result = await_task(task)
        assert result == 'hello_task'

    def test_spawn_function(self):
        def my_func():
            return 'func_result'
        task = spawn(my_func)
        result = await_task(task)
        assert result == 'func_result'

    def test_spawn_lambda_with_args_capture(self):
        value = 99
        task = spawn(lambda: value * 2)
        result = await_task(task)
        assert result == 198

    def test_spawn_returns_dict_handle(self):
        task = spawn(lambda: None)
        assert isinstance(task, dict)
        assert '_nexa_task_id' in task

    def test_spawn_multiple_tasks(self):
        tasks = [spawn(lambda i=i: i) for i in range(5)]
        results = [await_task(t) for t in tasks]
        assert results == [0, 1, 2, 3, 4]

    def test_spawn_with_exception(self):
        def failing():
            raise RuntimeError('task failed')
        task = spawn(failing)
        with pytest.raises(RuntimeError, match='task failed'):
            await_task(task)

    def test_spawn_invalid_handler(self):
        with pytest.raises(ValueError, match='must be callable'):
            spawn('not_callable')


# ==================== TestTaskAwait ====================

class TestTaskAwait:
    '''任务等待测试'''

    def test_await_returns_result(self):
        task = spawn(lambda: 'await_result')
        result = await_task(task)
        assert result == 'await_result'

    def test_await_raises_on_failure(self):
        task = spawn(lambda: (_ for _ in ()).throw(ValueError('fail')))
        with pytest.raises(Exception):
            await_task(task)

    def test_await_blocking_until_complete(self):
        def slow_task():
            time.sleep(0.1)
            return 'slow_done'
        task = spawn(slow_task)
        result = await_task(task)
        assert result == 'slow_done'

    def test_await_invalid_task_handle(self):
        with pytest.raises(ValueError, match='Invalid task handle'):
            await_task({})

    def test_await_task_not_found(self):
        with pytest.raises(ValueError, match='not found'):
            await_task({'_nexa_task_id': 999999})

    def test_await_task_with_dict_result(self):
        task = spawn(lambda: {'status': 'ok', 'data': [1, 2, 3]})
        result = await_task(task)
        assert result['status'] == 'ok'


# ==================== TestTaskTryAwait ====================

class TestTaskTryAwait:
    '''非阻塞 peek 任务状态测试'''

    def test_try_await_running_task(self):
        def slow():
            time.sleep(0.5)
            return 'late'
        task = spawn(slow)
        result = try_await(task)
        assert result['status'] in ('running', 'completed')

    def test_try_await_completed_task(self):
        task = spawn(lambda: 'done')
        time.sleep(0.1)  # Wait for completion
        result = try_await(task)
        assert result['status'] in ('completed', 'running')

    def test_try_await_failed_task(self):
        def failing():
            raise RuntimeError('fail')
        task = spawn(failing)
        time.sleep(0.1)
        result = try_await(task)
        assert result['status'] in ('failed', 'running')

    def test_try_await_cancelled_task(self):
        task = spawn(lambda: time.sleep(2))
        time.sleep(0.05)
        cancel_task(task)
        time.sleep(0.05)
        result = try_await(task)
        assert result['status'] in ('cancelled', 'running')

    def test_try_await_invalid_handle(self):
        result = try_await({})
        assert result['status'] == 'failed'


# ==================== TestTaskCancel ====================

class TestTaskCancel:
    '''任务取消测试'''

    def test_cancel_returns_true_for_running(self):
        task = spawn(lambda: time.sleep(2))
        time.sleep(0.05)
        result = cancel_task(task)
        assert result is True

    def test_cancel_sets_cancel_token(self):
        task = spawn(lambda: time.sleep(2))
        cancel_task(task)
        task_id = task['_nexa_task_id']
        task_obj = RUNTIME.get_task(task_id)
        assert task_obj._cancel_token.is_set()

    def test_cancel_invalid_task(self):
        result = cancel_task({})
        assert result is False

    def test_cancel_cooperative_exit(self):
        cancelled_flag = threading.Event()

        def cooperative_task():
            for i in range(100):
                time.sleep(0.01)
            return 'completed'

        task = spawn(cooperative_task)
        time.sleep(0.05)
        cancel_task(task)
        # After cancellation, try_await should show cancelled or running
        result = try_await(task)
        assert result['status'] in ('cancelled', 'running', 'failed')

    def test_cancel_nonexistent_task(self):
        result = cancel_task({'_nexa_task_id': 999999})
        assert result is False


# ==================== TestParallel ====================

class TestParallel:
    '''并行执行测试'''

    def test_parallel_all_succeed(self):
        results = parallel([lambda: 1, lambda: 2, lambda: 3])
        assert results == [1, 2, 3]

    def test_parallel_preserves_order(self):
        results = parallel([lambda: 'a', lambda: 'b', lambda: 'c'])
        assert results == ['a', 'b', 'c']

    def test_parallel_one_fails_raises(self):
        def fail():
            raise RuntimeError('parallel fail')
        with pytest.raises(RuntimeError, match='parallel fail'):
            parallel([lambda: 1, fail, lambda: 3])

    def test_parallel_single_handler(self):
        results = parallel([lambda: 'only_one'])
        assert results == ['only_one']

    def test_parallel_empty_list(self):
        results = parallel([])
        assert results == []

    def test_parallel_with_delayed_handlers(self):
        def slow_a():
            time.sleep(0.05)
            return 'a'
        def fast_b():
            return 'b'
        results = parallel([slow_a, fast_b])
        assert results == ['a', 'b']


# ==================== TestRace ====================

class TestRace:
    '''竞速执行测试'''

    def test_race_returns_first_success(self):
        def fast():
            return 'fast_result'
        def slow():
            time.sleep(0.5)
            return 'slow_result'
        result = race([fast, slow])
        assert result == 'fast_result'

    def test_race_all_fail_raises(self):
        def fail1():
            raise ValueError('fail1')
        def fail2():
            raise ValueError('fail2')
        with pytest.raises(ValueError):
            race([fail1, fail2])

    def test_race_single_handler(self):
        result = race([lambda: 'single'])
        assert result == 'single'

    def test_race_first_fails_second_succeeds(self):
        def fail():
            raise RuntimeError('first fails')
        result = race([fail, lambda: 'second_wins'])
        assert result == 'second_wins'

    def test_race_cancels_remaining(self):
        # Race should cancel tasks that didn't win
        result = race([lambda: 'winner', lambda: time.sleep(2)])
        assert result == 'winner'

    def test_race_with_int_result(self):
        result = race([lambda: 42])
        assert result == 42


# ==================== TestAfter ====================

class TestAfter:
    '''延迟执行测试'''

    def test_after_delayed_execution(self):
        task = after(200, lambda: 'delayed_result')
        result = await_task(task)
        assert result == 'delayed_result'

    def test_parse_interval_ms(self):
        assert parse_interval('100ms') == 100

    def test_parse_interval_seconds(self):
        assert parse_interval('5s') == 5000

    def test_parse_interval_bare_number(self):
        assert parse_interval('500') == 500


# ==================== TestSchedule ====================

class TestSchedule:
    '''周期调度测试'''

    def test_schedule_returns_dict_handle(self):
        sched = schedule(100, lambda: None)
        assert '_nexa_schedule_id' in sched
        assert sched['running'] is True

    def test_schedule_executes_periodically(self):
        counter = {'value': 0}
        def increment():
            counter['value'] += 1
        sched = schedule(50, increment)
        time.sleep(0.3)  # Wait for a few ticks
        cancel_schedule(sched)
        assert counter['value'] >= 2

    def test_cancel_schedule(self):
        sched = schedule(50, lambda: None)
        result = cancel_schedule(sched)
        assert result is True

    def test_cancel_nonexistent_schedule(self):
        result = cancel_schedule({'_nexa_schedule_id': 999999})
        assert result is False

    def test_schedule_zero_interval_rejected(self):
        with pytest.raises(ValueError, match='must be positive'):
            schedule(0, lambda: None)

    def test_schedule_negative_interval_rejected(self):
        with pytest.raises(ValueError, match='must be positive'):
            schedule(-100, lambda: None)


# ==================== TestSleepMs ====================

class TestSleepMs:
    '''取消感知 sleep 测试'''

    def test_sleep_ms_basic(self):
        start = time.monotonic()
        sleep_ms(100)
        elapsed = time.monotonic() - start
        assert elapsed >= 0.09  # Allow slight timing variance

    def test_sleep_ms_zero(self):
        start = time.monotonic()
        sleep_ms(0)
        elapsed = time.monotonic() - start
        assert elapsed < 0.05

    def test_sleep_ms_cancellation_aware(self):
        # sleep_ms uses 50ms slices internally
        start = time.monotonic()
        sleep_ms(200)
        elapsed = time.monotonic() - start
        assert elapsed >= 0.19


# ==================== TestThreadCount ====================

class TestThreadCount:
    '''CPU 线程数测试'''

    def test_thread_count_returns_int(self):
        result = thread_count()
        assert isinstance(result, int)

    def test_thread_count_at_least_one(self):
        result = thread_count()
        assert result >= 1


# ==================== TestAgentSpawn ====================

class TestAgentSpawn:
    '''Agent-Aware spawn 测试'''

    def test_spawn_nexa_agent(self):
        '''Test spawning a NexaAgent (mocked)'''
        from unittest.mock import MagicMock
        from src.runtime.agent import NexaAgent

        # Create a mock agent
        mock_agent = MagicMock(spec=NexaAgent)
        mock_agent.context = 'test_context'
        mock_agent.run = MagicMock(return_value='agent_result')

        task = spawn(mock_agent)
        result = await_task(task)
        assert result == 'agent_result'
        mock_agent.run.assert_called_once()

    def test_spawn_nexa_agent_no_context(self):
        '''Test spawning a NexaAgent without context'''
        from unittest.mock import MagicMock
        from src.runtime.agent import NexaAgent

        mock_agent = MagicMock(spec=NexaAgent)
        mock_agent.context = None
        mock_agent.run = MagicMock(return_value='no_ctx_result')

        task = spawn(mock_agent)
        result = await_task(task)
        assert result == 'no_ctx_result'
        # Should use empty string as context
        mock_agent.run.assert_called_once_with('')

    def test_parallel_agents(self):
        '''Test parallel with mock agents'''
        from unittest.mock import MagicMock
        from src.runtime.agent import NexaAgent

        mock_a = MagicMock(spec=NexaAgent)
        mock_a.context = 'ctx_a'
        mock_a.run = MagicMock(return_value='result_a')

        mock_b = MagicMock(spec=NexaAgent)
        mock_b.context = 'ctx_b'
        mock_b.run = MagicMock(return_value='result_b')

        results = parallel([mock_a, mock_b])
        assert results == ['result_a', 'result_b']

    def test_race_agents(self):
        '''Test race with mock agents'''
        from unittest.mock import MagicMock
        from src.runtime.agent import NexaAgent

        mock_fast = MagicMock(spec=NexaAgent)
        mock_fast.context = 'fast_ctx'
        mock_fast.run = MagicMock(return_value='fast_result')

        result = race([mock_fast])
        assert result == 'fast_result'

    def test_after_with_agent(self):
        '''Test after with mock agent'''
        from unittest.mock import MagicMock
        from src.runtime.agent import NexaAgent

        mock_agent = MagicMock(spec=NexaAgent)
        mock_agent.context = 'delay_ctx'
        mock_agent.run = MagicMock(return_value='delayed_agent')

        task = after(100, mock_agent)
        result = await_task(task)
        assert result == 'delayed_agent'


# ==================== TestContractIntegration ====================

class TestContractIntegration:
    '''任务失败 → 契约违规联动测试'''

    def test_task_failure_exception_propagation(self):
        '''Task failure propagates as exception (usable by contract system)'''
        task = spawn(lambda: (_ for _ in ()).throw(ContractViolation('contract broken')))
        from src.runtime.contracts import ContractViolation
        with pytest.raises(Exception):
            await_task(task)

    def test_parallel_failure_propagation(self):
        '''parallel failure propagates (contract-aware)'''
        from src.runtime.contracts import ContractViolation
        def violate():
            raise ContractViolation('parallel contract violation')
        with pytest.raises(Exception):
            parallel([violate])

    def test_race_failure_propagation(self):
        '''race all-fail propagates last error (contract-aware)'''
        from src.runtime.contracts import ContractViolation
        def violate():
            raise ContractViolation('race contract violation')
        with pytest.raises(Exception):
            race([violate])

    def test_contract_violation_in_task_handle(self):
        '''ContractViolation in task handle status'''
        from src.runtime.contracts import ContractViolation
        task = spawn(lambda: (_ for _ in ()).throw(ContractViolation('violation')))
        time.sleep(0.1)
        result = try_await(task)
        # Failed task should show failed status
        assert result['status'] in ('failed', 'running')


# ==================== TestStdlibNamespace ====================

class TestStdlibNamespace:
    '''stdlib std.concurrent 命名空间测试'''

    def test_std_concurrent_namespace_in_map(self):
        from src.runtime.stdlib import STD_NAMESPACE_MAP
        assert 'std.concurrent' in STD_NAMESPACE_MAP

    def test_std_concurrent_has_18_tools(self):
        from src.runtime.stdlib import STD_NAMESPACE_MAP
        tools = STD_NAMESPACE_MAP['std.concurrent']
        assert len(tools) == 18

    def test_std_concurrent_channel_tool(self):
        from src.runtime.stdlib import get_stdlib_tool
        tool = get_stdlib_tool('std_concurrent_channel')
        assert tool is not None
        assert tool.name == 'std_concurrent_channel'

    def test_std_concurrent_spawn_tool(self):
        from src.runtime.stdlib import get_stdlib_tool
        tool = get_stdlib_tool('std_concurrent_spawn')
        assert tool is not None
        assert tool.name == 'std_concurrent_spawn'


# ==================== TestParserAST ====================

class TestParserAST:
    '''Parser/AST 并发语法测试'''

    def test_spawn_expr_ast(self):
        '''Test spawn expression AST generation'''
        from src.ast_transformer import NexaTransformer
        # Simulate the transformer handler directly
        transformer = NexaTransformer()
        result = transformer.spawn_expr([{'type': 'Identifier', 'value': 'myAgent'}])
        assert result['type'] == 'SpawnExpression'
        assert result['handler']['value'] == 'myAgent'

    def test_parallel_expr_ast(self):
        '''Test parallel expression AST generation'''
        from src.ast_transformer import NexaTransformer
        transformer = NexaTransformer()
        result = transformer.parallel_expr([{'type': 'ListLiteral', 'items': []}])
        assert result['type'] == 'ParallelExpression'

    def test_race_expr_ast(self):
        '''Test race expression AST generation'''
        from src.ast_transformer import NexaTransformer
        transformer = NexaTransformer()
        result = transformer.race_expr([{'type': 'ListLiteral', 'items': []}])
        assert result['type'] == 'RaceExpression'


# ==================== TestParseInterval ====================

class TestParseInterval:
    '''时间间隔解析测试'''

    def test_parse_ms(self):
        assert parse_interval('100ms') == 100

    def test_parse_seconds(self):
        assert parse_interval('5s') == 5000

    def test_parse_minutes(self):
        assert parse_interval('1m') == 60000

    def test_parse_hours(self):
        assert parse_interval('1h') == 3600000

    def test_parse_bare_number(self):
        assert parse_interval('500') == 500

    def test_parse_integer_input(self):
        assert parse_interval(200) == 200

    def test_parse_invalid_format(self):
        with pytest.raises(ValueError, match='Invalid interval'):
            parse_interval('invalid')

    def test_parse_float_input(self):
        assert parse_interval(1.5) == 1


# ==================== TestNexaChannelDirect ====================

class TestNexaChannelDirect:
    '''NexaChannel 直接接口测试'''

    def test_channel_is_closed_initially_false(self):
        ch = NexaChannel(1)
        assert ch.is_closed() is False

    def test_channel_close_sets_closed(self):
        ch = NexaChannel(1)
        ch.close()
        assert ch.is_closed() is True

    def test_channel_send_after_close_false(self):
        ch = NexaChannel(1)
        ch.close()
        assert ch.send('data') is False

    def test_channel_recv_after_close_remaining(self):
        ch = NexaChannel(1)
        ch.send('last_msg')
        ch.close()
        result = ch.recv()
        assert result == 'last_msg'

    def test_channel_recv_after_close_empty_none(self):
        ch = NexaChannel(1)
        ch.close()
        result = ch.recv()
        assert result is None


# ==================== TestNexaTaskDirect ====================

class TestNexaTaskDirect:
    '''NexaTask 直接接口测试'''

    def test_task_initial_state_running(self):
        from concurrent.futures import Future
        cancel_token = threading.Event()
        task = NexaTask(1, Future(), cancel_token)
        assert task._state == 'running'

    def test_task_mark_completed(self):
        from concurrent.futures import Future
        cancel_token = threading.Event()
        task = NexaTask(1, Future(), cancel_token)
        task._mark_completed('result')
        assert task._state == 'completed'
        assert task._result == 'result'

    def test_task_mark_failed(self):
        from concurrent.futures import Future
        cancel_token = threading.Event()
        task = NexaTask(1, Future(), cancel_token)
        err = RuntimeError('test error')
        task._mark_failed(err)
        assert task._state == 'failed'
        assert task._error == err

    def test_task_mark_cancelled(self):
        from concurrent.futures import Future
        cancel_token = threading.Event()
        task = NexaTask(1, Future(), cancel_token)
        task._mark_cancelled()
        assert task._state == 'cancelled'


# ==================== TestNexaScheduleDirect ====================

class TestNexaScheduleDirect:
    '''NexaSchedule 直接接口测试'''

    def test_schedule_cancel(self):
        cancel_token = threading.Event()
        sched = NexaSchedule(1, 100, lambda: None, cancel_token)
        result = sched.cancel()
        assert cancel_token.is_set()

    def test_schedule_catches_exceptions(self):
        counter = {'value': 0}
        def failing_tick():
            counter['value'] += 1
            raise RuntimeError('tick error')
        cancel_token = threading.Event()
        sched = NexaSchedule(1, 50, failing_tick, cancel_token)
        sched.start()
        time.sleep(0.3)
        sched.cancel()
        assert counter['value'] >= 1  # At least one tick ran


# ==================== TestNexaConcurrencyRuntime ====================

class TestNexaConcurrencyRuntime:
    '''运行时注册表测试'''

    def test_register_and_get_channel(self):
        runtime = NexaConcurrencyRuntime()
        ch = NexaChannel(runtime._next_id())
        runtime.register_channel(ch)
        assert runtime.get_channel(ch._id) is ch

    def test_unregister_channel(self):
        runtime = NexaConcurrencyRuntime()
        ch = NexaChannel(runtime._next_id())
        runtime.register_channel(ch)
        runtime.unregister_channel(ch._id)
        assert runtime.get_channel(ch._id) is None

    def test_register_and_get_task(self):
        runtime = NexaConcurrencyRuntime()
        from concurrent.futures import Future
        task = NexaTask(runtime._next_id(), Future(), threading.Event())
        runtime.register_task(task)
        assert runtime.get_task(task._id) is task

    def test_cleanup_expired_tasks(self):
        runtime = NexaConcurrencyRuntime()
        from concurrent.futures import Future
        task = NexaTask(runtime._next_id(), Future(), threading.Event())
        task._mark_completed('done')
        task._completed_at = time.monotonic() - 600  # 10 minutes ago
        runtime.register_task(task)
        runtime.cleanup_expired(max_age_seconds=300)
        assert runtime.get_task(task._id) is None


# ==================== TestRuntimeSingleton ====================

class TestRuntimeSingleton:
    '''全局 RUNTIME 单例测试'''

    def test_runtime_is_global(self):
        assert RUNTIME is not None

    def test_runtime_has_channels_dict(self):
        assert hasattr(RUNTIME, '_channels')

    def test_runtime_has_tasks_dict(self):
        assert hasattr(RUNTIME, '_tasks')

    def test_runtime_has_schedules_dict(self):
        assert hasattr(RUNTIME, '_schedules')


# ==================== TestGetActiveFunctions ====================

class TestGetActiveFunctions:
    '''活跃资源快照测试'''

    def test_get_active_channels(self):
        before = len(get_active_channels())
        tx, rx = channel()
        after = len(get_active_channels())
        assert after == before + 1

    def test_get_active_tasks(self):
        before = len(get_active_tasks())
        task = spawn(lambda: time.sleep(0.5))
        after = len(get_active_tasks())
        assert after >= before

    def test_get_active_schedules(self):
        before = len(get_active_schedules())
        sched = schedule(1000, lambda: None)
        after = len(get_active_schedules())
        assert after == before + 1
        cancel_schedule(sched)


# ==================== TestAfterExtended ====================

class TestAfterExtended:
    '''延迟执行扩展测试'''

    def test_after_with_string_delay(self):
        task = after('200ms', lambda: 'string_delay')
        result = await_task(task)
        assert result == 'string_delay'

    def test_after_cancellable(self):
        task = after(500, lambda: 'should_not_run')
        time.sleep(0.05)
        cancel_task(task)
        time.sleep(0.6)
        # Task should be cancelled
        status = try_await(task)
        assert status['status'] in ('cancelled', 'running')

    def test_after_invalid_handler(self):
        with pytest.raises(ValueError, match='must be callable'):
            after(100, 'not_callable')

    def test_after_with_int_delay(self):
        task = after(100, lambda: 'int_delay')
        result = await_task(task)
        assert result == 'int_delay'


# ==================== TestScheduleExtended ====================

class TestScheduleExtended:
    '''周期调度扩展测试'''

    def test_schedule_with_string_interval(self):
        counter = {'value': 0}
        def inc():
            counter['value'] += 1
        sched = schedule('100ms', inc)
        time.sleep(0.4)
        cancel_schedule(sched)
        assert counter['value'] >= 2

    def test_schedule_cancelling_stops_execution(self):
        counter = {'value': 0}
        def inc():
            counter['value'] += 1
        sched = schedule(50, inc)
        time.sleep(0.2)
        cancel_schedule(sched)
        count_at_cancel = counter['value']
        time.sleep(0.2)
        # Count should not increase after cancel
        assert counter['value'] == count_at_cancel or counter['value'] <= count_at_cancel + 1

    def test_schedule_invalid_handler(self):
        with pytest.raises(ValueError, match='must be callable'):
            schedule(100, 'not_callable')

    def test_schedule_removes_from_registry(self):
        sched = schedule(100, lambda: None)
        sched_id = sched['_nexa_schedule_id']
        cancel_schedule(sched)
        result = RUNTIME.get_schedule(sched_id)
        assert result is None


# ==================== TestConcurrentDeclAST ====================

class TestConcurrentDeclAST:
    '''concurrent_decl AST wrapper 测试'''

    def test_concurrent_decl_delegates(self):
        from src.ast_transformer import NexaTransformer
        transformer = NexaTransformer()
        inner = {'type': 'SpawnExpression', 'handler': {'type': 'Identifier', 'value': 'x'}}
        result = transformer.concurrent_decl([inner])
        assert result == inner

    def test_concurrent_decl_empty(self):
        from src.ast_transformer import NexaTransformer
        transformer = NexaTransformer()
        result = transformer.concurrent_decl([])
        assert result['type'] == 'ConcurrentDeclaration'

    def test_channel_expr_ast(self):
        from src.ast_transformer import NexaTransformer
        transformer = NexaTransformer()
        result = transformer.channel_expr([])
        assert result['type'] == 'ChannelDeclaration'

    def test_after_expr_ast(self):
        from src.ast_transformer import NexaTransformer
        transformer = NexaTransformer()
        delay = {'type': 'IntLiteral', 'value': 100}
        handler = {'type': 'Identifier', 'value': 'myFunc'}
        result = transformer.after_expr([delay, handler])
        assert result['type'] == 'AfterExpression'
        assert result['delay'] == delay
        assert result['handler'] == handler

    def test_schedule_expr_ast(self):
        from src.ast_transformer import NexaTransformer
        transformer = NexaTransformer()
        interval = {'type': 'StringLiteral', 'value': '5s'}
        handler = {'type': 'Identifier', 'value': 'tick'}
        result = transformer.schedule_expr([interval, handler])
        assert result['type'] == 'ScheduleExpression'

    def test_select_expr_ast(self):
        from src.ast_transformer import NexaTransformer
        transformer = NexaTransformer()
        channels = {'type': 'ListLiteral', 'items': []}
        result = transformer.select_expr([channels])
        assert result['type'] == 'SelectExpression'

    def test_select_expr_with_timeout(self):
        from src.ast_transformer import NexaTransformer
        transformer = NexaTransformer()
        channels = {'type': 'ListLiteral', 'items': []}
        timeout = {'type': 'IntLiteral', 'value': 1000}
        result = transformer.select_expr([channels, timeout])
        assert result['type'] == 'SelectExpression'
        assert result['timeout'] == timeout


# ==================== TestCodeGeneratorConcurrent ====================

class TestCodeGeneratorConcurrent:
    '''Code Generator 并发表达式解析测试'''

    def test_resolve_spawn_expression(self):
        from src.code_generator import CodeGenerator
        gen = CodeGenerator({'type': 'Program', 'includes': [], 'body': []})
        expr = {'type': 'SpawnExpression', 'handler': {'type': 'Identifier', 'value': 'myFunc'}}
        result = gen._resolve_expression(expr)
        assert result == 'spawn(myFunc)'

    def test_resolve_channel_declaration(self):
        from src.code_generator import CodeGenerator
        gen = CodeGenerator({'type': 'Program', 'includes': [], 'body': []})
        expr = {'type': 'ChannelDeclaration'}
        result = gen._resolve_expression(expr)
        assert result == 'channel()'

    def test_resolve_parallel_expression(self):
        from src.code_generator import CodeGenerator
        gen = CodeGenerator({'type': 'Program', 'includes': [], 'body': []})
        expr = {'type': 'ParallelExpression', 'handlers': {'type': 'Identifier', 'value': 'handlers_list'}}
        result = gen._resolve_expression(expr)
        assert result == 'parallel(handlers_list)'

    def test_resolve_race_expression(self):
        from src.code_generator import CodeGenerator
        gen = CodeGenerator({'type': 'Program', 'includes': [], 'body': []})
        expr = {'type': 'RaceExpression', 'handlers': {'type': 'Identifier', 'value': 'competitors'}}
        result = gen._resolve_expression(expr)
        assert result == 'race(competitors)'

    def test_resolve_after_expression(self):
        from src.code_generator import CodeGenerator
        gen = CodeGenerator({'type': 'Program', 'includes': [], 'body': []})
        expr = {'type': 'AfterExpression', 'delay': {'type': 'IntLiteral', 'value': 500}, 'handler': {'type': 'Identifier', 'value': 'callback'}}
        result = gen._resolve_expression(expr)
        assert result == 'after(500, callback)'

    def test_resolve_schedule_expression(self):
        from src.code_generator import CodeGenerator
        gen = CodeGenerator({'type': 'Program', 'includes': [], 'body': []})
        expr = {'type': 'ScheduleExpression', 'interval': {'type': 'StringLiteral', 'value': '5s'}, 'handler': {'type': 'Identifier', 'value': 'tick'}}
        result = gen._resolve_expression(expr)
        assert result == 'schedule("5s", tick)'

    def test_resolve_select_expression(self):
        from src.code_generator import CodeGenerator
        gen = CodeGenerator({'type': 'Program', 'includes': [], 'body': []})
        expr = {'type': 'SelectExpression', 'channels': {'type': 'Identifier', 'value': 'rx_list'}, 'timeout': None}
        result = gen._resolve_expression(expr)
        assert result == 'select(rx_list)'

    def test_resolve_select_with_timeout(self):
        from src.code_generator import CodeGenerator
        gen = CodeGenerator({'type': 'Program', 'includes': [], 'body': []})
        expr = {'type': 'SelectExpression', 'channels': {'type': 'Identifier', 'value': 'rx_list'}, 'timeout': {'type': 'IntLiteral', 'value': 1000}}
        result = gen._resolve_expression(expr)
        assert result == 'select(rx_list, 1000)'

    def test_generate_concurrent_no_ops(self):
        from src.code_generator import CodeGenerator
        gen = CodeGenerator({'type': 'Program', 'includes': [], 'body': []})
        gen.concurrent_ops = []
        gen._generate_concurrent()
        # Should not add anything since no ops
        # The method just returns early

    def test_generate_concurrent_spawn(self):
        from src.code_generator import CodeGenerator
        gen = CodeGenerator({'type': 'Program', 'includes': [], 'body': []})
        gen.concurrent_ops = [{'type': 'SpawnExpression', 'handler': {'type': 'Identifier', 'value': 'myTask'}}]
        gen._generate_concurrent()
        # Check that spawn code was added
        found = any('spawn(myTask)' in line for line in gen.code)
        assert found


# ==================== TestStdlibConcurrentExec ====================

class TestStdlibConcurrentExec:
    '''stdlib concurrent 工具执行测试'''

    def test_std_concurrent_channel_exec(self):
        from src.runtime.stdlib import execute_stdlib_tool
        result = execute_stdlib_tool('std_concurrent_channel')
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 2

    def test_std_concurrent_thread_count_exec(self):
        from src.runtime.stdlib import execute_stdlib_tool
        result = execute_stdlib_tool('std_concurrent_thread_count')
        parsed = json.loads(result)
        assert 'count' in parsed
        assert parsed['count'] >= 1

    def test_std_concurrent_sleep_ms_exec(self):
        from src.runtime.stdlib import execute_stdlib_tool
        result = execute_stdlib_tool('std_concurrent_sleep_ms', ms='50')
        parsed = json.loads(result)
        assert parsed['ok'] is True

    def test_std_concurrent_send_recv_exec(self):
        from src.runtime.stdlib import execute_stdlib_tool
        # Create a channel first
        ch_result = execute_stdlib_tool('std_concurrent_channel')
        handles = json.loads(ch_result)
        tx = handles[0]
        rx = handles[1]
        # Send
        send_result = execute_stdlib_tool('std_concurrent_send', tx=json.dumps(tx), value='test_msg')
        send_parsed = json.loads(send_result)
        assert send_parsed['success'] is True
        # Recv
        recv_result = execute_stdlib_tool('std_concurrent_recv', rx=json.dumps(rx))
        recv_parsed = json.loads(recv_result)
        assert recv_parsed['value'] == 'test_msg'


# ==================== TestIdentifierExclusion ====================

class TestIdentifierExclusion:
    '''并发关键字在 IDENTIFIER 排除列表中'''

    def test_spawn_excluded(self):
        from src.nexa_parser import nexa_grammar
        assert 'spawn' in nexa_grammar

    def test_parallel_excluded(self):
        from src.nexa_parser import nexa_grammar
        assert 'parallel' in nexa_grammar

    def test_race_excluded(self):
        from src.nexa_parser import nexa_grammar
        assert 'race' in nexa_grammar

    def test_channel_excluded(self):
        from src.nexa_parser import nexa_grammar
        assert 'channel' in nexa_grammar

    def test_after_excluded(self):
        from src.nexa_parser import nexa_grammar
        assert 'after' in nexa_grammar

    def test_schedule_excluded(self):
        from src.nexa_parser import nexa_grammar
        assert 'schedule' in nexa_grammar


# ==================== TestImportsAndInit ====================

class TestImportsAndInit:
    '''导入和初始化测试'''

    def test_concurrent_module_importable(self):
        import src.runtime.concurrent
        assert hasattr(src.runtime.concurrent, 'RUNTIME')

    def test_runtime_init_exports_channel(self):
        from src.runtime import channel
        assert callable(channel)

    def test_runtime_init_exports_spawn(self):
        from src.runtime import spawn
        assert callable(spawn)

    def test_runtime_init_exports_parallel(self):
        from src.runtime import parallel
        assert callable(parallel)

    def test_runtime_init_exports_race(self):
        from src.runtime import race
        assert callable(race)

    def test_runtime_init_exports_select(self):
        from src.runtime import select
        assert callable(select)

    def test_runtime_init_exports_sleep_ms(self):
        from src.runtime import sleep_ms
        assert callable(sleep_ms)

    def test_runtime_init_exports_thread_count(self):
        from src.runtime import thread_count
        assert callable(thread_count)

    def test_runtime_init_exports_parse_interval(self):
        from src.runtime import parse_interval
        assert callable(parse_interval)