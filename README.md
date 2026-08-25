# File Concatenator

A powerful Python utility to recursively concatenate text files with extension filtering, directory exclusion, output size limits, and automatic file splitting – now with **multipart (or plain) output**, **time‑based filtering**, and **per‑file modification timestamps**.

## 🚀 Features

- **Multipart MIME‑style output** (default) – each file is a separate part with a unique boundary.  
  Global `Content-Type` and `X‑Global‑Mark` headers are included (the mark is URL‑encoded).  
  Each part has a `modified` parameter with the file’s last‑modified time (UTC).
- **Plain headers mode** – simple `--- 🟦 FILE: path ---` headers for human readability.
- **Explicit split metadata** – if a file exceeds the size limit, every chunk includes `multipart`, `part`, and `start` parameters.
- **Multiple sources** – mix directories and individual files. Use `-i` to add extra sources.
- **Extension filtering** – include only specific extensions when scanning (explicit files are always included).
- **Directory exclusion** – skip unwanted folders.
- **Output size limits** – split into multiple files with automatic `partX` naming.
- **Time filters** – include only files modified since a given date (`--since`) or within the last N seconds/minutes/hours/days (`--ago`).  
  `--ago` accepts a quoted string (`"8 hours"`) or unquoted tokens (`8 hours`).
- **Human‑friendly size parsing** – `1MB`, `500K`, `2G`, etc.
- **Error aggregation** – non‑fatal errors are collected and printed at the end.
- **Custom boundary** – override the multipart boundary with `--boundary`.

## 📦 Installation

No installation required – just clone and run:

```bash
git clone https://github.com/yourusername/file-concatenator.git
cd file-concatenator
python3 file_concatenator.py --help
```

## 🛠 Usage

```bash
./file_concatenator.py [OPTIONS] [SOURCES...]
```

**SOURCES** can be files or directories. You can also use `-i` to add more sources.

### Options

| Option | Description |
|--------|-------------|
| `SOURCES` | One or more source paths (files or directories). |
| `-i, --include` | Additional sources to include (merged with positional). |
| `-e, --extensions` | List of extensions to include when scanning directories (default: `txt md html css js`). Explicit files are always included. |
| `-x, --exclude` | List of directory names or relative paths to exclude from directory scans. |
| `-o, --output` | Output file base name (writes to stdout if omitted). |
| `--size-limit` | Max size per output file (e.g. `100K`, `1MB`). |
| `--headroom` | Minimum space required before writing a new file (default: `1K`). |
| `--since` | Include files modified **at or after** this UTC datetime (ISO 8601). Example: `--since 2026-08-25T14:30:00`. |
| `--ago` | Include files modified **within the last** DURATION. Can be quoted (`"8 hours"`) or unquoted (`8 hours`). Examples: `--ago "5 minutes"`, `--ago 2.5 days`, `--ago 1h30m`, `--ago 00:01:00:00`. |
| `--plain-headers` | Use plain headers (no multipart boundaries) for output. |
| `--boundary` | Custom boundary string for multipart mode (default: auto‑generated like `qxj_7MA4YWxkTrZu0gW`). |
| `--max-source-file-size` | Maximum size of a source file to read entirely; larger files are streamed (default: ∞). |
| `-v, --verbose` | Print every file processed and skip reasons. |
| `--summary` | Print a summary of processed/skipped files. |

> `--since` and `--ago` are mutually exclusive.

### Examples

```bash
# Multipart output, include only .js modified in the last 2 hours
./file_concatenator.py . --extensions js --ago "2 hours" -o recent.js

# Plain headers, include all .txt files modified after 2026-08-25
./file_concatenator.py . -e txt --since 2026-08-25 --plain-headers -o after_date.txt

# Full example: scan .js/.css/.html, exclude node_modules, split into 1MB parts,
# include files changed in the last week, use a custom boundary
./file_concatenator.py . \
  --extensions js css html \
  --exclude node_modules dist \
  --ago 7 days \
  --output combined.txt \
  --size-limit 1MB \
  --boundary "my_custom_boundary"
```

## 📂 Output Format

### Multipart (default)

The output begins with global headers:
```
Content-Type: multipart/form-data; boundary=qxj_dC679rYRB5g177MR
X-Global-Mark: 🟦 FILE

```

Each source file is wrapped as:
```
--qxj_dC679rYRB5g177MR
Content-Disposition: form-data; name="PLAN.md"; modified="2026-08-25T14:30:00+00:00"

🟦 FILE
# actual file content ...
```

If a file is split, each chunk includes `multipart`, `part`, and `start`:
```
--qxj_dC679rYRB5g177MR
Content-Disposition: form-data; name="large.js"; modified="2026-08-25T14:30:00+00:00"; multipart; part=0; start=0

🟦 FILE
// first half ...
```

Continuation:
```
--qxj_dC679rYRB5g177MR
Content-Disposition: form-data; name="large.js"; modified="2026-08-25T14:30:00+00:00"; multipart; part=1; start=500000

🟦 FILE
// second half ...
--qxj_dC679rYRB5g177MR--
```

### Plain headers (with `--plain-headers`)

```
--- 🟦 FILE: src/utils.js ---
// content ...

--- 🟦 FILE: src/main.js ---
// first half ...

--- 🟦 FILE: src/main.js continued ---
// second half ...
```

## 🧪 Testing

```bash
mkdir test_dir
echo "Hello" > test_dir/a.txt
echo "World" > test_dir/b.txt
python3 file_concatenator.py test_dir -o output.txt --plain-headers
cat output.txt
```

## 🧠 Notes

- **Boundary collision**: The default boundary is randomly generated to avoid collisions. You can also set your own.
- **Time filters apply to all files**, including explicit ones.
- **Non‑fatal errors** are collected and printed at the end.
- The tool is designed for text files (UTF‑8). Binary files may produce garbled output.
- Output files are automatically excluded from processing.

## 📜 License

MIT License. See `LICENSE` file for details.
```

---

All requested changes are now live. The output is cleaner, includes modification timestamps, and uses the new header format. The `--since` error message is also more helpful.