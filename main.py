#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config import DATA_DIR_MARKDOWN, DATA_DIR_PDFS, DATA_DIR_WEB, LANCEDB_DIR
from src.ingest import check_index_exists

console = Console()


def cmd_ingest(args):
    from src.ingest import ingest_all

    console.print("[bold]Indexando documentos...[/bold]")
    try:
        _table, count = ingest_all()
        console.print(f"[green]OK[/green] {count} chunks indexados com sucesso!")
    except ValueError as e:
        console.print(f"[red]Erro: {e}[/red]")
        sys.exit(1)


def cmd_ask(args):
    from src.query import ask_with_sources

    question = " ".join(args.question)
    try:
        result = ask_with_sources(question, top_k=args.top_k)
    except (ValueError, FileNotFoundError) as e:
        console.print(f"[red]Erro: {e}[/red]")
        sys.exit(1)

    console.print(
        Panel(
            result["answer"],
            title="[bold green]Resposta[/bold green]",
            border_style="green",
        )
    )

    if result["sources"]:
        console.print("\n[bold]Fontes:[/bold]")
        for i, src in enumerate(result["sources"], 1):
            meta = src.get("metadata", {})
            source_file = meta.get("source", "desconhecido")
            stype = meta.get("search_type", "?")
            console.print(
                f"  {i}. [dim]Score: {src['score']:.3f} ({stype}) | {source_file}[/dim]"
            )
            preview = src["text"][:200].replace("\n", " ")
            console.print(f"     [dim]{preview}...[/dim]")


def cmd_chat(args):
    from src.chat import chat

    chat()


def cmd_scrape(args):
    from src.web_scraper import scrape_urls

    urls = args.urls
    console.print(f"[bold]Fazendo scrape de {len(urls)} URLs...[/bold]")
    results = scrape_urls(urls)
    console.print(f"[green]OK[/green] {len(results)} páginas salvas em data/web/")


def cmd_status(args):
    table = Table(title="Status do Projeto")
    table.add_column("Componente", style="cyan")
    table.add_column("Itens", style="green")
    table.add_column("Caminho", style="dim")

    pdfs = list(DATA_DIR_PDFS.glob("*.pdf"))
    mds = list(DATA_DIR_MARKDOWN.glob("*.md"))
    webs = list(DATA_DIR_WEB.glob("*.txt"))

    db_exists = check_index_exists()
    chunk_count = 0
    if db_exists:
        import lancedb

        db = lancedb.connect(str(LANCEDB_DIR))
        t = db.open_table("chunks")
        chunk_count = t.count_rows()

    table.add_row("PDFs", str(len(pdfs)), str(DATA_DIR_PDFS))
    table.add_row("Markdown", str(len(mds)), str(DATA_DIR_MARKDOWN))
    table.add_row("Web (scraped)", str(len(webs)), str(DATA_DIR_WEB))
    table.add_row("Chunks indexados", str(chunk_count), str(LANCEDB_DIR))

    console.print(table)


def cmd_migrate(args):
    from src.migrate import run_migrations

    console.print("[bold]Executando migrations...[/bold]")
    try:
        applied = run_migrations()
        if applied == 0:
            console.print("[yellow]Nenhuma migration pendente.[/yellow]")
        else:
            console.print(f"[green]OK[/green] {applied} migration(s) aplicada(s)!")
    except Exception as e:
        console.print(f"[red]Erro: {e}[/red]")
        sys.exit(1)


def cmd_serve(args):
    import uvicorn

    console.print("[bold]Iniciando servidor API...[/bold]")
    console.print(f"  Endpoint: [cyan]http://{args.host}:{args.port}[/cyan]")
    console.print(f"  Docs:     [cyan]http://{args.host}:{args.port}/docs[/cyan]")

    uvicorn.run(
        "server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


def main():
    parser = argparse.ArgumentParser(
        description="RAG Agroecologia — DeepSeek + LanceDB + bge-m3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python main.py ingest                        # Indexar documentos
  python main.py ask "O que é agroecologia?"   # Pergunta única
  python main.py chat                           # Chat interativo
  python main.py serve                          # Iniciar API REST
  python main.py migrate                        # Executar migrations
  python main.py scrape https://exemplo.com     # Scraping de URLs
  python main.py status                         # Ver status
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Comando disponível")

    sub_ingest = subparsers.add_parser("ingest", help="Indexar documentos")
    sub_ingest.set_defaults(func=cmd_ingest)

    sub_ask = subparsers.add_parser("ask", help="Fazer uma pergunta")
    sub_ask.add_argument("question", nargs="+", help="Sua pergunta")
    sub_ask.add_argument("--top-k", type=int, default=5, help="Número de chunks")
    sub_ask.set_defaults(func=cmd_ask)

    sub_chat = subparsers.add_parser("chat", help="Chat interativo")
    sub_chat.set_defaults(func=cmd_chat)

    sub_scrape = subparsers.add_parser("scrape", help="Fazer scrape de URLs")
    sub_scrape.add_argument("urls", nargs="+", help="URLs para fazer scrape")
    sub_scrape.set_defaults(func=cmd_scrape)

    sub_status = subparsers.add_parser("status", help="Ver status do projeto")
    sub_status.set_defaults(func=cmd_status)

    sub_serve = subparsers.add_parser("serve", help="Iniciar API REST")
    sub_serve.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    sub_serve.add_argument(
        "--port", type=int, default=8000, help="Porta (default: 8000)"
    )
    sub_serve.add_argument("--reload", action="store_true", help="Auto-reload em dev")
    sub_serve.set_defaults(func=cmd_serve)

    sub_migrate = subparsers.add_parser("migrate", help="Executar migrations")
    sub_migrate.set_defaults(func=cmd_migrate)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
