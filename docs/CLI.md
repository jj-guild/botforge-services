# botforge CLI — the developer's didactic toolbox

`botforge` is a small command-line tool for developers (including
juniors — it explains everything it does) and occasional ops. It lives in
this repository, has no extra dependencies (Python stdlib only), and
follows the same lint/typecheck/test rules as the rest of the code.

Install it into your dev environment with the usual `make setup`
(`uv sync`) — the `botforge` command comes from the package.

## Guided tour

```bash
botforge                    # help
botforge doctor             # check your machine, print fixes
botforge local up           # start bot + MongoDB + Redis (docker compose)
botforge local logs         # follow the bot logs
botforge local test         # run the test suite (no token, no network)
botforge local reset        # stop AND wipe local data (asks first)
```

## doctor — "why doesn't it work?"

`botforge doctor` checks Python 3.12, `uv`, Docker and the compose
plugin, your `.env` (and `DISCORD_TOKEN`), and whether something listens
on port 8000. Every failed check prints a `->` line telling you exactly
what to do next. Exit code is non-zero only when something essential is
missing (WARN means "optional tool absent").

## local — the dev stack, explained

`botforge local <up|down|logs|status|reset|test|lint>` wraps the
existing Makefile targets, printing what will happen before doing it.
The CLI never reimplements the Makefile logic: it explains and delegates.
`reset` destroys the local data volumes and requires an explicit `yes`.

## remote — a distant server, key auth only

Hosts are stored per-user in `~/.config/botforge/cli.toml` (no secrets —
authentication always goes through your own ssh keys, passwords are
refused on purpose via `PasswordAuthentication=no`).

```bash
botforge remote add --name prod --host 1.2.3.4 --user root --key ~/.ssh/id_ed25519
botforge remote list
botforge remote status prod     # uptime over ssh
botforge remote logs prod       # last 100 bot log lines
botforge remote run prod 'df -h'          # arbitrary command (asks if it looks destructive)
botforge remote ssh prod        # interactive session
botforge remote rm prod
```

`deploy` opens an interactive ssh session and points you at the infra
repo — the deploy procedure is owned by `botforge-infra`, not by the
CLI. GPG/secret storage is deliberately out of scope: the CLI stores no
secret, so there is nothing to encrypt.

## runner — optional self-hosted GitHub Actions runner

`botforge runner setup [owner/repo]` prints a security-first guide
(dedicated machine, token scope, sane defaults) and the exact `gh`
commands to register a runner. It never downloads or executes anything
itself.

## Adding a new command

Each domain is a module in `src/botforge/cli/` exposing
`main(argv: list[str]) -> int`. Register it in `build_parser()` in
`src/botforge/cli/__main__.py`, add tests in `tests/unit/test_cli.py`,
and keep the didactic bar: explain before doing, actionable error
messages, confirmation before anything destructive.
