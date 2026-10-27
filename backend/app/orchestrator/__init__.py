"""
The orchestrator — the chatbot's own reasoning loop, and the only
component in this system that talks to the user directly. Classifies what
a message needs, then either answers directly or calls one or more
registered tools (see app/tools/) and folds their results into a single
reply. A new chat capability becomes callable by registering a tool, not by
editing orchestration code — the Tool contract is the only thing this
package depends on for *answering*. Conversation state and applicant
profile data are the two exceptions: read (and, for conversation, written)
through their own domain's interface.py, same as any other cross-domain
read — see turn_service.py.
"""
