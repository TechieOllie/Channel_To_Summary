# Channel To Summary

Bot Discord qui génère automatiquement un résumé quotidien en français pour les salons configurés, en utilisant un LLM local via Ollama.

## Fonctionnalités

- Résumé quotidien à une heure configurable (UTC)
- Résumé en français via un LLM local (Ollama — aucun appel cloud)
- Publication dans le salon d'origine ou dans un salon dédié
- Mémoire des résumés précédents pour éviter les répétitions
- Tag automatique des participants (`@utilisateur`)
- Configuration entièrement via commandes slash Discord
- Prêt pour Docker

## Prérequis

- [Docker](https://docs.docker.com/engine/install/) et [Docker Compose](https://docs.docker.com/compose/install/)
- Un token de bot Discord ([portail développeur](https://discord.com/developers/applications))
  - Activer les intents `Message Content` et `Server Members` dans la page du bot

## Installation

### 1. Créer le fichier `.env`

```bash
cp .env.example .env
```

Éditer `.env` :

```env
DISCORD_TOKEN=ton_token_ici
OLLAMA_URL=http://ollama:11434
```

### 2. Lancer les services

```bash
docker compose up -d
```

### 3. Télécharger un modèle LLM

```bash
docker compose exec ollama ollama pull qwen2.5:3b
```



### 4. Inviter le bot sur un serveur

Générer l'URL d'invitation depuis le portail développeur Discord avec les scopes `bot` et `applications.commands`, et les permissions `Send Messages`, `Read Message History`, `Manage Webhooks`.

### 5. Configurer les salons via Discord

Une fois le bot connecté, utiliser les commandes slash dans un salon où le bot est présent :

| Commande | Description |
|---|---|
| `/summary add <channel> [mode] [destination]` | Ajouter un salon à résumer |
| `/summary remove <channel>` | Retirer un salon |
| `/summary list` | Lister les salons configurés |
| `/summary time <HH:MM>` | Définir l'heure du résumé (UTC) |
| `/summary now` | Déclencher un résumé immédiat |

Exemple :

```
/summary add channel:#général mode:"Salon dédié" destination:#résumés
```

## Structure du projet

```
Channel_To_Summary/
├── bot/
│   ├── __init__.py
│   ├── __main__.py       # Point d'entrée
│   ├── config.py         # Lecture du .env
│   ├── main.py           # Bot Discord + commandes slash + scheduling
│   ├── memory.py         # Persistance SQLite
│   └── summarizer.py     # Appel à l'API Ollama
├── data/                 # Base de données (montée en volume)
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## Fonctionnement

1. Le bot se connecte à Discord et synchronise les commandes slash
2. Le planificateur attend l'heure configurée (modifiable à la volée via `/summary time`)
3. À l'heure dite, il récupère les messages des dernières 24h pour chaque salon configuré
4. Il envoie les messages à Ollama avec le contexte des résumés précédents
5. Le LLM génère un résumé en français
6. Les noms d'utilisateurs sont convertis en mentions Discord (`<@id>`)
7. Le résumé est posté et sauvegardé en base pour éviter les répétitions futures
