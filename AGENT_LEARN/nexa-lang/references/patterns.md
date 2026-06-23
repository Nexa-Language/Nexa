# Nexa Patterns & Anti-Patterns

## Proven Patterns

### Pattern 1: Tool-Agent-Flow Trinity

The canonical Nexa pattern. Every Nexa program follows this structure:

```nexa
// 1. Declare tools
@tool("Description")
fn my_tool(param: string): string { python! """...""" }

// 2. Declare agent(s) that use tools
agent MyAgent {
    prompt: "You are an expert. Use tools when needed."
    model: "minimax-m2.5"
}

// 3. Orchestrate in flow
flow main {
    result = MyAgent.run("User request");
    print(result);
}
```

**Why it works:** Clean separation of concerns. Tools are capabilities, agents
are personas, flows are orchestration. Each layer is independently testable.

### Pattern 2: Multi-File Include

For projects with multiple agents or many tools:

```
project/
  main.nx          ← include "tools.nx"; include "agents.nx"; include "flows.nx"
  tools.nx         ← all @tool fn declarations
  agents.nx        ← all agent declarations
  flows.nx         ← all flow declarations
  secrets.nxs      ← API configuration (gitignored)
```

**Why it works:** Each file has a single responsibility. The `main.nx` file
is just composition. Changes to tools don't touch agents, and vice versa.

### Pattern 3: ReAct Loop with Harness

For autonomous agents that think → act → observe → loop:

```nexa
@tool("Read a file")
fn read_file(path: string): string { python! """...""" }

@tool("Write to a file")
fn write_file(path: string, content: string): string { python! """...""" }

agent Coder {
    prompt: "You are a coding assistant. Use tools to read/write files.
             Think before acting. Verify after writing."
}

flow main {
    task = input("Task: ");

    autoloop max_steps: 20, exit_when: "task completed", timeout: 600 {
        with_context max_tokens: 50000 {
            snap = snapshot();

            try_agent {
                result = Coder.run(task);
            } catch_correction(e: ToolError) {
                reflect "Tool error. Adjust approach.";
            }

            verify result satisfies string;
        }
    }

    print(result);
}
```

**Why it works:** Harness dimensions compose naturally. E (autoloop) provides
the loop, C (with_context) manages tokens, S (snapshot) provides rollback,
L (reflect) enables self-correction, V (verify) ensures output quality.

### Pattern 4: Semantic Routing

Use `match intent` when you have multiple specialized agents:

```nexa
agent FinanceAgent { prompt: "You handle financial queries." }
agent TechAgent { prompt: "You handle technical questions." }
agent GeneralAgent { prompt: "You handle everything else." }

flow main {
    user_input = input("Ask anything: ");

    match intent user_input {
        "financial calculations, accounting, taxes, investments" => FinanceAgent;
        "programming, debugging, system design, architecture" => TechAgent;
        default => GeneralAgent;
    }

    response = result.run(user_input);
    print(response);
}
```

### Pattern 5: Pipeline Composition

Chain agents for multi-step processing:

```nexa
agent Researcher { prompt: "Research thoroughly. Output raw findings." }
agent Analyst { prompt: "Analyze findings. Identify patterns and insights." }
agent Writer { prompt: "Write a polished article from the analysis." }

flow main {
    topic = "AI safety in autonomous systems";

    // Pipeline: Research → Analyze → Write
    article = Researcher.run(topic)
           >> Analyst
           >> Writer;

    verify article satisfies "is a well-structured article with introduction, body, and conclusion";
    print(article);
}
```

### Pattern 6: Validation Loop

Self-correcting agent with explicit validation:

```nexa
flow main {
    task = "Write a function that sorts a list";
    max_attempts = 3;

    autoloop max_steps: max_attempts, exit_when: "code passes all tests" {
        snap = snapshot();

        code = Coder.run(task);

        // Write code to file
        write_file("output.py", code);

        // Run tests
        test_result = shell_exec("python -m pytest tests/ -q");

        if (test_result contains "FAILED") {
            reflect "Tests failed. Fix the code.";
            // Continue loop — Coder will see the failure in context
        }
    }
}
```

---

## Anti-Patterns

### Anti-Pattern 1: Giant Single File

```nexa
// DON'T: 500+ lines in one .nx file
@tool("a") fn a: string { ... }
@tool("b") fn b: string { ... }
// ... 20 more tools ...
agent Agent1 { ... }
agent Agent2 { ... }
agent Agent3 { ... }
flow main { /* 200 lines of orchestration */ }
```

**Problem:** Hard to maintain, impossible to reuse tools across projects.

**Fix:** Split into `tools.nx`, `agents.nx`, `flows.nx` and use `include`.

### Anti-Pattern 2: Missing Harness Primitives

```nexa
// DON'T: Bare agent call with no safety net
flow main {
    result = Agent.run(task);
    print(result);
}
```

**Problem:** No loop control, no context management, no error recovery, no
output verification. The agent runs once and if it fails, you get nothing.

**Fix:** Wrap in `autoloop` + `with_context` + `verify`. The Harness dimensions
exist precisely to prevent this class of failure.

### Anti-Pattern 3: Over-Engineering Before Testing

```nexa
// DON'T: Add all 6 Harness dimensions before a single test run
flow main {
    autoloop max_steps: 100 {
        with_context max_tokens: 100000 {
            fork {
                snap = snapshot();
                try_agent { result = Agent.run(task); }
                catch_correction(e: ToolError) { reflect "error"; }
                verify result satisfies string;
            } and { /* ... */ }
        }
    }
}
```

**Problem:** Too much complexity before you know what's needed. Debugging is
harder.

**Fix:** Start simple — one agent, one flow. Add dimensions incrementally as
you observe failure modes. E (autoloop) first, then C (context), then V
(verify), then S/L.

### Anti-Pattern 4: Tool Without Return Type

```nexa
// DON'T: Missing return type
@tool("Search the web")
fn web_search(query: string) {  // ← missing : string
    python! """..."""
}
```

**Problem:** The compiler warns (T-004). The LLM can't interpret the tool's
output format without a return type. Tool calls may produce unexpected results.

**Fix:** Always add an explicit return type: `fn web_search(query: string): string {`

### Anti-Pattern 5: .nxs as .nx

```nexa
// DON'T: Nexa code in a .nxs file
// file: config.nxs
agent MyAgent { ... }  // ← won't parse!
flow main { ... }
```

**Problem:** `.nxs` files use a different format (`config default{...}`).
The compiler skips them. Any Nexa syntax in a `.nxs` file is silently ignored.

**Fix:** Use `.nx` for source code, `.nxs` only for `config default{...}`.

### Anti-Pattern 6: Hardcoding API Keys

```nexa
// DON'T: API key in source
agent MyAgent {
    prompt: "You are helpful."
    model: "sk-abc123..."  // ← API key exposed!
}
```

**Problem:** API keys in source code get committed, leaked, and are hard to
rotate.

**Fix:** Use `secrets.nxs`:
```
config default{
    API_KEY = "sk-..."
    MODEL_NAME = { "default": "minimax-m2.5" }
}
```
And reference the model name in the agent: `model: "default"`.

---

## Decision Tree: Which Harness Dimensions Do I Need?

```
Start here:
  └─ Is this a one-shot task? (ask → answer → done)
      ├─ YES → No Harness needed beyond V (verify)
      └─ NO → Is this a multi-turn autonomous agent?
          ├─ YES → E (autoloop) + C (with_context)
          │   └─ Is failure recovery critical?
          │       ├─ YES → + S (snapshot/restore) + L (reflect)
          │       └─ NO → done
          └─ Is this a pipeline of agents?
              ├─ YES → Consider Actor (fork/merge)
              └─ NO → Review if you need any Harness at all