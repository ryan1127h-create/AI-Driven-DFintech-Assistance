"""
Conversation — owns chat session state: the bounded raw message tail, block-
based incremental history summarization, the read/write locks that guard a
turn's read-modify-write, and the read-side operations (listing, full
transcript, rollback) the /chat/* endpoints need. The orchestrator calls
this domain once per turn to load/record state; it never touches storage or
summarization directly, so either can be changed or swapped here without
the orchestrator noticing.
"""
