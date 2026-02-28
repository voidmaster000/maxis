"""
Helper utility functions for Maxis
"""

import random
import re
from datetime import datetime
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Dict
from enum import Enum

import discord
import pymongo

from bot.objects.user_settings import UserSettings
from bot.objects.warn import Warn

# Set decimal precision for expression evaluation
getcontext().prec = 50

# Constants
VERSION = "5.0.0"
BASIC_COOLDOWN = 30
DAILY_COOLDOWN = 86400
WEEKLY_COOLDOWN = 604800
MONTHLY_COOLDOWN = 2592000

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESOURCES_DIR = PROJECT_ROOT / "resources"

# Maps (will be initialized from database)
custom_replies: Dict[str, str] = {}
balance_map: Dict[int, int] = {}
warn_map: Dict[int, Dict[int, Warn]] = {}

# Work messages
WORKS = [
    "did babysitting for 6 hours and earned",
    "finished a 100-day job and earned",
    "found some money on road and got",
    "sold a modern art picture and earned",
    "caught a robber and was prized with",
    "fixed neighbour's PC and earned",
    "checked his car bonnet and found",
    "won a bet and earned",
    "repaired cars at workshop for a day and earned",
    "won a lucky draw and earned",
]


class RpsResult(Enum):
    BOT_WIN = "bot_win"
    USER_WIN = "user_win"
    TIE = "tie"
    ERROR = "error"


class ExpressionResult:
    def __init__(self, success: bool, result: Decimal = Decimal("0"), error: str = ""):
        self.success = success
        self.result = result
        self.error = error


def get_random_color() -> discord.Colour:
    """Generate a random Discord color"""
    return discord.Colour.from_rgb(
        random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
    )


def resource_path(*parts: str) -> Path:
    """Build an absolute path inside the resources directory"""
    return RESOURCES_DIR.joinpath(*parts)


def get_win_status(choice_bot: str, choice_user: str) -> RpsResult:
    """Determine RPS game result"""
    if choice_bot == "r":
        if choice_user == "r":
            return RpsResult.TIE
        elif choice_user == "p":
            return RpsResult.USER_WIN
        elif choice_user == "s":
            return RpsResult.BOT_WIN
    elif choice_bot == "p":
        if choice_user == "r":
            return RpsResult.BOT_WIN
        elif choice_user == "p":
            return RpsResult.TIE
        elif choice_user == "s":
            return RpsResult.USER_WIN
    elif choice_bot == "s":
        if choice_user == "r":
            return RpsResult.USER_WIN
        elif choice_user == "p":
            return RpsResult.BOT_WIN
        elif choice_user == "s":
            return RpsResult.TIE
    return RpsResult.ERROR


def get_choice_name(choice: str) -> str:
    """Get full name of RPS choice"""
    choices = {"r": "Rock", "p": "Paper", "s": "Scissors"}
    return choices.get(choice, "Unknown")


def get_random_integer(max_inclusive: int, min_inclusive: int) -> int:
    """Get random integer between min and max (inclusive)"""
    if max_inclusive == min_inclusive:
        return max_inclusive
    if max_inclusive < min_inclusive:
        return 0
    val = random.randint(min_inclusive, max_inclusive)
    return val


def solve_expression(expr: str) -> ExpressionResult:
    """Evaluate a mathematical expression"""
    try:
        # Check for invalid characters
        if not all(c.isdigit() or c in "+-*/%^(). " for c in expr):
            return ExpressionResult(
                success=False, error="Invalid characters in expression"
            )

        # Check for mismatched parentheses
        if expr.count("(") != expr.count(")"):
            return ExpressionResult(
                success=False, error="Mismatched parentheses in expression"
            )

        # P in PEMDAS
        if expr.count("(") > 0:
            # We will check for valid opening and closing parentheses then recursively pass smaller expression
            parentheses_groups = _get_top_parentheses_groups(expr)
            for group in parentheses_groups:
                group_result = solve_expression(group)
                if not group_result.success:
                    return group_result
                # Replace the parentheses group with its result in the original expression
                expr = expr.replace(f"({group})", str(group_result.result), 1)
            # A no-parentheses combinational sub-end portion
            return solve_expression(expr)
        else:
            # A no-parentheses end portion
            expr = expr.replace(" ", "")  # Sanitise spaces
            operators: list[str] = [c for c in expr if c in "+-*/%^"]
            # A robust regular expression for finding decimals and integers
            # Pattern explanation:
            # \d*\.\d+|\d+\.? : matches numbers with or without decimals
            operands: list[Decimal] = [
                Decimal(c) for c in re.findall(r"\d*\.\d+|\d+\.?", expr)
            ]

            # Handle leading negative numbers and negative numbers after operators
            i = 0
            sampledExprForRealtimeUpdates = expr
            while i < len(operators):
                op = operators[i]
                if op == "-":
                    nthMinus = operators[:i].count("-")
                    allMinusIndexes = [i for i, c in enumerate(sampledExprForRealtimeUpdates) if c == "-"]
                    indexOfThisMinus = allMinusIndexes[nthMinus]
                    if indexOfThisMinus > 0 and sampledExprForRealtimeUpdates[indexOfThisMinus - 1] in "+-*/%^":
                        operands[i] = -operands[i]  # Handle negative after operator
                        operators.pop(i)  # Remove negative for the number
                        sampledExprForRealtimeUpdates = sampledExprForRealtimeUpdates[:indexOfThisMinus] + sampledExprForRealtimeUpdates[indexOfThisMinus + 1:]  # Remove the minus from the sampled expression for accurate indexing
                        # No increment when pop because in-place shift
                    elif indexOfThisMinus == 0:
                        operands[i] = -operands[i]  # Handle first/lone leading negative
                        operators.pop(i)  # Remove negative for the number
                        sampledExprForRealtimeUpdates = sampledExprForRealtimeUpdates[1:]  # Remove the minus from the sampled expression for accurate indexing
                        # No increment when pop because in-place shift
                    else:
                        i += 1  # Normal subtraction operator, move to next
                else:
                    i += 1  # Not a minus operator, move to next

            if len(operators) + 1 != len(operands):
                return ExpressionResult(
                    success=False, error="Invalid expression format"
                )
            if len(operators) == 0 and len(operands) == 1:
                return ExpressionResult(
                    success=True, result=operands[0]
                )  # Single number expression

            # EMD in PEMDAS
            i = 0
            while i < len(operators):
                op = operators[i]
                if op == "*":
                    operands[i] = operands[i] * operands[i + 1]
                    operands.pop(i + 1)
                    operators.pop(i)
                elif op == "/":
                    operands[i] = operands[i] / operands[i + 1]
                    operands.pop(i + 1)
                    operators.pop(i)
                elif op == "%":
                    operands[i] = operands[i] % operands[i + 1]
                    operands.pop(i + 1)
                    operators.pop(i)
                elif op == "^":
                    operands[i] = operands[i] ** operands[i + 1]
                    operands.pop(i + 1)
                    operators.pop(i)
                else:
                    i += 1  # No increment when pop because in-place shift, increment when skip

            if len(operators) == 0 and len(operands) == 1:
                return ExpressionResult(
                    success=True, result=operands[0]
                )  # Single number expression after EMD

            # AS in PEMDAS
            i = 0
            while i < len(operators):
                op = operators[i]
                if op == "+":
                    operands[i] = operands[i] + operands[i + 1]
                    operands.pop(i + 1)
                    operators.pop(i)
                elif op == "-":
                    operands[i] = operands[i] - operands[i + 1]
                    operands.pop(i + 1)
                    operators.pop(i)
                else:
                    i += 1  # No increment when pop because in-place shift, increment when skip

            return ExpressionResult(success=True, result=operands[0])
    except Exception as e:
        return ExpressionResult(success=False, error=str(e))


def _get_top_parentheses_groups(expr: str) -> list[str]:
    """Get top-level parentheses groups in an expression"""
    groups: list[str] = []
    stack: list[int] = []
    for i, char in enumerate(expr):
        if char == "(":
            stack.append(i)
        elif char == ")" and stack:
            start = stack.pop()
            if not stack:  # Only consider top-level groups
                groups.append(
                    expr[(start + 1):i]
                )  # Remove parentheses from group (exclusive selection)
    return groups


def get_random_work() -> str:
    """Get a random work message"""
    return random.choice(WORKS)


def refresh_replies(settings: str):
    """Refresh custom replies in database"""

    def refresh():
        try:
            client = pymongo.MongoClient(settings)
            db = client["UnknownDatabase"]
            collection = db["UnknownCollection"]

            doc = {
                "name": "reply",
                "key": list(custom_replies.keys()),
                "val": list(custom_replies.values()),
            }

            if collection.count_documents({"name": "reply"}) > 0:
                collection.replace_one({"name": "reply"}, doc)
            else:
                collection.insert_one(doc)
            client.close()
        except Exception as e:
            print(f"Error refreshing replies: {e}")

    import threading

    threading.Thread(target=refresh, daemon=True).start()


def refresh_user_settings(settings: str, user_settings_map: Dict[int, UserSettings]):
    """Refresh user settings in database"""

    def refresh():
        try:
            client = pymongo.MongoClient(settings)
            db = client["UnknownDatabase"]
            collection = db["UnknownCollection"]

            settings_list = []
            for user_settings in user_settings_map.values():
                settings_list.append(
                    {
                        "dm": user_settings.bank_dm_enabled,
                        "passive": user_settings.bank_passive_enabled,
                    }
                )

            doc = {
                "name": "usersettings",
                "key": list(user_settings_map.keys()),
                "val": settings_list,
            }

            if collection.count_documents({"name": "usersettings"}) > 0:
                collection.replace_one({"name": "usersettings"}, doc)
            else:
                collection.insert_one(doc)
            client.close()
        except Exception as e:
            print(f"Error refreshing user settings: {e}")

    import threading

    threading.Thread(target=refresh, daemon=True).start()


def refresh_balances(settings: str):
    """Refresh balances in database"""

    def refresh():
        try:
            client = pymongo.MongoClient(settings)
            db = client["UnknownDatabase"]
            collection = db["UnknownCollection"]

            doc = {
                "name": "balance",
                "key": list(balance_map.keys()),
                "val": list(balance_map.values()),
            }

            if collection.count_documents({"name": "balance"}) > 0:
                collection.replace_one({"name": "balance"}, doc)
            else:
                collection.insert_one(doc)
            client.close()
        except Exception as e:
            print(f"Error refreshing balances: {e}")

    import threading

    threading.Thread(target=refresh, daemon=True).start()


def refresh_works(settings: str, user_worked_times: Dict[int, datetime]):
    """Refresh work times in database"""

    def refresh():
        try:
            client = pymongo.MongoClient(settings)
            db = client["UnknownDatabase"]
            collection = db["UnknownCollection"]

            dates = [dt for dt in user_worked_times.values()]
            doc = {"name": "work", "key": list(user_worked_times.keys()), "val": dates}

            if collection.count_documents({"name": "work"}) > 0:
                collection.replace_one({"name": "work"}, doc)
            else:
                collection.insert_one(doc)
            client.close()
        except Exception as e:
            print(f"Error refreshing works: {e}")

    import threading

    threading.Thread(target=refresh, daemon=True).start()


def refresh_robs(settings: str, user_robbed_times: Dict[int, datetime]):
    """Refresh rob times in database"""

    def refresh():
        try:
            client = pymongo.MongoClient(settings)
            db = client["UnknownDatabase"]
            collection = db["UnknownCollection"]

            dates = [dt for dt in user_robbed_times.values()]
            doc = {"name": "rob", "key": list(user_robbed_times.keys()), "val": dates}

            if collection.count_documents({"name": "rob"}) > 0:
                collection.replace_one({"name": "rob"}, doc)
            else:
                collection.insert_one(doc)
            client.close()
        except Exception as e:
            print(f"Error refreshing robs: {e}")

    import threading

    threading.Thread(target=refresh, daemon=True).start()


def refresh_dailies(settings: str, user_daily_times: Dict[int, datetime]):
    """Refresh daily times in database"""

    def refresh():
        try:
            client = pymongo.MongoClient(settings)
            db = client["UnknownDatabase"]
            collection = db["UnknownCollection"]

            dates = [dt for dt in user_daily_times.values()]
            doc = {"name": "daily", "key": list(user_daily_times.keys()), "val": dates}

            if collection.count_documents({"name": "daily"}) > 0:
                collection.replace_one({"name": "daily"}, doc)
            else:
                collection.insert_one(doc)
            client.close()
        except Exception as e:
            print(f"Error refreshing dailies: {e}")

    import threading

    threading.Thread(target=refresh, daemon=True).start()


def refresh_weeklies(settings: str, user_weekly_times: Dict[int, datetime]):
    """Refresh weekly times in database"""

    def refresh():
        try:
            client = pymongo.MongoClient(settings)
            db = client["UnknownDatabase"]
            collection = db["UnknownCollection"]

            dates = [dt for dt in user_weekly_times.values()]
            doc = {
                "name": "weekly",
                "key": list(user_weekly_times.keys()),
                "val": dates,
            }

            if collection.count_documents({"name": "weekly"}) > 0:
                collection.replace_one({"name": "weekly"}, doc)
            else:
                collection.insert_one(doc)
            client.close()
        except Exception as e:
            print(f"Error refreshing weeklies: {e}")

    import threading

    threading.Thread(target=refresh, daemon=True).start()


def refresh_monthlies(settings: str, user_monthly_times: Dict[int, datetime]):
    """Refresh monthly times in database"""

    def refresh():
        try:
            client = pymongo.MongoClient(settings)
            db = client["UnknownDatabase"]
            collection = db["UnknownCollection"]

            dates = [dt for dt in user_monthly_times.values()]
            doc = {
                "name": "monthly",
                "key": list(user_monthly_times.keys()),
                "val": dates,
            }

            if collection.count_documents({"name": "monthly"}) > 0:
                collection.replace_one({"name": "monthly"}, doc)
            else:
                collection.insert_one(doc)
            client.close()
        except Exception as e:
            print(f"Error refreshing monthlies: {e}")

    import threading

    threading.Thread(target=refresh, daemon=True).start()


def refresh_warns(settings: str):
    """Refresh warns in database"""

    def refresh():
        try:
            client = pymongo.MongoClient(settings)
            db = client["UnknownDatabase"]
            collection = db["UnknownCollection"]

            docs = []
            for map_val in warn_map.values():
                warns = []
                for warn in map_val.values():
                    warns.append(
                        {
                            "id": warn.user_id,
                            "warns": warn.warns,
                            "causes": warn.warn_causes,
                        }
                    )
                docs.append({"key": list(map_val.keys()), "val": warns})

            doc = {"name": "warn", "key": list(warn_map.keys()), "val": docs}

            if collection.count_documents({"name": "warn"}) > 0:
                collection.replace_one({"name": "warn"}, doc)
            else:
                collection.insert_one(doc)
            client.close()
        except Exception as e:
            print(f"Error refreshing warns: {e}")

    import threading

    threading.Thread(target=refresh, daemon=True).start()


async def credit_balance(
    credit_amount: int,
    interaction: discord.Interaction,
    settings: str,
    user_settings_map: Dict[int, UserSettings],
    balance_map: Dict[int, int],
) -> bool:
    """Credit balance to user's account"""
    if interaction.user.id not in balance_map:
        balance_map[interaction.user.id] = 0
        refresh_balances(settings)

    old_bal = balance_map[interaction.user.id]
    if credit_amount > 0:
        new_bal = old_bal + credit_amount
        balance_map[interaction.user.id] = new_bal

        if (
            interaction.user.id in user_settings_map
            and user_settings_map[interaction.user.id].bank_dm_enabled
        ):
            try:
                embed = discord.Embed(
                    title="Successfully updated account! Details:-",
                    color=get_random_color(),
                )
                embed.add_field(name="Opening Balance", value=f":coin: {old_bal}")
                embed.add_field(name="Deposited", value=f":coin: {credit_amount}")
                embed.add_field(name="Closing Balance", value=f":coin: {new_bal}")
                await interaction.user.send(embed=embed)
            except Exception as e:
                print(f"Error sending DM: {e}")

        refresh_balances(settings)
        return True
    else:
        embed = discord.Embed(
            title="Error!",
            description="Value should be more than 0.",
            color=get_random_color(),
        )
        await interaction.response.send_message(embed=embed)
    return False


async def credit_balance_for_different_user(
    credit_amount: int,
    user: discord.User,
    interaction: discord.Interaction,
    settings: str,
    user_settings_map: Dict[int, UserSettings],
    balance_map: Dict[int, int],
) -> bool:
    """Credit balance to user's account"""
    if user.id not in balance_map:
        balance_map[user.id] = 0
        refresh_balances(settings)

    old_bal = balance_map[user.id]
    if credit_amount > 0:
        new_bal = old_bal + credit_amount
        balance_map[user.id] = new_bal

        if user.id in user_settings_map and user_settings_map[user.id].bank_dm_enabled:
            try:
                embed = discord.Embed(
                    title="Successfully updated account! Details:-",
                    color=get_random_color(),
                )
                embed.add_field(name="Opening Balance", value=f":coin: {old_bal}")
                embed.add_field(name="Deposited", value=f":coin: {credit_amount}")
                embed.add_field(name="Closing Balance", value=f":coin: {new_bal}")
                await user.send(embed=embed)
            except Exception as e:
                print(f"Error sending DM: {e}")

        refresh_balances(settings)
        return True
    else:
        embed = discord.Embed(
            title="Error!",
            description="Value should be more than 0.",
            color=get_random_color(),
        )
        await interaction.response.send_message(embed=embed)
    return False


async def debit_balance(
    debit_amount: int,
    interaction: discord.Interaction,
    settings: str,
    user_settings_map: Dict[int, UserSettings],
    balance_map: Dict[int, int],
) -> bool:
    """Debit balance from user's account"""
    if interaction.user.id not in balance_map:
        balance_map[interaction.user.id] = 0
        refresh_balances(settings)

    old_bal = balance_map[interaction.user.id]
    if debit_amount > 0:
        if debit_amount <= old_bal:
            new_bal = old_bal - debit_amount
            balance_map[interaction.user.id] = new_bal

            if (
                interaction.user.id in user_settings_map
                and user_settings_map[interaction.user.id].bank_dm_enabled
            ):
                try:
                    embed = discord.Embed(
                        title="Successfully updated account! Details:-",
                        color=get_random_color(),
                    )
                    embed.add_field(name="Opening Balance", value=f":coin: {old_bal}")
                    embed.add_field(name="Withdrawn", value=f":coin: {debit_amount}")
                    embed.add_field(name="Closing Balance", value=f":coin: {new_bal}")
                    await interaction.user.send(embed=embed)
                except Exception as e:
                    print(f"Error sending DM: {e}")

            refresh_balances(settings)
            return True
        elif old_bal == 0:
            embed = discord.Embed(
                title="Error!",
                description="You can't withdraw, because you have no money!",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                title="Error!",
                description="You can't withdraw more than you have in your bank!",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(
            title="Error!",
            description="Value should be more than 0.",
            color=get_random_color(),
        )
        await interaction.response.send_message(embed=embed)
    return False


async def debit_balance_for_different_user(
    debit_amount: int,
    user: discord.User,
    interaction: discord.Interaction,
    settings: str,
    user_settings_map: Dict[int, UserSettings],
    balance_map: Dict[int, int],
) -> bool:
    """Debit balance from user's account"""
    if user.id not in balance_map:
        balance_map[user.id] = 0
        refresh_balances(settings)

    old_bal = balance_map[user.id]
    if debit_amount > 0:
        if debit_amount <= old_bal:
            new_bal = old_bal - debit_amount
            balance_map[user.id] = new_bal

            if (
                user.id in user_settings_map
                and user_settings_map[user.id].bank_dm_enabled
            ):
                try:
                    embed = discord.Embed(
                        title="Successfully updated account! Details:-",
                        color=get_random_color(),
                    )
                    embed.add_field(name="Opening Balance", value=f":coin: {old_bal}")
                    embed.add_field(name="Withdrawn", value=f":coin: {debit_amount}")
                    embed.add_field(name="Closing Balance", value=f":coin: {new_bal}")
                    await user.send(embed=embed)
                except Exception as e:
                    print(f"Error sending DM: {e}")

            refresh_balances(settings)
            return True
        elif old_bal == 0:
            embed = discord.Embed(
                title="Error!",
                description="He can't withdraw, because he has no money!",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                title="Error!",
                description="He can't withdraw more than he has in his bank!",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(
            title="Error!",
            description="Value should be more than 0.",
            color=get_random_color(),
        )
        await interaction.response.send_message(embed=embed)
    return False
