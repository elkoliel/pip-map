# pip-map

A lightweight command-line tool that lists installed Python distributions and estimates the disk space used by their recorded files.

## Features

- List installed distributions, versions, and estimated sizes.
- Sort by size or package name.
- Show installation locations.
- Limit the displayed rows with `--top`.
- Export results as JSON.
- Deduplicate shared files in the environment-wide total.
- No runtime third-party dependencies.

## Requirements

- Python 3.11 or newer.

## Install from a local checkout

```bash
python -m pip install .
```

## Usage

```bash
pip-map
pip-map --path
pip-map --sort name
pip-map --top 10
pip-map --json
```

You can also run the module directly before installing it:

```bash
python pip_map.py
```

## How size estimates work

`pip-map` reads each distribution's recorded file list through `importlib.metadata` and measures the corresponding regular files on disk. The environment-wide total counts a physical file only once when multiple distributions record the same file.

These values are estimates, not authoritative installation sizes. A distribution may not provide a file inventory, files may have been removed or become inaccessible, editable installs may not record the full source tree, and files created after installation may not appear in the recorded inventory.

## Development

Run the tests with:

```bash
python -m unittest discover -s tests -v
```

## License

MIT. See `LICENSE`.
