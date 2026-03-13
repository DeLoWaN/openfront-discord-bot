from __future__ import annotations

import argparse
import sys
from typing import Sequence

from ...core.config import load_config
from ...data.database import close_shared_database, init_shared_database
from ...data.shared.schema import bootstrap_shared_schema
from ...services.guild_sites import (
    build_guild_site_selector,
    create_guild_site,
    delete_guild_site,
    get_guild_site,
    list_guild_clan_tags,
    list_guild_sites,
    set_guild_site_active,
    update_guild_site,
)


def _state_label(is_active: object) -> str:
    return "active" if bool(is_active) else "inactive"


def _expand_clan_tag_args(values: Sequence[str] | None) -> list[str] | None:
    if values is None:
        return None
    tags: list[str] = []
    for value in values:
        for candidate in str(value).split(","):
            tags.append(candidate.strip())
    return tags


def _guild_summary(guild: object) -> str:
    tag_values = list_guild_clan_tags(guild)
    tags = f"[{', '.join(tag_values)}]" if tag_values else "-"
    discord_guild_id = getattr(guild, "discord_guild_id", None)
    return (
        f"id={guild.id} slug={guild.slug} subdomain={guild.subdomain} "
        f"display_name={guild.display_name!r} state={_state_label(guild.is_active)} "
        f"discord_guild_id={discord_guild_id!r} clan_tags={tags}"
    )


def _print_guild(guild: object) -> None:
    print(_guild_summary(guild))


def _add_selector_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--id", type=int, dest="guild_id")
    parser.add_argument("--slug")
    parser.add_argument("--subdomain")


def _selector_from_args(args: argparse.Namespace):
    return build_guild_site_selector(
        guild_id=getattr(args, "guild_id", None),
        slug=getattr(args, "slug", None),
        subdomain=getattr(args, "subdomain", None),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="guild-sites")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--slug", required=True)
    create_parser.add_argument("--subdomain", required=True)
    create_parser.add_argument("--display-name", required=True)
    create_parser.add_argument("--clan-tag", action="append", default=[])
    create_parser.add_argument("--discord-guild-id", type=int)
    create_parser.add_argument("--inactive", action="store_true")

    list_parser = subparsers.add_parser("list")
    list_parser.set_defaults()

    show_parser = subparsers.add_parser("show")
    _add_selector_arguments(show_parser)

    update_parser = subparsers.add_parser("update")
    _add_selector_arguments(update_parser)
    update_parser.add_argument("--new-slug")
    update_parser.add_argument("--new-subdomain")
    update_parser.add_argument("--display-name")
    update_parser.add_argument("--clan-tag", action="append", default=None)
    update_parser.add_argument("--clear-clan-tags", action="store_true")
    update_parser.add_argument("--discord-guild-id", type=int)
    update_parser.add_argument("--clear-discord-guild-id", action="store_true")
    state_group = update_parser.add_mutually_exclusive_group()
    state_group.add_argument("--active", action="store_true")
    state_group.add_argument("--inactive", action="store_true")

    activate_parser = subparsers.add_parser("activate")
    _add_selector_arguments(activate_parser)

    deactivate_parser = subparsers.add_parser("deactivate")
    _add_selector_arguments(deactivate_parser)

    delete_parser = subparsers.add_parser("delete")
    _add_selector_arguments(delete_parser)
    delete_parser.add_argument("--confirm", action="store_true")

    return parser


def _bootstrap_database() -> None:
    config = load_config()
    if config.mariadb is None:
        raise ValueError("mariadb must be configured to manage website guilds")
    database = init_shared_database(config.mariadb)
    bootstrap_shared_schema(database)


def run_command(args: argparse.Namespace) -> int:
    command = args.command
    if command == "create":
        guild = create_guild_site(
            slug=args.slug,
            subdomain=args.subdomain,
            display_name=args.display_name,
            clan_tags=_expand_clan_tag_args(args.clan_tag),
            is_active=not args.inactive,
            discord_guild_id=args.discord_guild_id,
        )
        _print_guild(guild)
        return 0

    if command == "list":
        guilds = list_guild_sites()
        if not guilds:
            print("No guild sites found")
            return 0
        for guild in guilds:
            _print_guild(guild)
        return 0

    selector = _selector_from_args(args)

    if command == "show":
        guild = get_guild_site(selector)
        if guild is None:
            raise ValueError("Guild site not found")
        _print_guild(guild)
        return 0

    if command == "update":
        updates: dict[str, object] = {}
        if args.new_slug is not None:
            updates["slug"] = args.new_slug
        if args.new_subdomain is not None:
            updates["subdomain"] = args.new_subdomain
        if args.display_name is not None:
            updates["display_name"] = args.display_name
        if args.clear_clan_tags:
            updates["clan_tags"] = []
        elif args.clan_tag is not None:
            updates["clan_tags"] = _expand_clan_tag_args(args.clan_tag)
        if args.clear_discord_guild_id:
            updates["discord_guild_id"] = None
        elif args.discord_guild_id is not None:
            updates["discord_guild_id"] = args.discord_guild_id
        if args.active:
            updates["is_active"] = True
        elif args.inactive:
            updates["is_active"] = False
        guild = update_guild_site(selector, **updates)
        _print_guild(guild)
        return 0

    if command == "activate":
        guild = set_guild_site_active(selector, is_active=True)
        _print_guild(guild)
        return 0

    if command == "deactivate":
        guild = set_guild_site_active(selector, is_active=False)
        _print_guild(guild)
        return 0

    if command == "delete":
        delete_guild_site(selector, confirm=args.confirm)
        print("Guild site deleted")
        return 0

    raise ValueError(f"Unknown command: {command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        return int(exc.code)

    try:
        _bootstrap_database()
        return run_command(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        close_shared_database()


if __name__ == "__main__":
    raise SystemExit(main())
