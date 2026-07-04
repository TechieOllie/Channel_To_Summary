import logging

import aiohttp

log = logging.getLogger(__name__)


MODEL = "qwen2.5:3b"


class Summarizer:
    def __init__(self, config):
        self.url = config.ollama_url.rstrip("/")

    async def summarize(
        self,
        channel_name: str,
        messages: list[dict],
        user_map: dict[str, int],
        previous_summaries: list[tuple[str, str]] | None = None,
    ) -> str:
        prompt = self._build_prompt(channel_name, messages, user_map, previous_summaries)
        log.info("Envoi de %d messages à %s", len(messages), MODEL)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.url}/api/generate",
                json={"model": MODEL, "prompt": prompt, "stream": False},
                timeout=aiohttp.ClientTimeout(total=180),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    log.error("LLM API error %d: %s", resp.status, text)
                    return "*Erreur lors de la génération du résumé.*"
                data = await resp.json()
                return data.get("response", "")

    def _build_prompt(
        self,
        channel_name: str,
        messages: list[dict],
        user_map: dict[str, int],
        previous_summaries: list[tuple[str, str]] | None,
    ) -> str:
        participants = ", ".join(sorted(f"@{name}" for name in user_map))

        conversation = "\n".join(
            f"{m['author_name']}: {m['content']}"
            for m in messages[-200:]
        )

        prev = ""
        if previous_summaries:
            prev = "Résumés précédents (ne répète PAS ces informations) :\n" + "\n---\n".join(
                s for s, _ in previous_summaries
            )

        return (
            f"Résume la conversation Discord du canal #{channel_name} aujourd'hui.\n"
            f"Style : informel, concis, va droit au but. 3-4 phrases max.\n"
            f"\n"
            f"Participants : {participants}\n"
            f"{prev}\n"
            f"Conversation :\n"
            f"{conversation}\n"
            f"\n"
            f"Écris un résumé en français, sans blabla."
            f"Cite les gens avec @nom. Ne répète pas les résumés précédents."
        )
