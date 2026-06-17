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

import concurrent.futures
from typing import List, Any
from .agent import NexaAgent

def join_agents(agents: List[NexaAgent], initial_input: str) -> str:
    """
    Run multiple agents concurrently with the same input.
    """
    print(f"\\n[Join] Fan-out to {len(agents)} agents...")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(agents)) as executor:
        future_to_agent = {executor.submit(agent.run, initial_input): agent for agent in agents}
        for future in concurrent.futures.as_completed(future_to_agent):
            agent = future_to_agent[future]
            try:
                res = future.result()
                results.append(f"Output from {agent.name}: {res}")
            except Exception as exc:
                results.append(f"Output from {agent.name} failed: {exc}")
                
    return "\\n".join(results)

def nexa_pipeline(initial_input: str, agents: List[NexaAgent]) -> str:
    """
    Execute a pipeline of agents explicitly.
    data = AgentA.run(input) >> AgentB >> AgentC
    """
    curr_input = initial_input
    for agent in agents:
        curr_input = agent.run(curr_input)
    return curr_input


def nexa_context_pipeline(initial_input, agents: List[NexaAgent]):
    """v2.2.1: Pipeline with AgentContext handoff.

    Unlike ``nexa_pipeline``, this variant threads the upstream agent's
    ``AgentContext`` into the downstream agent's ``run()`` so that declared
    inherit fields (messages, artifacts, tool_results) carry over. Agents
    without a ``context_spec`` fall back to v2.1 string-only behavior.
    """
    from .agent_context import AgentContext

    curr = initial_input
    for agent in agents:
        has_context = getattr(agent, "context_spec", None) is not None
        if has_context:
            if isinstance(curr, AgentContext):
                curr = agent.run(curr)
            else:
                curr = agent.run(curr)
                if agent.last_context() is not None:
                    curr = agent.last_context()
        else:
            if isinstance(curr, AgentContext):
                curr = curr.output_text
            curr = agent.run(curr)
    if isinstance(curr, AgentContext):
        return curr.output_text
    return curr
