"""
Command cogs for Maxis.

One `GroupCog` per category, which registers as an `app_commands.Group` so
commands are invoked as `/<category> <command>`. `/help` is top-level and
lives in `help_command`, since it documents the categories rather than
being one:

    utility_commands    -> /utility
    moderation_commands -> /moderation
    economy_commands    -> /economy
    image_commands      -> /image

`COGS` in `bot.main` decides the order they are added to the tree, and
`/help` reads the registered groups back off it. Nothing imports these from the
package itself, so the cogs are left to be imported by module.
"""