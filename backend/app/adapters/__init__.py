"""
Concrete implementations of the ports declared in app/ports/, wired to
real infrastructure. Each adapter exposes a module-level singleton that
domains import directly (the port type exists for documentation and for
swappability — writing a second adapter behind the same port doesn't
require touching any domain).
"""
