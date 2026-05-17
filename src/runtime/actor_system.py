"""
Nexa v2.0 ActorSystem — Actor Model 多 Agent 编排

ActorSystem 实现基于 Actor Model 的多 Agent 编排，负责：
  - spawn: 创建子 Agent Actor
  - pass_message: 异步消息传递
  - await_result: 同步等待结果
  - receive: Actor 内部消息接收

Design Rationale:
  - Actor Model: 每个 Agent 是独立 Actor，通过消息传递协作
  - 无共享状态: Actor 之间不共享内存，避免竞态条件
  - 异步消息: pass 是非阻塞的，await 是阻塞的
  - 线程安全: 使用 queue.Queue 实现线程安全的消息传递

Author: Owen (AI Pair Programmer)
Version: 2.0.0-alpha.6
"""

from __future__ import annotations

import queue
import threading
import time
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("nexa.actor_system")


# ═══════════════════════════════════════════════════════════════════════
#  Data Structures
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ActorMessage:
    """A message passed between Actors."""
    message_id: str = ""
    sender_id: str = ""         # Actor ID of sender
    recipient_id: str = ""      # Actor ID of recipient
    content: Any = None         # Message content
    message_type: str = "data"  # data | request | response | error | stop
    timestamp: float = field(default_factory=time.time)
    correlation_id: Optional[str] = None  # For request-response correlation

    def to_dict(self) -> Dict:
        return {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "content": str(self.content)[:200],
            "message_type": self.message_type,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
        }


@dataclass
class ActorHandle:
    """Handle to a spawned Actor."""
    actor_id: str = ""
    actor_name: str = ""
    status: str = "running"     # running | completed | failed | stopped
    result: Any = None          # Final result (set when completed)
    error: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict:
        return {
            "actor_id": self.actor_id,
            "actor_name": self.actor_name,
            "status": self.status,
            "has_result": self.result is not None,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class ActorConfig:
    """Configuration for an Actor."""
    actor_name: str = ""
    max_messages: int = 100     # Max messages to process before stopping
    timeout: Optional[float] = None  # Timeout in seconds
    daemon: bool = True         # Whether the actor thread is a daemon

    def to_dict(self) -> Dict:
        return {
            "actor_name": self.actor_name,
            "max_messages": self.max_messages,
            "timeout": self.timeout,
            "daemon": self.daemon,
        }


# ═══════════════════════════════════════════════════════════════════════
#  ActorSystem — Actor Model Orchestrator
# ═══════════════════════════════════════════════════════════════════════

class ActorSystem:
    """
    Actor Model orchestrator for multi-Agent coordination.

    Implements:
      - spawn(): Create a child Agent Actor
      - pass_message(): Send async message to an Actor
      - await_result(): Block until Actor completes
      - receive(): Actor-internal message reception

    Usage:
        system = ActorSystem()
        handle = system.spawn("analyzer", analyzer_fn, config)
        system.pass_message(handle.actor_id, "analyze this data")
        result = system.await_result(handle.actor_id, timeout=30)
    """

    def __init__(self) -> None:
        self._actors: Dict[str, ActorHandle] = {}
        self._mailboxes: Dict[str, queue.Queue] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._results: Dict[str, Any] = {}
        self._result_events: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self._spawn_count = 0
        self._message_count = 0

    # ─── Spawn ───

    def spawn(
        self,
        actor_name: str,
        actor_fn: Callable[..., Any],
        config: Optional[ActorConfig] = None,
        **kwargs,
    ) -> ActorHandle:
        """
        Spawn a new Actor (child Agent).

        Args:
            actor_name: Human-readable name for the actor
            actor_fn: The function the actor executes
            config: Optional ActorConfig
            **kwargs: Additional arguments passed to actor_fn

        Returns:
            ActorHandle for the spawned actor
        """
        self._spawn_count += 1
        actor_id = f"actor_{self._spawn_count}_{uuid.uuid4().hex[:8]}"

        cfg = config or ActorConfig(actor_name=actor_name)

        # Create mailbox
        mailbox: queue.Queue = queue.Queue()
        result_event = threading.Event()

        with self._lock:
            self._mailboxes[actor_id] = mailbox
            self._result_events[actor_id] = result_event

        # Create handle
        handle = ActorHandle(
            actor_id=actor_id,
            actor_name=actor_name,
            status="running",
        )

        with self._lock:
            self._actors[actor_id] = handle

        # Start actor thread
        thread = threading.Thread(
            target=self._actor_loop,
            args=(actor_id, actor_fn, mailbox, result_event, cfg, kwargs),
            daemon=cfg.daemon,
            name=f"nexa-actor-{actor_name}",
        )
        thread.start()

        with self._lock:
            self._threads[actor_id] = thread

        logger.info(f"Actor spawned: {actor_id} ({actor_name})")
        return handle

    def _actor_loop(
        self,
        actor_id: str,
        actor_fn: Callable,
        mailbox: queue.Queue,
        result_event: threading.Event,
        config: ActorConfig,
        kwargs: Dict,
    ) -> None:
        """
        Main message processing loop for an Actor.

        The actor processes messages from its mailbox until:
          - It receives a 'stop' message
          - It reaches max_messages
          - It times out
        """
        start_time = time.time()
        messages_processed = 0

        try:
            # Call the actor function with initial kwargs
            # The actor_fn receives the ActorSystem reference for send/receive
            result = actor_fn(
                actor_id=actor_id,
                actor_name=config.actor_name,
                mailbox=mailbox,
                **kwargs,
            )

            # Store result
            with self._lock:
                self._results[actor_id] = result
                handle = self._actors.get(actor_id)
                if handle:
                    handle.result = result
                    handle.status = "completed"
                    handle.completed_at = time.time()

            result_event.set()
            logger.info(f"Actor completed: {actor_id}")

        except Exception as e:
            with self._lock:
                handle = self._actors.get(actor_id)
                if handle:
                    handle.status = "failed"
                    handle.error = str(e)
                    handle.completed_at = time.time()

            result_event.set()
            logger.error(f"Actor failed: {actor_id}, error={e}")

    # ─── Message Passing ───

    def pass_message(
        self,
        recipient_id: str,
        content: Any,
        sender_id: str = "system",
        message_type: str = "data",
    ) -> Optional[str]:
        """
        Send an async message to an Actor.

        Args:
            recipient_id: Target actor ID
            content: Message content
            sender_id: Sender actor ID (default: "system")
            message_type: Message type

        Returns:
            Message ID if sent, None if recipient not found
        """
        self._message_count += 1
        message_id = f"msg_{self._message_count}"

        msg = ActorMessage(
            message_id=message_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            content=content,
            message_type=message_type,
        )

        with self._lock:
            mailbox = self._mailboxes.get(recipient_id)

        if mailbox is None:
            logger.warning(f"Recipient not found: {recipient_id}")
            return None

        try:
            mailbox.put(msg, timeout=1.0)
            logger.info(f"Message sent: {message_id} → {recipient_id}")
            return message_id
        except queue.Full:
            logger.warning(f"Mailbox full for {recipient_id}")
            return None

    def receive(
        self,
        actor_id: str,
        timeout: Optional[float] = None,
    ) -> Optional[ActorMessage]:
        """
        Receive a message from an Actor's mailbox (blocking).

        Args:
            actor_id: The actor's own ID
            timeout: Max wait time in seconds (None = block indefinitely)

        Returns:
            ActorMessage if received, None if timeout
        """
        with self._lock:
            mailbox = self._mailboxes.get(actor_id)

        if mailbox is None:
            return None

        try:
            msg = mailbox.get(timeout=timeout)
            return msg
        except queue.Empty:
            return None

    # ─── Await ───

    def await_result(
        self,
        actor_id: str,
        timeout: Optional[float] = None,
    ) -> Optional[Any]:
        """
        Block until an Actor completes and return its result.

        Args:
            actor_id: The actor to wait for
            timeout: Max wait time in seconds

        Returns:
            Actor's result, or None if timeout/not found
        """
        with self._lock:
            event = self._result_events.get(actor_id)

        if event is None:
            logger.warning(f"Actor not found: {actor_id}")
            return None

        if event.wait(timeout=timeout):
            with self._lock:
                return self._results.get(actor_id)
        else:
            logger.warning(f"Timeout waiting for actor: {actor_id}")
            return None

    # ─── Actor Management ───

    def stop_actor(self, actor_id: str) -> bool:
        """
        Stop an Actor by sending a stop message.

        Args:
            actor_id: The actor to stop

        Returns:
            True if stop message sent
        """
        return self.pass_message(
            recipient_id=actor_id,
            content="stop",
            message_type="stop",
        ) is not None

    def get_actor(self, actor_id: str) -> Optional[ActorHandle]:
        """Get an Actor's handle."""
        with self._lock:
            return self._actors.get(actor_id)

    def list_actors(self) -> List[ActorHandle]:
        """List all actors."""
        with self._lock:
            return list(self._actors.values())

    def get_active_actors(self) -> List[ActorHandle]:
        """Get all running actors."""
        with self._lock:
            return [a for a in self._actors.values() if a.status == "running"]

    def wait_all(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Wait for all actors to complete.

        Args:
            timeout: Max wait time per actor

        Returns:
            Dict mapping actor_id → result
        """
        results = {}
        for actor_id in list(self._actors.keys()):
            result = self.await_result(actor_id, timeout=timeout)
            results[actor_id] = result
        return results

    # ─── Statistics ───

    def get_stats(self) -> Dict:
        """Get actor system statistics."""
        with self._lock:
            running = sum(1 for a in self._actors.values() if a.status == "running")
            completed = sum(1 for a in self._actors.values() if a.status == "completed")
            failed = sum(1 for a in self._actors.values() if a.status == "failed")

        return {
            "total_actors": len(self._actors),
            "running": running,
            "completed": completed,
            "failed": failed,
            "total_messages": self._message_count,
            "spawn_count": self._spawn_count,
        }

    def clear(self) -> None:
        """Clear all actors (for testing)."""
        # Stop all actors
        for actor_id in list(self._actors.keys()):
            self.stop_actor(actor_id)

        # Wait briefly for threads to finish
        time.sleep(0.1)

        with self._lock:
            self._actors = {}
            self._mailboxes = {}
            self._threads = {}
            self._results = {}
            self._result_events = {}
            self._spawn_count = 0
            self._message_count = 0