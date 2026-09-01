"""
Abstract contracts for infrastructure a domain depends on (a relational
store, a cache, ...), independent of any specific vendor or driver. A
domain or adapter type-hints against these; app/adapters/ holds the
concrete implementations wired to real infrastructure.
"""
