import os
import sys
import asyncio

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# --- Configuration ---
# Requires a local Ollama server (default: http://localhost:11434)
# and the selected model pulled, e.g.: ollama pull devstral-small-2:24b-cloud
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "devstral-small-2:24b-cloud")
TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.0"))

try:
    llm = ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_HOST,
        temperature=TEMPERATURE,
    )
    print(f"Language model initialized: {OLLAMA_MODEL} @ {OLLAMA_HOST}")
except Exception as e:
    print(f"Error initializing Ollama LLM: {e}", file=sys.stderr)
    print("Ensure Ollama is running and the model is available.", file=sys.stderr)
    sys.exit(1)

# --- Define Chain Components ---

generation_chain = (
    ChatPromptTemplate.from_messages(
        [
            ("system", "Write a short, simple project description for a to-do application."),
            ("user", "{project_details}"),
        ]
    )
    | llm
    | StrOutputParser()
)

critique_chain = (
    ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Critique the following project description based on clarity, conciseness, and appeal. "
                "Provide specific suggestions for improvement.",
            ),
            ("user", "Project Description to Critique:\n{initial_description}"),
        ]
    )
    | llm
    | StrOutputParser()
)

refinement_chain = (
    ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Based on the original Project details and the following critique, rewrite the Project "
                "description to be more effective.\n\n"
                "Original Project Details: {project_details}\n"
                "Critique: {critique}\n\n"
                "Refined Project Description:",
            ),
            ("user", ""),
        ]
    )
    | llm
    | StrOutputParser()
)

full_reflection_chain = (
    RunnablePassthrough.assign(initial_description=generation_chain)
    | RunnablePassthrough.assign(critique=critique_chain)
    | refinement_chain
)

# --- Runner utilities (works in scripts and notebooks) ---

async def run_reflection_example(project_details: str) -> str:
    """Returns the final refined description."""
    return await full_reflection_chain.ainvoke({"project_details": project_details})

def run_reflection(project_details: str) -> None:
    """
    Safe entrypoint:
    - If no event loop is running: uses asyncio.run (normal script usage).
    - If an event loop is running (Jupyter/interactive): schedules the task and prints when done.
    """
    async def _runner() -> None:
        print(f"\n--- Running Reflection Example for Project: '{project_details}' ---")
        try:
            result = await run_reflection_example(project_details)
            print("\n--- Final Refined Project Description ---")
            print(result)
        except Exception as e:
            print(f"\nAn error occurred during chain execution: {e}", file=sys.stderr)

    try:
        loop = asyncio.get_running_loop()
        in_running_loop = loop.is_running()
    except RuntimeError:
        in_running_loop = False

    if in_running_loop:
        task = asyncio.create_task(_runner())

        # Optional: log exceptions if the task fails.
        def _on_done(t: asyncio.Task) -> None:
            exc = t.exception()
            if exc:
                print(f"\nTask failed: {exc}", file=sys.stderr)

        task.add_done_callback(_on_done)
    else:
        asyncio.run(_runner())

if __name__ == "__main__":
    run_reflection("A simple to-do application in python.")
