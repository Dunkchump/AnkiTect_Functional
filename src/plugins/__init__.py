"""
Plugin System - Extensible Architecture for AnkiTect.

Enables dynamic loading of:
- Custom image providers (DALL-E, Midjourney, Stable Diffusion)
- Custom TTS engines (Google, Amazon Polly, local Piper)
- Custom card templates
- Custom data processors

Plugin Discovery:
- Plugins are Python files in the 'plugins/' directory
- Each plugin must have a 'register(manager)' function
- Plugins are loaded at startup or on-demand
"""

import importlib.util
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

from ..config import Config
from ..fetchers.base import BaseFetcher


@dataclass
class PluginInfo:
    """Information about a loaded plugin."""
    name: str
    version: str
    description: str
    author: str
    plugin_type: str  # 'image_fetcher', 'audio_fetcher', 'template', 'processor'
    file_path: str
    loaded_at: datetime
    enabled: bool = True


class PluginBase(ABC):
    """Base class for all plugins."""
    
    # Plugin metadata - override in subclass
    PLUGIN_NAME: str = "Base Plugin"
    PLUGIN_VERSION: str = "1.0.0"
    PLUGIN_DESCRIPTION: str = "A plugin for AnkiTect"
    PLUGIN_AUTHOR: str = "Unknown"
    PLUGIN_TYPE: str = "generic"
    
    @classmethod
    def get_info(cls) -> PluginInfo:
        """Get plugin information."""
        return PluginInfo(
            name=cls.PLUGIN_NAME,
            version=cls.PLUGIN_VERSION,
            description=cls.PLUGIN_DESCRIPTION,
            author=cls.PLUGIN_AUTHOR,
            plugin_type=cls.PLUGIN_TYPE,
            file_path="",
            loaded_at=datetime.now(),
        )


class ImageFetcherPlugin(PluginBase, BaseFetcher):
    """Base class for image fetcher plugins."""
    
    PLUGIN_TYPE = "image_fetcher"
    
    @abstractmethod
    async def fetch(self, source: str, output_path: str) -> bool:
        """Generate/download image from source to output_path."""
        pass


class AudioFetcherPlugin(PluginBase, BaseFetcher):
    """Base class for audio fetcher plugins."""
    
    PLUGIN_TYPE = "audio_fetcher"
    
    @abstractmethod
    async def fetch(self, source: str, output_path: str) -> bool:
        """Generate audio from text to output_path."""
        pass


class TemplatePlugin(PluginBase):
    """Base class for card template plugins."""
    
    PLUGIN_TYPE = "template"
    
    @abstractmethod
    def get_css(self) -> str:
        """Return CSS styles for the template."""
        pass
    
    @abstractmethod
    def get_front_template(self) -> str:
        """Return front card HTML template."""
        pass
    
    @abstractmethod
    def get_back_template(self) -> str:
        """Return back card HTML template."""
        pass


class ProcessorPlugin(PluginBase):
    """Base class for data processor plugins."""
    
    PLUGIN_TYPE = "processor"
    
    @abstractmethod
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process vocabulary data and return modified data."""
        pass


class PluginManager:
    """
    Central manager for plugin discovery, loading, and management.
    
    Usage:
        manager = PluginManager()
        manager.discover_plugins()
        
        # Get a specific plugin
        dalle_fetcher = manager.get_plugin("dalle", "image_fetcher")
        
        # List all plugins
        for plugin in manager.list_plugins():
            print(f"{plugin.name}: {plugin.description}")
    """
    
    # Default plugins directory
    DEFAULT_PLUGINS_DIR = "plugins"
    
    def __init__(self, plugins_dir: Optional[str] = None):
        """
        Initialize plugin manager.
        
        Args:
            plugins_dir: Directory to search for plugins
        """
        if plugins_dir is None:
            plugins_dir = str(Path(Config.BASE_DIR) / self.DEFAULT_PLUGINS_DIR)
        
        self.plugins_dir = Path(plugins_dir)
        
        # Registry: {plugin_type: {name: plugin_class}}
        self._registry: Dict[str, Dict[str, Type[PluginBase]]] = {
            "image_fetcher": {},
            "audio_fetcher": {},
            "template": {},
            "processor": {},
        }
        
        # Loaded plugin instances
        self._instances: Dict[str, Dict[str, PluginBase]] = {
            "image_fetcher": {},
            "audio_fetcher": {},
            "template": {},
            "processor": {},
        }
        
        # Plugin info cache
        self._plugin_info: Dict[str, PluginInfo] = {}
        
        # Callbacks for plugin lifecycle events
        self._on_load_callbacks: List[Callable[[PluginInfo], None]] = []
        self._on_unload_callbacks: List[Callable[[str], None]] = []
    
    def discover_plugins(self, auto_load: bool = True) -> List[str]:
        """
        Discover plugins in the plugins directory.
        
        Args:
            auto_load: Whether to automatically load discovered plugins
            
        Returns:
            List of discovered plugin file paths
        """
        discovered = []
        
        if not self.plugins_dir.exists():
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
            self._create_example_plugin()
            return discovered
        
        for file in self.plugins_dir.glob("*.py"):
            if file.name.startswith("_"):
                continue  # Skip __init__.py and similar
            
            discovered.append(str(file))
            
            if auto_load:
                try:
                    self.load_plugin(str(file))
                except Exception as e:
                    print(f"Failed to load plugin {file.name}: {e}")
        
        return discovered
    
    def load_plugin(self, file_path: str) -> Optional[PluginInfo]:
        """
        Load a plugin from a Python file.
        
        Args:
            file_path: Path to the plugin file
            
        Returns:
            PluginInfo if loaded successfully, None otherwise
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Plugin file not found: {file_path}")
        
        # Load module
        module_name = f"ankitect_plugin_{file_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load plugin spec: {file_path}")
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            del sys.modules[module_name]
            raise ImportError(f"Error executing plugin: {e}")
        
        # Look for register function or plugin classes
        if hasattr(module, "register"):
            # Plugin uses register() pattern
            module.register(self)
        else:
            # Auto-discover plugin classes
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, PluginBase) and 
                    attr not in (PluginBase, ImageFetcherPlugin, AudioFetcherPlugin, 
                                TemplatePlugin, ProcessorPlugin)):
                    self.register_plugin(attr)
        
        return None
    
    def register_plugin(
        self, 
        plugin_class: Type[PluginBase],
        name: Optional[str] = None
    ) -> None:
        """
        Register a plugin class.
        
        Args:
            plugin_class: The plugin class to register
            name: Optional name (uses class PLUGIN_NAME if not provided)
        """
        plugin_type = plugin_class.PLUGIN_TYPE
        plugin_name = name or plugin_class.PLUGIN_NAME.lower().replace(" ", "_")
        
        if plugin_type not in self._registry:
            self._registry[plugin_type] = {}
        
        self._registry[plugin_type][plugin_name] = plugin_class
        
        # Create plugin info
        info = plugin_class.get_info()
        info.loaded_at = datetime.now()
        self._plugin_info[f"{plugin_type}:{plugin_name}"] = info
        
        # Notify callbacks
        for callback in self._on_load_callbacks:
            try:
                callback(info)
            except Exception:
                pass
        
        print(f"Registered plugin: {plugin_name} ({plugin_type})")
    
    def get_plugin(
        self, 
        name: str, 
        plugin_type: str,
        **kwargs
    ) -> Optional[PluginBase]:
        """
        Get a plugin instance by name and type.
        
        Args:
            name: Plugin name
            plugin_type: Plugin type ('image_fetcher', 'audio_fetcher', etc.)
            **kwargs: Arguments to pass to plugin constructor
            
        Returns:
            Plugin instance or None if not found
        """
        if plugin_type not in self._registry:
            return None
        
        if name not in self._registry[plugin_type]:
            return None
        
        # Create instance if not cached
        cache_key = f"{name}:{id(kwargs) if kwargs else 'default'}"
        
        if cache_key not in self._instances[plugin_type]:
            plugin_class = self._registry[plugin_type][name]
            try:
                instance = plugin_class(**kwargs)
                self._instances[plugin_type][cache_key] = instance
            except Exception as e:
                print(f"Error instantiating plugin {name}: {e}")
                return None
        
        return self._instances[plugin_type][cache_key]
    
    def list_plugins(self, plugin_type: Optional[str] = None) -> List[PluginInfo]:
        """
        List all registered plugins.
        
        Args:
            plugin_type: Optional filter by type
            
        Returns:
            List of PluginInfo objects
        """
        plugins = []
        
        for key, info in self._plugin_info.items():
            if plugin_type is None or info.plugin_type == plugin_type:
                plugins.append(info)
        
        return plugins
    
    def list_image_fetchers(self) -> List[str]:
        """List all registered image fetcher plugin names."""
        return list(self._registry.get("image_fetcher", {}).keys())
    
    def list_audio_fetchers(self) -> List[str]:
        """List all registered audio fetcher plugin names."""
        return list(self._registry.get("audio_fetcher", {}).keys())
    
    def list_templates(self) -> List[str]:
        """List all registered template plugin names."""
        return list(self._registry.get("template", {}).keys())
    
    def list_processors(self) -> List[str]:
        """List all registered processor plugin names."""
        return list(self._registry.get("processor", {}).keys())
    
    def on_plugin_load(self, callback: Callable[[PluginInfo], None]) -> None:
        """Register callback for plugin load events."""
        self._on_load_callbacks.append(callback)
    
    def on_plugin_unload(self, callback: Callable[[str], None]) -> None:
        """Register callback for plugin unload events."""
        self._on_unload_callbacks.append(callback)
    
    def _create_example_plugin(self) -> None:
        """Create an example plugin file."""
        example_content = '''"""
Example AnkiTect Plugin - Custom Image Fetcher
==============================================

This is a template for creating custom plugins.
Place plugin files in the 'plugins/' directory.

Plugin Types:
- ImageFetcherPlugin: Custom image generation/download
- AudioFetcherPlugin: Custom TTS or audio download
- TemplatePlugin: Custom card templates
- ProcessorPlugin: Custom data processing
"""

from src.plugins import ImageFetcherPlugin


class ExampleImageFetcher(ImageFetcherPlugin):
    """Example custom image fetcher plugin."""
    
    PLUGIN_NAME = "Example Image Fetcher"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_DESCRIPTION = "An example image fetcher plugin"
    PLUGIN_AUTHOR = "AnkiTect"
    
    async def fetch(self, source: str, output_path: str) -> bool:
        """
        Fetch an image based on the source prompt.
        
        Args:
            source: Image prompt or URL
            output_path: Where to save the image
            
        Returns:
            True if successful
        """
        # TODO: Implement your image fetching logic here
        # Example: Call DALL-E API, download from URL, etc.
        print(f"Example plugin: Would fetch '{source}' to '{output_path}'")
        return False
    
    async def close(self) -> None:
        """Cleanup resources."""
        pass


def register(manager):
    """Register plugins with the manager."""
    manager.register_plugin(ExampleImageFetcher, "example")
'''
        
        example_file = self.plugins_dir / "_example_plugin.py"
        example_file.write_text(example_content, encoding="utf-8")


# Global plugin manager instance
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


def init_plugins(plugins_dir: Optional[str] = None) -> PluginManager:
    """
    Initialize and discover plugins.
    
    Args:
        plugins_dir: Optional custom plugins directory
        
    Returns:
        Configured PluginManager instance
    """
    global _plugin_manager
    _plugin_manager = PluginManager(plugins_dir)
    _plugin_manager.discover_plugins()
    return _plugin_manager
