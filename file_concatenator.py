#!/usr/bin/env python3
# FILENAME: file_concatenator.py
# DESCRIPTION: Concatenate text files from directories and/or explicit files, with size limits and file splitting.

import argparse
from pathlib import Path
import sys
import os
import re

# Helper function to convert human-readable size strings to bytes
def human_readable_to_bytes(size_str):
    """
    Given a human-readable byte string (e.g. 2G, 30M, 20K, 100000), return the number of bytes.
    Handles k/K/m/M/g/G multipliers.
    """
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
        bytes_size = numeric_size * 1024**3
    elif unit == "M":
        bytes_size = numeric_size * 1024**2
    elif unit == "K":
        bytes_size = numeric_size * 1024**1
    else:
        bytes_size = numeric_size

    return int(bytes_size)

def is_excluded(file_path, start_dir, exclude_dirs):
    """Checks if a file path is within any of the excluded directories."""
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

class OutputFileManager:
    """Manages the state of output files, handles, indexing, and switching."""
    def __init__(self, output_file_base, use_multipart_naming):
        self.output_file_base = output_file_base
        self.use_multipart_naming = use_multipart_naming
        self.current_file_index = 1
        self.outfile_handle = sys.stdout
        self.last_source_file_written = None # Track the exact source file written to the *previous* output file
        self.open_handle()

    def open_handle(self):
        if not self.output_file_base:
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
            if self.current_file_index > 1:
                print(f"--- Starting new output file: {final_path.name} ---")
        except IOError as e:
            print(f"Error opening output file {final_path}: {e}", file=sys.stderr)
            sys.exit(1)

    def switch_to_new_file(self):
        self.current_file_index += 1
        self.open_handle()
        return self.outfile_handle

def write_to_output(mgr, content_bytes, size_limit, relative_path_str, current_source_file_path):
    """
    Handles writing chunks of content, managing file splitting and headers.
    Updates mgr state.
    """
    bytes_remaining_to_write = len(content_bytes)
    bytes_written_from_this_chunk = 0
    
    header_base = f"--- 🟦 FILE: {relative_path_str} ---"
    header_cont = f"--- 🟦 FILE: {relative_path_str} continued ---"
    
    is_first_chunk_of_source_file_write = True

    while bytes_remaining_to_write > 0:
        current_output_size = mgr.outfile_handle.tell()
        
        if current_output_size == 0:
            # At the start of an OUTPUT file. Check against the committed last source file path.
            is_truly_continued = (mgr.last_source_file_written == current_source_file_path)
            
            header_to_write = header_cont if is_truly_continued else header_base
            mgr.outfile_handle.write(header_to_write + '\n\n')
            current_output_size = mgr.outfile_handle.tell()
            # After writing header, we are no longer "continued" for the rest of this output file part
            mgr.last_source_file_written = None # Reset this state here to prevent accidental re-use if subsequent files are skipped/excluded
        
        elif is_first_chunk_of_source_file_write:
            # Not at the start of output file, but start of new source file within an existing output file
            header_to_write = header_base
            mgr.outfile_handle.write('\n\n' + header_to_write + '\n\n')
            current_output_size = mgr.outfile_handle.tell()
            mgr.last_source_file_written = None


        is_first_chunk_of_source_file_write = False
        
        space_available = size_limit - current_output_size if size_limit is not None else bytes_remaining_to_write
        
        bytes_to_write_len = min(bytes_remaining_to_write, space_available)
        chunk_to_write = content_bytes[bytes_written_from_this_chunk : bytes_written_from_this_chunk + bytes_to_write_len]
        
        mgr.outfile_handle.write(chunk_to_write.decode('utf-8')) 

        bytes_remaining_to_write -= len(chunk_to_write)
        bytes_written_from_this_chunk += len(chunk_to_write)
        
        # If we still have bytes left and we are capacity limited, we need to switch files
        if bytes_remaining_to_write > 0 and size_limit is not None:
            # A true mid-file split occurred. Commit the source file path before switching handles.
            mgr.last_source_file_written = current_source_file_path 
            mgr.switch_to_new_file()
            # Loop continues, current_output_size == 0 will hit the is_truly_continued logic

    # After the while loop finishes processing a *complete* source file with no remaining bytes:
    if bytes_remaining_to_write == 0:
        # We finished this file entirely within the current output handle. Reset state for the next file.
        mgr.last_source_file_written = None 


def concatenate_files(sources, extensions, output_file_base, exclude_dirs, size_limit_bytes, headroom_bytes, use_multipart_naming):
    """
    Finds files from the given sources (directories and/or explicit files) and concatenates their content,
    splitting into new files if size limit is reached.
    """
    # Use current working directory as base for relative paths in headers
    base_dir = Path.cwd()
    
    if not output_file_base:
        size_limit_bytes = None
        headroom_bytes = 0
        use_multipart_naming = False

    output_manager = OutputFileManager(output_file_base, use_multipart_naming)
    output_path_base_resolved = Path(output_file_base).resolve() if output_file_base else None
    
    excluded_output_paths_resolved = set()
    if output_file_base:
        output_ext = Path(output_file_base).suffix.lstrip('.')
        if output_ext in extensions:
            excluded_output_paths_resolved.add(str(Path(output_file_base).resolve()))

    collected_files = set()         # use set to avoid duplicates (if a file is given twice)
    for source in sources:
        source_path = Path(source)
        if source_path.is_dir():
            # Recursively walk directory
            for root, dirs, files in os.walk(source_path):
                # Exclude directories (both by name and relative path)
                dirs[:] = [d for d in dirs if d not in exclude_dirs and not Path(root, d).is_relative_to(source_path) in [Path(ed) for ed in exclude_dirs]]

                for file in files:
                    file_path = Path(root) / file
                    if any(file_path.name.endswith(f".{ext}") for ext in extensions):
                        collected_files.add(file_path)
        elif source_path.is_file():
            # Explicit file: include it unconditionally (ignore extension and exclusion)
            collected_files.add(source_path)
        else:
            print(f"Warning: {source} is not a valid file or directory, skipping.", file=sys.stderr)

    # Filter out output files (self‑exclusion)
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
        if not is_output_file:
            files_to_process.append(file_path)

    # Sort for deterministic order
    files_to_process.sort()

    for file_path in files_to_process:
        # Show path relative to the current working directory
        try:
            relative_path_str = os.path.relpath(file_path, base_dir)
        except ValueError:
            relative_path_str = str(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile:
                content_bytes = infile.read().encode('utf-8')
                
                # Headroom check: Decide BEFORE write_to_output if we *must* switch files immediately
                if size_limit_bytes is not None and output_manager.outfile_handle is not sys.stdout:
                    current_output_size = output_manager.outfile_handle.tell()
                    if current_output_size > 0:
                        space_remaining = size_limit_bytes - current_output_size
                        if space_remaining < headroom_bytes:
                            # We force a switch here. We do NOT update last_source_file_written here, 
                            # because we haven't written any content for this file yet.
                            output_manager.switch_to_new_file()

                write_to_output(
                    output_manager, 
                    content_bytes, 
                    size_limit_bytes, 
                    relative_path_str,
                    file_path # Pass the full path to track completion state
                )
                
        except IOError as e:
            print(f"Error reading file {file_path}: {e}", file=sys.stderr)

    if output_file_base and output_manager.outfile_handle is not sys.stdout:
        output_manager.outfile_handle.close()
        if output_manager.current_file_index > 1:
             print(f"\nSuccessfully concatenated files into {Path(output_file_base).stem}.partX.ext files.")
        else:
             print(f"\nSuccessfully concatenated files into {Path(output_file_base).name}")


def main():
    custom_usage = "%(prog)s source [source ...] [-e EXTENSIONS ...] [-x EXCLUDE ...] [-o OUTPUT] [--size-limit SIZE] [--headroom SIZE] [-h]"

    parser = argparse.ArgumentParser(
        usage=custom_usage,
        description="Concatenate text files from directories and/or explicit files, with extension filtering, directory exclusion, and output size limits.",
        epilog="Examples:\n"
               "  ./file_concatenator.py . --extensions js --exclude node_modules -o combined.txt --size-limit 1MB\n"
               "  ./file_concatenator.py file1.txt file2.md src/ --extensions py -o all.txt"
    )
    
    parser.add_argument(
        "sources",
        nargs="+",
        help="One or more source paths (files or directories). Directories are scanned recursively; files are included directly."
    )
    
    parser.add_argument(
        "-e", "--extensions",
        nargs="+",
        default=["txt", "md", "html", "css", "js"],
        help="A space-separated list of file extensions to include when scanning directories (default: txt md html css js). "
             "Explicitly given files are always included regardless of extension."
    )

    parser.add_argument(
        "-x", "--exclude",
        nargs="+",
        default=[],
        help="A space-separated list of directory names or relative paths to exclude from search. E.g., 'node_modules' or 'src/temp'."
    )
    
    parser.add_argument(
        "-o", "--output",
        dest="output_file_base",
        help="Specify an output file base name to write the concatenated content to. If not specified, output goes to stdout (screen)."
    )

    parser.add_argument(
        "--size-limit",
        dest="size_limit",
        default=None,
        help="Limits the size of output files (e.g., '100k', '1MB', '1gb'). Only used with -o. Activates 'basename.partX.ext' naming scheme if splitting occurs."
    )

    parser.add_argument(
        "--headroom",
        dest="headroom",
        default="1K",
        help="Minimum remaining space required in the current output file before attempting to write a new source file's content (default: 1K). Set to '0' to maximize file utilization. Only used with -o and --size-limit."
    )
    
    args = parser.parse_args()

    size_limit_bytes = human_readable_to_bytes(args.size_limit)
    headroom_bytes = human_readable_to_bytes(args.headroom) if args.size_limit else 0
    
    use_multipart_naming = args.size_limit is not None 

    concatenate_files(args.sources, args.extensions, args.output_file_base, args.exclude, size_limit_bytes, headroom_bytes, use_multipart_naming)

if __name__ == "__main__":
    main()