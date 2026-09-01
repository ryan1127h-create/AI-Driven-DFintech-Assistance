"""
The orchestrator — the chatbot's own reasoning loop, and the only
component in this system that talks to the user directly. Classifies what
a message needs, then either answers directly or calls one or more
registered tools (see app/tools/) and folds their results into a single
reply. Depends only on the Tool contract, never on a specific domain — a
new capability becomes callable by registering a tool, not by editing
orchestration code.
"""
