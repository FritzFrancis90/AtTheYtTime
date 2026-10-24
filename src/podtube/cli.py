"""CLI entry point for PodTube."""

import argparse
from pathlib import Path
from typing import Optional
from podtube.config import load_config
from podtube.pipeline import run_sync
from podtube.services.youtube import get_channels

try:
    import typer
    from rich.console import Console
    from rich.table import Table

    HAS_TYPER = True
except ImportError:
    HAS_TYPER = False


def _print_channels(all_channels: bool = False, config_path: Optional[Path] = None):
    cfg = load_config(config_path=config_path)
    channels = get_channels(cfg.spreadsheet_url)
    if not all_channels:
        channels = [ch for ch in channels if ch.isActive == 1]

    if HAS_TYPER:
        console = Console()
        table = Table(title="PodTube Channels")
        table.add_column("Channel Name", style="cyan")
        table.add_column("Channel ID", style="dim")
        table.add_column("Active", justify="center")
        table.add_column("Max Mins", justify="right")
        table.add_column("Include Keywords")
        table.add_column("Exclude Keywords")

        for ch in channels:
            table.add_row(
                ch.Name,
                ch.ID,
                "Yes" if ch.isActive == 1 else "No",
                str(ch.maxLength // 60) if ch.maxLength > 0 else "No limit",
                ", ".join(p for p in ch.includePhrases if p),
                ", ".join(p for p in ch.excludePhrases if p),
            )
        console.print(table)
    else:
        print(f"{'Channel Name':<30} | {'Channel ID':<26} | {'Active':<6} | {'Max Mins'}")
        print("-" * 80)
        for ch in channels:
            max_mins = str(ch.maxLength // 60) if ch.maxLength > 0 else "No limit"
            active_str = "Yes" if ch.isActive == 1 else "No"
            print(f"{ch.Name:<30} | {ch.ID:<26} | {active_str:<6} | {max_mins}")


if HAS_TYPER:
    _typer_app = typer.Typer(
        name="podtube",
        help="Convert YouTube channels into audio podcast feeds.",
        add_completion=False,
    )

    @_typer_app.command()
    def sync(
        channel: Optional[str] = typer.Option(
            None,
            "--channel",
            "-c",
            help="Filter sync to a specific channel name or YouTube Channel ID.",
        ),
        days_back: Optional[int] = typer.Option(
            None,
            "--days-back",
            "-d",
            help="Override defaultDaysToLookBack from config.yaml.",
        ),
        dry_run: bool = typer.Option(
            False,
            "--dry-run",
            help="Check for new videos without downloading or uploading.",
        ),
        config_path: Optional[Path] = typer.Option(
            None,
            "--config",
            help="Path to a custom config.yaml file.",
        ),
    ):
        """Sync active YouTube channels and publish updated podcast feeds."""
        cfg = load_config(config_path=config_path, days_back_override=days_back)
        run_sync(cfg, channel_filter=channel, dry_run=dry_run)

    @_typer_app.command("channels")
    def list_channels(
        all_channels: bool = typer.Option(
            False,
            "--all",
            "-a",
            help="Include inactive channels in the output.",
        ),
        config_path: Optional[Path] = typer.Option(
            None,
            "--config",
            help="Path to a custom config.yaml file.",
        ),
    ):
        """List configured YouTube channels from the spreadsheet."""
        _print_channels(all_channels=all_channels, config_path=config_path)


def _run_argparse():
    parser = argparse.ArgumentParser(
        prog="podtube",
        description="Convert YouTube channels into audio podcast feeds.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser(
        "sync", help="Sync active YouTube channels and publish updated podcast feeds."
    )
    sync_parser.add_argument(
        "-c", "--channel", help="Filter sync to a specific channel name or YouTube Channel ID."
    )
    sync_parser.add_argument(
        "-d", "--days-back", type=int, help="Override defaultDaysToLookBack from config.yaml."
    )
    sync_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check for new videos without downloading or uploading.",
    )
    sync_parser.add_argument("--config", type=Path, help="Path to a custom config.yaml file.")

    channels_parser = subparsers.add_parser(
        "channels", help="List configured YouTube channels from the spreadsheet."
    )
    channels_parser.add_argument(
        "-a", "--all", action="store_true", help="Include inactive channels in the output."
    )
    channels_parser.add_argument("--config", type=Path, help="Path to a custom config.yaml file.")

    args = parser.parse_args()
    if args.command == "sync":
        cfg = load_config(config_path=args.config, days_back_override=args.days_back)
        run_sync(cfg, channel_filter=args.channel, dry_run=args.dry_run)
    elif args.command == "channels":
        _print_channels(all_channels=args.all, config_path=args.config)


def app():
    if HAS_TYPER:
        _typer_app()
    else:
        _run_argparse()


if __name__ == "__main__":
    app()
