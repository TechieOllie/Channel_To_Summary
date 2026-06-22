from __future__ import annotations

import logging
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import discord

import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Local LLM via llama.cpp
# ---------------------------------------------------------------------------

_LLM_INSTANCE = None


def _load_llm():
    global _LLM_INSTANCE
    if _LLM_INSTANCE is not None:
        return _LLM_INSTANCE

    model_path = config.LLAMA_MODEL_PATH
    if not model_path or not os.path.exists(model_path):
        logger.warning("LLM model not found at %s — using template summarizer", model_path)
        _LLM_INSTANCE = False
        return None

    try:
        from llama_cpp import Llama
        _LLM_INSTANCE = Llama(
            model_path=model_path,
            n_ctx=4096,
            n_threads=os.cpu_count() or 4,
            verbose=False,
        )
        logger.info("LLM loaded from %s", model_path)
        return _LLM_INSTANCE
    except ImportError:
        logger.warning("llama-cpp-python not installed — using template summarizer")
        _LLM_INSTANCE = False
        return None
    except Exception:
        logger.exception("Failed to load LLM — using template summarizer")
        _LLM_INSTANCE = False
        return None


_CHATML_TEMPLATE = """<|im_start|>system
Tu résumes des conversations Discord en français. Sois concis, va à l'essentiel. Réponds uniquement avec le résumé, sans préambule.<|im_end|>
<|im_start|>user
Résumé du salon #{channel_name} aujourd'hui :

{messages}

Résumé :<|im_end|>
<|im_start|>assistant"""


def _summarize_with_llm(messages: list[discord.Message], channel_name: str) -> str | None:
    llm = _load_llm()
    if not llm:
        return None

    text_messages = [m for m in messages if m.clean_content.strip()]
    if not text_messages:
        return None

    convo = "\n".join(
        f"[{m.created_at.strftime('%H:%M')}] <@{m.author.id}> {m.author.display_name}: {m.clean_content}"
        for m in text_messages
    )
    if not convo.strip():
        return None

    if len(convo) > 3000:
        convo = convo[:3000] + "\n…"

    prompt = _CHATML_TEMPLATE.format(channel_name=channel_name, messages=convo)

    try:
        response = llm(
            prompt,
            max_tokens=256,
            temperature=0.2,
            repeat_penalty=1.2,
            stop=["<|im_end|>", "<|im_start|>"],
        )
        text = response["choices"][0]["text"].strip()
        if text:
            return text
    except Exception:
        logger.exception("LLM inference failed")

    return None


# ---------------------------------------------------------------------------
#  Stop words: French + English (template fallback only)
# ---------------------------------------------------------------------------

_STOP_WORDS: set[str] | None = None


def _get_stop_words() -> set[str]:
    global _STOP_WORDS
    if _STOP_WORDS is not None:
        return _STOP_WORDS

    _STOP_WORDS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "shall", "can",
        "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above",
        "below", "between", "out", "off", "over", "under", "again",
        "further", "then", "once", "here", "there", "when", "where",
        "why", "how", "all", "each", "every", "both", "few", "more",
        "most", "other", "some", "such", "no", "nor", "not", "only",
        "own", "same", "so", "than", "too", "very", "just", "because",
        "and", "but", "or", "if", "while", "that", "this", "these",
        "those", "it", "its", "i", "me", "my", "we", "our", "you",
        "your", "he", "him", "his", "she", "her", "they", "them",
        "their", "what", "which", "who", "whom",
        "le", "la", "les", "un", "une", "des", "du", "de", "ce",
        "cet", "cette", "ces", "mon", "ton", "son", "ma", "ta", "sa",
        "mes", "tes", "ses", "nos", "vos", "leurs", "notre", "votre",
        "leur", "et", "ou", "mais", "donc", "car", "ni", "que", "qui",
        "quoi", "dont", "où", "avec", "sans", "pour", "dans", "sur",
        "sous", "par", "entre", "chez", "vers", "depuis", "pendant",
        "avant", "après", "contre", "selon", "jusque", "dès",
        "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
        "me", "te", "se", "lui", "y", "en", "ça", "celui", "celle",
        "ceux", "celles", "au", "aux", "ne", "pas", "plus", "peu",
        "très", "trop", "si", "oui", "non", "rien", "personne",
        "tout", "tous", "toute", "toutes", "chaque", "quelque",
        "quelques", "plusieurs", "certain", "certaine", "certains",
        "certaines", "même", "aussi", "bien", "mal", "comme", "car",
        "est", "sont", "ai", "a", "ont", "avons", "avez", "suis",
        "cest", "ca", "cela", "peut", "peux", "peuvent", "veut",
        "veux", "voulons", "font", "fait", "faire", "ete", "était",
        "étaient", "être", "avoir", "aller", "va", "vas", "vais",
        "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses",
        "notre", "nos", "votre", "vos", "leur", "leurs",
        "salut", "bonjour", "bonsoir", "hello", "hey", "coucou",
        "ok", "okay", "daccord", "super", "cool", "genial", "merci",
        "stp", "svp", "voila", "voilà", "oui", "non", "peutêtre",
    }
    return _STOP_WORDS


_WORD_RE = re.compile(r"[a-zA-Z\u00C0-\u024F0-9#+]{2,}")
_URL_RE = re.compile(r"https?://\S+")
_QUESTION_RE = re.compile(r".*\?\s*$")
_BUG_SIGNALS = re.compile(
    r"\b(bug|crash|erreur|error|fix|répare|réparé|casse|cassé|"
    r"plante|planté|anomalie|régress|warning|fail|échec|panne|"
    r"marche\s*pas|ne\s*marche|ne\s*fonctionne)\b",
    re.IGNORECASE,
)
_ANNOUNCEMENT_SIGNALS = re.compile(
    r"\b(annonce|prévu|prévue|dispo|disponible|prêt|prête|lancé|"
    r"déployé|déployée|sortie|release|livré|publié)\b",
    re.IGNORECASE,
)
_TIME_GAP_MINUTES = 25


async def fetch_messages_for_day(
    channel: discord.TextChannel, date: datetime | None = None
) -> list[discord.Message]:
    if date is None:
        date = datetime.now(timezone.utc)

    start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    messages: list[discord.Message] = []
    async for msg in channel.history(
        limit=config.MESSAGE_FETCH_LIMIT,
        after=start,
        before=end,
        oldest_first=True,
    ):
        messages.append(msg)

    return messages


# ---------------------------------------------------------------------------
#  Template-based fallback
# ---------------------------------------------------------------------------

class _Cluster(NamedTuple):
    messages: list[discord.Message]
    start: datetime
    end: datetime
    authors: list[str]


def _cluster_messages(messages: list[discord.Message]) -> list[_Cluster]:
    if not messages:
        return []

    clusters: list[list[discord.Message]] = [[messages[0]]]
    for msg in messages[1:]:
        gap = (msg.created_at - clusters[-1][-1].created_at).total_seconds() / 60
        if gap > _TIME_GAP_MINUTES:
            clusters.append([])
        clusters[-1].append(msg)

    result = []
    for c in clusters:
        seen: list[str] = []
        for m in c:
            n = m.author.display_name
            if n not in seen:
                seen.append(n)
        result.append(_Cluster(
            messages=c,
            start=c[0].created_at,
            end=c[-1].created_at,
            authors=seen,
        ))
    return result


def _extract_topic(messages: list[discord.Message]) -> str:
    stop = _get_stop_words()
    words: list[str] = []
    for m in messages:
        for w in _WORD_RE.findall(m.clean_content.lower()):
            if w not in stop:
                words.append(w)
    if not words:
        return ""
    counter = Counter(words)
    top = counter.most_common(2)
    return " ".join(w for w, c in top if c > 1) or top[0][0]


def _single_person_line(msg: discord.Message, author: str) -> str | None:
    content = msg.clean_content
    has_link = bool(_URL_RE.search(content))
    has_question = bool(_QUESTION_RE.match(content))
    has_bug = bool(_BUG_SIGNALS.search(content))
    has_announce = bool(_ANNOUNCEMENT_SIGNALS.search(content))

    if has_bug:
        return f"**{author}** a signalé un problème : « {_truncate(content, 70)} »"
    if has_announce:
        return f"**{author}** a annoncé : « {_truncate(content, 80)} »"
    if has_link:
        return f"**{author}** a partagé un lien : « {_truncate(content, 70)} »"
    if has_question:
        return f"**{author}** a demandé : « {_truncate(content, 70)} »"
    if len(content) <= 100:
        return f"**{author}** : {content}"
    return f"**{author}** : {_truncate(content, 80)}"


def _describe_cluster(cluster: _Cluster) -> str | None:
    msgs = [m for m in cluster.messages if m.clean_content.strip()]
    if not msgs:
        return None

    authors = cluster.authors
    total_reactions = sum(sum(r.count for r in m.reactions) for m in msgs)

    if len(authors) == 1:
        return _single_person_line(msgs[-1], authors[0])

    has_link = any(_URL_RE.search(m.clean_content) for m in msgs if m.clean_content)
    has_question = any(_QUESTION_RE.match(m.clean_content) for m in msgs if m.clean_content)
    has_bug = any(_BUG_SIGNALS.search(m.clean_content) for m in msgs if m.clean_content)
    topic = _extract_topic(msgs)

    labels: list[str] = []
    if has_bug:
        labels.append("bug")
    if has_question:
        labels.append("questions")
    if has_link:
        labels.append("liens")
    if total_reactions >= 2:
        labels.append(f"{total_reactions} réactions")

    a_list = _join_names(authors)
    base = f"**{a_list}** — {len(msgs)} messages"
    if topic:
        base += f" sur {topic}"
    if labels:
        base += f" ({', '.join(labels)})"

    prefix = "📌" if total_reactions >= 3 else "💬"
    return f"{prefix} {base}"


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _join_names(names: list[str]) -> str:
    if len(names) <= 2:
        return " et ".join(names)
    return ", ".join(names[:-1]) + " et " + names[-1]


def _build_summary(messages: list[discord.Message]) -> str | None:
    clusters = _cluster_messages(messages)
    lines = [txt for c in clusters if (txt := _describe_cluster(c)) is not None]
    return "\n".join(lines) if lines else None


# ---------------------------------------------------------------------------
#  Stats (used only for the footer)
# ---------------------------------------------------------------------------

def _compute_stats(messages: list[discord.Message]) -> dict:
    participants: set[str] = set()
    hourly: Counter[int] = Counter()
    reaction_count = 0

    for msg in messages:
        hourly[msg.created_at.hour] += 1
        if msg.clean_content.strip():
            participants.add(msg.author.display_name)
        reaction_count += sum(r.count for r in msg.reactions)

    busiest = hourly.most_common(1)
    return {
        "total_messages": len(messages),
        "participants": len(participants),
        "busiest_hour": busiest[0][0] if busiest else None,
        "reactions": reaction_count,
    }


# ---------------------------------------------------------------------------
#  Entry point
# ---------------------------------------------------------------------------

def _names_to_mentions(body: str, messages: list[discord.Message]) -> str:
    seen: dict[str, int] = {}
    for m in messages:
        n = m.author.display_name
        if n not in seen:
            seen[n] = m.author.id
    for name in sorted(seen, key=len, reverse=True):
        body = re.sub(rf"\b{re.escape(name)}\b", f"<@{seen[name]}>", body)
    return body


async def generate_summary(
    messages: list[discord.Message],
    channel_name: str,
    guild_name: str,
) -> str:
    if not messages:
        return "*Aucun message aujourd'hui dans ce salon.*"

    stats = _compute_stats(messages)

    body = _summarize_with_llm(messages, channel_name)
    if not body:
        body = _build_summary(messages)
    if not body:
        body = f"*{stats['total_messages']} messages échangés, aucun sujet majeur identifié.*"

    body = _names_to_mentions(body, messages)

    footer = (
        f"*{stats['total_messages']} messages · {stats['participants']} participants · "
        f"{stats['reactions']} réactions · pic à {stats['busiest_hour']:02d}:00*"
        if stats["busiest_hour"] is not None
        else f"*{stats['total_messages']} messages · {stats['participants']} participants*"
    )

    return f"{body}\n\n{footer}"
