"""
Bot objects for Maxis.

One class per feature: the games, the shop and its catalogue, the hacker laptop
and its history, the calculator, the nitro boost -- plus the two plain data
classes the database stores, `user_settings` and `warn`.

Every module here carries a real class. A command or a listener decides when to
use one; the object itself owns the rules and, where there is one, the view.
"""
