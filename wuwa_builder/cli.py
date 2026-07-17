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
    max_items_per_dataset: int = typer.Option(250, min=1, max=500),
    include_images: bool = typer.Option(
        False,
        help="Download only representative images whose file metadata declares a reusable license.",
    ),
) -> None:
    """Read trusted structured sources, validate records, and build release packages."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    manifest = asyncio.run(
        build_release(
            output_dir=output,
            version=version,
            max_items_per_dataset=max_items_per_dataset,
            include_images=include_images,
        )
    )
    console.print(f"[green]Built database {manifest.database.version}[/green]")
    console.print(f"Output: {output.resolve()}")


if __name__ == "__main__":
    app()
