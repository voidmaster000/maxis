"""
Core services for Maxis.

The modules that commands, listeners and objects all reach for: configuration
and state, persistence, the money rules, and the shared helpers.

    global_state   -> every tuning constant + all mutable runtime state
    database_sync  -> syncs global_state to MongoDB
    transactions   -> credit / debit
    helper         -> stateless helpers + /help rendering

Nothing here imports a command or a listener, and the only import from the rest
of the bot is `global_state`'s two data classes (`user_settings`, `warn`) from
`bot.objects`, which import nothing themselves. That keeps the package out of
any import cycle.

Nothing imports these from the package itself, so they are left to be imported
by module.
"""
