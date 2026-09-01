"""
One bounded context per business capability. Each domain owns its own data
and workflow, and exposes itself to the rest of the app only through its
own interface.py — sibling domains never import each other's internals.
"""
