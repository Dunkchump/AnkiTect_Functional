"""Data models for AnkiTect."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CardData:
    """Структура даних для однієї картки."""
    
    # Основні дані
    target_word: str
    meaning: str
    part_of_speech: str
    
    # Метадані
    ipa: str = ""
    gender: str = ""
    morphology: str = ""
    etymology: str = ""
    nuance: str = ""
    
    # Контекст
    sentences: list = field(default_factory=lambda: ["", "", ""])
    context_translation: str = ""
    context_sentences: str = ""
    
    # Дополнительно
    mnemonic: str = ""
    analogues: str = ""
    image_url: str = ""
    tags: str = ""
    
    # Файли
    audio_word: Optional[str] = None
    audio_sentences: list = field(default_factory=lambda: [None, None, None])
    image_path: Optional[str] = None
    
    # UUID для унікальності
    uuid: str = ""
