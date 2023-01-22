# Discord Sleep Bot

This is a Discord bot designed to ~~judge~~ assist people in improving their
sleep schedules. It is designed to fit a specific role within a Discord server
I'm in, and is not designed for general use.

## Requirements

- `python` >= 3.11.0
- `discord.py`

## Required Files

Files are stored in a directory given by the environment variable
`SLEEP_BOT_CONFIG` (`~/.config/sleep-bot` is a good idea). In there, several
configuration files should be created:

### `log.json`

This file logs sleeping results. It is mostly necessary in the event of the bot
crashing, so that the night's sleep logs can be easily recovered. This file is
not meant to be edited by hand, although it can be if necessary.

### `exemptions.json`

This file keeps track of individual people's exemptions. Anyone who is exempt is
not logged for the night and does not appear on the next day's scoreboard. This
file is not meant to be edited by hand, although it can be if necessary.

### `abroad.json`

This file lists the current users who are not on campus. This is only used if
the `at_reed` variable is set to `true` in `config.toml`. When a user is in this
list, they are treated as being in their listed time zone even when everybody
else is listed as being at Reed. This file can be edited through the `/in_town`
and `/out_of_town` commands.

### `config.toml`

This file contains user-editable configuration for the bot.

- `token`: This is the API token the bot uses to access Discord.
- `at_reed`: This is a boolean representing whether or not people's time zone
  roles should be respected (`at_reed=true` means that everybody will use the
  default time zone)
- `server`: This contains settings for the server the bot runs on:
    - `id`: This is the Discord ID for the server.
    - `channel`: This is the Discord ID for the bedtime channel (where results
      are posted daily)
    - `insomniacs`: This is the Discord ID for the role marking people to be
      tracked by the bot.
    - `patrol`: This is the Discord ID for the role of bot administrators; these
      people get a slightly extended command suite.

### `users.json`

This file contains user nicknames. If a user has no entry in this file, then
their current display name is used for the nightly recap. Otherwise, this is
what is used. This file can be edited through the `/name` and `/name_other`
commands.

## Commands

This bot uses Discord's new(ish) Slash Commands API.

### `/name`

The `/name` command changes your own nickname. This is the name the bot uses
when creating the daily write-up, as well as any other things that require
referring to a user (besides pings).

### `/name_other`

This command is similar to `/name`, but is used to name a different user than
the one who made the command.

### `/confess`

The `/confess` command is a manual override for the night's sleep. This will set
the user's sleep result for the night to be whatever is listed in the command.
The bot will also update the night's announcement accordingly, if it has already
been posted.

### `/snitch`

This command is similar to `/confess`, but it is used to change the result for a
different user than the current one.

### `/exempt`

The `/exempt` command marks a user as exempt for the given night. This command
takes a date argument, which is either "today" or "tomorrow". This argument
allows the user to be set as exempt for either the current or next day's sleep
bracket.

This command is only usable by a patrol member.

### `/list_users`

The `/list_users` command lists all users currently enrolled in the program,
either as an insomniac or a partol member. This is mostly to be used for
debugging, and it does not edit any files or permanent data.

### `/out_of_town`

The `/out_of_town` command sets a user as being out of town. This adds the
user's ID to the `abroad.json` file.

This command is only usable by a patrol member.

### `/in_town`

The `/in_town` command sets a user as being in town. This removes the user's ID
from the `abroad.json` file.

This command is only usable by a patrol member.

### `/set_break`

This command sets the current break status. This is currently not functional,
see below.

This command is only usable by a patrol member.

FIXME: Because `tomllib` does not support writing TOML, this does not actually
work at the moment. For now, edit the `at_reed` parameter in `config.json`
manually.

### `/current_date`

This command prints the current date for both the user inputting the command and
the default time zone.

## The day

Since this bot, by necessity, deals with events that span the conventional
end-of-day boundary, a different system is needed to refer to individual days.
For the purposes of this bot, a "day" begins and ends at 8 PM, in the time zone
local to the relevant user. For commands that do not refer to a specific user,
then the `America/Los_Angeles` time zone is used as a default. Dates are
referred to by the number of the *larger* proper date of the two they span; in
other words, the date boundary is shifted 4 hours earlier than what would
otherwise be expected. The current date can be accessed using the `/date`
command.
