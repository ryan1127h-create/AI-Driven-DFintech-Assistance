"""
S6 — output modes. Each implements base.ModeStrategy: it takes what S3-S5
produced (models.ModeInput) and decides the result's shape
(models.ModeOutput). To add a mode, implement the strategy in a module
here and register it in workflow.py's MODES.
"""
