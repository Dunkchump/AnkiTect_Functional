"""
AI Service - LLM Integration for Intelligent Flashcard Enhancement.

Provides abstraction over multiple LLM providers (OpenAI, Anthropic, local models)
for generating high-quality flashcard content:
- Example sentences
- Enhanced image prompts
- Mnemonics
- Context-aware translations
"""

import asyncio
import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp

from ..config import Config


class AIProvider(Enum):
    """Supported AI providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"  # Local models
    GROQ = "groq"  # Fast inference


@dataclass
class AIConfig:
    """Configuration for AI service."""
    provider: AIProvider = AIProvider.OPENAI
    model: str = "gpt-4o-mini"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1000
    timeout: int = 30


class BaseAIProvider(ABC):
    """Abstract base class for AI providers."""
    
    def __init__(self, config: AIConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self) -> None:
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    @abstractmethod
    async def complete(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate completion for the given prompt."""
        pass


class OpenAIProvider(BaseAIProvider):
    """OpenAI API provider (also works with compatible APIs)."""
    
    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    
    async def complete(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate completion using OpenAI API."""
        session = await self._get_session()
        
        base_url = self.config.base_url or self.DEFAULT_BASE_URL
        url = f"{base_url}/chat/completions"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        
        try:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    error = await response.text()
                    raise Exception(f"OpenAI API error {response.status}: {error[:200]}")
        except asyncio.TimeoutError:
            raise Exception("OpenAI API timeout")


class AnthropicProvider(BaseAIProvider):
    """Anthropic Claude API provider."""
    
    BASE_URL = "https://api.anthropic.com/v1"
    
    async def complete(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate completion using Anthropic API."""
        session = await self._get_session()
        
        url = f"{self.BASE_URL}/messages"
        
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["content"][0]["text"]
                else:
                    error = await response.text()
                    raise Exception(f"Anthropic API error {response.status}: {error[:200]}")
        except asyncio.TimeoutError:
            raise Exception("Anthropic API timeout")


class OllamaProvider(BaseAIProvider):
    """Ollama local model provider."""
    
    DEFAULT_BASE_URL = "http://localhost:11434"
    
    async def complete(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate completion using local Ollama."""
        session = await self._get_session()
        
        base_url = self.config.base_url or self.DEFAULT_BASE_URL
        url = f"{base_url}/api/generate"
        
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        
        payload = {
            "model": self.config.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
            },
        }
        
        try:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("response", "")
                else:
                    error = await response.text()
                    raise Exception(f"Ollama error {response.status}: {error[:200]}")
        except aiohttp.ClientConnectorError:
            raise Exception("Cannot connect to Ollama. Is it running?")


class GroqProvider(BaseAIProvider):
    """Groq fast inference provider."""
    
    BASE_URL = "https://api.groq.com/openai/v1"
    
    async def complete(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate completion using Groq API (OpenAI-compatible)."""
        session = await self._get_session()
        
        url = f"{self.BASE_URL}/chat/completions"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        
        try:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    error = await response.text()
                    raise Exception(f"Groq API error {response.status}: {error[:200]}")
        except asyncio.TimeoutError:
            raise Exception("Groq API timeout")


class AIService:
    """
    High-level AI service for flashcard content generation.
    
    Provides specialized methods for vocabulary learning:
    - Generate example sentences at specific difficulty levels
    - Create memorable mnemonics
    - Enhance image generation prompts
    - Generate context-aware translations
    """
    
    # System prompts for different tasks
    SYSTEM_PROMPTS = {
        "sentences": """You are a language learning expert creating example sentences for vocabulary flashcards.
Rules:
- Create natural, useful sentences that a native speaker would actually say
- Include the target word in a clear, memorable context
- Match the requested difficulty level (A1-C2 CEFR)
- Wrap the target word in <b></b> tags
- Return ONLY the sentences, one per line, no numbering""",

        "mnemonic": """You are a memory expert creating mnemonics for vocabulary learning.
Rules:
- Create a memorable, vivid association
- Use wordplay, sound associations, or visual imagery
- Keep it short (1-2 sentences)
- Make it stick in memory
- Return ONLY the mnemonic, no explanation""",

        "image_prompt": """You are an expert at creating image generation prompts for vocabulary flashcards.
Rules:
- Create a vivid, specific visual description
- Focus on a single clear concept that represents the word
- Use style hints: illustrated, colorful, clean background
- Avoid text in images
- Keep under 100 words
- Return ONLY the prompt""",

        "translation": """You are a translator providing context-aware translations.
Rules:
- Translate the sentences naturally, not literally
- Preserve the meaning and tone
- Return translations in the same order, separated by newlines
- Return ONLY the translations""",
    }
    
    def __init__(self, config: Optional[AIConfig] = None):
        """
        Initialize AI service.
        
        Args:
            config: AI configuration. If None, uses environment variables.
        """
        self.config = config or self._config_from_env()
        self._provider: Optional[BaseAIProvider] = None
    
    def _config_from_env(self) -> AIConfig:
        """Create config from environment variables."""
        provider_name = os.environ.get("AI_PROVIDER", "openai").lower()
        
        provider_map = {
            "openai": AIProvider.OPENAI,
            "anthropic": AIProvider.ANTHROPIC,
            "ollama": AIProvider.OLLAMA,
            "groq": AIProvider.GROQ,
        }
        
        model_defaults = {
            AIProvider.OPENAI: "gpt-4o-mini",
            AIProvider.ANTHROPIC: "claude-3-haiku-20240307",
            AIProvider.OLLAMA: "llama3.2",
            AIProvider.GROQ: "llama-3.1-8b-instant",
        }
        
        provider = provider_map.get(provider_name, AIProvider.OPENAI)
        
        return AIConfig(
            provider=provider,
            model=os.environ.get("AI_MODEL", model_defaults.get(provider, "gpt-4o-mini")),
            api_key=os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("GROQ_API_KEY"),
            base_url=os.environ.get("AI_BASE_URL"),
            temperature=float(os.environ.get("AI_TEMPERATURE", "0.7")),
        )
    
    def _get_provider(self) -> BaseAIProvider:
        """Get or create the appropriate provider."""
        if self._provider is None:
            provider_classes = {
                AIProvider.OPENAI: OpenAIProvider,
                AIProvider.ANTHROPIC: AnthropicProvider,
                AIProvider.OLLAMA: OllamaProvider,
                AIProvider.GROQ: GroqProvider,
            }
            provider_class = provider_classes.get(self.config.provider, OpenAIProvider)
            self._provider = provider_class(self.config)
        return self._provider
    
    async def close(self) -> None:
        """Close the AI service and release resources."""
        if self._provider:
            await self._provider.close()
            self._provider = None
    
    async def generate_sentences(
        self, 
        word: str, 
        part_of_speech: str,
        meaning: str,
        language: str = "German",
        target_language: str = "German",
        count: int = 3,
        level: str = "B1"
    ) -> List[str]:
        """
        Generate example sentences for a vocabulary word.
        
        Args:
            word: The target vocabulary word
            part_of_speech: Part of speech (noun, verb, etc.)
            meaning: English meaning of the word
            language: Language of the word
            target_language: Language for sentences
            count: Number of sentences to generate
            level: CEFR difficulty level (A1-C2)
            
        Returns:
            List of example sentences with the word marked in <b></b>
        """
        provider = self._get_provider()
        
        prompt = f"""Generate {count} example sentences in {target_language} using the word "{word}" ({part_of_speech}).
The word means: {meaning}
Difficulty level: {level}
Wrap the target word in <b></b> tags."""
        
        try:
            response = await provider.complete(prompt, self.SYSTEM_PROMPTS["sentences"])
            sentences = [s.strip() for s in response.strip().split("\n") if s.strip()]
            return sentences[:count]
        except Exception as e:
            print(f"AI sentence generation failed: {e}")
            return []
    
    async def generate_mnemonic(
        self,
        word: str,
        meaning: str,
        language: str = "German",
        native_language: str = "English"
    ) -> str:
        """
        Generate a memorable mnemonic for a vocabulary word.
        
        Args:
            word: The target vocabulary word
            meaning: Meaning of the word
            language: Language of the word
            native_language: User's native language
            
        Returns:
            Mnemonic string
        """
        provider = self._get_provider()
        
        prompt = f"""Create a mnemonic for the {language} word "{word}" which means "{meaning}" in {native_language}.
Use sound associations, visual imagery, or wordplay to make it memorable."""
        
        try:
            response = await provider.complete(prompt, self.SYSTEM_PROMPTS["mnemonic"])
            return response.strip()
        except Exception as e:
            print(f"AI mnemonic generation failed: {e}")
            return ""
    
    async def enhance_image_prompt(
        self,
        word: str,
        meaning: str,
        basic_prompt: Optional[str] = None,
        style: str = "illustrated vocabulary flashcard"
    ) -> str:
        """
        Enhance or generate an image prompt for the vocabulary word.
        
        Args:
            word: The target vocabulary word
            meaning: Meaning of the word
            basic_prompt: Optional basic prompt to enhance
            style: Desired image style
            
        Returns:
            Enhanced image generation prompt
        """
        provider = self._get_provider()
        
        if basic_prompt:
            prompt = f"""Enhance this image prompt for the word "{word}" ({meaning}):
Original: {basic_prompt}
Style: {style}
Make it more vivid and specific for image generation."""
        else:
            prompt = f"""Create an image generation prompt for the word "{word}" which means "{meaning}".
Style: {style}
The image should clearly represent the concept."""
        
        try:
            response = await provider.complete(prompt, self.SYSTEM_PROMPTS["image_prompt"])
            return response.strip()
        except Exception as e:
            print(f"AI image prompt generation failed: {e}")
            return basic_prompt or f"A visual representation of {meaning}, {style}"
    
    async def translate_sentences(
        self,
        sentences: List[str],
        source_language: str = "German",
        target_language: str = "English"
    ) -> List[str]:
        """
        Translate sentences with context awareness.
        
        Args:
            sentences: List of sentences to translate
            source_language: Language of the sentences
            target_language: Language to translate to
            
        Returns:
            List of translated sentences
        """
        if not sentences:
            return []
        
        provider = self._get_provider()
        
        sentences_text = "\n".join(sentences)
        prompt = f"""Translate these {source_language} sentences to {target_language}:

{sentences_text}"""
        
        try:
            response = await provider.complete(prompt, self.SYSTEM_PROMPTS["translation"])
            translations = [t.strip() for t in response.strip().split("\n") if t.strip()]
            # Ensure we return same number of translations
            while len(translations) < len(sentences):
                translations.append("")
            return translations[:len(sentences)]
        except Exception as e:
            print(f"AI translation failed: {e}")
            return [""] * len(sentences)
    
    async def generate_etymology(
        self,
        word: str,
        language: str = "German"
    ) -> str:
        """
        Generate etymological information for a word.
        
        Args:
            word: The target vocabulary word
            language: Language of the word
            
        Returns:
            Etymology explanation
        """
        provider = self._get_provider()
        
        prompt = f"""Provide a brief, interesting etymology for the {language} word "{word}".
Include origin, root words, and historical evolution.
Keep it concise (2-3 sentences) and engaging for language learners."""
        
        try:
            response = await provider.complete(prompt)
            return response.strip()
        except Exception as e:
            print(f"AI etymology generation failed: {e}")
            return ""
    
    async def batch_enhance(
        self,
        word: str,
        meaning: str,
        part_of_speech: str,
        language: str = "German"
    ) -> Dict[str, Any]:
        """
        Generate multiple enhancements for a word in parallel.
        
        Args:
            word: The target vocabulary word
            meaning: Meaning of the word
            part_of_speech: Part of speech
            language: Language of the word
            
        Returns:
            Dictionary with sentences, mnemonic, image_prompt, etymology
        """
        tasks = [
            self.generate_sentences(word, part_of_speech, meaning, language),
            self.generate_mnemonic(word, meaning, language),
            self.enhance_image_prompt(word, meaning),
            self.generate_etymology(word, language),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            "sentences": results[0] if not isinstance(results[0], Exception) else [],
            "mnemonic": results[1] if not isinstance(results[1], Exception) else "",
            "image_prompt": results[2] if not isinstance(results[2], Exception) else "",
            "etymology": results[3] if not isinstance(results[3], Exception) else "",
        }
    
    @property
    def is_configured(self) -> bool:
        """Check if AI service is properly configured."""
        if self.config.provider == AIProvider.OLLAMA:
            return True  # Ollama doesn't need API key
        return bool(self.config.api_key)


# Convenience factory function
def create_ai_service(
    provider: str = "openai",
    model: Optional[str] = None,
    api_key: Optional[str] = None
) -> AIService:
    """
    Create an AI service with specified configuration.
    
    Args:
        provider: Provider name (openai, anthropic, ollama, groq)
        model: Model name (uses default if None)
        api_key: API key (uses environment if None)
        
    Returns:
        Configured AIService instance
    """
    provider_enum = {
        "openai": AIProvider.OPENAI,
        "anthropic": AIProvider.ANTHROPIC,
        "ollama": AIProvider.OLLAMA,
        "groq": AIProvider.GROQ,
    }.get(provider.lower(), AIProvider.OPENAI)
    
    config = AIConfig(
        provider=provider_enum,
        model=model or {
            AIProvider.OPENAI: "gpt-4o-mini",
            AIProvider.ANTHROPIC: "claude-3-haiku-20240307",
            AIProvider.OLLAMA: "llama3.2",
            AIProvider.GROQ: "llama-3.1-8b-instant",
        }.get(provider_enum, "gpt-4o-mini"),
        api_key=api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("GROQ_API_KEY"),
    )
    
    return AIService(config)
