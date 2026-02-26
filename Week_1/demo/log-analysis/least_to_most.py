from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

llm = ChatOllama(model="gpt-oss:120b-cloud", temperature=0.0)
system = SystemMessage(content="You are a senior software engineer. DONT VERBOSE. WRITE EXACT ANSWERS ONLY.")

steps = [
    "Classify possible 502 causes and log patterns.",
    "Given logs, identify dominant failure mode. No fixes.",
    "Propose minimal falsification plan.",
    "Given OOMKilled pods and early readiness, propose fixes with verification."
]

prev = ""
for i, step in enumerate(steps, 1):
    prompt = f"Step {i}: {step}\nPrevious output:\n{prev}"
    resp = llm.invoke([system, HumanMessage(content=prompt)])
    print(f"\n=== Step {i} ===\n{resp.content}")
    prev = resp.content
