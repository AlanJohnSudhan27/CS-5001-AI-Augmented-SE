
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

llm = ChatOllama(model="gpt-oss:120b-cloud", temperature=0.0)
system = SystemMessage(content="You are a senior backend engineer. Be precise and explicit. DONT Verbose.")

BUGGY_CODE = '''
def calculate_total(items, discount):
    total = 0
    for item in items:
        total += item["price"] * item["quantity"]
    if discount:
        total = total - discount
    return total
'''

gen = f"""Fix the bug in this function:

{BUGGY_CODE}
"""

first = llm.invoke([system, HumanMessage(content=gen)]).content

critique_prompt = f"""Review the following fix for unsafe assumptions and missing cases.
Revise if needed.

{first}
"""

second = llm.invoke([system, HumanMessage(content=critique_prompt)]).content

print("INITIAL FIX:\n", first)
print("\nREVISED FIX:\n", second)
