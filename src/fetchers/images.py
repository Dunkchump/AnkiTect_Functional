"""Image fetcher - downloading images from URLs."""

import asyncio
import os
import re
import ssl
import random
from typing import Optional, Callable

import aiohttp

from ..config import Config
from .base import BaseFetcher


class ImageFetcher(BaseFetcher):
    """Handle image downloading with adaptive parallelization."""
    
    # Realistic browser headers
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://pollinations.ai/",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }
    
    def __init__(self, concurrency_callback: Optional[Callable] = None):
        """
        Initialize image fetcher.
        
        Args:
            concurrency_callback: Function to call for adaptive concurrency adjustments
        """
        self.concurrency_callback = concurrency_callback
        self.retries = Config.RETRIES
    
    def extract_url(self, raw_input: str) -> str:
        """Extract URL from various formats."""
        if not raw_input or str(raw_input).lower() == "nan":
            return ""
        
        # Try to extract from img tag
        match = re.search(r'src=["\']([^"\']+)["\']', str(raw_input))
        if match:
            return match.group(1)
        
        return str(raw_input).strip().strip('"').strip("'")
    
    async def fetch(self, source: str, output_path: str) -> bool:
        """
        Download image from URL.
        
        Args:
            source: Image URL or HTML tag with URL
            output_path: Path to save image
            
        Returns:
            True if successful, False otherwise
        """
        url = self.extract_url(source)
        
        if not url or len(url) < 5:
            return False
        
        # Check if already exists and is valid
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True
        
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        
        # Exponential backoff with jitter
        for attempt in range(self.retries):
            try:
                # Realistic delay before request
                delay = random.uniform(Config.REQUEST_DELAY_MIN, Config.REQUEST_DELAY_MAX)
                await asyncio.sleep(delay)
                
                connector = aiohttp.TCPConnector(ssl=False)
                timeout = aiohttp.ClientTimeout(total=Config.IMAGE_TIMEOUT)
                
                async with aiohttp.ClientSession(connector=connector, headers=self.HEADERS, timeout=timeout) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            content = await response.read()
                            
                            if len(content) > 500:  # File size check
                                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                                with open(output_path, 'wb') as f:
                                    f.write(content)
                                
                                if self.concurrency_callback:
                                    self.concurrency_callback(status_code=200, is_success=True)
                                
                                return True
                        else:
                            if response.status == 429 and self.concurrency_callback:
                                self.concurrency_callback(status_code=429)
                            
                            backoff = 2 ** attempt
                            await asyncio.sleep(backoff)
            
            except asyncio.TimeoutError:
                if self.concurrency_callback:
                    self.concurrency_callback(is_success=False)
                
                if attempt < self.retries - 1:
                    await asyncio.sleep(2 ** attempt)
            
            except Exception as e:
                if self.concurrency_callback:
                    self.concurrency_callback(is_success=False)
                
                if attempt < self.retries - 1:
                    await asyncio.sleep(2 ** attempt)
        
        return False
