from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from .config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    SIMILARITY_TOP_K,
    SYSTEM_PROMPT,
    USER_PROMPT,
)
from .ingest import check_index_exists
from .retriever import hybrid_search

console = Console()
MAX_HISTORY = 10


def chat():
    if not check_index_exists():
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

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    top_k = SIMILARITY_TOP_K
    history: list[dict] = []

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
            retrieved = hybrid_search(question, top_k=top_k)
            used = retrieved[:top_k]

            parts = []
            for i, r in enumerate(used, 1):
                source = r.get("source", "unknown")
                parts.append(f"[{i}] (source: {source})\n{r['text'].strip()}")
            context = "\n\n".join(parts)

            messages = [{"role": "system", "content": SYSTEM_PROMPT}]

            recent = history[-(MAX_HISTORY * 2) :]
            for msg in recent:
                messages.append(msg)

            messages.append(
                {
                    "role": "user",
                    "content": USER_PROMPT.format(context=context, question=question),
                }
            )

            stream = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
                stream=True,
            )

            console.print()
            answer_parts = []
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    console.print(delta, end="")
                    answer_parts.append(delta)
            console.print()

            answer = "".join(answer_parts)

            history.append({"role": "user", "content": question})
            history.append({"role": "assistant", "content": answer})

            if used:
                console.print("\n[dim]Sources:[/dim]")
                for i, src in enumerate(used, 1):
                    dist = src.get("_distance", 0)
                    score = 1.0 / (1.0 + float(dist)) if dist else 0.0
                    source_file = src.get("source", "unknown")
                    stype = src.get("_search_type", "?")
                    console.print(
                        f"  [dim]{i}. Score: {score:.3f} ({stype}) | {source_file}[/dim]"
                    )

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
