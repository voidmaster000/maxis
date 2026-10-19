"""
Interaction listeners for Maxis.

Not cogs: `bot.main.on_interaction` dispatches to these by interaction type,
and each holds only static methods. One module per kind of interaction, and
each hands its work on to the object that owns the feature in `bot.objects`:

    components_listener -> button and select menu clicks
    modals_listener     -> modal submissions
"""
