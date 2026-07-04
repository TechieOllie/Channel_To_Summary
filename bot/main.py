import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from .config import Config
from .memory import Memory
from .summarizer import Summarizer

log = logging.getLogger(__name__)

# ------------------------------------------------------------------
# slash command group  (/summary …)
# ------------------------------------------------------------------

summary_group = app_commands.Group(
    name="summary",
    description="Gérer les résumés quotidiens des salons",
    guild_only=True,
)


@summary_group.command(name="add", description="Ajouter un salon à résumer quotidiennement")
@app_commands.describe(
    channel="Salon à résumer",
    mode="Où publier le résumé",
    destination="Salon dédié (obligatoire si mode = dedicated)",
)
@app_commands.choices(mode=[
    app_commands.Choice(name="Dans le même salon", value="same"),
    app_commands.Choice(name="Salon dédié", value="dedicated"),
])
@app_commands.checks.has_permissions(manage_channels=True)
async def _cmd_add(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    mode: app_commands.Choice[str] | None = None,
    destination: discord.TextChannel | None = None,
):
    bot: ChannelToSummary = interaction.client

    post_in_channel = True
    dest_id = None
    if mode and mode.value == "dedicated":
        if destination is None:
            await interaction.response.send_message(
                "❌ Tu dois spécifier un salon de destination quand le mode est « dedicated ».",
                ephemeral=True,
            )
            return
        post_in_channel = False
        dest_id = destination.id

    bot.memory.set_channel_config(channel.id, post_in_channel, dest_id)
    dest_info = f"<#{channel.id}>" if post_in_channel else f"<#{dest_id}>"
    await interaction.response.send_message(
        f"✅ Salon <#{channel.id}> ajouté – résumé publié dans {dest_info}.",
        ephemeral=True,
    )


@summary_group.command(name="remove", description="Supprimer un salon de la liste")
@app_commands.describe(channel="Salon à ne plus résumer")
@app_commands.checks.has_permissions(manage_channels=True)
async def _cmd_remove(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
):
    bot: ChannelToSummary = interaction.client
    bot.memory.remove_channel_config(channel.id)
    await interaction.response.send_message(
        f"✅ Salon <#{channel.id}> retiré de la liste.",
        ephemeral=True,
    )


@summary_group.command(name="list", description="Lister les salons configurés")
async def _cmd_list(interaction: discord.Interaction):
    bot: ChannelToSummary = interaction.client
    channels = bot.memory.get_channel_configs()
    if not channels:
        await interaction.response.send_message(
            "Aucun salon configuré. Utilise `/summary add` pour en ajouter un.",
            ephemeral=True,
        )
        return

    lines = []
    for ch in channels:
        dest = f"<#{ch['channel_id']}>" if ch["post_in_channel"] else f"<#{ch['summary_channel_id']}>"
        lines.append(f"- <#{ch['channel_id']}> → {dest}")
    await interaction.response.send_message(
        "**Salons configurés :**\n" + "\n".join(lines),
        ephemeral=True,
    )


@summary_group.command(name="time", description="Définir l'heure du résumé quotidien (UTC)")
@app_commands.describe(heure="Heure au format HH:MM (UTC)")
@app_commands.checks.has_permissions(manage_channels=True)
async def _cmd_time(interaction: discord.Interaction, heure: str):
    bot: ChannelToSummary = interaction.client
    if not _valid_hhmm(heure):
        await interaction.response.send_message(
            "❌ Format invalide. Utilise HH:MM (ex: 23:00).",
            ephemeral=True,
        )
        return
    bot.memory.set_setting("summary_time", heure)
    await interaction.response.send_message(
        f"✅ Heure du résumé définie à {heure} UTC.",
        ephemeral=True,
    )


@summary_group.command(name="now", description="Déclencher un résumé immédiat")
async def _cmd_now(interaction: discord.Interaction):
    bot: ChannelToSummary = interaction.client
    await interaction.response.defer(ephemeral=True)
    channels = bot.memory.get_channel_configs()
    if not channels:
        await interaction.followup.send("Aucun salon configuré.")
        return
    for ch in channels:
        try:
            await bot._summarize_channel(
                ch["channel_id"],
                ch["post_in_channel"],
                ch["summary_channel_id"],
            )
        except Exception as exc:
            log.error("Erreur canal %d : %s", ch["channel_id"], exc)
    await interaction.followup.send(f"✅ Résumé généré pour {len(channels)} salon(s).")


# ------------------------------------------------------------------
# bot class
# ------------------------------------------------------------------

class ChannelToSummary(commands.Bot):
    def __init__(self, config: Config):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="", intents=intents)

        self.bot_config = config
        self.memory = Memory()
        self.summarizer = Summarizer(config)

    async def on_message(self, message: discord.Message):
        pass  # slash commands only, ignore prefix-based processing

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    async def setup_hook(self):
        self.tree.add_command(summary_group)
        await self.tree.sync()
        self.loop.create_task(self._summary_scheduler())

    async def on_ready(self):
        log.info("Connecté en tant que %s (ID: %s)", self.user, self.user.id)

    # ------------------------------------------------------------------
    # summary scheduler
    # ------------------------------------------------------------------

    async def _summary_scheduler(self):
        await self.wait_until_ready()
        while not self.is_closed():
            target_time = self.memory.get_setting("summary_time") or "23:00"
            target_h, target_m = map(int, target_time.split(":"))
            now = datetime.now(timezone.utc)
            target = now.replace(hour=target_h, minute=target_m, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            sleep_s = (target - now).total_seconds()
            log.info("Prochain résumé à %s (dans %d s)", target.isoformat(), sleep_s)
            await asyncio.sleep(sleep_s)
            await self._summarize_all()

    async def _summarize_all(self):
        log.info("Début du cycle de résumé quotidien")
        for ch in self.memory.get_channel_configs():
            try:
                await self._summarize_channel(
                    ch["channel_id"],
                    ch["post_in_channel"],
                    ch["summary_channel_id"],
                )
            except Exception as exc:
                log.error("Erreur canal %d : %s", ch["channel_id"], exc)

    # ------------------------------------------------------------------
    # core summarization
    # ------------------------------------------------------------------

    async def _summarize_channel(
        self,
        channel_id: int,
        post_in_channel: bool,
        summary_channel_id: int | None,
    ):
        channel = self.get_channel(channel_id)
        if not channel:
            log.warning("Canal %d introuvable", channel_id)
            return

        after = datetime.now(timezone.utc) - timedelta(days=1)
        user_map: dict[str, int] = {}
        messages: list[dict] = []

        async for msg in channel.history(limit=500, after=after):
            if msg.author.bot:
                continue
            user_map[msg.author.name] = msg.author.id
            nick = getattr(msg.author, "nick", None)
            if nick:
                user_map[nick] = msg.author.id
            messages.append({
                "author_name": msg.author.name,
                "content": msg.content,
            })

        messages.reverse()
        if not messages:
            log.info("Aucun message dans le canal %d, ignoré", channel_id)
            return

        prev = self.memory.get_recent_summaries(channel_id)
        summary = await self.summarizer.summarize(
            channel.name, messages, user_map, prev,
        )

        for name, uid in sorted(user_map.items(), key=lambda x: -len(x[0])):
            summary = summary.replace(f"@{name}", f"<@{uid}>")

        self.memory.save_summary(channel_id, summary, len(messages))

        header = f"📢 **#{channel.name}**\n"
        content = header + summary

        if post_in_channel:
            await channel.send(content)
        elif summary_channel_id:
            dest = self.get_channel(summary_channel_id)
            if dest:
                await dest.send(content)
            else:
                log.warning("Canal de destination %d introuvable", summary_channel_id)
                await channel.send(content)
        else:
            await channel.send(content)

        log.info("Résumé posté pour le canal %d (%d messages)", channel_id, len(messages))


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------

def _valid_hhmm(s: str) -> bool:
    try:
        h, m = map(int, s.split(":"))
        return 0 <= h <= 23 and 0 <= m <= 59
    except (ValueError, AttributeError):
        return False


def main():
    config = Config()
    bot = ChannelToSummary(config)
    bot.run(config.token)
