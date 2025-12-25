# 🎓 AnkiTect: Intelligent Anki Deck Generator

> **Transform vocabulary lists into multimedia-rich Anki decks** with one command. AnkiTect generates cards with audio, images, etymologies, and mnemonics automatically.

**Supported Languages:** German (DE), English (EN), and expandable...

---

## ✨ Key Features

### 🎯 **Smart Card Generation**

- **Multiple Card Types** - Recognition (flashcard), Production (fill-in), Listening (audio-first), Context (sentence cloze)
- **Professional Audio** - Microsoft Edge-TTS with **random voice selection per card** (4 voices per language)
- **Auto Image Fetching** - Downloads relevant images from Pollinations API
- **Rich Metadata** - Etymology, IPA pronunciation, morphology, mnemonics, analogues, contextual examples
- **Dual Language Support** - German (DE) & English (EN) with language-specific configuration

### 📊 **Dynamic Deck Organization**

- **Auto Month-Based Subdecks** - Creates subdecks automatically based on current month/year
- **Main Decks** - Separate parent decks for each language:
  - 🇩🇪 **DE Das Fundament** → 2025.12 | Dezember → Cards
  - 🇬🇧 **GB The Cornerstone** → 2025.12 | December → Cards
- **Zero-Config** - Subdeck names adjust each month automatically

### ⚡ **High Performance**

- **Async Processing** - Concurrent TTS + image downloads
- **Smart Caching** - Avoids re-downloading identical media
- **Error Handling** - Graceful fallbacks for failed resources
- **Adaptive Rate Limiting** - Detects 429 errors and adjusts concurrency

### 🎨 **Beautiful Card Design**

- **Modern CSS** - Glassmorphic UI with gradients and animations
- **Gender-Based Colors** (German):
  - 🔵 **der** (articles) → Blue
  - 🔴 **die** (nouns) → Red
  - 🟢 **das** (articles) → Green
  - 🟣 **No article** → Purple
- **Responsive Layout** - Works on Anki Desktop, AnkiDroid, AnkiWeb

---

## 🚀 Quick Start

### 1. **Install Dependencies**

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Mac/Linux
pip install -r requirements.txt
```

### 2. **Prepare Your Vocabulary**

Edit `vocabulary.csv` with your words. Required columns:

- `TargetWord` - The word to learn
- `Meaning` - Definition/translation
- `Tags` - Category tags

Optional columns add richness:

- `IPA` - Pronunciation
- `ContextSentences` - Example usage
- `Etymology` - Word origin
- `Mnemonic` - Memory trick
- `Analogues` - Related words

### 3. **Select Language & Build**

Edit `src/config/settings.py`:

```python
CURRENT_LANG = "DE"  # or "EN"
```

Then run:

```bash
python build_deck.py
```

Output appears in `data/output/` as `.apkg` file.

### 4. **Import to Anki**

1. Open Anki
2. File → Import → Select `.apkg` file
3. Start reviewing! 🎉

---

## 📋 Configuration

### Language Settings (`src/config/languages.py`)

Each language defines:

- Deck name (shown in Anki)
- Default TTS voice
- **Available voices** - Pool for random selection
- Localized month names

```python
"DE": {
    "deck_name": "DE Das Fundament",
    "voice": "de-DE-ConradNeural",
    "available_voices": [
        "de-DE-ConradNeural",
        "de-DE-AmalaNeural",
        "de-DE-KatjaNeural",
        "de-DE-KillianNeural",
    ],
    "month_names": {1: "Januar", 2: "Februar", ...}
}
```

### Global Settings (`src/config/settings.py`)

```python
CURRENT_LANG = "DE"            # Language to build
Config.CONCURRENCY = 4         # Parallel download workers
Config.RETRIES = 5             # Retry failed requests
Config.TIMEOUT = 60            # Request timeout (seconds)
```

### Deck Naming Formula

Decks are named dynamically based on current date:

```
{DECK_NAME}::{YEAR}.{MONTH:02d} | {MONTH_NAME}
```

Examples:

- December 2025: `DE Das Fundament::2025.12 | Dezember`
- January 2026: `DE Das Fundament::2026.01 | Januar`
- February 2025: `GB The Cornerstone::2025.02 | February`

---

## 📁 Project Structure

```
├── src/
│   ├── config/           # Language & app configuration
│   │   ├── languages.py  # Language settings + voice lists
│   │   └── settings.py   # Global config + deck naming
│   ├── deck/             # Anki deck building logic
│   │   ├── builder.py    # Main deck generator
│   │   └── cache.py      # Media caching system
│   ├── fetchers/         # External data sources
│   │   ├── audio.py      # TTS with random voice selection
│   │   ├── images.py     # Image downloads
│   │   └── base.py       # Base fetcher class
│   ├── models/           # Data classes
│   │   └── card.py       # Card structure
│   ├── templates/        # Anki card design
│   │   └── __init__.py   # HTML/CSS templates
│   └── utils/            # Utilities
│       ├── helpers.py    # Helper functions
│       └── logger.py     # Logging setup
├── data/
│   ├── input/            # Input CSVs (optional)
│   ├── output/           # Generated .apkg files (gitignored)
│   └── cache/            # Media cache (gitignored)
├── media/                # Generated images/audio (gitignored)
├── vocabulary.csv        # Vocabulary source (pipe-delimited)
├── build_deck.py         # Main entry point
├── requirements.txt      # Python dependencies
├── LICENSE               # MIT License
└── README.md            # This file
```

---

## 🎤 Random Voice Selection

### How It Works

Each time audio is generated (word pronunciation or sentence), a **random voice** is selected from the language's available pool. This means:

- Same word on review #1: Male voice (Conrad)
- Same word on review #2: Female voice (Katja)
- Same word on review #3: Different female voice (Amalia)

### Benefits

✅ Adapts to different accents  
✅ Improves listening comprehension  
✅ Makes learning more engaging  
✅ Prepares for real-world variety

### Available Voices

**German (DE):**

- 🔵 ConradNeural (male, deep)
- 🔴 AmalaNeural (female, warm)
- 🟡 KatjaNeural (female, clear)
- 🟢 KillianNeural (male, young)

**English (EN):**

- 🔵 SoniaNeural (female, British)
- 🔴 RyanNeural (male, British)
- 🟡 ThomasNeural (male, British)
- 🟢 LibbyNeural (female, British)

To customize, edit `src/config/languages.py`:

```python
"available_voices": [
    "de-DE-ConradNeural",
    "de-DE-NewVoiceNeural",  # Add new voice
]
```

---

## 📊 CSV Format

**Pipe-delimited** (|) with headers:

```csv
TargetWord|Meaning|IPA|Part_of_Speech|Gender|Morphology|Nuance|ContextSentences|ContextTranslation|Etymology|Mnemonic|Analogues|Image|Tags
die Paraphilie|Paraphilia|/parafeˈliː/|Noun|die|Pl: -n|formal|1. Example<br>2. Example|1. Translation<br>2. Translation|Gk. para-+philia|Sounds like...|Analogues here|url|Noun C1 Psychology
```

**Column Explanations:**

- **TargetWord** - Word with article (German) or bare word (English)
- **Meaning** - Definition or translation
- **IPA** - Phonetic pronunciation
- **Part_of_Speech** - Noun, Verb, Adj, etc.
- **Gender** - der/die/das for German, empty for English
- **Morphology** - Plurals, tenses, etc.
- **Nuance** - Formal, Colloquial, Archaic, etc.
- **ContextSentences** - Example uses (HTML `<br>` for line breaks)
- **ContextTranslation** - Sentence translations
- **Etymology** - Word origin/derivation
- **Mnemonic** - Memory aid/trick
- **Analogues** - Similar/related words
- **Image** - URL to image (or leave empty for auto-fetch)
- **Tags** - Searchable tags (comma or space separated)

---

## 🔧 Customization

### Add New Language

1. **Add to `src/config/languages.py`:**

```python
"FR": {
    "deck_name": "FR Français Facile",
    "voice": "fr-FR-DeniseNeural",
    "available_voices": [
        "fr-FR-DeniseNeural",
        "fr-FR-Henri Neural",
        # Add up to 4 voices
    ],
    "month_names": {
        1: "Janvier", 2: "Février", 3: "Mars",
        # ... complete all 12 months
    }
}
```

2. **Update `src/config/settings.py`:**

```python
CURRENT_LANG = "FR"  # Change active language
```

3. **Run builder:**

```bash
python build_deck.py
```

### Modify Card Templates

Edit `src/templates/__init__.py`:

- `FRONT_REC` - Recognition card question side
- `BACK_REC` - Recognition card answer side
- `FRONT_PROD` - Production (write answer) front
- `FRONT_LIST` - Listening card (audio-first)
- `FRONT_CONTEXT` - Cloze deletion card
- `CSS` - All styling (colors, fonts, layout)

### Filter Words by Tag

Edit `build_deck.py`:

```python
# Only C1 advanced level
df = df[df['Tags'].str.contains('C1', na=False)]

# Only specific category
df = df[df['Tags'].str.contains('Business|IT', na=False)]
```

### Disable Media Downloads

In `src/config/settings.py`:

```python
DOWNLOAD_IMAGES = False  # Skip image downloads
DOWNLOAD_AUDIO = False   # Skip audio generation
```

---

## ⚙️ Advanced Options

### Performance Tuning

```python
# src/config/settings.py

Config.CONCURRENCY = 2      # Reduce for slow connections
Config.RETRIES = 3          # Lower to fail faster
Config.TIMEOUT = 120        # Increase for large images
```

### Custom Deck Hierarchy

```python
# src/config/settings.py
# Default: "DE Das Fundament::2025.12 | Dezember"

# Custom format (e.g., add proficiency level):
DECK_NAME = f"DE Das Fundament::C1 Advanced::{YEAR}.{MONTH_NAME}"
# Result: "DE Das Fundament::C1 Advanced::2025.December"
```

### Batch Processing Multiple CSVs

```python
# build_deck.py
import os

for csv_file in os.listdir('data/input/'):
    df = pd.read_csv(f'data/input/{csv_file}', sep='|')
    # Process each file...
    builder.build_deck(df)
```

---

## 🚨 Troubleshooting

| Issue                           | Solution                                                          |
| ------------------------------- | ----------------------------------------------------------------- |
| **"429 Too Many Requests"**     | Reduce `CONCURRENCY` in settings (try 2 or 1)                     |
| **Cards have no audio**         | Check internet, reduce `CONCURRENCY`, verify voice names          |
| **Images not downloading**      | Check image URLs valid, verify proxy/firewall, check image column |
| **Build takes forever**         | Increase `CONCURRENCY` (if connection allows), disable images     |
| **Cards show placeholder text** | Check CSV column names match exactly, verify data format          |
| **Anki won't import .apkg**     | Try re-downloading latest Anki version, check file integrity      |

### Getting Help

1. Check `build_output.txt` for detailed error logs
2. Review cached files in `data/cache/` to understand what succeeded
3. Test with smaller CSV (5-10 words) to isolate issues
4. Verify internet connection and that TTS/image services aren't blocked

---

## 📦 Dependencies

| Package    | Purpose              | License    |
| ---------- | -------------------- | ---------- |
| `genanki`  | Anki deck generation | MIT        |
| `pandas`   | CSV manipulation     | BSD-3      |
| `edge-tts` | Microsoft TTS voice  | MIT        |
| `aiohttp`  | Async HTTP requests  | Apache 2.0 |
| `pillow`   | Image processing     | HPND       |
| `tqdm`     | Progress bars        | MPL 2.0    |

Install all with:

```bash
pip install -r requirements.txt
```

---

## 📈 Performance Tips

1. **Use caching** - Runs 2-3x faster with cached media
2. **Reduce concurrency on weak connections** - Set `CONCURRENCY = 1-2`
3. **Batch imports** - Import full .apkg once, then add incrementally
4. **Clear old cache** - Delete `data/cache/` if media becomes stale
5. **Test with small CSV first** - Verify settings before processing 500+ words

---

## 📜 License

MIT License - Free for personal and commercial use.  
See [LICENSE](LICENSE) file for details.

---

## 🎯 Roadmap

- [ ] Web UI for deck management
- [ ] Support for images without URL (auto-crop Wikipedia)
- [ ] Spaced repetition analytics integration
- [ ] Support for Mandarin, Spanish, French, Russian
- [ ] Audio waveform display on cards
- [ ] Dictionary lookup integration

---

**Made with ❤️ for language learners worldwide**

**Questions?** Check the troubleshooting section or review `src/` code comments.
