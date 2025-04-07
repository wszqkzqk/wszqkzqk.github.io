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
        # Segment must contain at least one hyphen
        if '-' not in segment:
            return False
        # Check if all characters are either '-', or ':' at the start/end
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

        # Line 0: Potential Header
        # Line 1: Potential Separator
        potential_separator_line = lines[1]
        separator_segments = TableConverter._parse_table_line(potential_separator_line)

        # Validate the potential separator line
        is_separator = False
        if separator_segments and all(TableConverter._is_valid_separator_segment(seg) for seg in separator_segments):
             is_separator = True

        if not is_separator:
            print(f"Warning: The second line does not appear to be a valid Markdown table separator:\n  '{potential_separator_line}'", file=sys.stderr)
            print("Separator segments must consist of '---' with optional ':' at ends (e.g., :---, ---:, :---:).", file=sys.stderr)
            return [] # Treat as parsing failure if separator isn't line 2

        # If we reach here, line 1 is confirmed as the separator
        header_cells = TableConverter._parse_table_line(lines[0])
        num_columns = len(header_cells)

        # Check if separator column count matches header
        if len(separator_segments) != num_columns:
             print(f"Warning: Header has {num_columns} columns, but separator line seems to have {len(separator_segments)}. Processing anyway.", file=sys.stderr)
             # Adjust num_columns based on header, as it's usually the source of truth
             
        table_rows = [header_cells] # Start with the header

        # Process data lines (lines[2:])
        for i, data_line in enumerate(lines[2:]):
            data_cells = TableConverter._parse_table_line(data_line)
            # Basic validation: Check if data row looks like a separator - skip if it does
            if all(TableConverter._is_valid_separator_segment(seg) for seg in data_cells):
                 print(f"Warning: Skipping line {i+3} as it resembles a separator: '{data_line}'", file=sys.stderr)
                 continue

            # Check column count consistency (optional, but good practice)
            if len(data_cells) != num_columns:
                print(f"Warning: Line {i+3} has {len(data_cells)} cells, expected {num_columns}. Padding/truncating.", file=sys.stderr)
                # Pad with empty strings if too few cells
                while len(data_cells) < num_columns:
                    data_cells.append('')
                # Truncate if too many cells
                data_cells = data_cells[:num_columns]

            table_rows.append(data_cells)

        return table_rows

    # --- markdown_to_csv method remains largely the same, using the new read_markdown_table ---
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
            # Catch potential file writing errors specifically
            sys.exit(f"Error writing CSV file '{output_path}': {e}")


    # --- csv_to_markdown and its helpers remain unchanged ---
    @staticmethod
    def csv_to_markdown(
        input_path: Path,
        output_path: Path,
        delimiter: str = ',',
        align: Optional[str] = None
    ) -> None:
        """Convert CSV to properly formatted Markdown table"""
        try:
            with input_path.open('r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=delimiter)
                # Filter out potential empty rows from CSV
                rows = [row for row in reader if any(cell.strip() for cell in row)]
        except Exception as e:
            sys.exit(f"Error reading CSV file '{input_path}': {e}")

        if not rows:
            sys.exit("Error: CSV file is empty or contains only empty rows.")

        # Calculate column widths based on non-empty rows
        try:
            col_widths = [max(len(cell.strip()) for cell in col) for col in zip(*rows)]
        except IndexError:
             sys.exit("Error: Cannot calculate column widths. CSV might be malformed.")


        # Build Markdown content
        md_lines = []

        # Header row
        md_lines.append(TableConverter._format_md_row(rows[0], col_widths))

        # Separator row with optional alignment
        separator = TableConverter._create_separator(col_widths, align)
        md_lines.append(separator)

        # Data rows
        for i, row in enumerate(rows[1:]):
            # Ensure row has correct number of columns, pad if necessary
            if len(row) < len(col_widths):
                row.extend([''] * (len(col_widths) - len(row)))
            elif len(row) > len(col_widths):
                 print(f"Warning: Truncating CSV row {i+2} with extra cells: {row}", file=sys.stderr)
                 row = row[:len(col_widths)]
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
        padded_cells = list(cells)
        if len(padded_cells) < len(col_widths):
            padded_cells.extend([''] * (len(col_widths) - len(padded_cells)))
        
        formatted_cells = [
            cell.strip().ljust(width) for cell, width in zip(padded_cells, col_widths)
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
            else:
                separator_parts.append(base)
        return '|' + '|'.join(separator_parts) + '|'


# --- detect_conversion and main function remain the same ---
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
        formatter_class=argparse.RawTextHelpFormatter # Allows newlines in description
    )

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

    # Ensure input file exists before proceeding
    if not args.input.is_file():
        sys.exit(f"Error: Input file not found: {args.input}")

    # Ensure output directory exists
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        sys.exit(f"Error: Could not create output directory '{args.output.parent}': {e}")

    try:
        # Determine conversion direction
        direction = args.force if args.force else detect_conversion(args.input, args.output)

        # Perform conversion
        if direction == 'md2csv':
            with args.input.open('r', encoding='utf-8') as f:
                md_content = f.read()
            TableConverter.markdown_to_csv(md_content, args.output, args.delimiter)
        elif direction == 'csv2md':
             TableConverter.csv_to_markdown(args.input, args.output, args.delimiter, args.align)
    except ValueError as e: # Catch specific errors like detection failure
        sys.exit(f"Error: {e}")
    except Exception as e:
        # Catch any other unexpected errors during processing
        import traceback
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        # traceback.print_exc() # Uncomment for detailed debug info
        sys.exit(1) # Exit with non-zero status on error


if __name__ == "__main__":
    main()
