# File Concatenator

A powerful Python utility to recursively concatenate text files with extension filtering, directory exclusion, output size limits, and automatic file splitting. 

keywords: file join files join multiple files combine files concatenate files concatenate multiple files collect files collect multiple files

## 🚀 Features

- **Accepts multiple sources**: mix directories (recursively scanned) and individual files.
- Supports extension filtering (e.g., `.txt`, `.md`, `.js`) – only applies when scanning directories; explicit files are always included.
- Excludes specified directories from processing.
- Optional output to file or stdout.
- Enforces output file size limits with automatic multipart splitting.
- Adds clear headers for each source file.
- Handles human-readable size inputs (e.g., `1MB`, `500K`, `2G`).
- Gracefully manages file continuation across split outputs.

## 📦 Installation

No installation required. Just clone and run:

```bash
git clone https://github.com/yourusername/file-concatenator.git
cd file-concatenator
python3 file_concatenator.py --help
```

## 🛠 Usage

```bash
./file_concatenator.py SOURCE [SOURCE ...] [options]
```

**SOURCE** can be a file (included directly) or a directory (scanned recursively for matching extensions).

### Options

| Option | Description |
|--------|-------------|
| `-e`, `--extensions` | List of file extensions to include when scanning directories (default: `txt md html css js`). Explicit files are always included. |
| `-x`, `--exclude` | List of directory names or relative paths to exclude from directory scans. |
| `-o`, `--output` | Output file base name (writes to stdout if omitted). |
| `--size-limit` | Max size per output file (e.g., `100K`, `1MB`). |
| `--headroom` | Minimum space required before writing a new file (default: `1K`). |
| `-h`, `--help` | Show help message and exit. |

### Examples

```bash
# Scan current directory for .js, .css, .html files, exclude node_modules and dist
./file_concatenator.py . \
  --extensions js css html \
  --exclude node_modules dist \
  --output combined.txt \
  --size-limit 1MB \
  --headroom 1K

# Combine two specific files and a whole directory
./file_concatenator.py README.md file_concatenator.py src/ \
  --output docs.txt
```

## 📂 Output Behavior

- If `--output` is specified without `--size-limit`, all content goes into one file.
- If `--size-limit` is used, output is split into `basename.part1.ext`, `basename.part2.ext`, etc.
- Each file includes headers like:

```
--- 🟦 FILE: path/to/source.js ---
```

## 🧪 Testing

To test locally:

```bash
mkdir test_dir
echo "Hello" > test_dir/a.txt
echo "World" > test_dir/b.txt
python3 file_concatenator.py test_dir -o output.txt
```

## 🧠 Notes

- Handles UTF-8 encoding with fallback for ignored errors.
- Skips output files during recursive search to avoid self-inclusion.
- Designed for modular extension and auditability.
- Explicitly listed files are **always** included, regardless of extension and exclusion settings.

## 📜 License

MIT License. See `LICENSE` file for details.
