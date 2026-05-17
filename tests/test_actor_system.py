"""
Nexa v2.0 M5 Tests — ActorSystem

Tests cover:
  - ActorSystem: spawn, pass_message, await_result, receive
  - ActorHandle, ActorMessage, ActorConfig data structures
  - Integration: multi-actor coordination

Author: Owen (AI Pair Programmer)
Version: 2.0.0-alpha.6
"""

import time
import pytest

from src.runtime.actor_system import (
    ActorSystem, ActorHandle, ActorMessage, ActorConfig,
)


# ═══════════════════════════════════════════════════════════════════════
#  Data Structure Tests
# ═══════════════════════════════════════════════════════════════════════

class TestDataStructures:
    """Actor data structure tests."""

    def test_actor_message_to_dict(self):
        msg = ActorMessage(
            message_id="msg_1",
            sender_id="actor_a",
            recipient_id="actor_b",
            content="hello",
            message_type="data",
        )
        d = msg.to_dict()
        assert d["message_id"] == "msg_1"
        assert d["sender_id"] == "actor_a"

    def test_actor_handle_to_dict(self):
        handle = ActorHandle(actor_id="actor_1", actor_name="test", status="running")
        d = handle.to_dict()
        assert d["actor_id"] == "actor_1"
        assert d["status"] == "running"

    def test_actor_config_to_dict(self):
        config = ActorConfig(actor_name="test", max_messages=50, timeout=30.0)
        d = config.to_dict()
        assert d["actor_name"] == "test"
        assert d["max_messages"] == 50


# ═══════════════════════════════════════════════════════════════════════
#  ActorSystem Tests
# ═══════════════════════════════════════════════════════════════════════

class TestActorSystem:
    """ActorSystem spawn/pass/await tests."""

    def test_spawn_actor(self):
        """Spawn a simple actor."""
        system = ActorSystem()

        def simple_actor(actor_id, actor_name, mailbox, **kwargs):
            time.sleep(0.05)  # Small delay so we can check running status
            return f"done: {actor_name}"

        handle = system.spawn("test_actor", simple_actor)
        assert handle.actor_name == "test_actor"
        assert handle.status == "running"

        # Wait for completion
        result = system.await_result(handle.actor_id, timeout=5)
        assert result == "done: test_actor"

    def test_spawn_multiple_actors(self):
        """Spawn multiple actors concurrently."""
        system = ActorSystem()

        def worker(actor_id, actor_name, mailbox, **kwargs):
            time.sleep(0.1)
            return f"result from {actor_name}"

        handles = []
        for i in range(3):
            h = system.spawn(f"worker_{i}", worker)
            handles.append(h)

        results = system.wait_all(timeout=5)
        assert len(results) == 3
        for h in handles:
            assert h.actor_id in results

    def test_pass_and_receive_message(self):
        """Pass a message and receive it in the actor."""
        system = ActorSystem()
        received_messages = []

        def receiver(actor_id, actor_name, mailbox, **kwargs):
            # Receive one message
            msg = system.receive(actor_id, timeout=5)
            if msg:
                received_messages.append(msg.content)
            return "done"

        handle = system.spawn("receiver", receiver)
        time.sleep(0.05)  # Let actor start

        system.pass_message(handle.actor_id, "hello world")
        result = system.await_result(handle.actor_id, timeout=5)

        assert result == "done"
        assert len(received_messages) == 1
        assert received_messages[0] == "hello world"

    def test_pass_multiple_messages(self):
        """Pass multiple messages to an actor."""
        system = ActorSystem()
        received = []

        def receiver(actor_id, actor_name, mailbox, **kwargs):
            for _ in range(3):
                msg = system.receive(actor_id, timeout=5)
                if msg:
                    received.append(msg.content)
            return "done"

        handle = system.spawn("receiver", receiver)
        time.sleep(0.05)

        system.pass_message(handle.actor_id, "msg1")
        system.pass_message(handle.actor_id, "msg2")
        system.pass_message(handle.actor_id, "msg3")

        result = system.await_result(handle.actor_id, timeout=5)
        assert result == "done"
        assert received == ["msg1", "msg2", "msg3"]

    def test_await_result_timeout(self):
        """Await with timeout returns None."""
        system = ActorSystem()

        def slow_actor(actor_id, actor_name, mailbox, **kwargs):
            time.sleep(10)  # Very slow
            return "done"

        handle = system.spawn("slow", slow_actor)
        result = system.await_result(handle.actor_id, timeout=0.1)
        assert result is None

    def test_stop_actor(self):
        """Stop an actor by sending stop message."""
        system = ActorSystem()
        stopped = []

        def stoppable(actor_id, actor_name, mailbox, **kwargs):
            while True:
                msg = system.receive(actor_id, timeout=1)
                if msg and msg.message_type == "stop":
                    stopped.append(True)
                    return "stopped"

        handle = system.spawn("stoppable", stoppable)
        time.sleep(0.05)

        system.stop_actor(handle.actor_id)
        result = system.await_result(handle.actor_id, timeout=5)
        assert result == "stopped"
        assert len(stopped) == 1

    def test_actor_error_handling(self):
        """Actor failure is captured in handle."""
        system = ActorSystem()

        def failing_actor(actor_id, actor_name, mailbox, **kwargs):
            raise RuntimeError("actor failed")

        handle = system.spawn("failing", failing_actor)
        result = system.await_result(handle.actor_id, timeout=5)

        assert result is None
        # Re-fetch handle to get updated status
        handle = system.get_actor(handle.actor_id)
        assert handle.status == "failed"
        assert "actor failed" in handle.error

    def test_get_actor(self):
        """Get actor handle by ID."""
        system = ActorSystem()

        def simple(actor_id, actor_name, mailbox, **kwargs):
            return "done"

        handle = system.spawn("simple", simple)
        fetched = system.get_actor(handle.actor_id)
        assert fetched.actor_name == "simple"

    def test_list_actors(self):
        """List all actors."""
        system = ActorSystem()

        def simple(actor_id, actor_name, mailbox, **kwargs):
            return "done"

        system.spawn("a", simple)
        system.spawn("b", simple)

        actors = system.list_actors()
        assert len(actors) == 2

    def test_get_active_actors(self):
        """Get only running actors."""
        system = ActorSystem()

        def slow(actor_id, actor_name, mailbox, **kwargs):
            time.sleep(0.5)
            return "done"

        def fast(actor_id, actor_name, mailbox, **kwargs):
            return "done"

        system.spawn("slow", slow)
        fast_handle = system.spawn("fast", fast)
        system.await_result(fast_handle.actor_id, timeout=5)

        active = system.get_active_actors()
        assert len(active) >= 1  # slow is still running

    def test_stats(self):
        """Actor system stats are accurate."""
        system = ActorSystem()

        def simple(actor_id, actor_name, mailbox, **kwargs):
            return "done"

        h1 = system.spawn("a", simple)
        h2 = system.spawn("b", simple)
        system.await_result(h1.actor_id, timeout=5)
        system.await_result(h2.actor_id, timeout=5)

        stats = system.get_stats()
        assert stats["total_actors"] == 2
        assert stats["completed"] == 2

    def test_clear(self):
        """Clear removes all actors."""
        system = ActorSystem()

        def simple(actor_id, actor_name, mailbox, **kwargs):
            return "done"

        system.spawn("a", simple)
        system.clear()
        assert system.get_stats()["total_actors"] == 0


# ═══════════════════════════════════════════════════════════════════════
#  Integration Tests
# ═══════════════════════════════════════════════════════════════════════

class TestIntegration:
    """End-to-end: multi-actor coordination."""

    def test_pipeline_pattern(self):
        """Pipeline: actor_a → actor_b → actor_c."""
        system = ActorSystem()
        pipeline_results = []

        def stage_a(actor_id, actor_name, mailbox, **kwargs):
            result = "data_from_a"
            system.pass_message(kwargs["next_actor"], result, sender_id=actor_id)
            return result

        def stage_b(actor_id, actor_name, mailbox, **kwargs):
            msg = system.receive(actor_id, timeout=5)
            processed = f"processed_{msg.content}"
            system.pass_message(kwargs["next_actor"], processed, sender_id=actor_id)
            return processed

        def stage_c(actor_id, actor_name, mailbox, **kwargs):
            msg = system.receive(actor_id, timeout=5)
            pipeline_results.append(msg.content)
            return f"final: {msg.content}"

        # Spawn in reverse order so next_actor IDs are available
        h_c = system.spawn("stage_c", stage_c)
        h_b = system.spawn("stage_b", stage_b, next_actor=h_c.actor_id)
        h_a = system.spawn("stage_a", stage_a, next_actor=h_b.actor_id)

        results = system.wait_all(timeout=5)
        assert len(pipeline_results) == 1
        assert "processed_data_from_a" in pipeline_results[0]

    def test_fan_out_pattern(self):
        """Fan-out: one actor sends to multiple workers."""
        system = ActorSystem()
        worker_results = []

        def worker(actor_id, actor_name, mailbox, **kwargs):
            msg = system.receive(actor_id, timeout=5)
            if msg:
                worker_results.append(f"{actor_name}:{msg.content}")
            return "done"

        def dispatcher(actor_id, actor_name, mailbox, **kwargs):
            workers = kwargs["workers"]
            for w_id in workers:
                system.pass_message(w_id, f"task_for_{w_id}", sender_id=actor_id)
            return "dispatched"

        # Spawn workers first
        w1 = system.spawn("worker_1", worker)
        w2 = system.spawn("worker_2", worker)
        w3 = system.spawn("worker_3", worker)

        # Spawn dispatcher with worker IDs
        d = system.spawn("dispatcher", dispatcher,
                         workers=[w1.actor_id, w2.actor_id, w3.actor_id])

        system.wait_all(timeout=5)
        assert len(worker_results) == 3

    def test_request_response_pattern(self):
        """Request-response between two actors."""
        system = ActorSystem()

        def server(actor_id, actor_name, mailbox, **kwargs):
            msg = system.receive(actor_id, timeout=5)
            if msg:
                # Send response back
                system.pass_message(
                    msg.sender_id,
                    f"response_to:{msg.content}",
                    sender_id=actor_id,
                )
            return "done"

        def client(actor_id, actor_name, mailbox, **kwargs):
            server_id = kwargs["server_id"]
            system.pass_message(server_id, "ping", sender_id=actor_id)
            response = system.receive(actor_id, timeout=5)
            return response.content if response else "no_response"

        s = system.spawn("server", server)
        time.sleep(0.05)
        c = system.spawn("client", client, server_id=s.actor_id)

        result = system.await_result(c.actor_id, timeout=5)
        assert result == "response_to:ping"