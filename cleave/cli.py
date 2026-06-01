import argparse
import sys
from pathlib import Path

from cleave.analyse import run_analyse
from cleave.extract import STEM_NAMES
from cleave.separate import StemsAlreadyExist, run_separate

SIGNALS_FILENAME = "signals.json"


def _exit_error(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(1)


def validate_stems_dir(stems_dir: Path) -> None:
    if not stems_dir.exists():
        _exit_error(f"error: stems directory not found: {stems_dir}")
    if not stems_dir.is_dir():
        _exit_error(f"error: not a directory: {stems_dir}")


def validate_stem_files(stems_dir: Path) -> None:
    missing = [
        f"{name}.wav"
        for name in STEM_NAMES
        if not (stems_dir / f"{name}.wav").is_file()
    ]
    if missing:
        _exit_error(
            f"error: missing stem files in {stems_dir}: {', '.join(missing)}"
        )


def validate_source(source: Path) -> None:
    if not source.is_file():
        _exit_error(f"error: source file not found: {source}")


def cmd_analyse(args: argparse.Namespace) -> None:
    stems_dir = Path(args.stems_dir)
    validate_stems_dir(stems_dir)
    validate_stem_files(stems_dir)

    if args.source is not None:
        validate_source(Path(args.source))

    signals_path = stems_dir / SIGNALS_FILENAME
    if signals_path.exists() and not args.force:
        print(
            f"signals.json already exists at {signals_path}; "
            "use --force to regenerate"
        )
        return

    source = Path(args.source) if args.source is not None else None
    signals_path = run_analyse(stems_dir, source=source, slow=args.slow)
    print(f"Wrote signals to {signals_path}")


def cmd_separate(args: argparse.Namespace) -> None:
    try:
        stems_dir = run_separate(
            Path(args.audiofile), slow=args.slow, force=args.force
        )
    except StemsAlreadyExist as e:
        print(
            f"stems already exist at {e.stems_dir}; "
            "use --force to re-separate"
        )
        return
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        _exit_error(f"error: {e}")

    print(f"Wrote stems to {stems_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cleave",
        description="Stem-driven music visualizer",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyse = subparsers.add_parser(
        "analyse",
        help="Extract per-stem signals to signals.json",
    )
    analyse.add_argument(
        "stems_dir",
        help="Directory containing drums.wav, bass.wav, vocals.wav, other.wav",
    )
    analyse.add_argument(
        "--source",
        metavar="PATH",
        help="Original mixed audio file (for comparison)",
    )
    analyse.add_argument(
        "--slow",
        action="store_true",
        help="Use pyin for vocal pitch (default: yin)",
    )
    analyse.add_argument(
        "--force",
        action="store_true",
        help="Regenerate signals.json even if it already exists",
    )
    analyse.set_defaults(func=cmd_analyse)

    separate = subparsers.add_parser(
        "separate",
        help="Separate audio into stems with Demucs",
    )
    separate.add_argument(
        "audiofile",
        help="Audio file to separate",
    )
    separate.add_argument(
        "--slow",
        action="store_true",
        help="Use htdemucs_ft model (default: htdemucs)",
    )
    separate.add_argument(
        "--force",
        action="store_true",
        help="Re-separate even if stems already exist",
    )
    separate.set_defaults(func=cmd_separate)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
