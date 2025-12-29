#!/usr/bin/env python3

"""
Extract and convert B3 transaction data from Excel to CSV format.
Reads B3 transaction Excel files and outputs a simplified CSV with key columns.

Usage:
    python transactions_from_b3.py <input_xlsx> [output_csv]
    
Example:
    python transactions_from_b3.py ~/Downloads/negociacao-2025-12-23-16-16-18.xlsx
    python transactions_from_b3.py ~/Downloads/negociacao-2025-12-23-16-16-18.xlsx transactions.csv
"""

import sys
from pathlib import Path
import pandas as pd


def process_b3_transactions(input_file, output_file=None):
    """
    Process B3 transaction Excel file and convert to CSV.
    
    Args:
        input_file: Path to input Excel file
        output_file: Path to output CSV file (optional, auto-generated if not provided)
        
    Returns:
        Path to the output CSV file
    """
    input_path = Path(input_file).expanduser()
    
    # Validate input file
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    if input_path.suffix.lower() not in ['.xlsx', '.xls']:
        raise ValueError(f"Input file must be an Excel file (.xlsx or .xls): {input_path}")
    
    # Generate output filename if not provided
    if output_file is None:
        output_path = input_path.parent / f"{input_path.stem}_processed.csv"
    else:
        output_path = Path(output_file).expanduser()
    
    print(f"📖 Reading: {input_path}")
    
    # Read Excel file
    try:
        df = pd.read_excel(input_path)
    except Exception as e:
        raise Exception(f"Error reading Excel file: {e}")
    
    # Verify required columns exist
    required_columns = {
        'Código de Negociação': 'Ticker',
        'Data do Negócio': 'Data',
        'Preço': 'Preço',
        'Tipo de Movimentação': 'Tipo'
    }
    
    missing_columns = [col for col in required_columns.keys() if col not in df.columns]
    if missing_columns:
        print("\n❌ Error: Missing required columns:")
        for col in missing_columns:
            print(f"   - {col}")
        print(f"\nAvailable columns in the file:")
        for col in df.columns:
            print(f"   - {col}")
        raise ValueError("Required columns not found in the input file")
    
    # Select and rename columns
    df_output = df[list(required_columns.keys())].copy()
    df_output.columns = list(required_columns.values())
    
    # Remove 'F' suffix from tickers (fractional shares)
    df_output['Ticker'] = df_output['Ticker'].astype(str).str.replace(r'F$', '', regex=True)
    
    # Ensure Preço is numeric
    df_output['Preço'] = pd.to_numeric(df_output['Preço'], errors='coerce')
    
    # Write to CSV
    print(f"💾 Writing: {output_path}")
    df_output.to_csv(output_path, index=False, encoding='utf-8')
    
    # Print summary
    print(f"\n✅ Success!")
    print(f"   📊 Processed {len(df_output)} transaction(s)")
    print(f"   📁 Output: {output_path}")
    
    # Show data quality info
    null_prices = df_output['Preço'].isna().sum()
    if null_prices > 0:
        print(f"\n⚠️  Warning: {null_prices} row(s) with invalid/missing price values")
    
    return output_path


def main():
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print("Usage: python transactions_from_b3.py <input_xlsx> [output_csv]")
        print()
        print("Example:")
        print("  python transactions_from_b3.py ~/Downloads/negociacao-2025-12-23-16-16-18.xlsx")
        print("  python transactions_from_b3.py ~/Downloads/negociacao-2025-12-23-16-16-18.xlsx transactions.csv")
        print()
        print("Extracts B3 transaction data and converts to CSV format.")
        print("Output columns: Ticker, Data, Preço, Tipo")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        process_b3_transactions(input_file, output_file)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

