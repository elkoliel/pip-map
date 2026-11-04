# pip-map

A lightweight command-line tool that lists installed Python distributions and estimates the disk space used by their recorded files.

## Features

- List installed distributions, versions, and estimated sizes.
- Sort by package size or name.
- Display package installation locations.
- Limit displayed results with `--top`.
- Export package information as JSON.
- Deduplicate shared files when calculating the environment-wide total.
- No runtime third-party dependencies.

## Requirements

- Python 3.11 or newer.

## Installation

Install from a local checkout:

```bash
python -m pip install .
```

## Usage

Display installed packages:

```bash
pip-map
```

Show installation paths:

```bash
pip-map --path
```

Sort packages by name:

```bash
pip-map --sort name
```

Display the 10 largest packages:

```bash
pip-map --top 10
```

Export results as JSON:

```bash
pip-map --json
```

You can also run the script directly without installing it:

```bash
python pip_map.py
```

## How Size Estimates Work

`pip-map` reads each distribution's recorded file list through `importlib.metadata` and measures the corresponding regular files on disk.

The environment-wide total counts a physical file only once when multiple distributions record the same file.

These values are estimates, not authoritative installation sizes. A distribution may not provide a file inventory, files may have been removed or become inaccessible, editable installs may not record the full source tree, and files created after installation may not appear in the recorded inventory.

## Development

Run the test suite with:

```bash
python -m unittest discover -s tests -v
```

## License

MIT. See [LICENSE](LICENSE).
