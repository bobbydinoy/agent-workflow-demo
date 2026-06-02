# Microsoft Agent Framework (MAF) - Available Agents & Building Blocks

## Key Concept: No "Pre-built Agents" in MAF

Microsoft Agent Framework **does not provide pre-built specialized agents**. Instead, it provides:

1. **Base classes** to extend (like `Executor`)
2. **Orchestration patterns** (Sequential, Parallel, etc.)
3. **Tool integration capabilities**

You **create custom agents** by extending the base `Executor` class.

---

## MAF Core Building Blocks

### 1. **Executor** (Base Agent Class)
```python
from agent_framework import Executor

class MyCustomAgent(Executor):
    def __init__(self):
        super().__init__(id="my_agent")
    
    @handler
    async def run(self, input_data, ctx):
        # Your logic here
        await ctx.yield_output(result)
```

**What it provides:**
- `id`: Unique identifier for the agent
- `@handler`: Decorator to define the agent's entry point
- `ctx.yield_output()`: Send output to next agent
- `ctx.send_message()`: Send messages in workflow

### 2. **WorkflowContext**
```python
from agent_framework import WorkflowContext

class MyContext(WorkflowContext):
    goal: str
    result: dict
```

Shared state passed between agents (avoids global state).

### 3. **Message**
```python
from agent_framework import Message

message = Message(
    role="user",
    contents=["Your message here"]
)
```

Used for LLM communication and inter-agent messaging.

---

## Orchestration Patterns Available in MAF

### 1. **SequentialBuilder** (Used in your project)
```python
from agent_framework_orchestrations import SequentialBuilder

workflow = SequentialBuilder(
    participants=[agent1, agent2, agent3],
    output_from=[agent3],
    intermediate_output_from="all_other",
).build()
```
- Agents run **one after another**
- Output of agent N becomes input to agent N+1

### 2. **ParallelBuilder**
```python
from agent_framework_orchestrations import ParallelBuilder

workflow = ParallelBuilder(
    participants=[agent1, agent2, agent3],
    output_from=[agent1, agent2, agent3],
).build()
```
- All agents run **simultaneously**
- Useful for independent tasks

### 3. **ConditionalBuilder** (Branching)
```python
from agent_framework_orchestrations import ConditionalBuilder

workflow = ConditionalBuilder(
    # Route based on conditions
).build()
```
- Agents run based on **conditions**
- Useful for decision trees

---

## Agents in THIS Project (Custom-Built Examples)

Your project includes **6 custom agents** that extend `Executor`:

| Agent | File | Purpose |
|-------|------|---------|
| **PlannerAgent** | `agents/planner.py` | Creates workflow task sequence |
| **ResearchAgent** | `agents/researcher.py` | Gathers evidence from sources |
| **AnalysisAgent** | `agents/analyzer.py` | Synthesizes guide & metrics |
| **ReviewAgent** | `agents/reviewer.py` | Validates safety & structure |
| **ComplianceAgent** | `agents/compliance.py` | Runs policy checks |
| **HumanApprovalAgent** | `agents/approval.py` | Final authorization gate |

Each is a **reference implementation** showing different patterns:
- Simple logic (Planner)
- Multi-source data gathering (Researcher)
- Conditional LLM fallback (Analyzer)
- Safety validation (Reviewer)
- Policy enforcement (Compliance)
- Human-in-the-loop (Approval)

---

## LLM Integration in MAF

### Available LLM Clients

#### 1. **OpenAIChatClient** (Full chat with tools)
```python
from agent_framework_openai import OpenAIChatClient

client = OpenAIChatClient(
    model="gpt-4o-mini",
    api_key="sk-...",
    base_url="https://api.openai.com/v1",
)

response = await client.get_response(
    messages=[Message(role="user", contents=["Hello"])],
    options={
        "temperature": 0.7,
        "tools": [web_search_tool],
    }
)
```

**Features:**
- Support for tools/function calling
- Web search integration
- Streaming support

#### 2. **OpenAIChatCompletionClient** (Text completion)
```python
from agent_framework_openai import OpenAIChatCompletionClient

client = OpenAIChatCompletionClient(
    model="gpt-4o-mini",
    api_key="sk-...",
)

response = await client.get_response(
    messages=[Message(role="user", contents=["Hello"])],
    options={
        "temperature": 0.2,
        "max_tokens": 500,
        "response_format": {"type": "json_object"},
    }
)
```

**Features:**
- Simpler interface
- JSON response formatting
- Lower latency

#### 3. **Web Search Tool** (Built-in)
```python
from agent_framework_openai import OpenAIChatClient

tool = OpenAIChatClient.get_web_search_tool(
    search_context_size="high"  # low, medium, high
)

response = await client.get_response(
    messages=messages,
    options={"tools": [tool]},
)
```

Available in your `tools/llm_tools.py`.

---

## Tool Integration Pattern in MAF

MAF agents can integrate tools through:

### 1. **Function Calling (LLM-based)**
```python
from agent_framework_openai import OpenAIChatClient

# Define tool schema
tool = {
    "type": "function",
    "function": {
        "name": "search_docs",
        "description": "Search company documentation",
        "parameters": {...}
    }
}

# Let LLM decide when to call it
response = await client.get_response(
    messages=messages,
    options={"tools": [tool]},
)
```

### 2. **Explicit Tool Calls (Agent-based)**
```python
# In your agent:
from tools.api_tools import search_public_api
from tools.file_tools import read_file

class MyAgent(Executor):
    @handler
    async def run(self, input_data, ctx):
        # Call tools directly
        notes = read_file("path/to/file.txt")
        api_result = search_public_api("query")
        
        await ctx.yield_output({"result": notes + api_result})
```

Used in your project for explicit, deterministic tool calls.

---

## Message Passing & Communication

### Types of Messages in MAF

```python
from agent_framework import Message

# System message (instruction)
system_msg = Message(role="system", contents=["You are helpful"])

# User message
user_msg = Message(role="user", contents=["Hello, help me with..."])

# Assistant message
assistant_msg = Message(role="assistant", contents=["I'll help by..."])
```

### Inter-Agent Communication

```python
class MyAgent(Executor):
    @handler
    async def run(self, input_data, ctx):
        # Send message to next agent
        await ctx.send_message({
            "stage": "my_agent",
            "payload": result_data,
            "metadata": {...}
        })
        
        # Yield structured output
        await ctx.yield_output({"stage": "my_agent", "payload": result_data})
```

Used in your project for multi-stage output collection.

---

## Comparison: Custom Agents vs. Pre-built

| Aspect | MAF Approach | Your Project Example |
|--------|--------------|----------------------|
| **Agent types** | Extend `Executor` | All agents extend Executor |
| **Specialization** | You decide | Custom agents for each role |
| **Flexibility** | Very high | High (can swap/modify easily) |
| **Learning curve** | Moderate | Good reference implementations |
| **Reusability** | Build your own library | Agents are reusable across projects |

---

## How to Create a New Agent

Template for building custom agents:

```python
from agent_framework import Executor, WorkflowContext, handler
import logging

logger = logging.getLogger(__name__)

class MyNewAgent(Executor):
    """Description of what this agent does."""
    
    def __init__(self, param1: str = "default"):
        super().__init__(id="my_new_agent")
        self.param1 = param1
    
    @handler
    async def run(
        self,
        input_data: dict,
        ctx: WorkflowContext,
    ) -> None:
        """Process input and yield output."""
        logger.info("MyNewAgent started")
        
        # Your processing logic
        result = {
            "processed": True,
            "data": input_data,
            "param": self.param1,
        }
        
        logger.info("MyNewAgent finished")
        
        # Send to next agent
        await ctx.yield_output({
            "stage": "my_new_agent",
            "payload": result,
        })
        
        await ctx.send_message(result)
```

Then register in workflow:

```python
my_agent = MyNewAgent(param1="value")

step_to_participant = {
    "my_new_agent": my_agent,
    # ... other agents
}

participants.append(my_agent)
```

---

## Summary: MAF Agent Ecosystem

```
┌─────────────────────────────────────────┐
│   Microsoft Agent Framework (MAF)       │
├─────────────────────────────────────────┤
│                                         │
│  Base Classes:                          │
│  • Executor (custom agents extend)      │
│  • WorkflowContext (shared state)       │
│  • Message (inter-agent communication)  │
│                                         │
│  Orchestration:                         │
│  • SequentialBuilder                    │
│  • ParallelBuilder                      │
│  • ConditionalBuilder                   │
│                                         │
│  LLM Integration:                       │
│  • OpenAIChatClient                     │
│  • OpenAIChatCompletionClient           │
│  • Web Search Tool                      │
│                                         │
│  Your Custom Agents (in this project):  │
│  • PlannerAgent                         │
│  • ResearchAgent                        │
│  • AnalysisAgent                        │
│  • ReviewAgent                          │
│  • ComplianceAgent                      │
│  • HumanApprovalAgent                   │
│                                         │
└─────────────────────────────────────────┘
```

**Key Takeaway:** MAF is **flexible and extensible**—you build agents for your specific use case, not limited to pre-built types.
