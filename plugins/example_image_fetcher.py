"""
Example Custom Image Fetcher Plugin
====================================

This is an example plugin that shows how to create a custom image fetcher.
Copy this file and modify it to create your own image provider.

Usage:
    1. Copy this file and rename it (e.g., my_image_fetcher.py)
    2. Modify the fetch() method to use your image API
    3. The plugin will be automatically discovered and registered
"""

from typing import Optional
from src.plugins import ImageFetcherPlugin


class ExampleImageFetcher(ImageFetcherPlugin):
    """
    Example custom image fetcher using a hypothetical API.
    
    Replace the fetch() method with your own implementation.
    """
    
    name = "example_images"
    description = "Example image fetcher plugin (template)"
    version = "1.0.0"
    author = "Your Name"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the fetcher.
        
        Args:
            api_key: Optional API key for the image service
        """
        self.api_key = api_key
        self.base_url = "https://api.example.com/images"
    
    async def fetch(self, prompt: str, **kwargs) -> Optional[bytes]:
        """
        Fetch an image based on the prompt.
        
        Args:
            prompt: Text description of the image to generate
            **kwargs: Additional parameters (width, height, style, etc.)
            
        Returns:
            Image bytes if successful, None otherwise
        """
        # Example implementation - replace with your API
        # 
        # import aiohttp
        # 
        # width = kwargs.get('width', 512)
        # height = kwargs.get('height', 512)
        # 
        # async with aiohttp.ClientSession() as session:
        #     params = {
        #         'prompt': prompt,
        #         'width': width,
        #         'height': height,
        #         'api_key': self.api_key,
        #     }
        #     async with session.get(self.base_url, params=params) as response:
        #         if response.status == 200:
        #             return await response.read()
        #         return None
        
        # For now, return None (not implemented)
        print(f"[ExampleImageFetcher] Would fetch image for: {prompt}")
        return None
    
    def validate_config(self) -> bool:
        """Validate that the plugin is properly configured."""
        # Add your validation logic here
        # For example, check if API key is set:
        # return self.api_key is not None
        return True


# The plugin class that will be discovered
plugin_class = ExampleImageFetcher
