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
