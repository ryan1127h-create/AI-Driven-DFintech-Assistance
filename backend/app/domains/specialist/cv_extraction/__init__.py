"""
CV extraction — reads the facts a CV states explicitly into profile field
values, each backed by a verbatim quote. One LLM call. Reads no data
itself: the caller (app.domains.cv_import) passes in the CV text and the
field definitions it may fill, then checks every quote and value before
anything reaches the profile.
"""
