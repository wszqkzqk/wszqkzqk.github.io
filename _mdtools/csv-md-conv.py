#!/usr/bin/env python3

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

class TableConverter:
    _SEPARATOR_PATTERN = re.compile(r':?--*:?')

    @staticmethod
    def _is_valid_separator_segment(segment: str) -> bool:
        """Checks if a string segment follows the Markdown separator format (e.g., '---', ':--', '---:', ':-:')."""
        # The regex pattern ensures '-' is present and handles ':' placement.
        return TableConverter._SEPARATOR_PATTERN.fullmatch(segment) is not None

    @staticmethod
    def _parse_table_line(line: str) -> List[str]:
        """Strips outer pipes and whitespace, then splits line by '|'."""
        return [cell.strip() for cell in line.strip().strip('|').split('|')]

    @staticmethod
    def read_markdown_table(md_text: str) -> List[List[str]]:
        """
        Parses Markdown table text into a list of rows (header + data).
        Uses structural validation to identify the separator line.
        """
        lines = [line for line in md_text.strip().split('\n') if line.strip()]

        if len(lines) < 2:
            print("Warning: Not enough lines for a valid Markdown table (header + separator).", file=sys.stderr)
            return []

        # Assume Line 1 is the separator and validate it
        potential_separator_line = lines[1]
        separator_segments = TableConverter._parse_table_line(potential_separator_line)

        if not separator_segments or not all(TableConverter._is_valid_separator_segment(seg) for seg in separator_segments):
            print(f"Warning: The second line does not appear to be a valid Markdown table separator:\n  '{potential_separator_line}'", file=sys.stderr)
            print("Separator segments must consist of '---' with optional ':' at ends (e.g., :---, ---:, :---:).", file=sys.stderr)
            return [] # Treat as parsing failure if separator isn't line 2

        header_cells = TableConverter._parse_table_line(lines[0])
        num_columns = len(header_cells)

        table_rows = [header_cells] # Start with the header

        # Process data lines (lines[2:])
        for i, data_line in enumerate(lines[2:]):
            data_cells = TableConverter._parse_table_line(data_line)

            # Skip lines that look like separators
            if len(data_cells) == len(separator_segments) and all(TableConverter._is_valid_separator_segment(seg) for seg in data_cells):
                 print(f"Warning: Skipping line {i+3} as it resembles a separator: '{data_line}'", file=sys.stderr)
                 continue

            # Adjust row length to match header column count
            if len(data_cells) != num_columns:
                print(f"Warning: Line {i+3} has {len(data_cells)} cells, expected {num_columns}. Adjusting.", file=sys.stderr)
                # Pad or truncate
                data_cells.extend([''] * (num_columns - len(data_cells))) # Pad if too short
                data_cells = data_cells[:num_columns] # Truncate if too long

            table_rows.append(data_cells)

        return table_rows

    # --- markdown_to_csv method remains largely the same ---
    @staticmethod
    def markdown_to_csv(md_text: str, output_path: Path, delimiter: str = ',') -> None:
        """Convert Markdown table to clean CSV using the revised parser"""
        try:
            rows = TableConverter.read_markdown_table(md_text)
            if not rows:
                # Warnings are printed inside read_markdown_table
                sys.exit("Error: Failed to parse valid table data from Markdown. Check warnings.")

            with output_path.open('w', newline='', encoding='utf-8') as f:
                csv_writer = csv.writer(f, delimiter=delimiter)
                csv_writer.writerows(rows)
            print(f"Success: Created {output_path}")
        except Exception as e:
            sys.exit(f"Error writing CSV file '{output_path}': {e}")


    # --- csv_to_markdown and its helpers ---
    @staticmethod
    def csv_to_markdown(
        input_path: Path,
        output_path: Path,
        delimiter: str = ',',
        align: Optional[str] = None
    ) -> None:
        """Convert CSV to properly formatted Markdown table"""
        rows = []
        try:
            with input_path.open('r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=delimiter)
                # Filter out potential empty rows from CSV
                rows = [row for row in reader if any(cell.strip() for cell in row)]
        except FileNotFoundError:
             sys.exit(f"Error: Input CSV file not found: '{input_path}'")
        except Exception as e:
            sys.exit(f"Error reading CSV file '{input_path}': {e}")

        if not rows:
            sys.exit("Error: CSV file is empty or contains only empty rows.")

        # Calculate column widths
        try:
            # Ensure all rows have the same number of columns based on the header
            num_cols = len(rows[0])
            processed_rows = []
            for i, row in enumerate(rows):
                if len(row) < num_cols:
                    row.extend([''] * (num_cols - len(row)))
                elif len(row) > num_cols:
                    print(f"Warning: Truncating CSV row {i+1} with extra cells: {row}", file=sys.stderr)
                    row = row[:num_cols]
                processed_rows.append([cell.strip() for cell in row])

            rows = processed_rows # Use processed rows from now on
            col_widths = [max(len(cell) for cell in col) for col in zip(*rows)]
        except IndexError: # Handles empty rows list or rows with varying lengths if processing failed
             sys.exit("Error: Cannot calculate column widths. CSV might be empty or malformed.")


        # Build Markdown content
        md_lines = []
        md_lines.append(TableConverter._format_md_row(rows[0], col_widths)) # Header
        md_lines.append(TableConverter._create_separator(col_widths, align)) # Separator

        # Data rows
        for row in rows[1:]:
            md_lines.append(TableConverter._format_md_row(row, col_widths))

        try:
            with output_path.open('w', encoding='utf-8') as f:
                f.write('\n'.join(md_lines) + '\n') # Add trailing newline
            print(f"Success: Created {output_path}")
        except Exception as e:
            sys.exit(f"Error writing Markdown file '{output_path}': {e}")

    @staticmethod
    def _format_md_row(cells: List[str], col_widths: List[int]) -> str:
        """Format cells into a Markdown table row with proper spacing"""
        # Assumes cells list length matches col_widths due to prior processing
        formatted_cells = [
            cell.ljust(width) for cell, width in zip(cells, col_widths)
        ]
        return '| ' + ' | '.join(formatted_cells) + ' |'

    @staticmethod
    def _create_separator(col_widths: List[int], align: Optional[str]) -> str:
        """Create Markdown table separator with optional alignment"""
        separator_parts = []
        min_sep_len = 3
        for width in col_widths:
            sep_len = max(width, min_sep_len)
            base = '-' * sep_len

            if align == 'left':
                separator_parts.append(f':{base[1:]}')
            elif align == 'center':
                separator_parts.append(f':{base[1:-1]}:')
            elif align == 'right':
                separator_parts.append(f'{base[:-1]}:')
            else: # Default (right-aligned usually, but depends on renderer)
                separator_parts.append(base)
        # Use '-' padding for the joiner itself for consistency
        return '|' + '-|-'.join(separator_parts) + '-|' # Adjusted joiner


# --- detect_conversion function remains the same ---
def detect_conversion(input_path: Path, output_path: Path) -> str:
    """Auto-detect conversion direction based on file extensions"""
    input_ext = input_path.suffix.lower()
    output_ext = output_path.suffix.lower()

    if input_ext in ['.md', '.markdown'] and output_ext == '.csv':
        print("Detected conversion: Markdown -> CSV")
        return 'md2csv'
    elif input_ext == '.csv' and output_ext in ['.md', '.markdown']:
        print("Detected conversion: CSV -> Markdown")
        return 'csv2md'
    else:
        # Raise ValueError directly here for cleaner handling in main
        raise ValueError(
            f"Cannot auto-detect conversion between '{input_ext}' and '{output_ext}'.\n"
            "Supported conversions:\n"
            "- Markdown (.md, .markdown) -> CSV (.csv)\n"
            "- CSV (.csv) -> Markdown (.md, .markdown)"
        )

def main():
    parser = argparse.ArgumentParser(
        description='Convert between Markdown tables and CSV files.\n'
                    'Auto-detects conversion direction based on file extensions (.md/.markdown <-> .csv).',
        formatter_class=argparse.RawTextHelpFormatter
    )
    # ... existing argument definitions ...
    parser.add_argument('input', type=Path, help='Input file path (e.g., table.md or data.csv)')
    parser.add_argument('output', type=Path, help='Output file path (e.g., data.csv or table.md)')
    parser.add_argument(
        '--delimiter',
        default=',',
        help='CSV delimiter character (default: comma)'
    )
    parser.add_argument(
        '--align',
        choices=['left', 'center', 'right'],
        default=None, # Default Markdown alignment depends on renderer
        help='Column alignment for Markdown output (e.g., --align center)'
    )
    parser.add_argument(
        '--force',
        choices=['md2csv', 'csv2md'],
        help='Force specific conversion direction, overriding auto-detection'
    )

    args = parser.parse_args()

    try:
        # Ensure input file exists before proceeding
        if not args.input.is_file():
            # Use FileNotFoundError for consistency
            raise FileNotFoundError(f"Input file not found: {args.input}")

        # Ensure output directory exists
        args.output.parent.mkdir(parents=True, exist_ok=True)

        # Determine conversion direction
        direction = args.force if args.force else detect_conversion(args.input, args.output)

        # Perform conversion
        if direction == 'md2csv':
            # Read input file within the try block
            md_content = args.input.read_text(encoding='utf-8')
            TableConverter.markdown_to_csv(md_content, args.output, args.delimiter)
        elif direction == 'csv2md':
             # csv_to_markdown handles its own file reading now
             TableConverter.csv_to_markdown(args.input, args.output, args.delimiter, args.align)

    except (FileNotFoundError, ValueError, OSError, Exception) as e:
        # Catch specific and general errors here
        # OSError covers issues like directory creation failure
        # ValueError covers detection failure
        # Exception catches anything else (like CSV parsing issues handled internally or file write errors)
        sys.exit(f"Error: {e}")
    # No need for a separate broad Exception catch if specific ones cover expected issues


if __name__ == "__main__":
    main()
