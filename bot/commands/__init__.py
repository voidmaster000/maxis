"""
Command cogs for Maxis.

One `GroupCog` per help category, which registers as an `app_commands.Group` so
commands are invoked as `/<category> <command>`:

    utility_commands    -> /utility
    moderation_commands -> /moderation
    economy_commands    -> /economy
    image_commands      -> /image

`slash_commands.COGS` decides the order they are added to the tree, and
`/help` reads the registered groups back off it. Nothing imports these from the
package itself, so the cogs are left to be imported by module.
"""