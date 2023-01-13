# Discord Sleep Bot

This is a Discord bot designed to ~~judge~~ assist people in improving their
sleep schedules. It is designed to fit a specific role within a Discord server
I'm in, and is not designed for general use.

## requirements

- `python` >= 3.11.0
- `discord.py`

## Required Files

Files are stored in a directory given by the environment variable
`SLEEP_BOT_CONFIG` (`~/.config/sleep_bot` is a good idea). In there, several
configuration files should be created:

### `log.json`

This file logs sleeping results. It is mostly necessary in the event of the bot
crashing, so that the night's sleep logs can be easily recovered. This file is
not meant to be edited by hand, although it can be if necessary.

### `exemptions.json`

This file keeps track of individual people's exemptions. Anyone who is exempt is
not logged for the night and does not appear on the next day's scoreboard. This
file is not meant to be edited by hand, although it can be if necessary.

### `config.toml`

This file contains user-editable configuration for the bot.

- `token`: This is the API token the bot uses to access Discord.
- `at_reed`: This is a boolean representing whether or not people's time zone
  roles should be respected (`at_reed=true` means that everybody will use the
  default time zone)

### `users.json`

This file contains user nicknames. If a user has no entry in this file, then
their current display name is used for the nightly recap. Otherwise, this is
what is used.
