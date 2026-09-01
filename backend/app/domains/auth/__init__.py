"""
Auth — account registration, login/logout, and the identity check every
other domain relies on. Owns `student.users` and is the only domain that
touches passwords or tokens. Exposes get_current_user_id via interface.py
as the FastAPI dependency every protected endpoint, in any domain, uses to
resolve who's calling.
"""
