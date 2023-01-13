#!/usr/bin/env python3

from collections import defaultdict
from datetime import date, datetime, time
import json
import os
from pathlib import Path
import tomllib as toml
from typing import Optional
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import tasks

TOKEN = None
AT_REED = True
CONFIG = Path(
    os.getenv('SLEEP_BOT_CONFIG', '~/.config/sleep_bot')
).expanduser()

if not CONFIG.exists():
    CONFIG.mkdir()

LOG_FILE = CONFIG/'log.json'

client = discord.Client()

SERVER_INFO = None


class ServerInfo:
    """The class representing server information."""
    def __init__(
            self, server_id: int, bed_channel: int,
            insomniacs_role: int, patrol_role: int,
    ):
        self.server_id = server_id
        self.bed_channel = bed_channel
        self.insomniacs_role = insomniacs_role
        self.patrol_role = patrol_role


def load_config():
    """Loads config and sets global variables accordingly."""
    with open(CONFIG/'config.toml', 'r', encoding='utf8') as f:
        config = toml.load(f)
        global TOKEN, AT_REED, SERVER_INFO
        TOKEN = config["token"]
        AT_REED = config["at_reed"]
        info = config["server"]
        SERVER_INFO = ServerInfo(
            info["id"],
            info["bed_channel"],
            info["insomniacs"],
            info["patrol"],
        )


class RoleNotFoundError(RuntimeError):
    """An error to throw if a role cannot be found."""


# TODO: Make this a config file?
TIME_ZONE_NAMES = {
    "PST": ZoneInfo('America/Los_Angeles'),
    "MST": ZoneInfo('America/Denver'),
    "CST": ZoneInfo('America/Chicago'),
    "EST": ZoneInfo('America/New_York'),
    "IST": ZoneInfo('Asia/Kolkata'),
}

REED_TZ = ZoneInfo('America/Los_Angeles')


@client.event
async def on_message(message: discord.Message):
    """Handles messages and updates log file accordingly"""
    insomniacs_role = message.guild.get_role(SERVER_INFO.insomniacs_role)
    if insomniacs_role is None:
        raise RoleNotFoundError("Could not find Insomniacs role")

    if (message.author == client.user or
            insomniacs_role not in message.author.roles):
        return

    time_zone = find_time_zone(message.author.roles)
    current_date = todays_date(time_zone)
    sent_time = message.created_at.astimezone(time_zone)
    if (not is_exempt(current_date, message.author.id) and
            in_judgment_range(sent_time, current_date)):
        # Log file format: dict[date -> dict[id -> timestamp]]
        # Log file type: dict[str, dict[str, str]]
        with open(LOG_FILE, 'w', encoding='utf8') as log:
            data = json.load(log)
            today = data[current_date.isoformat()]
            # Note that JSON only allows strings as keys, so we have to convert
            # to avoid rather nasty bugs
            author_id = str(message.author.id)
            if author_id not in today or today[author_id] <= sent_time:
                today[author_id] = sent_time.time.isoformat()
            json.dump(data, log)


@tasks.loop(time=time(7, 0, 0, tzinfo=REED_TZ))
async def show_results(guild: discord.Guild):
    """Send a message with the previous night's results to the server."""
    current_date = todays_date(REED_TZ)
    with open(LOG_FILE, 'r', encoding='utf8') as log:
        data = json.load(log)
        today = data[current_date.isoformat()]
        results = create_results(current_date, today)
    exempt = get_exemptions(current_date)
    channel = client.get_channel(SERVER_INFO.bed_channel)
    message = await channel.send(format_results(results, exempt, guild))
    with open(CONFIG/'announcements.json', 'w', encoding='utf8') as f:
        data = json.load(f)
        data[current_date.isoformat()] = message.id
        json.dump(data, f)


def create_results(day: date, data: dict[str, str]) -> dict[str, str]:
    """Create a dictionary mapping results to names.

    This takes as input a dictionary of ids (formatted as strings) to
    timestamps.
    """
    result = defaultdict(list)
    for identity, post_time in data.values():
        bucket = result_bucket(day, time.fromisoformat(post_time))
        name = user_name(int(identity))
        result[bucket] += name
    return result


class Result:
    """The class representing a result bracket."""
    def __init__(self, name: str, start: str, end: str):
        self.name = name
        self.start = time.fromisoformat(start)
        self.end = time.fromisoformat(end)

    def start_time(self, zone: ZoneInfo) -> time:
        """The starting time for the bracket, relative to the given time zone.
        """
        return self.start.replace(tzinfo=zone)

    def end_time(self, zone: ZoneInfo) -> time:
        """The ending time for the bracket, relative to the given time zone."""
        return self.end.replace(tzinfo=zone)


RESULTS = [
    Result("Winner", "22:00:00", "00:00:00"),
    Result("12-1", "00:00:00", "01:00:00"),
    Result("1-2", "01:00:00", "02:00:00"),
    Result("2-3", "02:00:00", "03:00:00"),
    Result("bruh", "03:00:00", "04:00:00"),
    Result("*my brother in christ*", "04:00:00", "05:00:00"),
    Result("turbo cringe", "05:00:00", "06:00:00"),
]


WEEKEND = [
    Result("Winner", "22:00:00", "01:00:00"),
    Result("1-2", "01:00:00", "02:00:00"),
    Result("2-3", "02:00:00", "03:00:00"),
    Result("bruh", "03:00:00", "04:00:00"),
    Result("*my brother in christ*", "04:00:00", "05:00:00"),
    Result("turbo cringe", "05:00:00", "06:00:00"),
]


def todays_results(day: date) -> list[Result]:
    """Get the results for the given day."""
    return RESULTS if day.weekday() < 5 else WEEKEND


def result_bucket(day: date, post_time: time) -> str:
    """Calculates which result the given timestamp is in, and then returns the
    name of said bucket."""
    for result in todays_results(day):
        start = result.start_time(post_time.tzinfo())
        end = result.end_time(post_time.tzinfo())
        if start <= post_time < end:
            return result.name
    raise RuntimeError("Time does not go into any result bucket")


def format_results(
        results: dict[str, list[str]],
        exemptions: list[str],
        server: discord.Guild,
) -> str:
    """Formats the night's results into a message.

    This message mentions both the Insomniacs and Bedtime Patrol roles.
    """
    res = "\n".join(
        f"{r.name}: {', '.join(results[r.name])}" for r in todays_results(date)
    )
    exempt = f"Exemptions: {', '.join(exemptions)}"
    insomniacs = server.get_role(SERVER_INFO.insomniacs_role).mention
    patrol = server.get_role(SERVER_INFO.patrol_role).mention
    return f"{insomniacs} {patrol} Last night's results:\n{exempt}\n{res}"


def user_name(identity: int) -> str:
    """Get the name used to refer to the given user."""
    with open(CONFIG/'users.json', 'r', encoding='utf8') as data:
        users = json.load(data)
        name = users.get(str(identity))
    return name or client.get_user(identity).display_name


def find_time_zone(roles: list[discord.Role]):
    """Gets the user's local time zone from their role."""
    if AT_REED:
        return REED_TZ
    for role in roles:
        zone = TIME_ZONE_NAMES.get(role.name)
        if zone is not None:
            return zone
    return REED_TZ


def in_judgment_range(msg_time: datetime, current_date: date) -> bool:
    """Determine if a timestamp is in the judgement range for the current date.

    Both `msg_time` and `current_date` should be relative to the same timezone.
    """
    if msg_time.time >= time(20, 0, 0, tzinfo=datetime.tzinfo):
        msg_date = msg_time.date + date.day
    else:
        msg_date = msg_time.date
    return current_date == msg_date and (
        current_date.time < end_time(datetime.tzinfo) or
        current_date.time >= start_time(datetime.tzinfo)
    )


def start_time(zone: ZoneInfo) -> time:
    """The start time for judged messages."""
    time(22, 0, 0, tzinfo=zone)


def end_time(zone: ZoneInfo) -> time:
    """The end time for judged messages."""
    time(6, 0, 0, tzinfo=zone)


def is_exempt(current_date: date, user_id: int) -> bool:
    """Determine if a user is exempt from the night's proceedings."""
    # Format of exemptions.json: dict[date -> list[id]]
    # Actual type: dict[str, list[int]]
    with open(CONFIG/'exemptions.json', 'r', encoding='utf8') as exempt:
        data = json.load(exempt)
        today = data[current_date.isoformat()]
        return user_id in today


def get_exemptions(current_date: date) -> list[str]:
    """Get the list of users who are exempt, formatted as the names to be
    displayed."""
    with open(CONFIG/'exemptions.json', 'r', encoding='utf8') as data:
        data = json.load(data)
    with open(CONFIG/'users.json', 'r', encoding='utf8') as users:
        user_data = json.load(users)
    today = data[current_date.isoformat()]
    return [
        user_data.get(str(u), client.get_user(u).display_name) for u in today
    ]


def todays_date(zone: ZoneInfo) -> date:
    """The current date, in the time zone given."""
    current_time = datetime.now(tz=zone)
    if current_time.time >= time(20, 0, 0, tzinfo=zone):
        return current_time.date + date.day
    else:
        return current_time.date


@app_commands.command(name="name")
async def add_nickname(interaction: discord.Interaction, name: str):
    """Sets the name you would like to be called by the program when announcing
    the night's results."""
    with open(CONFIG/'users.json', 'w', encoding='utf8') as users:
        data = json.load(users)
        data[str(interaction.user.id)] = name
        json.dump(data, users)
    await interaction.response.send_message(f"Changed name to '{name}'")


@app_commands.command(name="name_other")
async def name_other(
        interaction: discord.Interaction,
        user: discord.Member,
        name: str
):
    """Sets the name to be displayed for another user."""
    with open(CONFIG/'users.json', 'w', encoding='utf8') as users:
        data = json.load(users)
        data[str(user.id)] = name
        json.dump(data, users)
    user_ping = user.mention
    await interaction.response.send_message(
        f"Changed {user_ping}'s name to '{name}'"
    )


async def update_message(
        server: discord.Guild,
        user: discord.Member,
        result=Result,
):
    """Updates the given user's info with the given result.

    This does two things: updates the log file to reflect the change to the
    user's state, and then updates the corresponding day's announcement message
    to reflect the changes.
    """
    current_date = todays_date(REED_TZ)
    with open(LOG_FILE, 'w', encoding='utf8') as log:
        data = json.load(log)
        today = data[current_date.isoformat()]
        today[str(user.id)] = result.start_time(find_time_zone(user.roles))
        json.dump(data, log)
    with open(CONFIG/'announcements.json', 'r', encoding='utf8') as ann:
        announcements = json.load(ann)

    exempt = get_exemptions(today)
    announcement = announcements.get(today.isoformat())
    if announcement is not None:
        channel_id, message_id = announcement
        channel = client.get_channel(channel_id)
        message = await channel.fetch_message(message_id)
        await message.edit(
            content=format_results(today, exempt, server)
        )


def correct_result(index: int, day: date) -> Optional[Result]:
    """Maps weekday choices to weekend choices, when necessary.

    Because Discord only allows command choices to be static, and the results
    change on the weekend, we need a way to map the weekday choices to the
    weekend one. This only works because the weekday choices are a superset of
    the weekend ones. If the given choice is not valid on the weekend, this
    returns None.
    """
    if day.weekday() < 5:
        return RESULTS[index]
    weekday_result = RESULTS[index]
    return next((x for x in WEEKEND if x.name == weekday_result.name), None)


@app_commands.command(name="snitch")
@app_commands.choices(result=[
    Choice(name=r.name, value=i) for i, r in enumerate(RESULTS)
])
async def snitch(
        interaction: discord.Interaction,
        user: discord.Member,
        result=Choice[int]
):
    """Update someone else's sleep for the previous night."""
    today = todays_date(REED_TZ)
    todays_result = correct_result(result.value, today)
    if todays_result is not None:
        await update_message(interaction.guild, user, todays_result)
        await interaction.response.send_message(
            "Updated! Thank you for your service"
        )
    else:
        await interaction.response.send_message(
            f"Could not update; {result.name} is not a valid result for today"
        )


@app_commands.command(name="confess")
@app_commands.choices(result=[
    Choice(name=r.name, value=i) for i, r in enumerate(RESULTS)
])
async def confess(interaction: discord.Interaction, result=Choice[int]):
    """Update your sleep for the previous night."""
    today = todays_date(REED_TZ)
    todays_result = correct_result(result.value, today)
    if todays_result is not None:
        await update_message(
            interaction.guild, interaction.user, todays_result
        )
        await interaction.response.send_message(
            "Updated! Thank you for your honesty"
        )
    else:
        await interaction.response.send_message(
            f"Could not update; {result.name} is not a valid result for today"
        )


@app_commands.command(name="exempt")
@app_commands.choices(day=[
    Choice(name="today", value="today"),
    Choice(name="tomorrow", value="tomorrow"),
])
async def make_exempt(
        interaction: discord.Interaction,
        user: discord.Member,
        day=Choice[str]
):
    """Marks a user as exempt from the night's list.

    If the date is "today", then this refers to the current night. If an
    announcement has been made, then this also edits the announcement to have
    the correct information. There is no way yet to edit days before the most
    recent.
    """
    if day.value == "today":
        today = todays_date(REED_TZ)
    else:
        today = todays_date(REED_TZ) + date.day
    with open(CONFIG/'exemptions.json', 'w', encoding='utf8') as f:
        exempt = json.load(f)
        exempt.setdefault(today.isoformat(), [])
        exempt[today.isoformat()].append(user.id)
        json.dump(exempt, f)

    if day.value == "today":
        with open(LOG_FILE, 'w', encoding='utf8') as log:
            data = json.load(log)
            todays_data = data[today.isoformat()]
            del todays_data[str(user.id)]
            json.dump(data, log)
        with open(
                CONFIG/'announcements.json', 'w', encoding='utf8'
        ) as announcements:
            data = json.load(announcements)
            announcement = data.get(today.isoformat())
        if announcement is not None:
            channel_id, message_id = announcement
            channel = client.get_channel(channel_id)
            message = channel.fetch_message(message_id)
            await message.edit(
                content=format_results(todays_data, exempt, channel.guild)
            )

    await interaction.response.send_message(
        f"{user.mention} has been added to {day.value}'s exempt list"
    )


@app_commands.command(name="list_users")
async def list_users(interaction: discord.Interaction):
    """Lists all users currently with the insomniacs role, as well as with the
    patrol role."""
    server = interaction.guild
    insomniacs = server.get_role(SERVER_INFO.insomniacs_role).members
    patrol = server.get_role(SERVER_INFO.patrol_role).members
    insomniac_names = '\n'.join(i.display_name for i in insomniacs)
    patrol_names = '\n'.join(i.display_name for i in patrol)
    await interaction.response.send_message(
        f"Insomniacs:\n{insomniac_names}\nBedtime patrol:\n{patrol_names}"
    )


if __name__ == "__main__":
    load_config()
    client.run(TOKEN)
