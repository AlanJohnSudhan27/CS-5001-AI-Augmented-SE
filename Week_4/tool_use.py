import os
import asyncio
from typing import Any, Dict, Optional

from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, BaseMessage


# --- Configuration ---
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "devstral-small-2:24b-cloud")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

try:
    llm = ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0,
    )
    print(f"✅ Ollama model initialized: {OLLAMA_MODEL} @ {OLLAMA_BASE_URL}")
except Exception as e:
    print(f"🛑 Error initializing language model: {e}")
    llm = None


# --- Tool Definition ---
@tool
def search_information(query: str) -> str:
    """
    Provides factual information on a given topic.
    This is a simulated search tool.
    """
    print(f"\n--- 🛠️ Tool Called: search_information('{query}') ---")
    simulated_results = {
        "weather in london": "The weather in London is currently cloudy with a temperature of 15°C.",
        "what's the weather like in london?": "The weather in London is currently cloudy with a temperature of 15°C.",
        "capital of france": "The capital of France is Paris.",
        "what is the capital of france?": "The capital of France is Paris.",
        "population of earth": "The estimated population of Earth is around 8 billion people.",
        "tallest mountain": "Mount Everest is the tallest mountain above sea level.",
    }
    return simulated_results.get(
        query.lower(),
        f"Simulated search result for '{query}': No specific information found, but the topic seems interesting."
    )


TOOLS = [search_information]
TOOL_BY_NAME = {t.name: t for t in TOOLS}


def _extract_tool_calls(msg: BaseMessage) -> Optional[list]:
    """
    Handles multiple LangChain message shapes across versions.
    Returns a list of tool calls or None.
    """
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        return tool_calls

    additional = getattr(msg, "additional_kwargs", None) or {}
    tool_calls = additional.get("tool_calls")
    if tool_calls:
        return tool_calls

    return None


async def _run_with_tools(user_input: str, max_steps: int = 6) -> str:
    """
    Minimal tool-calling loop:
    1) Ask the model.
    2) If it requests tools, run them and append ToolMessage(s).
    3) Repeat until final answer or max steps reached.
    """
    if llm is None:
        return "LLM is not initialized."

    model = llm.bind_tools(TOOLS)

    messages: list[BaseMessage] = [
        SystemMessage(content="You are a helpful assistant."),
        HumanMessage(content=user_input),
    ]

    for _ in range(max_steps):
        ai_msg = await model.ainvoke(messages)
        messages.append(ai_msg)

        calls = _extract_tool_calls(ai_msg)
        if not calls:
            return getattr(ai_msg, "content", "") or ""

        for call in calls:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            args = call.get("args") if isinstance(call, dict) else getattr(call, "args", None)
            call_id = call.get("id") if isinstance(call, dict) else getattr(call, "id", None)

            if not name or name not in TOOL_BY_NAME:
                result = f"Tool '{name}' not found."
                messages.append(ToolMessage(content=result, tool_call_id=call_id or "unknown"))
                continue

            tool_obj = TOOL_BY_NAME[name]
            tool_args: Dict[str, Any] = args if isinstance(args, dict) else {}

            try:
                tool_result = await tool_obj.ainvoke(tool_args)
            except Exception as e:
                tool_result = f"Tool '{name}' failed: {e}"

            messages.append(ToolMessage(content=str(tool_result), tool_call_id=call_id or "unknown"))

    return "Stopped: exceeded max tool-calling steps."


async def run_agent_with_tool(query: str) -> None:
    print(f"\n--- 🏃 Running Tool-Calling Chat: '{query}' ---")
    output = await _run_with_tools(query)
    print("\n--- ✅ Final Response ---")
    print(output)


async def main():
    await asyncio.gather(
        run_agent_with_tool("What is the capital of France?"),
        run_agent_with_tool("What's the weather like in London?"),
        run_agent_with_tool("Tell me something about dogs."),
    )


if __name__ == "__main__":
    asyncio.run(main())
