#!/usr/bin/env python3
"""
Convert IllegalArgumentException and BizException.badRequest() to BizException.failed()

This script replicates the changes made in commit ce34a2f9:
- Convert throw new IllegalArgumentException(...) to throw BizException.failed(code, ...)
- Convert BizException.badRequest(...) to BizException.failed(code, ...)
- Add BizException import if not present
- Update @throws JavaDoc from IllegalArgumentException to BizException

Usage:
    python3 convert_exceptions.py                           # Run with current date
    python3 convert_exceptions.py --date 20251218           # Custom date prefix
    python3 convert_exceptions.py --dry-run                 # Preview changes only
    python3 convert_exceptions.py --dirs cage-features      # Specify directories
"""

import argparse
import re
import os
from datetime import datetime
from pathlib import Path

# Default target directoriesonly biz exception

DEFAULT_DIRS = [
    "cage-features",
    "user-features",
    "gaming-table-feature",
    "common-shared",
    "shared-infrastructure",
]

BIZ_EXCEPTION_IMPORT = "import com.alliance.casino.common.exception.BizException;"


def find_java_files(directories: list[str], base_path: Path) -> list[Path]:
    """Recursively find all .java files in the given directories."""
    java_files = []
    for dir_name in directories:
        dir_path = base_path / dir_name
        if dir_path.exists():
            java_files.extend(dir_path.rglob("*.java"))
    return sorted(java_files)


def has_biz_exception_import(content: str) -> bool:
    """Check if the file already has BizException import."""
    return BIZ_EXCEPTION_IMPORT in content or "import com.alliance.casino.common.exception.BizException;" in content


def add_import_if_needed(content: str) -> tuple[str, bool]:
    """
    Add BizException import if not present.
    Returns (new_content, was_added).
    """
    if has_biz_exception_import(content):
        return content, False

    # Find the best place to insert the import
    lines = content.split('\n')
    insert_index = None

    # Look for existing imports
    last_import_index = None
    for i, line in enumerate(lines):
        if line.startswith('import '):
            last_import_index = i

    if last_import_index is not None:
        # Insert after the last import
        insert_index = last_import_index + 1
    else:
        # Find package statement and insert after it
        for i, line in enumerate(lines):
            if line.startswith('package '):
                insert_index = i + 1
                # Skip blank lines after package
                while insert_index < len(lines) and lines[insert_index].strip() == '':
                    insert_index += 1
                break

    if insert_index is not None:
        lines.insert(insert_index, BIZ_EXCEPTION_IMPORT)
        return '\n'.join(lines), True

    return content, False


def convert_illegal_argument_exception(content: str, counter: int, date_prefix: str) -> tuple[str, int, int]:
    """
    Convert throw new IllegalArgumentException(...) to throw BizException.failed(code, ...).
    Returns (new_content, new_counter, replacements_count).
    """
    replacements = 0

    def replace_func(match):
        nonlocal counter, replacements
        code = f"{date_prefix}{counter:05d}L"
        counter += 1
        replacements += 1
        return f"throw BizException.failed({code},"

    # Pattern for: throw new IllegalArgumentException(
    pattern = r'throw new IllegalArgumentException\('
    new_content = re.sub(pattern, replace_func, content)

    return new_content, counter, replacements


def convert_biz_exception_bad_request(content: str, counter: int, date_prefix: str) -> tuple[str, int, int]:
    """
    Convert BizException.badRequest(...) to BizException.failed(code, ...).
    Returns (new_content, new_counter, replacements_count).
    """
    replacements = 0

    def replace_func(match):
        nonlocal counter, replacements
        code = f"{date_prefix}{counter:05d}L"
        counter += 1
        replacements += 1
        return f"BizException.failed({code}, "

    # Pattern for: BizException.badRequest(
    pattern = r'BizException\.badRequest\('
    new_content = re.sub(pattern, replace_func, content)

    return new_content, counter, replacements


def update_javadoc_throws(content: str) -> tuple[str, int]:
    """
    Update @throws IllegalArgumentException to @throws BizException.
    Returns (new_content, replacements_count).
    """
    # Pattern for: @throws IllegalArgumentException ...
    pattern = r'@throws\s+IllegalArgumentException'
    new_content, count = re.subn(pattern, '@throws BizException', content)
    return new_content, count


def process_file(filepath: Path, counter: int, date_prefix: str, dry_run: bool = False) -> tuple[int, dict]:
    """
    Process a single Java file.
    Returns (new_counter, stats_dict).
    """
    stats = {
        'illegal_arg': 0,
        'bad_request': 0,
        'javadoc': 0,
        'import_added': False,
        'modified': False,
    }

    try:
        content = filepath.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        content = filepath.read_text(encoding='latin-1')

    original_content = content

    # Convert IllegalArgumentException
    content, counter, illegal_count = convert_illegal_argument_exception(content, counter, date_prefix)
    stats['illegal_arg'] = illegal_count

    # Convert BizException.badRequest
    content, counter, bad_request_count = convert_biz_exception_bad_request(content, counter, date_prefix)
    stats['bad_request'] = bad_request_count

    # Update Javadoc @throws
    content, javadoc_count = update_javadoc_throws(content)
    stats['javadoc'] = javadoc_count

    # Add import if needed and if we made any exception conversions
    if stats['illegal_arg'] > 0 or stats['bad_request'] > 0:
        content, import_added = add_import_if_needed(content)
        stats['import_added'] = import_added

    # Check if file was modified
    stats['modified'] = content != original_content

    # Write back if modified and not dry run
    if stats['modified'] and not dry_run:
        filepath.write_text(content, encoding='utf-8')

    return counter, stats


def main():
    parser = argparse.ArgumentParser(
        description='Convert IllegalArgumentException and BizException.badRequest() to BizException.failed()'
    )
    parser.add_argument(
        '--date',
        type=str,
        default=datetime.now().strftime('%Y%m%d'),
        help='Date prefix for error codes (default: today, format: YYYYMMDD)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without writing to files'
    )
    parser.add_argument(
        '--dirs',
        nargs='+',
        default=DEFAULT_DIRS,
        help='Directories to scan (default: cage-features, user-features, etc.)'
    )
    parser.add_argument(
        '--start-counter',
        type=int,
        default=1,
        help='Starting counter for error codes (default: 1)'
    )

    args = parser.parse_args()

    # Validate date format
    if not re.match(r'^\d{8}$', args.date):
        print(f"Error: Invalid date format '{args.date}'. Expected YYYYMMDD.")
        return 1

    base_path = Path.cwd()
    date_prefix = args.date
    counter = args.start_counter

    print(f"Date prefix: {date_prefix}")
    print(f"Starting counter: {counter}")
    print(f"Directories: {', '.join(args.dirs)}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'WRITE'}")
    print("-" * 60)

    # Find all Java files
    java_files = find_java_files(args.dirs, base_path)
    print(f"Found {len(java_files)} Java files")
    print("-" * 60)

    # Process each file
    total_stats = {
        'files_modified': 0,
        'illegal_arg': 0,
        'bad_request': 0,
        'javadoc': 0,
        'imports_added': 0,
    }

    for filepath in java_files:
        counter, stats = process_file(filepath, counter, date_prefix, args.dry_run)

        if stats['modified']:
            total_stats['files_modified'] += 1
            total_stats['illegal_arg'] += stats['illegal_arg']
            total_stats['bad_request'] += stats['bad_request']
            total_stats['javadoc'] += stats['javadoc']
            if stats['import_added']:
                total_stats['imports_added'] += 1

            rel_path = filepath.relative_to(base_path)
            changes = []
            if stats['illegal_arg']:
                changes.append(f"IllegalArg:{stats['illegal_arg']}")
            if stats['bad_request']:
                changes.append(f"badRequest:{stats['bad_request']}")
            if stats['javadoc']:
                changes.append(f"@throws:{stats['javadoc']}")
            if stats['import_added']:
                changes.append("import:+1")

            print(f"{'[DRY] ' if args.dry_run else ''}Modified: {rel_path} ({', '.join(changes)})")

    # Summary
    print("-" * 60)
    print("Summary:")
    print(f"  Files modified: {total_stats['files_modified']}")
    print(f"  IllegalArgumentException converted: {total_stats['illegal_arg']}")
    print(f"  BizException.badRequest converted: {total_stats['bad_request']}")
    print(f"  @throws Javadoc updated: {total_stats['javadoc']}")
    print(f"  Imports added: {total_stats['imports_added']}")
    print(f"  Last error code used: {date_prefix}{counter-1:05d}L")

    if args.dry_run:
        print("\n[DRY RUN] No files were actually modified.")

    return 0


if __name__ == '__main__':
    exit(main())
