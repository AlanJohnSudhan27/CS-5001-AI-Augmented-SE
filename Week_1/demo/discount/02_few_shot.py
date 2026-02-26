
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

example = '''
Example:
Bug: percentage discount treated as flat.
Fix: distinguish discount types.
'''

prompt = f"""{example}

Now fix the following function:

{BUGGY_CODE}
"""

resp = llm.invoke([system, HumanMessage(content=prompt)])
print(resp.content)
