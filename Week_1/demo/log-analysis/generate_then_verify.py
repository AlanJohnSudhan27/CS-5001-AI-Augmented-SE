from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

llm = ChatOllama(model="gpt-oss:120b-cloud", temperature=0.0)
system = SystemMessage(content="You are a senior software engineer. DONT VERBOSE. WRITE EXACT ANSWERS ONLY.")

gen = "Propose a fix for intermittent 502 errors."
critique = "Critique the above fix for production safety and revise it."

r1 = llm.invoke([system, HumanMessage(content=gen)])
r2 = llm.invoke([system, HumanMessage(content=r1.content + '\n\n' + critique)])

print("Initial:\n", r1.content)
print("\nRevised:\n", r2.content)
