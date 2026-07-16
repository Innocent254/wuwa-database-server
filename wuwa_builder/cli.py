from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import typer
from rich.console import Console

from wuwa_builder.builder import build_release

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command()
def build(
    output: Path = typer.Option(Path("build/release"), help="Generated release directory."),
    version: str = typer.Option("0.1.0", help="Database release version."),
    max_news_items: int = typer.Option(30, min=1, max=200),
    include_images: bool = typer.Option(True, help="Download and optimize source-linked images."),
) -> None:
    """Scrape trusted sources, validate records, and build release packages."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    manifest = asyncio.run(
        build_release(
            output_dir=output,
            version=version,
            max_news_items=max_news_items,
            include_images=include_images,
        )
    )
    console.print(f"[green]Built database {manifest.database.version}[/green]")
    console.print(f"Output: {output.resolve()}")


if __name__ == "__main__":
    app()
