from __future__ import annotations

import time

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from src.bootstrap.container import container
from src.shared.config import HYBRID_TOP_K

console = Console()


def chat() -> None:
    import asyncio

    asyncio.run(container.init())
    try:
        assert container.vector_store is not None
        if not container.vector_store.index_exists():
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
        top_k = HYBRID_TOP_K
        history: list[dict] = []
        use_case = container.ask_question
        assert use_case is not None, "ask_question not initialized"
        manage_docs = container.manage_docs
        document_metadata_map = (
            asyncio.run(manage_docs.get_metadata_map()) if manage_docs else {}
        )

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
                start = time.time()
                result = use_case.execute(
                    question,
                    top_k=top_k,
                    document_metadata_map=document_metadata_map,
                    history=history,
                )
                elapsed = time.time() - start
                used = result.sources[:top_k]

                console.print()
                answer = result.answer
                console.print(answer)
                console.print(f"[dim]({elapsed:.2f}s)[/dim]")

                history.append({"role": "user", "content": question})
                history.append({"role": "assistant", "content": answer})

                if used:
                    console.print("\n[dim]Sources:[/dim]")
                    for i, src in enumerate(used, 1):
                        meta = src.metadata
                        score = src.score
                        source_file = meta.get("source", "unknown")
                        stype = meta.get("search_type", "?")
                        console.print(
                            f"  [dim]{i}. Score: {score:.3f} ({stype}) | {source_file}[/dim]"
                        )

            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
    finally:
        asyncio.run(container.shutdown())
