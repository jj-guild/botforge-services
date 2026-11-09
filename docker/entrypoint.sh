#!/usr/bin/env bash
# Entrypoint for the BotForge containers (ADR-0020 multi-process).
# BOTFORGE_PROCESS selects the process: "bot" (default, legacy) or "core".
# Extra arguments are forwarded to the process (e.g. --preflight).
set -euo pipefail

export LOG_LEVEL="${LOG_LEVEL:-INFO}"

case "${BOTFORGE_PROCESS:-bot}" in
  bot)
    : "${MONGO_URI:?MONGO_URI is required}"
    : "${REDIS_URI:?REDIS_URI is required}"
    : "${DISCORD_TOKEN:?DISCORD_TOKEN is required}"
    exec python -m botforge.discord.bot.main "$@"
    ;;
  core)
    : "${MONGO_URI:?MONGO_URI is required}"
    : "${REDIS_URI:?REDIS_URI is required}"
    exec python -m botforge.core_process.server
    ;;
  ext-librematch)
    exec python -m botforge.ext_librematch.server
    ;;
  ext-aoe2lobby)
    exec python -m botforge.ext_aoe2lobby.server
    ;;
  ext-aoe2techtree)
    exec python -m botforge.ext_aoe2techtree.server
    ;;
  ext-liquipedia)
    : "${MONGO_URI:?MONGO_URI is required}"
    : "${PROVIDER_CONTACT:?PROVIDER_CONTACT is required}"
    exec python -m botforge.ext_liquipedia.server
    ;;
  game-aoe2)
    exec python -m botforge.game_aoe2.server
    ;;
  seed)
    : "${MONGO_URI:?MONGO_URI is required}"
    exec python -m botforge.core.games.aoe2.seed_cli
    ;;
  *)
    echo "BOTFORGE_PROCESS must be 'bot', 'core', 'ext-librematch', 'ext-aoe2lobby', 'ext-aoe2techtree', 'ext-liquipedia', 'game-aoe2' or 'seed' (got: ${BOTFORGE_PROCESS})"
    exit 1
    ;;
esac
