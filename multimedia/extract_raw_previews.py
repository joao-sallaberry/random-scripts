#!/usr/bin/env python3

"""
Extract JPEG previews from RAW camera images using dcraw.
Processes all RAW files in a directory and saves JPEGs to a subfolder.
"""

import subprocess
import sys
import shutil
from pathlib import Path
from typing import List

# Supported RAW image extensions
RAW_EXTENSIONS = {
    '.cr2', '.CR2',  # Canon
    '.nef', '.NEF',  # Nikon
    '.arw', '.ARW',  # Sony
    '.raf', '.RAF',  # Fujifilm
    '.orf', '.ORF',  # Olympus
    '.dng', '.DNG',  # Adobe Digital Negative
    '.rw2', '.RW2',  # Panasonic
    '.pef', '.PEF',  # Pentax
    '.srw', '.SRW',  # Samsung
}

OUTPUT_FOLDER_NAME = "extracted_jpegs"


def check_dcraw_installed() -> bool:
    """
    Check if dcraw is installed and available.
    
    Returns:
        bool: True if dcraw is available, False otherwise
    """
    return shutil.which("dcraw") is not None


def find_raw_files(directory: Path) -> List[Path]:
    """
    Find all RAW image files in the given directory.
    
    Args:
        directory: Path to the directory to search
        
    Returns:
        List of Path objects for RAW files
    """
    raw_files = [
        f for f in directory.iterdir()
        if f.is_file() and f.suffix in RAW_EXTENSIONS
    ]
    return sorted(raw_files)


def extract_jpeg_preview(raw_file: Path, output_dir: Path) -> bool:
    """
    Extract JPEG preview from a RAW file using dcraw.
    
    Args:
        raw_file: Path to the RAW image file
        output_dir: Path to the output directory
        
    Returns:
        bool: True if extraction was successful, False otherwise
    """
    try:
        # Run dcraw -e to extract embedded JPEG
        # dcraw creates files with .thumb.jpg extension in the same directory
        result = subprocess.run(
            ["dcraw", "-e", str(raw_file)],
            cwd=str(raw_file.parent),
            capture_output=True,
            check=True
        )
        
        # Find the generated thumb file
        thumb_file = raw_file.parent / f"{raw_file.stem}.thumb.jpg"
        
        if not thumb_file.exists():
            print(f"   ⚠️  Warning: No preview found in {raw_file.name}")
            return False
        
        # Move the thumb file to output directory
        output_file = output_dir / thumb_file.name
        shutil.move(str(thumb_file), str(output_file))
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Error running dcraw: {e}")
        if e.stderr:
            print(f"      {e.stderr.decode().strip()}")
        return False
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        return False


def main() -> None:
    """Main entry point for the script."""
    if len(sys.argv) != 2:
        print("Usage: python extract_raw_previews.py <directory>")
        print()
        print("Example:")
        print("  python extract_raw_previews.py /path/to/raw/images/")
        print()
        print("Extracts JPEG previews from RAW camera files using dcraw.")
        print(f"Supported formats: {', '.join(sorted(set(ext.upper().lstrip('.') for ext in RAW_EXTENSIONS)))}")
        sys.exit(1)
    
    # Validate dcraw is installed
    if not check_dcraw_installed():
        print("❌ Error: dcraw is not installed")
        print()
        print("Install dcraw:")
        print("  macOS:  brew install dcraw")
        print("  Ubuntu: sudo apt install dcraw")
        print("  Fedora: sudo dnf install dcraw")
        sys.exit(1)
    
    # Validate input directory
    input_dir = Path(sys.argv[1])
    
    if not input_dir.exists():
        print(f"❌ Error: Directory not found: {input_dir}")
        sys.exit(1)
    
    if not input_dir.is_dir():
        print(f"❌ Error: Not a directory: {input_dir}")
        sys.exit(1)
    
    # Create output directory
    output_dir = input_dir / OUTPUT_FOLDER_NAME
    output_dir.mkdir(exist_ok=True)
    
    print(f"📁 Input directory:  {input_dir}")
    print(f"📁 Output directory: {output_dir}")
    print()
    
    # Find all RAW files
    raw_files = find_raw_files(input_dir)
    
    if not raw_files:
        print("❌ No RAW image files found in the directory")
        print(f"   Supported formats: {', '.join(sorted(set(ext.upper().lstrip('.') for ext in RAW_EXTENSIONS)))}")
        sys.exit(0)
    
    print(f"📷 Found {len(raw_files)} RAW file(s)")
    print()
    
    # Process each RAW file
    success_count = 0
    error_count = 0
    
    for raw_file in raw_files:
        print(f"→ Extracting: {raw_file.name}")
        
        if extract_jpeg_preview(raw_file, output_dir):
            print(f"   ✅ Success")
            success_count += 1
        else:
            error_count += 1
        
        print()
    
    # Print summary
    print("=" * 60)
    print(f"✅ Successfully extracted: {success_count}")
    print(f"❌ Errors: {error_count}")
    print(f"📁 JPEGs saved in: {output_dir}")


if __name__ == "__main__":
    main()

