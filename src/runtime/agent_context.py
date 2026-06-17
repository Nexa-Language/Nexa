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
"""Nexa v2.2.1: AgentContext — Context-as-Structure runtime support.

This module implements the runtime data structures for the v2.2.1
Context-as-Structure feature. An ``AgentContext`` is the complete worldview
handed between two agents in a pipeline. ``ContextSpec`` is the parsed
declaration from the ``context { ... }`` block in the agent definition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ContextSpec:
    """Parsed ``context { ... }`` declaration — structural context properties.

    This is attached to a ``NexaAgent`` at construction time (like ``tools``
    and ``model``), so an agent's context behaviour is fully defined by its
    declaration, not by ad-hoc runtime parameters.
    """

    source: str = "upstream"               # "upstream" | "shared:name" | "fresh"
    sink: str = "downstream"               # "downstream" | "shared:name" | "discard"
    input_schema: Optional[str] = None     # Protocol name that upstream must satisfy
    output_schema: Optional[str] = None   # Protocol name this agent produces
    max_history_turns: Optional[int] = None
    inherit: List[str] = field(default_factory=list)  # ["messages", "artifacts", ...]

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> Optional["ContextSpec"]:
        """Build a ContextSpec from the AST ContextDecl dict, or None if absent."""
        if d is None:
            return None
        return cls(
            source=str(d.get("source", "upstream")),
            sink=str(d.get("sink", "downstream")),
            input_schema=d.get("input_schema"),
            output_schema=d.get("output_schema"),
            max_history_turns=d.get("max_history_turns"),
            inherit=list(d.get("inherit", []) or []),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "sink": self.sink,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "max_history_turns": self.max_history_turns,
            "inherit": list(self.inherit),
        }


@dataclass
class AgentContext:
    """The complete worldview handed between two agents.

    An ``AgentContext`` is produced by an agent at the end of its ``run`` and
    can be consumed by the next agent in a pipeline. It is **not** just the
    final string output — it carries the agent's full conversation history,
    tool call results, and structured artifacts, so the downstream agent can
    reference upstream reasoning, not just upstream conclusions.
    """

    agent_name: str
    messages: List[Dict[str, str]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    output_text: str = ""
    output_schema: Optional[str] = None
    output_schema_instance: Optional[Any] = None

    @classmethod
    def from_agent(cls, agent: Any) -> "AgentContext":
        """Snapshot an agent's current conversation state into a context."""
        spec = getattr(agent, "context_spec", None)
        return cls(
            agent_name=getattr(agent, "name", ""),
            messages=list(getattr(agent, "messages", [])),
            tool_results=list(getattr(agent, "_tool_results", [])),
            artifacts=dict(getattr(agent, "_artifacts", {})),
            output_text=getattr(agent, "_last_output_text", ""),
            output_schema=spec.output_schema if spec else None,
        )

    def apply_to(self, target: Any, inherit: Optional[List[str]] = None) -> None:
        """Inject selected fields of this context into a target agent.

        ``inherit`` selects which fields carry over. Defaults to ``["messages"]``
        which preserves backward-compatible string-only pipelines while still
        letting downstream agents see upstream reasoning.
        """
        if inherit is None:
            inherit = ["messages"]

        # Always carry the upstream's final output as a user message so the
        # downstream agent has at least the same information as v2.1.
        # (When inherit includes "messages", we instead copy the full history.)
        if "messages" in inherit and self.messages:
            # Replace target's messages with upstream history, keeping the
            # downstream agent's own system prompt as the first entry.
            target_messages = list(getattr(target, "messages", []))
            system_msgs = [m for m in target_messages if m.get("role") == "system"]
            new_messages = system_msgs + [
                m for m in self.messages if m.get("role") != "system"
            ]
            target.messages = new_messages
            if self.output_text and self.output_text not in [
                m.get("content") for m in new_messages
            ]:
                target.messages.append(
                    {"role": "user", "content": f"[Upstream {self.agent_name}]: {self.output_text}"}
                )
        elif self.output_text:
            # Legacy v2.1 behaviour: just append the upstream output as user msg.
            target.messages.append(
                {"role": "user", "content": f"[Upstream {self.agent_name}]: {self.output_text}"}
            )

        if "artifacts" in inherit and self.artifacts:
            current = dict(getattr(target, "_artifacts", {}))
            current.update(self.artifacts)
            target._artifacts = current

        if "tool_results" in inherit and self.tool_results:
            current = list(getattr(target, "_tool_results", []))
            current.extend(self.tool_results)
            target._tool_results = current


def is_compatible(upstream_spec: Optional[ContextSpec], downstream_spec: Optional[ContextSpec]) -> bool:
    """Check context compatibility for the Harness Validator C-004 rule.

    Returns True if the downstream agent's declared ``input_schema`` is
    satisfied by the upstream agent's declared ``output_schema``.
    Compatibility is checked by name equality (structural typing); if
    either side omits a schema, we are permissive (no error).
    """
    if upstream_spec is None or downstream_spec is None:
        return True
    expected_input = downstream_spec.input_schema
    provided_output = upstream_spec.output_schema
    if expected_input is None or provided_output is None:
        return True
    return expected_input == provided_output
