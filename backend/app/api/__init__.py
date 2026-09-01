"""
HTTP surface. Each mounted domain owns its own APIRouter (its api.py);
this package is the only place those routers get assembled into the
app's actual URL space.
"""
