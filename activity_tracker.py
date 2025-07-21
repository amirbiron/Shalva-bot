from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import List, Optional

import discord
from discord.ext import commands
from pymongo import ASCENDING, DESCENDING, MongoClient

# MongoDB connection string (replace with secure retrieval in production)
MONGO_URI: str = "mongodb+srv://username:password@cluster.mongodb.net/"

# Database/Collection names
DB_NAME: str = "ShalvaBotDB"
COLLECTION_NAME: str = "users"


def human_timedelta_hebrew(past: datetime, now: Optional[datetime] = None) -> str:
    """Return a human-readable relative time difference in Hebrew."""
    now = now or datetime.utcnow()
    delta = now - past
    minutes = int(delta.total_seconds() // 60)
    if minutes < 60:
        return f"לפני {minutes} דקות" if minutes != 1 else "לפני דקה"

    hours = minutes // 60
    if hours < 24:
        return f"לפני {hours} שעות" if hours != 1 else "לפני שעה"

    days = hours // 24
    return f"לפני {days} ימים" if days != 1 else "לפני יום"


class MongoActivityTracker(commands.Cog):
    """Discord Cog that tracks user activity and stores it in MongoDB."""

    # ------------------------------------------------------------------
    # Owner-only configuration & checks
    # ------------------------------------------------------------------
    YOUR_USER_ID = 123456789  # החלף במספר המשתמש שלך

    def is_owner():
        """Return a commands.check that allows only the bot owner to run the command."""

        def predicate(ctx):
            return ctx.author.id == MongoActivityTracker.YOUR_USER_ID

        return commands.check(predicate)

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Establish MongoDB connection
        self.client: MongoClient = MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        self.collection = self.db[COLLECTION_NAME]

        # Ensure indexes
        self.collection.create_index([("user_id", ASCENDING)], unique=True)
        self.collection.create_index([("last_activity", DESCENDING)])

    # ---------------------------------------------------------------------
    # Listeners
    # ---------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Track every non-bot message and update MongoDB accordingly."""
        if message.author.bot:
            return  # Ignore bot messages

        author = message.author
        payload = {
            "$set": {
                "username": str(author),  # Includes discriminator if present
                "last_activity": datetime.utcnow(),
            },
            "$inc": {"total_messages": 1},
        }
        self.collection.update_one({"user_id": author.id}, payload, upsert=True)

    # ---------------------------------------------------------------------
    # Commands
    # ---------------------------------------------------------------------
    @commands.command(
        name="recent_users",
        aliases=["recent", "משתמשים_אחרונים", "פעילים"],
        help="מציג משתמשים פעילים ב־X הימים האחרונים (ברירת מחדל 7)."
    )
    @is_owner()
    async def recent_users(self, ctx: commands.Context, days: int = 7):
        """Show users active within the last X days."""
        threshold = datetime.utcnow() - timedelta(days=days)
        cursor = (
            self.collection
            .find({"last_activity": {"$gte": threshold}})
            .sort("last_activity", DESCENDING)
        )
        users: List[dict] = list(cursor)

        if not users:
            await ctx.send("לא נמצאו משתמשים פעילים בטווח הזמן המבוקש.")
            return

        embed = discord.Embed(
            title=f"משתמשים פעילים ב־{days} הימים האחרונים",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )

        for user in users:
            last_activity = user.get("last_activity")
            relative = human_timedelta_hebrew(last_activity)
            embed.add_field(
                name=user.get("username", str(user["user_id"])),
                value=f"{relative} | סה""כ הודעות: {user.get('total_messages', 0)}",
                inline=False,
            )

        await ctx.send(embed=embed)

    @commands.command(
        name="user_info",
        aliases=["info", "מידע_משתמש"],
        help="מציג מידע על משתמש ספציפי."
    )
    @is_owner()
    async def user_info(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Display stored activity details for a specific user."""
        member = member or ctx.author
        record = self.collection.find_one({"user_id": member.id})

        if record is None:
            await ctx.send("לא נמצאה פעילות עבור המשתמש.")
            return

        embed = discord.Embed(
            title=f"מידע על {member}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="מזהה", value=str(record["user_id"]))
        embed.add_field(name="שם משתמש", value=record.get("username", "N/A"), inline=False)
        embed.add_field(
            name="הודעה אחרונה",
            value=human_timedelta_hebrew(record["last_activity"]),
            inline=False,
        )
        embed.add_field(
            name="סה""כ הודעות",
            value=str(record.get("total_messages", 0)),
            inline=False,
        )

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """Called by discord.py to add the cog."""
    await bot.add_cog(MongoActivityTracker(bot))