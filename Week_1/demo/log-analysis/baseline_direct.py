from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

INCIDENT = """Intermittent 502 errors behind reverse proxy during traffic spikes."""

llm = ChatOllama(model="gpt-oss:120b-cloud", temperature=0.0)
system = SystemMessage(content="You are a senior software engineer. DONT VERBOSE. WRITE EXACT ANSWERS ONLY.")


prompt = f"""{INCIDENT}
Diagnose the cause and propose a fix."""

resp = llm.invoke([system, HumanMessage(content=prompt)])
print(resp.content)
