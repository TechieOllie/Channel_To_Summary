from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands

import config
import storage
from summarizer import fetch_messages_for_day, generate_summary

logger = logging.getLogger(__name__)


def _admin_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "You need the **Manage Channels** permission to use this command.",
                ephemeral=True,
            )
            return False
        return True
    return app_commands.check(predicate)


def _summary_embed(title: str, summary: str, msg_count: int, color: discord.Color) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=summary,
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text=f"{msg_count} messages")
    return embed


async def _send_summary(
    channel: discord.TextChannel,
    embed: discord.Embed,
    notify_channel: discord.TextChannel | None = None,
) -> discord.Message:
    msg = await channel.send(embed=embed)
    if notify_channel:
        link = f"https://discord.com/channels/{channel.guild.id}/{channel.id}/{msg.id}"
        try:
            await notify_channel.send(
                f"📋 Résumé des discussions posté dans {channel.mention} : {link}"
            )
        except Exception:
            logger.exception("Failed to send cross-post notification")
    return msg


async def _summary_for_channel(
    channel: discord.TextChannel,
    guild: discord.Guild,
    today: str,
    summary_ch: discord.TextChannel | None,
) -> str:
    try:
        messages = await fetch_messages_for_day(channel)
    except discord.Forbidden:
        logger.warning("No read perms for %s", channel)
        return "error"
    except Exception:
        logger.exception("Failed to fetch messages for %s", channel)
        return "error"

    if not messages:
        logger.info("Skipping %s — no messages today", channel)
        return "empty"

    try:
        summary = await generate_summary(messages, channel.name, guild.name)
    except Exception:
        logger.exception("Failed to generate summary for %s", channel)
        return "error"

    storage.save_summary(guild.id, channel.id, today, summary, len(messages))

    embed = _summary_embed(
        f"📋 Résumé du #{channel.name}",
        summary,
        len(messages),
        discord.Color.green(),
    )

    dest = summary_ch or channel
    try:
        await _send_summary(dest, embed, notify_channel=channel if summary_ch else None)
    except discord.HTTPException as e:
        logger.error("Failed to send summary to %s: %s", dest, e)
        return "error"
    return "ok"


class SummaryGroup(app_commands.Group):
    @app_commands.command(name="enable", description="Activer les résumés quotidiens pour ce salon")
    @_admin_only()
    async def enable(self, interaction: discord.Interaction):
        assert interaction.guild
        storage.set_channel_enabled(interaction.guild.id, interaction.channel_id, True)
        await interaction.response.send_message(
            f"✅ Résumés quotidiens activés pour {interaction.channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(name="disable", description="Désactiver les résumés quotidiens pour ce salon")
    @_admin_only()
    async def disable(self, interaction: discord.Interaction):
        assert interaction.guild
        storage.set_channel_enabled(interaction.guild.id, interaction.channel_id, False)
        await interaction.response.send_message(
            f"❌ Résumés quotidiens désactivés pour {interaction.channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(name="list", description="Lister l'état des résumés par salon")
    async def list_channels(self, interaction: discord.Interaction):
        assert interaction.guild
        settings = storage.get_all_channel_settings(interaction.guild.id)
        enabled = []
        disabled = []
        for s in settings:
            ch = interaction.guild.get_channel(s["channel_id"])
            label = ch.mention if ch else f"`{s['channel_id']}`"
            (enabled if s["enabled"] else disabled).append(label)

        all_text = [
            c for c in interaction.guild.text_channels
            if c.permissions_for(interaction.guild.me).read_message_history
        ]
        set_ids = {s["channel_id"] for s in settings}
        unset = [c.mention for c in all_text if c.id not in set_ids]

        lines = [f"**Résumés — {interaction.guild.name}**"]
        lines.append(f"\n✅ **Activé ({len(enabled)}):**")
        lines.append(", ".join(enabled) if enabled else "Aucun")
        lines.append(f"\n❌ **Désactivé ({len(disabled)}):**")
        lines.append(", ".join(disabled) if disabled else "Aucun")
        if unset:
            lines.append(f"\n⚪ **Non défini ({len(unset)}):**")
            lines.append(", ".join(unset[:20]))
            if len(unset) > 20:
                lines.append(f"  … et {len(unset) - 20} autres")

        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="now", description="Générer un résumé maintenant pour ce salon")
    async def now(self, interaction: discord.Interaction):
        assert interaction.guild
        await interaction.response.defer(ephemeral=True)

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("Cette commande fonctionne uniquement dans les salons textuels.", ephemeral=True)
            return

        await interaction.followup.send(
            f"⏳ Récupération des messages de {channel.mention}…",
            ephemeral=True,
        )

        summary_ch_id = storage.get_summary_channel(interaction.guild.id)
        summary_ch = interaction.guild.get_channel(summary_ch_id) if summary_ch_id else None

        status = await _summary_for_channel(
            channel,
            interaction.guild,
            datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            summary_ch,
        )

        if status == "empty":
            await interaction.followup.send(
                f"📭 Aucun message aujourd'hui dans {channel.mention}.",
                ephemeral=True,
            )
            return

        if status == "error":
            await interaction.followup.send(
                f"❌ Une erreur est survenue lors de la génération du résumé pour {channel.mention}.",
                ephemeral=True,
            )
            return

        if summary_ch:
            await interaction.followup.send(
                f"✅ Résumé posté dans {summary_ch.mention} "
                f"(notification envoyée dans {channel.mention}).",
                ephemeral=True,
            )
        else:
            await interaction.followup.send("✅ Résumé généré.", ephemeral=True)

    @app_commands.command(
        name="setchannel",
        description="Définir le salon dédié aux résumés",
    )
    @_admin_only()
    async def set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        assert interaction.guild
        storage.set_summary_channel(interaction.guild.id, channel.id)
        await interaction.response.send_message(
            f"📌 Tous les résumés seront postés dans {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="status",
        description="Voir si les résumés sont activés pour ce salon",
    )
    async def status(self, interaction: discord.Interaction):
        assert interaction.guild
        enabled = storage.is_channel_enabled(interaction.guild.id, interaction.channel_id)
        emoji = "✅" if enabled else "❌"
        texte = "activés" if enabled else "désactivés"
        await interaction.response.send_message(
            f"{emoji} Les résumés sont **{texte}** pour {interaction.channel.mention}.",
            ephemeral=True,
        )


class SummaryBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.tree.add_command(SummaryGroup(name="summary", description="Gérer les résumés quotidiens"))

    async def on_ready(self):
        logger.info("Bot connecté — %s (ID: %s)", self.user, self.user.id)
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="les salons | /summary",
            )
        )

    async def setup_hook(self):
        await self.tree.sync()
        self.daily_task = asyncio.create_task(self._daily_scheduler())

    async def _daily_scheduler(self):
        await self.wait_until_ready()
        while not self.is_closed():
            now = datetime.now(timezone.utc)
            target_h, target_m = map(int, config.SUMMARY_TIME.split(":"))
            target = now.replace(hour=target_h, minute=target_m, second=0, microsecond=0)

            if target <= now:
                target += timedelta(days=1)

            delay = (target - now).total_seconds()
            logger.info("Prochain résumé à %s (dans %.0f s)", target.isoformat(), delay)
            await asyncio.sleep(delay)

            if self.is_closed():
                break

            try:
                await self._run_all_summaries()
            except Exception:
                logger.exception("Erreur lors des résumés quotidiens")

    async def _run_all_summaries(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        logger.info("Génération des résumés pour %s", today)

        for guild in self.guilds:
            enabled_ids = storage.get_enabled_channels(guild.id)
            if not enabled_ids:
                continue

            summary_ch_id = storage.get_summary_channel(guild.id)
            summary_ch = guild.get_channel(summary_ch_id) if summary_ch_id else None

            for channel_id in enabled_ids:
                channel = guild.get_channel(channel_id)
                if not isinstance(channel, discord.TextChannel):
                    continue

                perms = channel.permissions_for(guild.me)
                if not perms.read_message_history or not perms.read_messages:
                    logger.warning("Impossible de lire %s", channel)
                    continue

                await _summary_for_channel(channel, guild, today, summary_ch)
                await asyncio.sleep(1)
