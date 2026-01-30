"""Text parsing utilities for consistent text processing across the application."""

import re
import unicodedata
from typing import List


class TextParser:
    """
    Centralized text parsing utilities.
    
    Eliminates DRY violations by providing single source of truth
    for sentence splitting, text normalization, etc.
    """
    
    # Unified sentence splitting pattern (handles <br>, <br/>, <br />, \n)
    SENTENCE_PATTERN = re.compile(r'<br\s*/?>|\n')
    
    # HTML tag removal pattern
    HTML_TAG_PATTERN = re.compile(r'<[^>]+>')
    
    # Numbered list cleanup pattern
    NUMBERED_LIST_PATTERN = re.compile(r'(^|\s)\d+[\.\)]\s*')
    
    # Whitespace normalization pattern
    WHITESPACE_PATTERN = re.compile(r'\s+')
    
    @classmethod
    def normalize_unicode(cls, text: str) -> str:
        """
        Normalize text to NFC form for consistent Unicode handling.
        
        Prevents issues with characters like é being represented as
        either a single codepoint (NFC) or base + combining accent (NFD).
        
        Args:
            text: Input text
            
        Returns:
            NFC-normalized text
        """
        if not text:
            return ""
        return unicodedata.normalize('NFC', str(text))
    
    @classmethod
    def split_sentences(cls, text: str, max_count: int = 3, pad: bool = True) -> List[str]:
        """
        Split text into sentences using unified pattern.
        
        Handles both <br> tags and newlines consistently.
        
        Args:
            text: Raw text with sentences
            max_count: Maximum number of sentences to return
            pad: If True, pad result with empty strings to reach max_count
            
        Returns:
            List of sentences (stripped), optionally padded
        """
        if not text:
            return [""] * max_count if pad else []
        
        # Normalize first
        text = cls.normalize_unicode(str(text))
        
        # Split and clean
        sentences = [s.strip() for s in cls.SENTENCE_PATTERN.split(text) if s.strip()]
        
        # Limit to max_count
        sentences = sentences[:max_count]
        
        # Pad if needed
        if pad:
            while len(sentences) < max_count:
                sentences.append("")
        
        return sentences
    
    @classmethod
    def clean_for_tts(cls, text: str) -> str:
        """
        Clean text for TTS processing.
        
        Removes HTML, numbered lists, normalizes whitespace.
        
        Args:
            text: Raw text
            
        Returns:
            Cleaned text ready for TTS
        """
        import html
        
        if not text:
            return ""
        
        # Unescape HTML entities
        text = html.unescape(str(text))
        
        # Remove HTML tags
        text = cls.HTML_TAG_PATTERN.sub('', text)
        
        # Remove numbered lists
        text = cls.NUMBERED_LIST_PATTERN.sub(' ', text)
        
        # Normalize whitespace
        text = cls.WHITESPACE_PATTERN.sub(' ', text).strip()
        
        # Unicode normalization
        text = cls.normalize_unicode(text)
        
        return text
    
    @classmethod
    def clean_for_display(cls, text: str) -> str:
        """
        Clean translation text for card display.
        
        Preserves line breaks but removes numbered list prefixes.
        
        Args:
            text: Raw text
            
        Returns:
            Cleaned text for display
        """
        if not text:
            return ""
        
        # Normalize first
        text = cls.normalize_unicode(str(text))
        
        # Split by line separators, clean each line
        lines = re.split(r'(<br>|\n)', text)
        cleaned_lines = []
        
        for line in lines:
            if line in ['<br>', '\n']:
                cleaned_lines.append(line)
            else:
                # Remove numbered list prefix
                cleaned_lines.append(re.sub(r'^\s*\d+[\.\)]\s*', '', line))
        
        return "".join(cleaned_lines)
    
    @classmethod
    def format_analogues_html(cls, text: str) -> str:
        """
        Format analogues table from text.
        
        Converts "EN: word\\nDE: wort" format to HTML table.
        
        Args:
            text: Raw analogues text
            
        Returns:
            HTML table string
        """
        if not text or str(text).lower() == 'nan':
            return ""
        
        # Normalize first
        text = cls.normalize_unicode(str(text))
        
        lines = cls.SENTENCE_PATTERN.split(text)
        html_out = '<table class="analogues-table">'
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split(':', 1)
            if len(parts) == 2:
                code = parts[0].strip()
                word = parts[1].strip()
                html_out += f'<tr class="ana-row"><td class="ana-lang">{code}</td><td class="ana-word">{word}</td></tr>'
            else:
                html_out += f'<tr class="ana-row"><td colspan="2" class="ana-word">{line}</td></tr>'
        
        html_out += '</table>'
        return html_out
