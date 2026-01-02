"""
AnkiTect: Intelligent Anki Deck Generator
------------------------------------------

This is the main entry point for building Anki decks from vocabulary lists.
"""

import asyncio
import sys
from pathlib import Path

from src.config import Config
from src.deck import AnkiDeckBuilder


async def main():
    """Main entry point."""
    language = Config.CURRENT_LANG
    
    # Check if vocabulary file exists
    if not Path(Config.CSV_FILE).exists():
        print(f"❌ Error: {Config.CSV_FILE} not found!")
        print("Please ensure vocabulary.csv is in the project root.")
        return False
    
    try:
        # Initialize builder
        builder = AnkiDeckBuilder(language=language)
        
        # Build deck
        success = await builder.build(Config.CSV_FILE)
        if not success:
            return False
        
        # Export deck
        builder.export()
        return True
    
    except KeyboardInterrupt:
        print("\n[!] Build interrupted by user.")
        return False
    except Exception as e:
        import traceback
        print(f"[ERROR] Fatal error: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n[!] Aborted by user.")
        sys.exit(1)
