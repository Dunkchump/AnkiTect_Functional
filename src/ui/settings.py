"""
Settings View - Application Configuration UI
----------------------------------------------

Provides a UI for configuring AnkiTect settings using SettingsManager.
"""

import flet as ft
from typing import Any, Dict, List, Optional

from src.config.config_manager import SettingsManager


class SettingsView:
    """
    Settings view for configuring application options.
    
    Binds to SettingsManager for persistent storage.
    """
    
    # Available language options
    LANGUAGE_OPTIONS: Dict[str, str] = {
        "DE": "German (Deutsch)",
        "EN": "English",
    }
    
    def __init__(self, page: ft.Page) -> None:
        """
        Initialize the Settings view.
        
        Args:
            page: Flet page instance for updates
        """
        self.page = page
        self.settings = SettingsManager()
        
        # UI References
        self._lang_dropdown: Optional[ft.Dropdown] = None
        self._api_key_field: Optional[ft.TextField] = None
        self._concurrency_slider: Optional[ft.Slider] = None
        self._concurrency_label: Optional[ft.Text] = None
        self._timeout_field: Optional[ft.TextField] = None
        self._image_timeout_field: Optional[ft.TextField] = None
        self._retries_field: Optional[ft.TextField] = None
        self._save_button: Optional[ft.ElevatedButton] = None
        self._performance_switch: Optional[ft.Switch] = None
        
        # Track changes
        self._has_changes: bool = False
        
        # Build the view
        self._container = self._build_view()
    
    @property
    def container(self) -> ft.Container:
        """Get the main container for this view."""
        return self._container
    
    def _build_view(self) -> ft.Container:
        """Build the settings layout."""
        # Language Section
        lang_section = self._build_language_section()
        
        # API Section
        api_section = self._build_api_section()
        
        # Performance Section
        perf_section = self._build_performance_section()

        
        # Save Button
        self._save_button = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SAVE_ROUNDED, size=20),
                    ft.Text("Save Settings", size=15, weight=ft.FontWeight.W_500),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            style=ft.ButtonStyle(
                color={
                    ft.ControlState.DEFAULT: ft.Colors.WHITE,
                    ft.ControlState.DISABLED: ft.Colors.WHITE38,
                },
                bgcolor={
                    ft.ControlState.DEFAULT: ft.Colors.INDIGO_600,
                    ft.ControlState.HOVERED: ft.Colors.INDIGO_500,
                    ft.ControlState.DISABLED: ft.Colors.with_opacity(0.3, ft.Colors.INDIGO_600),
                },
                padding=ft.Padding.symmetric(horizontal=30, vertical=15),
                shape=ft.RoundedRectangleBorder(radius=10),
                elevation={
                    ft.ControlState.DEFAULT: 2,
                    ft.ControlState.HOVERED: 4,
                },
            ),
            on_click=self._on_save_click,
        )
        
        # Reset Button
        reset_button = ft.TextButton(
            content=ft.Text("Reset to Defaults", color=ft.Colors.WHITE54),
            on_click=self._on_reset_click,
        )
        
        # Main content
        content = ft.Column(
            controls=[
                # Header
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SETTINGS_ROUNDED, size=32, color=ft.Colors.INDIGO_200),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        "Settings",
                                        size=28,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.WHITE,
                                    ),
                                    ft.Text(
                                        "Configure your AnkiTect preferences",
                                        size=14,
                                        color=ft.Colors.WHITE54,
                                    ),
                                ],
                                spacing=2,
                            ),
                        ],
                        spacing=15,
                    ),
                    padding=ft.Padding.only(bottom=25),
                ),
                
                # Scrollable settings area
                ft.Container(
                    content=ft.Column(
                        controls=[
                            lang_section,
                            ft.Container(height=20),
                            api_section,
                            ft.Container(height=20),
                            perf_section,
                            ft.Container(height=20),
                            ft.Container(height=10),
                            
                            # Action buttons
                            ft.Row(
                                controls=[
                                    reset_button,
                                    ft.Container(expand=True),
                                    self._save_button,
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                        ],
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                    expand=True,
                ),
            ],
            expand=True,
        )
        
        return ft.Container(
            content=content,
            expand=True,
            padding=10,
        )
    
    def _build_section_card(self, title: str, icon: str, controls: list) -> ft.Container:
        """Build a styled section card."""
        return ft.Container(
            content=ft.Column(
                controls=[
                    # Section header
                    ft.Row(
                        controls=[
                            ft.Icon(icon, size=20, color=ft.Colors.INDIGO_200),
                            ft.Text(
                                title,
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Divider(height=1, color=ft.Colors.WHITE10),
                    ft.Container(height=5),
                    *controls,
                ],
                spacing=10,
            ),
            padding=20,
            border_radius=12,
            bgcolor="#1A1A1A",
            shadow=ft.BoxShadow(
                spread_radius=-2,
                blur_radius=15,
                color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK),
                offset=ft.Offset(0, 4),
            ),
        )
    
    def _build_language_section(self) -> ft.Container:
        """Build the language settings section."""
        current_lang = self.settings.get("CURRENT_LANG", "DE")
        
        self._lang_dropdown = ft.Dropdown(
            value=current_lang,
            options=[
                ft.dropdown.Option(key=code, text=name)
                for code, name in self.LANGUAGE_OPTIONS.items()
            ],
            label="Target Language",
            hint_text="Select the language for your vocabulary deck",
            border_color=ft.Colors.WHITE24,
            focused_border_color=ft.Colors.INDIGO_200,
            label_style=ft.TextStyle(color=ft.Colors.WHITE54),
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
            width=300,
        )
        
        return self._build_section_card(
            "Language",
            ft.Icons.LANGUAGE_ROUNDED,
            [
                ft.Text(
                    "Choose the target language for audio generation and deck configuration.",
                    size=12,
                    color=ft.Colors.WHITE38,
                ),
                ft.Container(height=10),
                self._lang_dropdown,
            ],
        )
    
    def _build_api_section(self) -> ft.Container:
        """Build the API configuration section."""
        current_key = self.settings.get("POLLINATIONS_API_KEY", "")
        
        self._api_key_field = ft.TextField(
            value=current_key,
            label="Pollinations API Key",
            hint_text="sk_... or pk_...",
            password=True,
            can_reveal_password=True,
            border_color=ft.Colors.WHITE24,
            focused_border_color=ft.Colors.INDIGO_200,
            label_style=ft.TextStyle(color=ft.Colors.WHITE54),
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
            cursor_color=ft.Colors.INDIGO_200,
            prefix_icon=ft.Icons.KEY_ROUNDED,
        )
        
        return self._build_section_card(
            "API Configuration",
            ft.Icons.API_ROUNDED,
            [
                ft.Text(
                    "Configure your Pollinations API credentials for image generation.",
                    size=12,
                    color=ft.Colors.WHITE38,
                ),
                ft.Container(height=5),
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=ft.Colors.TEAL_200),
                        ft.Text(
                            "Get your API key at pollinations.ai",
                            size=11,
                            color=ft.Colors.TEAL_200,
                        ),
                    ],
                    spacing=5,
                ),
                ft.Container(height=10),
                self._api_key_field,
            ],
        )
    
    def _build_performance_section(self) -> ft.Container:
        """Build the performance settings section."""
        current_concurrency = self.settings.get("CONCURRENCY", 4)
        current_timeout = self.settings.get("TIMEOUT", 60)
        current_img_timeout = self.settings.get("IMAGE_TIMEOUT", 90)
        current_retries = self.settings.get("RETRIES", 5)
        current_perf_mode = self.settings.get("PERFORMANCE_MODE", False)
        
        # Concurrency slider
        self._concurrency_label = ft.Text(
            f"Concurrency: {current_concurrency}",
            size=13,
            color=ft.Colors.WHITE70,
        )
        
        self._concurrency_slider = ft.Slider(
            min=1,
            max=16,
            divisions=15,
            value=current_concurrency,
            label="{value}",
            active_color=ft.Colors.INDIGO_400,
            inactive_color=ft.Colors.WHITE24,
            on_change_end=self._on_concurrency_change,
        )
        
        # Timeout fields
        self._timeout_field = ft.TextField(
            value=str(current_timeout),
            label="Request Timeout (seconds)",
            width=200,
            border_color=ft.Colors.WHITE24,
            focused_border_color=ft.Colors.INDIGO_200,
            label_style=ft.TextStyle(color=ft.Colors.WHITE54),
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
            cursor_color=ft.Colors.INDIGO_200,
            input_filter=ft.NumbersOnlyInputFilter(),
        )
        
        self._image_timeout_field = ft.TextField(
            value=str(current_img_timeout),
            label="Image Timeout (seconds)",
            width=200,
            border_color=ft.Colors.WHITE24,
            focused_border_color=ft.Colors.INDIGO_200,
            label_style=ft.TextStyle(color=ft.Colors.WHITE54),
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
            cursor_color=ft.Colors.INDIGO_200,
            input_filter=ft.NumbersOnlyInputFilter(),
        )
        
        self._retries_field = ft.TextField(
            value=str(current_retries),
            label="Max Retries",
            width=200,
            border_color=ft.Colors.WHITE24,
            focused_border_color=ft.Colors.INDIGO_200,
            label_style=ft.TextStyle(color=ft.Colors.WHITE54),
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
            cursor_color=ft.Colors.INDIGO_200,
            input_filter=ft.NumbersOnlyInputFilter(),
        )

        self._performance_switch = ft.Switch(
            value=bool(current_perf_mode),
            label="Performance Mode (less UI updates)",
            on_change=lambda _: self._mark_changed(),
        )
        
        return self._build_section_card(
            "Performance",
            ft.Icons.SPEED_ROUNDED,
            [
                ft.Text(
                    "Tune parallel downloads and network timeouts for optimal performance.",
                    size=12,
                    color=ft.Colors.WHITE38,
                ),
                ft.Container(height=15),
                
                # Concurrency
                self._concurrency_label,
                self._concurrency_slider,
                ft.Text(
                    "Higher values = faster builds, but may trigger rate limits.",
                    size=11,
                    color=ft.Colors.WHITE24,
                ),
                ft.Container(height=15),
                
                # Timeouts row
                ft.Row(
                    controls=[
                        self._timeout_field,
                        self._image_timeout_field,
                        self._retries_field,
                    ],
                    spacing=15,
                    wrap=True,
                ),
                ft.Container(height=10),
                self._performance_switch,
            ],
        )

    
    def _mark_changed(self) -> None:
        """Mark that settings have been changed."""
        self._has_changes = True
    
    def _on_concurrency_change(self, e: ft.ControlEvent) -> None:
        """Handle concurrency slider change."""
        value = int(e.control.value)
        if self._concurrency_label:
            self._concurrency_label.value = f"Concurrency: {value}"
        self._mark_changed()
        self.page.update()
    
    def _on_save_click(self, e: ft.ControlEvent) -> None:
        """Handle save button click."""
        try:
            # Gather values
            new_lang = self._lang_dropdown.value if self._lang_dropdown else "DE"
            new_api_key = self._api_key_field.value if self._api_key_field else ""
            new_concurrency = int(self._concurrency_slider.value) if self._concurrency_slider else 4
            new_timeout = int(self._timeout_field.value) if self._timeout_field and self._timeout_field.value else 60
            new_img_timeout = int(self._image_timeout_field.value) if self._image_timeout_field and self._image_timeout_field.value else 90
            new_retries = int(self._retries_field.value) if self._retries_field and self._retries_field.value else 5
            new_perf_mode = bool(self._performance_switch.value) if self._performance_switch else False
            
            # Save to SettingsManager
            self.settings.set("CURRENT_LANG", new_lang)
            self.settings.set("POLLINATIONS_API_KEY", new_api_key)
            self.settings.set("CONCURRENCY", new_concurrency)
            self.settings.set("TIMEOUT", new_timeout)
            self.settings.set("IMAGE_TIMEOUT", new_img_timeout)
            self.settings.set("RETRIES", new_retries)
            self.settings.set("PERFORMANCE_MODE", new_perf_mode)
            
            self._has_changes = False
            self._show_snackbar("Settings saved successfully!", success=True)
            
        except Exception as ex:
            self._show_snackbar(f"Error saving settings: {str(ex)}", success=False)
    
    def _on_reset_click(self, e: ft.ControlEvent) -> None:
        """Handle reset button click."""
        self.settings.reset()
        self._reload_ui()
        self._show_snackbar("Settings reset to defaults", success=True)
    
    def _reload_ui(self) -> None:
        """Reload UI with current settings values."""
        if self._lang_dropdown:
            self._lang_dropdown.value = self.settings.get("CURRENT_LANG", "DE")
        if self._api_key_field:
            self._api_key_field.value = self.settings.get("POLLINATIONS_API_KEY", "")
        if self._concurrency_slider:
            val = self.settings.get("CONCURRENCY", 4)
            self._concurrency_slider.value = val
            if self._concurrency_label:
                self._concurrency_label.value = f"Concurrency: {val}"
        if self._timeout_field:
            self._timeout_field.value = str(self.settings.get("TIMEOUT", 60))
        if self._image_timeout_field:
            self._image_timeout_field.value = str(self.settings.get("IMAGE_TIMEOUT", 90))
        if self._retries_field:
            self._retries_field.value = str(self.settings.get("RETRIES", 5))
        if self._performance_switch:
            self._performance_switch.value = bool(self.settings.get("PERFORMANCE_MODE", False))
        
        self._has_changes = False
        self.page.update()
    
    def _show_snackbar(self, message: str, success: bool = True) -> None:
        """Show a snackbar notification."""
        snackbar = ft.SnackBar(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE if success else ft.Icons.ERROR,
                        color=ft.Colors.WHITE,
                        size=18,
                    ),
                    ft.Text(message, color=ft.Colors.WHITE),
                ],
                spacing=10,
            ),
            bgcolor=ft.Colors.GREEN_700 if success else ft.Colors.RED_700,
            duration=3000,
        )
        # Clean up old snackbars and add new one
        for ctrl in list(self.page.overlay):
            if isinstance(ctrl, ft.SnackBar):
                self.page.overlay.remove(ctrl)
        self.page.overlay.append(snackbar)
        snackbar.open = True
        self.page.update()


def create_settings_view(page: ft.Page) -> ft.Container:
    """
    Factory function to create the settings view.
    
    Args:
        page: Flet page instance
        
    Returns:
        Container with the settings view
    """
    settings = SettingsView(page)
    return settings.container
