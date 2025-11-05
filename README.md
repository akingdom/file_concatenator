# File Concatenator

A powerful Python utility to recursively concatenate text files with extension filtering, directory exclusion, output size limits, and automatic file splitting.

## 🚀 Features

- Recursively traverses directories to find and concatenate files
- Supports extension filtering (e.g., `.txt`, `.md`, `.js`)
- Excludes specified directories from processing
- Optional output to file or stdout
- Enforces output file size limits with automatic multipart splitting
- Adds clear headers for each source file
- Handles human-readable size inputs (e.g., `1MB`, `500K`, `2G`)
- Gracefully manages file continuation across split outputs

## 📦 Installation

No installation required. Just clone and run:

```bash
git clone https://github.com/yourusername/file-concatenator.git
cd file-concatenator
python3 file_concatenator.py --help
```

## 🛠 Usage

```bash
./file_concatenator.py DIRECTORY [options]
```

### Options

| Option | Description |
|--------|-------------|
| `-e`, `--extensions` | List of file extensions to include (default: `txt md html css js`) |
| `-x`, `--exclude` | List of directory names or relative paths to exclude |
| `-o`, `--output` | Output file base name (writes to stdout if omitted) |
| `--size-limit` | Max size per output file (e.g., `100K`, `1MB`) |
| `--headroom` | Minimum space required before writing a new file (default: `1K`) |
| `-h`, `--help` | Show help message and exit |

### Example

```bash
./file_concatenator.py . \
  --extensions js css html \
  --exclude node_modules dist \
  --output combined.txt \
  --size-limit 1MB \
  --headroom 1K
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

- Handles UTF-8 encoding with fallback for ignored errors
- Skips output files during recursive search to avoid self-inclusion
- Designed for modular extension and auditability

## 📜 License

MIT License. See `LICENSE` file for details.

---

Let me know if you'd like badges, contributor sections, or GitHub Actions integration added.