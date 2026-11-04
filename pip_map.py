#!/usr/bin/env python3
"""Inspect installed Python distributions and estimate their disk usage."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from dataclasses import asdict, dataclass
from importlib.metadata import distributions
from typing import Iterable, List, Optional, Set, Tuple

__version__ = "0.1.0"


@dataclass
class PackageInfo:
    """Measured information about one installed distribution."""

    name: str
    version: str
    size_bytes: Optional[int]
    location: str
    files_available: bool
    files_listed: int
    files_measured: int
    files_skipped: int


@dataclass
class ScanSummary:
    """Totals for the inspected Python environment."""

    total_distributions: int
    unique_files_measured: int
    estimated_unique_size_bytes: int
    distributions_without_file_inventory: int
    file_entries_skipped: int
    metadata_errors: int


@dataclass
class ScanResult:
    packages: List[PackageInfo]
    summary: ScanSummary


def format_size(size_bytes: int) -> str:
    """Format a byte count using binary units (KiB, MiB, GiB, ...)."""
    value = float(size_bytes)
    units = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")

    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return "{:.0f} B".format(value)
            return "{:.2f} {}".format(value, unit)
        value /= 1024

    return "{:.2f} PiB".format(value)  # Defensive fallback.


def positive_int(value: str) -> int:
    """argparse type that accepts only positive integers."""
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer")

    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def _file_identity(path: str, file_stat: os.stat_result) -> Tuple[object, ...]:
    """Return an identity that deduplicates paths and hard links when possible."""
    inode = getattr(file_stat, "st_ino", 0)
    device = getattr(file_stat, "st_dev", 0)

    if inode:
        return ("inode", device, inode)

    # Some filesystems/platforms do not provide a useful inode number.
    return ("path", os.path.normcase(os.path.realpath(path)))


def _distribution_label(dist: object, index: int) -> Tuple[str, str, str, int]:
    """Read distribution metadata without letting one broken entry stop the scan."""
    metadata_errors = 0

    try:
        metadata = dist.metadata  # type: ignore[attr-defined]
    except Exception:
        metadata = {}
        metadata_errors += 1

    try:
        name = metadata.get("Name") or "Unknown distribution #{}".format(index)
    except Exception:
        name = "Unknown distribution #{}".format(index)
        metadata_errors += 1

    try:
        version = str(dist.version)  # type: ignore[attr-defined]
    except Exception:
        try:
            version = str(metadata.get("Version") or "unknown")
        except Exception:
            version = "unknown"
        metadata_errors += 1

    try:
        location = str(dist.locate_file(""))  # type: ignore[attr-defined]
    except Exception:
        location = "Unavailable"
        metadata_errors += 1

    return str(name), version, location, metadata_errors


def scan_distributions(
    distribution_iterable: Optional[Iterable[object]] = None,
) -> ScanResult:
    """Inspect distributions in the active interpreter, or a supplied iterable.

    Per-distribution file sizes are measured independently. The environment-wide
    total deduplicates files by filesystem identity so shared files are not added
    to the grand total more than once.
    """
    discovered = distributions() if distribution_iterable is None else distribution_iterable

    packages: List[PackageInfo] = []
    all_file_ids: Set[Tuple[object, ...]] = set()
    unique_size_bytes = 0
    unique_files_measured = 0
    distributions_without_inventory = 0
    file_entries_skipped = 0
    metadata_errors = 0

    for index, dist in enumerate(discovered, start=1):
        name, version, location, dist_errors = _distribution_label(dist, index)
        metadata_errors += dist_errors

        try:
            file_entries = dist.files  # type: ignore[attr-defined]
            files_available = file_entries is not None
        except Exception:
            file_entries = None
            files_available = False
            metadata_errors += 1

        if not files_available:
            distributions_without_inventory += 1

        package_file_ids: Set[Tuple[object, ...]] = set()
        package_size_bytes = 0
        files_listed = 0
        files_measured = 0
        files_skipped = 0

        if files_available:
            try:
                file_iterator = iter(file_entries)
            except Exception:
                file_iterator = iter(())
                files_skipped += 1

            while True:
                try:
                    file_entry = next(file_iterator)
                except StopIteration:
                    break
                except Exception:
                    files_skipped += 1
                    break

                files_listed += 1

                try:
                    located_file = dist.locate_file(file_entry)  # type: ignore[attr-defined]
                    file_path = os.fspath(located_file)
                    file_stat = os.stat(file_path)  # Follows symlinks; counts the target file.

                    if not stat.S_ISREG(file_stat.st_mode):
                        files_skipped += 1
                        continue

                    identity = _file_identity(file_path, file_stat)
                    if identity in package_file_ids:
                        continue

                    package_file_ids.add(identity)
                    package_size_bytes += file_stat.st_size
                    files_measured += 1

                    if identity not in all_file_ids:
                        all_file_ids.add(identity)
                        unique_size_bytes += file_stat.st_size
                        unique_files_measured += 1

                except Exception:
                    # Missing files, permission errors, zip-backed paths, and unusual
                    # metadata providers should not abort inspection of other files.
                    files_skipped += 1

        file_entries_skipped += files_skipped
        packages.append(
            PackageInfo(
                name=name,
                version=version,
                size_bytes=package_size_bytes if files_available else None,
                location=location,
                files_available=files_available,
                files_listed=files_listed,
                files_measured=files_measured,
                files_skipped=files_skipped,
            )
        )

    summary = ScanSummary(
        total_distributions=len(packages),
        unique_files_measured=unique_files_measured,
        estimated_unique_size_bytes=unique_size_bytes,
        distributions_without_file_inventory=distributions_without_inventory,
        file_entries_skipped=file_entries_skipped,
        metadata_errors=metadata_errors,
    )
    return ScanResult(packages=packages, summary=summary)


def sort_packages(packages: List[PackageInfo], sort_by: str) -> List[PackageInfo]:
    """Return a sorted copy of package rows."""
    if sort_by == "name":
        return sorted(
            packages,
            key=lambda package: (
                package.name.casefold(),
                package.version.casefold(),
                package.location.casefold(),
            ),
        )

    return sorted(
        packages,
        key=lambda package: (
            -(package.size_bytes if package.size_bytes is not None else -1),
            package.name.casefold(),
        ),
    )


def _clip(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 3:
        return value[:width]
    return value[: width - 3] + "..."


def print_table(packages: List[PackageInfo], show_path: bool) -> None:
    headers = ["Package", "Version", "Size", "Files"]
    if show_path:
        headers.append("Installation location")

    rows: List[List[str]] = []
    for package in packages:
        size = format_size(package.size_bytes) if package.size_bytes is not None else "Unknown"
        files = (
            "{}/{}".format(package.files_measured, package.files_listed)
            if package.files_available
            else "N/A"
        )
        row = [package.name, package.version, size, files]
        if show_path:
            row.append(package.location)
        rows.append(row)

    # Keep the table readable in ordinary terminals while preserving useful values.
    caps = [36, 18, 12, 12]
    if show_path:
        caps.append(60)

    widths = []
    for column_index, header in enumerate(headers):
        longest = max(
            [len(header)]
            + [len(row[column_index]) for row in rows]
        )
        widths.append(min(longest, caps[column_index]))

    def render_row(values: List[str]) -> str:
        cells = [
            _clip(value, width).ljust(width)
            for value, width in zip(values, widths)
        ]
        return "  ".join(cells)

    print(render_row(headers))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print(render_row(row))


def _json_payload(result: ScanResult, displayed: List[PackageInfo]) -> dict:
    package_rows = []
    for package in displayed:
        row = asdict(package)
        row["size_mib"] = (
            round(package.size_bytes / (1024 * 1024), 2)
            if package.size_bytes is not None
            else None
        )
        package_rows.append(row)

    summary = asdict(result.summary)
    summary["estimated_unique_size_mib"] = round(
        result.summary.estimated_unique_size_bytes / (1024 * 1024), 2
    )

    return {
        "tool": "pip-map",
        "version": __version__,
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "packages": package_rows,
        "summary": summary,
    }


def print_summary(result: ScanResult, displayed_count: int) -> None:
    summary = result.summary
    print()
    print("Total distributions       : {}".format(summary.total_distributions))
    if displayed_count != summary.total_distributions:
        print("Distributions displayed   : {}".format(displayed_count))
    print("Unique files measured     : {}".format(summary.unique_files_measured))
    print(
        "Estimated total size     : {}".format(
            format_size(summary.estimated_unique_size_bytes)
        )
    )

    if summary.distributions_without_file_inventory:
        print(
            "Missing file inventories : {}".format(
                summary.distributions_without_file_inventory
            )
        )
    if summary.file_entries_skipped:
        print("File entries skipped      : {}".format(summary.file_entries_skipped))
    if summary.metadata_errors:
        print("Metadata issues           : {}".format(summary.metadata_errors))

    if summary.distributions_without_file_inventory or summary.file_entries_skipped:
        print("Note: the total is an estimate and may exclude files that could not be measured.")
    print("Note: the environment total deduplicates files shared by distributions.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pip-map",
        description=(
            "List installed Python distributions and estimate their on-disk "
            "file sizes."
        ),
        epilog=(
            "Sizes are estimates based on files recorded in distribution metadata. "
            "Run pip-map with the Python environment you want to inspect."
        ),
    )
    parser.add_argument(
        "-p",
        "--path",
        action="store_true",
        help="include each distribution's installation location in table output",
    )
    parser.add_argument(
        "--sort",
        choices=("size", "name"),
        default="size",
        help="sort by estimated size (largest first) or package name (default: size)",
    )
    parser.add_argument(
        "--top",
        type=positive_int,
        metavar="N",
        help="display only the first N distributions (summary still covers all)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="output machine-readable JSON (includes installation locations)",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version="%(prog)s {}".format(__version__),
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    print("╔══════════════════════════════════╗")
    print("║          pip-map v0.1.0           ║")
    print("║           by: Alucard*            ║")
    print("╚══════════════════════════════════╝\n")

    try:
        result = scan_distributions()
    except Exception as exc:
        print(
            "pip-map: could not inspect this Python environment: {}".format(exc),
            file=sys.stderr,
        )
        return 1

    sorted_packages = sort_packages(result.packages, args.sort)
    displayed = sorted_packages[: args.top] if args.top else sorted_packages

    if args.json:
        print(json.dumps(_json_payload(result, displayed), indent=2, ensure_ascii=False))
        return 0

    if not displayed:
        print("No installed Python distributions were found.")
    else:
        print_table(displayed, show_path=args.path)

    print_summary(result, displayed_count=len(displayed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
