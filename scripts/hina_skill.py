#!/usr/bin/env python3
"""hina_skill.py — CLI for HINAA's Massive-Scale Skill Architecture.

Commands:
  list              List all discovered skills across categories.
  search <query>    Perform sub-5ms semantic/keyword skill routing.
  install <git_url> Install a remote GitHub skill repository hot into Hina.
  categories        Show skill distribution by domain.
  info <skill_id>   Inspect details of a specific skill.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Fix Windows cp1252 console unicode errors
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure api directory is in python path
ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from hinaa_api.skills import skill_catalog, skill_importer, skill_router


def cmd_list(args: argparse.Namespace) -> None:
    skill_catalog.load_all_skills(force_reload=args.refresh)
    skills = skill_catalog.list_all()

    if args.category:
        skills = [s for s in skills if s.category.lower() == args.category.lower()]

    print(f"\n✨ HINAA Skill Ecosystem — {len(skills)} Skills Available:\n" + "=" * 60)
    for s in sorted(skills, key=lambda x: (x.category, x.name)):
        kind_tag = "⚡ Tool" if s.kind == "executable_tool" else "🧠 Skill"
        print(f"[{kind_tag}] {s.name:<32} | {s.category:<25} | {s.id}")
        if args.verbose and s.description:
            print(f"       └─ {s.description[:110]}...")
    print("=" * 60 + f"\nTotal: {len(skills)} skills indexed.\n")


def cmd_search(args: argparse.Namespace) -> None:
    results = skill_router.search(args.query, top_k=args.limit)
    print(f"\n🔍 Search matches for '{args.query}' ({len(results)} found):\n" + "=" * 60)
    for r in results:
        kind_tag = "⚡ Tool" if r.skill.kind == "executable_tool" else "🧠 Skill"
        print(f"[{kind_tag}] {r.skill.name:<32} (Score: {r.score:.1f})")
        print(f"       Category: {r.skill.category} | Matched: {', '.join(r.matched_terms)}")
        if r.skill.description:
            print(f"       └─ {r.skill.description[:120]}...")
    print("=" * 60 + "\n")


def cmd_categories(args: argparse.Namespace) -> None:
    cats = skill_catalog.get_categories()
    total = sum(cats.values())
    print(f"\n📊 HINAA Skill Universe Breakdown — {total} Total Skills:\n" + "=" * 45)
    for cat, count in sorted(cats.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(count / max(cats.values()) * 20)
        print(f"{cat:<30} {count:>3} {bar}")
    print("=" * 45 + "\n")


def cmd_install(args: argparse.Namespace) -> None:
    print(f"\n📦 Installing skill from: {args.url} ...")
    try:
        record = skill_importer.import_from_git(args.url, custom_name=args.name)
        print(f"✅ Successfully installed and indexed '{record.name}' [{record.id}]")
        print(f"   Category: {record.category}")
        print(f"   Location: {record.source_path}")
        print(f"   Summary:  {record.description[:120]}...\n")
    except Exception as exc:
        print(f"❌ Failed to install skill: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_info(args: argparse.Namespace) -> None:
    skill = skill_catalog.get_skill(args.id) or skill_catalog.get_skill(f"tool:{args.id}")
    if not skill:
        print(f"❌ Skill '{args.id}' not found.", file=sys.stderr)
        sys.exit(1)

    print(f"\n📋 Skill Details: {skill.name} ({skill.id})\n" + "=" * 55)
    print(f"Kind:        {skill.kind}")
    print(f"Category:    {skill.category}")
    print(f"Triggers:    {', '.join(skill.triggers) if skill.triggers else 'None'}")
    print(f"Path:        {skill.source_path}")
    print(f"Description: {skill.description}\n")
    if skill.parameters:
        print("Parameters:")
        for k, v in skill.parameters.items():
            print(f"  - {k}: {v.get('type', 'any')} ({v.get('description', '')})")
    print("=" * 55 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="HINAA Skill Ecosystem Manager")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List all indexed skills")
    p_list.add_argument("-c", "--category", help="Filter by category")
    p_list.add_argument("-v", "--verbose", action="store_true", help="Show full descriptions")
    p_list.add_argument("-r", "--refresh", action="store_true", help="Force re-indexing")
    p_list.set_defaults(func=cmd_list)

    # search
    p_search = subparsers.add_parser("search", help="Semantic query search")
    p_search.add_argument("query", help="Query string")
    p_search.add_argument("-k", "--limit", type=int, default=5, help="Number of results")
    p_search.set_defaults(func=cmd_search)

    # categories
    p_cats = subparsers.add_parser("categories", help="Show category breakdown")
    p_cats.set_defaults(func=cmd_categories)

    # install
    p_inst = subparsers.add_parser("install", help="Install a skill from a Git repository")
    p_inst.add_argument("url", help="Git repository URL")
    p_inst.add_argument("--name", help="Custom folder name")
    p_inst.set_defaults(func=cmd_install)

    # info
    p_info = subparsers.add_parser("info", help="Inspect a specific skill")
    p_info.add_argument("id", help="Skill ID")
    p_info.set_defaults(func=cmd_info)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
