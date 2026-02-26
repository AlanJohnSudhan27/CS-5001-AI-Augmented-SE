from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

llm = ChatOllama(model="gpt-oss:120b-cloud", temperature=0.0)
system = SystemMessage(content="You are a senior software engineer. DONT VERBOSE. WRITE EXACT ANSWERS ONLY.")

example = """Example:
502 caused by readiness probe routing traffic too early.
Fix: delay readiness until app is ready."""

prompt = example + "\n\nDiagnose the current 502 issue."
resp = llm.invoke([system, HumanMessage(content=prompt)])
print(resp.content)
