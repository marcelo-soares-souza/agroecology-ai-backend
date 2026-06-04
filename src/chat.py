from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from .adapters.rest.dependencies import (
    get_ask_question,
    get_manage_docs,
    get_vector_store,
    init_services,
    shutdown_services,
)
from .shared.config import HYBRID_TOP_K

console = Console()


def chat():
    if not get_vector_store().index_exists():
        console.print("[red]Index not found. Run: python main.py ingest[/red]")
        return

    console.print(
        Panel(
            "[bold]Agroecology RAG Chat[/bold]\n"
            "Type your question or 'exit' to quit.\n"
            "Use '/top N' to adjust the number of retrieved chunks.",
            border_style="blue",
        )
    )

    import asyncio

    asyncio.run(init_services())
    try:
        top_k = HYBRID_TOP_K
        history: list[dict] = []
        use_case = get_ask_question()
        manage_docs = get_manage_docs()
        title_map = asyncio.run(manage_docs.get_title_map()) if manage_docs else {}

        while True:
            try:
                question = Prompt.ask("\n[bold cyan]You[/bold cyan]")
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Goodbye![/dim]")
                break

            if not question.strip():
                continue

            if question.strip().lower() in ("sair", "exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            if question.strip().startswith("/top"):
                try:
                    parts = question.strip().split()
                    top_k = int(parts[1])
                    console.print(f"[yellow]top_k set to {top_k}[/yellow]")
                except (IndexError, ValueError):
                    console.print("[red]Usage: /top N (e.g. /top 3)[/red]")
                continue

            try:
                result = use_case.execute(
                    question,
                    top_k=top_k,
                    title_map=title_map,
                    history=history,
                )
                used = result["sources"][:top_k]

                console.print()
                answer = result["answer"]
                console.print(answer)

                history.append({"role": "user", "content": question})
                history.append({"role": "assistant", "content": answer})

                if used:
                    console.print("\n[dim]Sources:[/dim]")
                    for i, src in enumerate(used, 1):
                        meta = src.get("metadata", {})
                        score = src.get("score", 0.0)
                        source_file = meta.get("source", "unknown")
                        stype = meta.get("search_type", "?")
                        console.print(
                            f"  [dim]{i}. Score: {score:.3f} ({stype}) | {source_file}[/dim]"
                        )

            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
    finally:
        asyncio.run(shutdown_services())
