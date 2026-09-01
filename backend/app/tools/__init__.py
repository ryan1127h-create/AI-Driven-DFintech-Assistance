"""
The Tool contract layer. Every callable capability in this system — a
small shared utility (summarize this) or an entire specialist domain's
workflow (plan this student's courses) — is exposed to callers through the
same Tool shape defined in contracts.py. The orchestrator, and any domain
workflow that wants to call a shared utility, only ever depend on this
contract, never on a specific domain's internals.
"""
