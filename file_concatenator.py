#!/usr/bin/env python3
# FILENAME: file_concatenator.py
# DESCRIPTION: Concatenate text files with multipart (or plain) output, size limits, and time filters.

import argparse
from pathlib import Path
import sys
import os
import re
import time
import random
import string
from datetime import datetime, timezone, timedelta

# ----------------------------------------------------------------------
# Helpers: time, bytes, random boundary
# ----------------------------------------------------------------------

def generate_boundary(prefix="qxj"):
    """Generate a random boundary string with a fixed prefix."""
    random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    return f"{prefix}_{random_part}"

def parse_datetime_to_timestamp(dt_str):
    """Parse ISO 8601 datetime to UTC timestamp."""
    if not ('Z' in dt_str or '+' in dt_str or '-' in dt_str[-6:]):
        dt_str = dt_str.strip() + '+00:00'
    try:
        dt = datetime.fromisoformat(dt_str)
    except ValueError:
        now_utc = datetime.now(timezone.utc)
        base = now_utc.strftime("%Y-%m-%d %H:%M")
        tz = now_utc.strftime("%z")
        formatted_utc = f"{base} {tz[:3]}:{tz[3:]}"
        raise ValueError(f"Invalid datetime format: {dt_str!r}. Use ISO 8601, e.g. '{formatted_utc}'")
    return dt.timestamp()

def parse_duration_to_timedelta(dur_str):
    """Parse duration string to timedelta."""
    dur_str = dur_str.strip().lower()
    if not dur_str:
        raise ValueError("Duration string is empty")
    if ':' in dur_str:
        parts = dur_str.split(':')
        if len(parts) == 4:
            days, hours, minutes, seconds = map(int, parts)
        elif len(parts) == 3:
            days, hours, minutes = 0, *map(int, parts)
            seconds = 0
        elif len(parts) == 2:
            days, hours, minutes = 0, 0, int(parts[0])
            seconds = int(parts[1])
        else:
            raise ValueError(f"Invalid colon‑duration format: {dur_str!r}")
        return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

    total_seconds = 0.0
    pattern = re.compile(r'([\d.]+)\s*([a-z]+)')
    pos = 0
    while pos < len(dur_str):
        match = pattern.match(dur_str, pos)
        if not match:
            raise ValueError(f"Unparseable duration fragment at position {pos} in {dur_str!r}")
        num = float(match.group(1))
        unit = match.group(2)
        if unit in ('s', 'sec', 'secs', 'second', 'seconds'):
            total_seconds += num
        elif unit in ('m', 'min', 'mins', 'minute', 'minutes'):
            total_seconds += num * 60
        elif unit in ('h', 'hr', 'hrs', 'hour', 'hours'):
            total_seconds += num * 3600
        elif unit in ('d', 'day', 'days'):
            total_seconds += num * 86400
        elif unit in ('w', 'week', 'weeks'):
            total_seconds += num * 604800
        else:
            raise ValueError(f"Unknown time unit: {unit!r} in {dur_str!r}")
        pos = match.end()
    if pos < len(dur_str):
        raise ValueError(f"Extra characters after duration: {dur_str[pos:]!r}")
    return timedelta(seconds=total_seconds)

def human_readable_to_bytes(size_str):
    if not size_str:
        return None
    size_str = size_str.upper().strip()
    if size_str.isdigit():
        return int(size_str)
    match = re.match(r'^([\d.]+)\s*([KMG])?B?$', size_str)
    if not match:
        if size_str.replace('.', '', 1).isdigit():
            return int(float(size_str))
        raise ValueError(f"Can't convert {size_str!r} to bytes")
    numeric_size = float(match.group(1))
    unit = match.group(2)
    if unit == "G":
        return int(numeric_size * 1024**3)
    elif unit == "M":
        return int(numeric_size * 1024**2)
    elif unit == "K":
        return int(numeric_size * 1024**1)
    else:
        return int(numeric_size)

def is_excluded(file_path, start_dir, exclude_dirs):
    if not exclude_dirs:
        return False
    relative_path = Path(os.path.relpath(file_path, start_dir))
    for part in relative_path.parts:
        if part in exclude_dirs:
            return True
    for excluded_path_str in exclude_dirs:
        excluded_path = Path(excluded_path_str.strip('/'))
        if relative_path.is_relative_to(excluded_path):
            return True
    return False

# ----------------------------------------------------------------------
# Output manager (multipart or plain)
# ----------------------------------------------------------------------

class OutputFileManager:
    def __init__(self, output_file_base, use_multipart_naming, boundary, plain_headers):
        self.output_file_base = output_file_base
        self.use_multipart_naming = use_multipart_naming
        self.boundary = boundary
        self.plain_headers = plain_headers
        self.current_file_index = 1
        self.outfile_handle = sys.stdout
        self.is_first_part_in_this_file = True
        self.global_headers_written = False
        self.file_state = {}          # per-source file: bytes_written, part_index, is_split, mtime_str
        self.open_handle()

    def open_handle(self):
        if not self.output_file_base:
            # stdout: we write global headers once at the beginning
            self.global_headers_written = False
            return
        output_path = Path(self.output_file_base)
        if self.use_multipart_naming:
            suffix = f".part{self.current_file_index}{output_path.suffix}" if output_path.suffix else f".part{output_path.name}.part{self.current_file_index}"
            final_path = output_path.with_suffix(suffix) if output_path.suffix else output_path.parent / (output_path.name + suffix)
        else:
            final_path = output_path
        try:
            if self.outfile_handle and self.outfile_handle is not sys.stdout:
                self.outfile_handle.close()
            self.outfile_handle = open(final_path, 'w', encoding='utf-8')
            self.is_first_part_in_this_file = True
            self.global_headers_written = False
            if self.current_file_index > 1:
                print(f"--- Starting new output file: {final_path.name} ---")
        except IOError as e:
            print(f"Error opening output file {final_path}: {e}", file=sys.stderr)
            sys.exit(1)

    def write_global_headers(self):
        """Write global headers if not already done and not in plain mode."""
        if self.plain_headers or self.global_headers_written:
            return
        if self.outfile_handle is sys.stdout:
            # We write them once at the beginning
            pass
        self.outfile_handle.write(f"Content-Type: multipart/form-data; boundary={self.boundary}\n")
        self.outfile_handle.write("X-Global-Mark: %F0%9F%9F%A6 FILE\n")   # URL‑encoded
        self.outfile_handle.write("\n")  # blank line after headers
        self.global_headers_written = True

    def switch_to_new_file(self):
        self.current_file_index += 1
        self.open_handle()
        # After opening a new file, we need to write global headers again
        self.write_global_headers()
        return self.outfile_handle

# ----------------------------------------------------------------------
# Core writing function (supports both multipart and plain headers)
# ----------------------------------------------------------------------

def format_mtime(mtime):
    """Convert a timestamp to ISO 8601 with timezone offset (UTC)."""
    dt = datetime.fromtimestamp(mtime, timezone.utc)
    # format: 2026-08-25T14:30:00+00:00
    return dt.strftime('%Y-%m-%dT%H:%M:%S') + '+00:00'

def write_to_output(mgr, content_bytes, size_limit, relative_path_str, source_file_path,
                    headroom_bytes, mtime_str):
    """
    Write content of one source file. If the file exceeds remaining space,
    it is split across multiple output files. Works in both multipart and plain modes.
    """
    boundary = mgr.boundary
    plain = mgr.plain_headers
    total_len = len(content_bytes)
    file_state = mgr.file_state

    # Initialize state for this source file if not already present
    if source_file_path not in file_state:
        # Determine if this file will be split
        if size_limit is not None and mgr.outfile_handle is not sys.stdout:
            current_pos = mgr.outfile_handle.tell()
            available = size_limit - current_pos
        else:
            available = total_len
        will_split = (size_limit is not None and total_len > available)
        file_state[source_file_path] = {
            'bytes_written': 0,
            'part_index': 0,
            'is_split': will_split,
            'mtime_str': mtime_str,
        }

    state = file_state[source_file_path]
    bytes_written_so_far = state['bytes_written']
    part_index = state['part_index']
    bytes_remaining = total_len - bytes_written_so_far
    mtime_str = state['mtime_str']

    while bytes_remaining > 0:
        # If we are in plain mode, we only add a header at the very start of the file
        if plain and bytes_written_so_far == 0:
            if mgr.is_first_part_in_this_file:
                mgr.outfile_handle.write(f"--- 🟦 FILE: {relative_path_str} ---\n\n")
            else:
                mgr.outfile_handle.write(f"\n\n--- 🟦 FILE: {relative_path_str} ---\n\n")
            mgr.is_first_part_in_this_file = False

        # For multipart: write boundary and header
        if not plain:
            if mgr.is_first_part_in_this_file:
                mgr.outfile_handle.write(f"--{boundary}\n")
                mgr.is_first_part_in_this_file = False
            else:
                mgr.outfile_handle.write(f"\n--{boundary}\n")

            # Build header: name and modified
            header = f'Content-Disposition: form-data; name="{relative_path_str}"; modified="{mtime_str}"'
            if state['is_split']:
                header += f'; multipart; part={part_index}; start={bytes_written_so_far}'
            mgr.outfile_handle.write(header + "\n\n")

            # Write the mark inside the body
            mgr.outfile_handle.write("🟦 FILE\n\n")

        # Determine chunk size
        if size_limit is not None and mgr.outfile_handle is not sys.stdout:
            current_pos = mgr.outfile_handle.tell()
            space_left = size_limit - current_pos
            if space_left <= 0:
                mgr.switch_to_new_file()
                continue
            chunk_size = min(bytes_remaining, space_left)
        else:
            chunk_size = bytes_remaining

        chunk = content_bytes[bytes_written_so_far: bytes_written_so_far + chunk_size]
        mgr.outfile_handle.write(chunk.decode('utf-8'))
        bytes_written_so_far += len(chunk)
        bytes_remaining -= len(chunk)
        state['bytes_written'] = bytes_written_so_far

        if bytes_remaining > 0:
            # Need to continue in a new output file
            mgr.switch_to_new_file()
            part_index += 1
            state['part_index'] = part_index
            # If plain mode, we will write a "continued" header on next loop
            if plain:
                # Write a "continued" header at the start of the new file
                mgr.outfile_handle.write(f"--- 🟦 FILE: {relative_path_str} continued ---\n\n")
                mgr.is_first_part_in_this_file = False
            # In multipart, the next loop will add a boundary and header with updated part/start

    # After writing all content, mark this file as done in state (optional cleanup)
    # We leave state for potential future reference; but we won't reuse it.

# ----------------------------------------------------------------------
# Main concatenation function
# ----------------------------------------------------------------------

def concatenate_files(sources, extensions, output_file_base, exclude_dirs,
                      size_limit_bytes, headroom_bytes, use_multipart_naming,
                      verbose, summary, cutoff_timestamp, plain_headers,
                      boundary, max_source_file_size_bytes):
    """
    Finds files from sources, filters by extension/time/exclusion, and writes
    content to output with optional splitting and headers.
    """
    def vprint(msg):
        if verbose:
            print(msg, file=sys.stderr, flush=True)

    # Statistics and error collection
    stats = {
        'total': 0,
        'included': 0,
        'skipped_extension': 0,
        'skipped_extensions': set(),
        'skipped_output': 0,
        'skipped_error': 0,
        'skipped_other': 0,
        'skipped_time': 0,
        'errors': [],   # collect error messages for non‑fatal errors
    }

    base_dir = Path.cwd()

    if not output_file_base:
        size_limit_bytes = None
        headroom_bytes = 0
        use_multipart_naming = False

    mgr = OutputFileManager(output_file_base, use_multipart_naming, boundary, plain_headers)
    # Write global headers if not plain and output is to a file
    if output_file_base and not plain_headers:
        mgr.write_global_headers()

    output_path_base_resolved = Path(output_file_base).resolve() if output_file_base else None

    excluded_output_paths_resolved = set()
    if output_file_base:
        output_ext = Path(output_file_base).suffix.lstrip('.')
        if output_ext in extensions:
            excluded_output_paths_resolved.add(str(Path(output_file_base).resolve()))

    collected_files = set()
    for source in sources:
        source_path = Path(source)
        if source_path.is_dir():
            for root, dirs, files in os.walk(source_path):
                # Exclude directories (both by name and relative path)
                dirs[:] = [d for d in dirs if d not in exclude_dirs and not Path(root, d).is_relative_to(source_path) in [Path(ed) for ed in exclude_dirs]]
                for file in files:
                    file_path = Path(root) / file
                    if any(file_path.name.endswith(f".{ext}") for ext in extensions):
                        collected_files.add(file_path)
                    else:
                        ext = file_path.suffix.lstrip('.')
                        vprint(f"✗ {file_path}: skipped by extension (.{ext} not in {extensions})")
                        stats['skipped_extension'] += 1
                        stats['skipped_extensions'].add(ext)
        elif source_path.is_file():
            collected_files.add(source_path)
        else:
            err_msg = f"Warning: {source} is not a valid file or directory, skipping."
            stats['errors'].append(err_msg)
            stats['skipped_other'] += 1

    # Filter out output files and apply time filter
    files_to_process = []
    for file_path in collected_files:
        resolved_file_path_str = str(file_path.resolve())
        is_output_file = False
        if resolved_file_path_str in excluded_output_paths_resolved:
            is_output_file = True
        if output_file_base and use_multipart_naming:
            output_base_name = Path(output_file_base).name
            if re.match(rf"^{re.escape(output_base_name)}\.part\d+$", file_path.name) or \
               re.match(rf"^{re.escape(Path(output_file_base).stem)}\.part\d+{re.escape(Path(output_file_base).suffix)}$", file_path.name):
                is_output_file = True
        if is_output_file:
            vprint(f"✗ {file_path}: skipped (output file)")
            stats['skipped_output'] += 1
            continue

        # Time filter
        if cutoff_timestamp is not None:
            try:
                mtime = os.path.getmtime(file_path)
            except OSError as e:
                err_msg = f"Error reading modification time for {file_path}: {e}"
                stats['errors'].append(err_msg)
                stats['skipped_error'] += 1
                continue
            if mtime < cutoff_timestamp:
                vprint(f"✗ {file_path}: skipped by time filter")
                stats['skipped_time'] += 1
                continue

        files_to_process.append(file_path)

    stats['total'] = len(files_to_process) + stats['skipped_extension'] + stats['skipped_output'] + stats['skipped_error'] + stats['skipped_other'] + stats['skipped_time']
    files_to_process.sort()

    for file_path in files_to_process:
        try:
            relative_path_str = os.path.relpath(file_path, base_dir)
        except ValueError:
            relative_path_str = str(file_path)

        # Get modification time
        try:
            mtime = os.path.getmtime(file_path)
            mtime_str = format_mtime(mtime)
        except OSError as e:
            err_msg = f"Error reading modification time for {file_path}: {e}"
            stats['errors'].append(err_msg)
            stats['skipped_error'] += 1
            continue

        try:
            # Read entire file (we could stream, but for simplicity we read all)
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile:
                content_bytes = infile.read().encode('utf-8')
        except (IOError, UnicodeDecodeError) as e:
            err_msg = f"Error reading {file_path}: {e}"
            stats['errors'].append(err_msg)
            stats['skipped_error'] += 1
            continue

        # Headroom check: switch file if remaining space is below headroom
        if size_limit_bytes is not None and mgr.outfile_handle is not sys.stdout:
            current_pos = mgr.outfile_handle.tell()
            if current_pos > 0:
                space_remaining = size_limit_bytes - current_pos
                if space_remaining < headroom_bytes:
                    mgr.switch_to_new_file()

        write_to_output(mgr, content_bytes, size_limit_bytes, relative_path_str, file_path,
                        headroom_bytes, mtime_str)
        vprint(f"✓ {file_path}")
        stats['included'] += 1

    # Write closing boundary for multipart mode
    if output_file_base and mgr.outfile_handle is not sys.stdout:
        if not plain_headers:
            mgr.outfile_handle.write(f"\n--{mgr.boundary}--\n")
        mgr.outfile_handle.close()
        if mgr.current_file_index > 1:
            print(f"\nSuccessfully concatenated files into {Path(output_file_base).stem}.partX.ext files.")
        else:
            print(f"\nSuccessfully concatenated files into {Path(output_file_base).name}")

    # Print errors (non‑fatal) at the end
    if stats['errors']:
        print("\n--- Non‑fatal errors occurred ---", file=sys.stderr)
        for err in stats['errors']:
            print(f"  {err}", file=sys.stderr)

    # Summary
    if summary:
        print("\n--- Summary ---", file=sys.stderr)
        print(f"Total files encountered: {stats['total']}", file=sys.stderr)
        print(f"Files included: {stats['included']}", file=sys.stderr)
        if stats['skipped_extension']:
            print(f"Skipped by extension: {stats['skipped_extension']} (extensions: {', '.join(sorted(stats['skipped_extensions']))})", file=sys.stderr)
        if stats['skipped_time']:
            print(f"Skipped by time filter: {stats['skipped_time']}", file=sys.stderr)
        if stats['skipped_output']:
            print(f"Skipped because they are output files: {stats['skipped_output']}", file=sys.stderr)
        if stats['skipped_error']:
            print(f"Skipped due to read/encoding errors: {stats['skipped_error']}", file=sys.stderr)
        if stats['skipped_other']:
            print(f"Skipped for other reasons: {stats['skipped_other']}", file=sys.stderr)
        if stats['errors']:
            print(f"Total non‑fatal errors: {len(stats['errors'])} (see above)", file=sys.stderr)

# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Concatenate text files with multipart (or plain) output, size limits, and time filters.",
        epilog="Examples:\n"
               "  ./file_concatenator.py . --extensions js --exclude node_modules -o combined.txt --size-limit 1MB\n"
               "  ./file_concatenator.py file1.txt file2.md src/ --extensions py -o all.txt"
    )
    # Sources: positional and optional --include
    parser.add_argument("sources", nargs="*", help="Source paths (files or directories).")
    parser.add_argument("-i", "--include", nargs="+", default=[],
                        help="Additional files/directories to include (merged with sources).")

    parser.add_argument("-e", "--extensions", nargs="+", default=["txt", "md", "html", "css", "js"],
                        help="Extensions to include when scanning directories (default: txt md html css js).")
    parser.add_argument("-x", "--exclude", nargs="+", default=[],
                        help="Directories to exclude (by name or relative path).")
    parser.add_argument("-o", "--output", dest="output_file_base",
                        help="Output file base name (writes to stdout if omitted).")
    parser.add_argument("--size-limit", dest="size_limit", default=None,
                        help="Max size per output file (e.g. 100K, 1MB). Activates multipart naming.")
    parser.add_argument("--headroom", dest="headroom", default="1K",
                        help="Minimum remaining space before switching files (default: 1K).")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print every file processed and skip reasons.")
    parser.add_argument("--summary", action="store_true",
                        help="Print summary instead of per‑file details.")
    parser.add_argument("--plain-headers", action="store_true",
                        help="Use plain headers (no multipart boundaries) for output.")
    parser.add_argument("--boundary", dest="boundary", default=None,
                        help="Custom boundary string for multipart mode (default: random).")

    time_group = parser.add_mutually_exclusive_group()
    time_group.add_argument("--since", metavar="DATETIME",
                            help="Include files modified at or after this UTC datetime (ISO 8601).")
    # Allow --ago to take multiple tokens (e.g., --ago 8 hours) by using nargs='*'
    time_group.add_argument("--ago", nargs="*",
                            help="Include files modified within the last DURATION (e.g. '5 minutes', '1h30m', or '8 hours').")

    parser.add_argument("--max-source-file-size", dest="max_source_file_size", default=None,
                        help="Maximum size of a source file to read entirely; larger files are streamed (default: ∞).")

    args = parser.parse_args()

    # Merge sources and --include
    sources = args.sources + args.include
    if not sources:
        parser.error("At least one source path (positional or --include) must be provided.")

    size_limit_bytes = human_readable_to_bytes(args.size_limit)
    headroom_bytes = human_readable_to_bytes(args.headroom) if args.size_limit else 0
    use_multipart_naming = args.size_limit is not None

    cutoff_timestamp = None
    if args.since:
        try:
            cutoff_timestamp = parse_datetime_to_timestamp(args.since)
        except ValueError as e:
            parser.error(f"Invalid datetime for --since: {e}")
    elif args.ago is not None:
        # Join multiple tokens into one string
        ago_str = ' '.join(args.ago).strip()
        if not ago_str:
            parser.error("--ago requires a duration (e.g., '8 hours')")
        try:
            duration = parse_duration_to_timedelta(ago_str)
        except ValueError as e:
            parser.error(f"Invalid duration for --ago: {e}")
        cutoff_timestamp = time.time() - duration.total_seconds()

    # Boundary: if not provided, generate one
    boundary = args.boundary if args.boundary is not None else generate_boundary("qxj")

    max_source_file_size_bytes = human_readable_to_bytes(args.max_source_file_size)

    concatenate_files(sources, args.extensions, args.output_file_base, args.exclude,
                      size_limit_bytes, headroom_bytes, use_multipart_naming,
                      args.verbose, args.summary, cutoff_timestamp,
                      args.plain_headers, boundary, max_source_file_size_bytes)

if __name__ == "__main__":
    main()