from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

llm = ChatOllama(model="gpt-oss:120b-cloud", temperature=0.0)
system = SystemMessage(content="You are a senior software engineer. DONT VERBOSE. WRITE EXACT ANSWERS ONLY.")

prompt = """List three hypotheses for intermittent 502 errors.
For each, specify confirming and falsifying evidence.
Do not propose fixes."""

resp = llm.invoke([system, HumanMessage(content=prompt)])
print(resp.content)
