#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.adapters.rest.dependencies import (
    get_ask_question,
    get_ingest,
    get_manage_docs,
    get_vector_store,
    get_web_scraper,
    init_services,
    shutdown_services,
)
from src.shared.config import DATA_DIR_MARKDOWN, DATA_DIR_PDFS, DATA_DIR_WEB
from src.shared.logging_utils import configure_logging

console = Console()
configure_logging()


def cmd_ingest(args):
    import asyncio

    console.print("[bold]Ingesting documents...[/bold]")
    try:
        asyncio.run(init_services())
        count = asyncio.run(get_ingest().execute(force=args.force))
        console.print(f"[green]OK[/green] {count} chunks indexed successfully!")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    finally:
        asyncio.run(shutdown_services())


def cmd_ask(args):
    import asyncio

    question = " ".join(args.question)
    try:
        asyncio.run(init_services())
        manage_docs = get_manage_docs()
        title_map = asyncio.run(manage_docs.get_title_map()) if manage_docs else {}
        result = get_ask_question().execute(
            question,
            top_k=args.top_k,
            title_map=title_map,
        )
    except (ValueError, FileNotFoundError) as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    finally:
        asyncio.run(shutdown_services())

    console.print(
        Panel(
            result.answer,
            title="[bold green]Answer[/bold green]",
            border_style="green",
        )
    )

    if result.sources:
        console.print("\n[bold]Sources:[/bold]")
        for i, src in enumerate(result.sources, 1):
            meta = src.metadata
            source_file = meta.get("source", "unknown")
            stype = meta.get("search_type", "?")
            console.print(
                f"  {i}. [dim]Score: {src.score:.3f} ({stype}) | {source_file}[/dim]"
            )
            preview = src.text[:200].replace("\n", " ")
            console.print(f"     [dim]{preview}...[/dim]")


def cmd_chat(args):
    from src.chat import chat

    chat()


def cmd_scrape(args):
    import asyncio

    urls = args.urls
    console.print(f"[bold]Scraping {len(urls)} URLs...[/bold]")
    try:
        asyncio.run(init_services())
        results = get_web_scraper().scrape_urls(urls)
        console.print(f"[green]OK[/green] {len(results)} pages saved to data/web/")
    finally:
        asyncio.run(shutdown_services())


def cmd_status(args):
    import asyncio

    table = Table(title="Project Status")
    table.add_column("Component", style="cyan")
    table.add_column("Count", style="green")
    table.add_column("Path", style="dim")

    pdfs = list(DATA_DIR_PDFS.glob("*.pdf"))
    mds = list(DATA_DIR_MARKDOWN.glob("*.md"))
    webs = list(DATA_DIR_WEB.glob("*.txt"))

    try:
        asyncio.run(init_services())
        vector_store = get_vector_store()
        db_exists = vector_store.index_exists()
        chunk_count = vector_store.count_chunks() if db_exists else 0

        table.add_row("PDFs", str(len(pdfs)), str(DATA_DIR_PDFS))
        table.add_row("Markdown", str(len(mds)), str(DATA_DIR_MARKDOWN))
        table.add_row("Web (scraped)", str(len(webs)), str(DATA_DIR_WEB))
        table.add_row("Chunks indexed", str(chunk_count), "LanceDB")

        console.print(table)
    finally:
        asyncio.run(shutdown_services())


def cmd_db_migrate(args):
    from src.migrate import ensure_database, run_migrations

    console.print("[bold]Checking database...[/bold]")
    try:
        created = ensure_database()
        if created:
            console.print("[green]Database created successfully![/green]")
        else:
            console.print("[dim]Database already exists.[/dim]")
    except Exception as e:
        console.print(f"[red]Error creating database: {e}[/red]")
        sys.exit(1)

    console.print("[bold]Running migrations...[/bold]")
    try:
        applied = run_migrations()
        if applied == 0:
            console.print("[yellow]No pending migrations.[/yellow]")
        else:
            console.print(f"[green]OK[/green] {applied} migration(s) applied!")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def cmd_db_create(args):
    from src.migrate import ensure_database

    console.print("[bold]Checking database...[/bold]")
    try:
        created = ensure_database()
        if created:
            console.print("[green]Database created successfully![/green]")
        else:
            console.print("[dim]Database already exists.[/dim]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def cmd_db_seed(args):
    from src.seed import seed_roles_and_admin

    console.print("[bold]Seeding roles and admin user...[/bold]")
    try:
        roles_created, admin_created = seed_roles_and_admin()
        if roles_created:
            console.print("[green]Roles created (admin, user)![/green]")
        else:
            console.print("[dim]Roles already exist.[/dim]")
        if admin_created:
            console.print("[green]Admin user created successfully![/green]")
        else:
            console.print(
                "[yellow]Admin user already exists. Password updated.[/yellow]"
            )
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def cmd_serve(args):
    import uvicorn

    from src.adapters.rest.server import app

    console.print("[bold]Starting API server...[/bold]")
    console.print(f"  Endpoint: [cyan]http://{args.host}:{args.port}[/cyan]")
    console.print(f"  Docs:     [cyan]http://{args.host}:{args.port}/docs[/cyan]")

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


def main():
    parser = argparse.ArgumentParser(
        description="Agroecology RAG — DeepSeek + LanceDB + bge-m3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py ingest                        # Index documents
  python main.py ask "What is agroecology?"    # Single question
  python main.py chat                           # Interactive chat
  python main.py serve                          # Start API server
  python main.py db:migrate                     # Create database + run migrations
  python main.py db:create                      # Create database only
  python main.py scrape https://example.com     # Scrape URLs
  python main.py status                         # View status
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available command")

    sub_ingest = subparsers.add_parser("ingest", help="Index documents")
    sub_ingest.add_argument(
        "--force", action="store_true", help="Force re-ingestion of all documents"
    )
    sub_ingest.set_defaults(func=cmd_ingest)

    sub_ask = subparsers.add_parser("ask", help="Ask a question")
    sub_ask.add_argument("question", nargs="+", help="Your question")
    sub_ask.add_argument("--top-k", type=int, default=5, help="Number of chunks")
    sub_ask.set_defaults(func=cmd_ask)

    sub_chat = subparsers.add_parser("chat", help="Interactive chat")
    sub_chat.set_defaults(func=cmd_chat)

    sub_scrape = subparsers.add_parser("scrape", help="Scrape URLs")
    sub_scrape.add_argument("urls", nargs="+", help="URLs to scrape")
    sub_scrape.set_defaults(func=cmd_scrape)

    sub_status = subparsers.add_parser("status", help="View project status")
    sub_status.set_defaults(func=cmd_status)

    sub_serve = subparsers.add_parser("serve", help="Start API server")
    sub_serve.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    sub_serve.add_argument(
        "--port", type=int, default=8000, help="Port (default: 8000)"
    )
    sub_serve.add_argument(
        "--reload", action="store_true", help="Auto-reload (dev mode)"
    )
    sub_serve.set_defaults(func=cmd_serve)

    sub_migrate = subparsers.add_parser(
        "db:migrate", help="Create database and run migrations"
    )
    sub_migrate.set_defaults(func=cmd_db_migrate)

    sub_dbcreate = subparsers.add_parser("db:create", help="Create database only")
    sub_dbcreate.set_defaults(func=cmd_db_create)

    sub_dbseed = subparsers.add_parser("db:seed", help="Seed roles and admin user")
    sub_dbseed.set_defaults(func=cmd_db_seed)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
