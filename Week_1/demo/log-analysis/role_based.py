from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

llm = ChatOllama(model="gpt-oss:120b-cloud", temperature=0.0)
system = SystemMessage(content="You are a senior software engineer. DONT VERBOSE. WRITE EXACT ANSWERS ONLY.")

prompt = "Analyze intermittent 502 errors and propose remediation."
resp = llm.invoke([system, HumanMessage(content=prompt)])
print(resp.content)
