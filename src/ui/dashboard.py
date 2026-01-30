"""
Dashboard View - Build Control and Progress Monitoring
-------------------------------------------------------

Provides the main build controls, progress tracking, and live logging.
Modern UI with 12-column grid system and improved visual hierarchy.
"""

import asyncio
import csv
import io
import os
import time
import queue
from datetime import datetime
from typing import Any, Dict, List, Optional

import flet as ft

from src.config import Config
from src.config.config_manager import SettingsManager
from src.deck import AnkiDeckBuilder
from src.utils.parsing import TextParser


# =============================================================================
# DESIGN TOKENS
# =============================================================================
class DesignTokens:
    """Centralized design tokens for consistent styling."""
    # Colors - Deep dark theme
    BG_PRIMARY = "#121212"
    BG_SURFACE = "#1A1A1B"
    BG_CARD = "#242426"
    BG_CARD_HOVER = "#2A2A2C"
    BG_ELEVATED = "#2D2D30"
    
    # Text colors
    TEXT_PRIMARY = "#FFFFFF"
    TEXT_SECONDARY = "#B3B3B3"
    TEXT_TERTIARY = "#808080"
    TEXT_MUTED = "#5C5C5C"
    
    # Accent colors (desaturated)
    ACCENT_PRIMARY = "#7C4DFF"  # Main CTA - slightly desaturated purple
    ACCENT_PRIMARY_HOVER = "#9E7AFF"
    ACCENT_SECONDARY = "#536DFE"  # Secondary actions
    ACCENT_DANGER = "#E57373"  # Muted red for destructive actions
    ACCENT_DANGER_HOVER = "#EF9A9A"
    ACCENT_SUCCESS = "#81C784"  # Muted green
    ACCENT_WARNING = "#FFB74D"  # Muted amber
    
    # Log colors
    LOG_INFO = "#B3B3B3"
    LOG_SUCCESS = "#81C784"
    LOG_WARNING = "#FFB74D"
    LOG_ERROR = "#E57373"
    LOG_PROGRESS = "#9E7AFF"
    LOG_TIMESTAMP = "#5C5C5C"
    LOG_BG_ALT = "#1F1F21"
    
    # Spacing
    SPACING_XS = 4
    SPACING_SM = 8
    SPACING_MD = 16
    SPACING_LG = 24
    SPACING_XL = 32
    
    # Border radius
    RADIUS_SM = 8
    RADIUS_MD = 12
    RADIUS_LG = 16
    RADIUS_XL = 20
    
    # Button heights
    BUTTON_HEIGHT_SM = 36
    BUTTON_HEIGHT_MD = 44
    BUTTON_HEIGHT_LG = 52
    
    # Typography
    FONT_MONO = "JetBrains Mono, Consolas, Monaco, monospace"
    FONT_SANS = "Inter, Roboto, Segoe UI, sans-serif"


class DashboardView:
    """
    Dashboard view with build controls and live logging.
    
    Provides a Start Build button, progress bar, and live log output.
    """
    
    def __init__(self, page: ft.Page) -> None:
        """
        Initialize the Dashboard view.
        
        Args:
            page: Flet page instance for updates
        """
        self.page = page
        self.is_building: bool = False
        
        # UI References
        self._progress_bar: Optional[ft.ProgressBar] = None
        self._progress_text: Optional[ft.Text] = None
        self._log_view: Optional[ft.ListView] = None
        self._build_button: Optional[ft.ElevatedButton] = None
        self._status_text: Optional[ft.Text] = None
        self._csv_status_icon: Optional[ft.Icon] = None
        self._csv_status_text: Optional[ft.Text] = None
        self._drop_zone: Optional[ft.Container] = None
        self._paste_input: Optional[ft.TextField] = None
        self._paste_button: Optional[ft.ElevatedButton] = None
        self._paste_clear_button: Optional[ft.TextButton] = None
        self._build_status_icon: Optional[ft.Icon] = None
        
        # Log entries
        self._log_entries: List[ft.Control] = []

        # Throttled UI update state
        self._pending_logs: List[Dict[str, str]] = []
        self._pending_progress: Optional[Dict[str, Any]] = None
        self._ui_update_scheduled: bool = False
        self._last_ui_update_ts: float = 0.0
        self._min_ui_update_interval: float = 0.15  # seconds

        # Thread-safe progress queue (to keep UI responsive)
        self._progress_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._queue_polling: bool = False

        # Performance mode
        self._perf_mode: bool = SettingsManager().get("PERFORMANCE_MODE", False)
        self._info_log_counter: int = 0
        
        # Build the view
        self._container = self._build_view()

    # Default CSV header
    DEFAULT_COLUMNS = [
        "TargetWord",
        "Meaning",
        "IPA",
        "Part_of_Speech",
        "Gender",
        "Morphology",
        "Nuance",
        "ContextSentences",
        "ContextTranslation",
        "Etymology",
        "Mnemonic",
        "Analogues",
        "ImagePrompt",
        "Tags",
    ]
    
    @property
    def container(self) -> ft.Container:
        """Get the main container for this view."""
        return self._container
    
    def _build_view(self) -> ft.Container:
        """
        Build the main dashboard layout as a Fixed Viewport Application.
        No body scroll - fits exactly to screen height.
        """
        # Header section
        header = self._build_header()
        
        # Build control section (1 column)
        build_section = self._build_control_section()
        
        # Quick Paste section (2 columns)
        paste_sidebar = self._build_paste_sidebar()
        
        # Log section (fills remaining vertical space)
        log_section = self._build_log_section()
        
        # Top Grid: Build Controls (1 col) + Quick Paste (2 cols)
        top_grid = ft.Row(
            controls=[
                ft.Container(
                    content=build_section,
                    expand=1,  # 1 out of 3 columns
                ),
                ft.Container(
                    content=paste_sidebar,
                    expand=2,  # 2 out of 3 columns
                ),
            ],
            spacing=DesignTokens.SPACING_LG,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        
        # Top section wrapper with fixed height
        top_section = ft.Container(
            content=top_grid,
            height=380,  # Fixed height for top section
        )
        
        # Fixed Viewport Layout - NO SCROLL on main container
        main_content = ft.Column(
            controls=[
                # Header (fixed height, intrinsic)
                header,
                ft.Container(height=DesignTokens.SPACING_MD),
                
                # Top Section (fixed height)
                top_section,
                ft.Container(height=DesignTokens.SPACING_MD),
                
                # Bottom Section - Build Log (flex-1, fills remaining space)
                log_section,
            ],
            spacing=0,
            expand=True,  # Fill viewport
            scroll=None,  # NO scroll on main layout
        )
        
        # Main container: 100vh equivalent, overflow hidden
        return ft.Container(
            content=main_content,
            expand=True,
            padding=DesignTokens.SPACING_LG,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,  # overflow-hidden
        )
    
    def _build_header(self) -> ft.Container:
        """Build the header section with language switcher in top-right."""
        # Language indicator - now in global header
        self._lang_indicator = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.LANGUAGE, color=DesignTokens.TEXT_TERTIARY, size=18),
                    ft.Text(
                        Config.CURRENT_LANG,
                        size=14,
                        weight=ft.FontWeight.W_600,
                        color=DesignTokens.TEXT_SECONDARY,
                    ),
                ],
                spacing=6,
            ),
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            border_radius=DesignTokens.RADIUS_SM,
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.WHITE),
        )
        
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                "Dashboard",
                                size=32,
                                weight=ft.FontWeight.W_700,
                                color=DesignTokens.TEXT_PRIMARY,
                            ),
                            ft.Text(
                                "Build and manage your Anki decks",
                                size=14,
                                color=DesignTokens.TEXT_TERTIARY,
                            ),
                        ],
                        spacing=6,
                    ),
                    ft.Container(expand=True),
                    # Language switcher in top-right
                    self._lang_indicator,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.Padding.only(bottom=DesignTokens.SPACING_SM),
        )
    
    def _build_control_section(self) -> ft.Container:
        """Build the main build control section with flex column layout."""
        self._status_text = ft.Text(
            "Ready to build",
            size=13,
            color=DesignTokens.TEXT_TERTIARY,
        )

        # Main CTA button - larger, more prominent
        self._build_button = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ROCKET_LAUNCH_ROUNDED, size=20),
                    ft.Text("Start Build", size=15, weight=ft.FontWeight.W_600),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10,
            ),
            style=ft.ButtonStyle(
                color=DesignTokens.TEXT_PRIMARY,
                bgcolor={
                    ft.ControlState.DEFAULT: DesignTokens.ACCENT_PRIMARY,
                    ft.ControlState.HOVERED: DesignTokens.ACCENT_PRIMARY_HOVER,
                    ft.ControlState.PRESSED: "#6A3FE0",
                    ft.ControlState.DISABLED: ft.Colors.with_opacity(0.3, DesignTokens.ACCENT_PRIMARY),
                },
                padding=ft.Padding.symmetric(horizontal=32, vertical=16),
                shape=ft.RoundedRectangleBorder(radius=DesignTokens.RADIUS_MD),
                elevation={"default": 2, "hovered": 4},
                animation_duration=150,
            ),
            height=DesignTokens.BUTTON_HEIGHT_LG,
            on_click=self._on_build_click,
        )
        
        # CSV file status badge - for card header
        csv_exists = os.path.exists(Config.CSV_FILE)
        self._csv_status_icon = ft.Icon(
            ft.Icons.CHECK_CIRCLE if csv_exists else ft.Icons.ERROR_OUTLINE,
            color=DesignTokens.ACCENT_SUCCESS if csv_exists else DesignTokens.ACCENT_DANGER,
            size=16,
        )
        self._csv_status_text = ft.Text(
            f"{'Found' if csv_exists else 'Not found'}",
            size=12,
            color=DesignTokens.ACCENT_SUCCESS if csv_exists else DesignTokens.ACCENT_DANGER,
        )
        
        csv_status_badge = ft.Container(
            content=ft.Row(
                controls=[
                    self._csv_status_icon,
                    self._csv_status_text,
                ],
                spacing=4,
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            border_radius=DesignTokens.RADIUS_SM,
            bgcolor=ft.Colors.with_opacity(0.1, 
                DesignTokens.ACCENT_SUCCESS if csv_exists else DesignTokens.ACCENT_DANGER),
        )
        
        # Card Header with title and CSV status
        card_header = ft.Row(
            controls=[
                ft.Text(
                    "Build Controls",
                    size=18,
                    weight=ft.FontWeight.W_700,
                    color=DesignTokens.TEXT_PRIMARY,
                ),
                ft.Container(expand=True),
                csv_status_badge,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        
        # Drop Zone - will expand to fill remaining space
        self._drop_zone = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.CLOUD_UPLOAD_OUTLINED, 
                        size=48, 
                        color=DesignTokens.TEXT_MUTED
                    ),
                    ft.Container(height=DesignTokens.SPACING_SM),
                    ft.Text(
                        "Drop CSV here",
                        size=16,
                        weight=ft.FontWeight.W_600,
                        color=DesignTokens.TEXT_SECONDARY,
                    ),
                    ft.Text(
                        "Drag vocabulary.csv from File Explorer",
                        size=12,
                        color=DesignTokens.TEXT_MUTED,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=4,
            ),
            expand=True,  # flex-grow: 1 - fills remaining space
            border_radius=DesignTokens.RADIUS_LG,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.WHITE),
            border=ft.border.all(2, ft.Colors.with_opacity(0.15, ft.Colors.WHITE)),
        )

        # Progress section - integrated under button
        self._progress_text = ft.Text(
            "0%",
            size=13,
            weight=ft.FontWeight.W_600,
            color=DesignTokens.ACCENT_PRIMARY,
        )

        self._progress_bar = ft.ProgressBar(
            value=0,
            color=DesignTokens.ACCENT_PRIMARY,
            bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.WHITE),
            border_radius=4,
        )
        
        progress_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("Progress", size=12, color=DesignTokens.TEXT_TERTIARY),
                            ft.Container(expand=True),
                            self._progress_text,
                        ],
                    ),
                    ft.Container(height=8),
                    ft.Container(
                        content=self._progress_bar,
                        height=6,
                    ),
                ],
                spacing=0,
            ),
            padding=ft.Padding.only(top=DesignTokens.SPACING_MD),
        )

        # Build card with flex column layout (height: 100%)
        build_card = ft.Container(
            content=ft.Column(
                controls=[
                    # Card Header with CSV status
                    card_header,
                    ft.Container(height=DesignTokens.SPACING_LG),
                    
                    # Build button - centered
                    ft.Container(
                        content=self._build_button,
                        alignment=ft.Alignment(0, 0),
                    ),
                    
                    # Progress bar
                    progress_section,
                    
                    ft.Container(height=DesignTokens.SPACING_SM),
                    
                    # Status text
                    self._status_text,
                    
                    ft.Container(height=DesignTokens.SPACING_MD),
                    
                    # Drop zone - expands to fill remaining space
                    self._drop_zone,
                ],
                spacing=0,
                expand=True,  # Column fills container height
            ),
            padding=DesignTokens.SPACING_LG,
            border_radius=DesignTokens.RADIUS_LG,
            bgcolor=DesignTokens.BG_CARD,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=12,
                color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK),
                offset=ft.Offset(0, 4),
            ),
            expand=True,  # Card fills parent height
        )

        return build_card
    
    def _build_paste_sidebar(self) -> ft.Container:
        """Build the Quick Paste sidebar with actions in header."""
        # Paste CSV input
        self._paste_input = ft.TextField(
            hint_text="Paste pipe-delimited rows (header optional)",
            multiline=True,
            min_lines=10,
            max_lines=16,
            border_radius=DesignTokens.RADIUS_SM,
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
            border_color=ft.Colors.with_opacity(0.1, ft.Colors.WHITE),
            focused_border_color=DesignTokens.ACCENT_SECONDARY,
            text_style=ft.TextStyle(size=13),
            expand=True,
        )

        # Append button - styled nicely for header
        self._paste_button = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ADD_ROUNDED, size=16, color=DesignTokens.TEXT_PRIMARY),
                    ft.Text("Append", size=12, weight=ft.FontWeight.W_600, color=DesignTokens.TEXT_PRIMARY),
                ],
                spacing=4,
            ),
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            border_radius=DesignTokens.RADIUS_SM,
            bgcolor=DesignTokens.ACCENT_SECONDARY,
            on_click=lambda _: self._import_csv_text(self._paste_input.value if self._paste_input else ""),
            ink=True,
        )

        # Replace button - danger style
        replace_button = ft.Container(
            content=ft.Text(
                "Replace all",
                size=11,
                color=DesignTokens.ACCENT_DANGER,
            ),
            padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            border_radius=DesignTokens.RADIUS_SM,
            on_click=lambda _: self._confirm_replace(),
            ink=True,
        )

        # Clear button
        self._paste_clear_button = ft.Container(
            content=ft.Text("Clear", size=11, color=DesignTokens.TEXT_TERTIARY),
            padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            border_radius=DesignTokens.RADIUS_SM,
            on_click=lambda _: self._clear_paste_input(),
            ink=True,
        )
        
        # Card header with title and all actions
        card_header = ft.Row(
            controls=[
                ft.Text(
                    "Quick Paste",
                    size=18,
                    weight=ft.FontWeight.W_700,
                    color=DesignTokens.TEXT_PRIMARY,
                ),
                ft.Container(expand=True),
                self._paste_clear_button,
                replace_button,
                self._paste_button,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        )

        paste_sidebar = ft.Container(
            content=ft.Column(
                controls=[
                    # Card header with all actions
                    card_header,
                    ft.Text(
                        "Paste one or multiple CSV rows. Header is optional.",
                        size=12,
                        color=DesignTokens.TEXT_TERTIARY,
                    ),
                    ft.Container(height=DesignTokens.SPACING_MD),
                    # Textarea expands to fill space
                    ft.Container(content=self._paste_input, expand=True),
                ],
                spacing=6,
                expand=True,
            ),
            padding=DesignTokens.SPACING_LG,
            border_radius=DesignTokens.RADIUS_LG,
            bgcolor=DesignTokens.BG_CARD,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=12,
                color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK),
                offset=ft.Offset(0, 4),
            ),
        )

        return paste_sidebar
    
    def _confirm_replace(self) -> None:
        """Show confirmation dialog for replace action."""
        def do_replace(e):
            dialog.open = False
            self.page.update()
            if dialog in self.page.overlay:
                self.page.overlay.remove(dialog)
            self._replace_csv_text(self._paste_input.value if self._paste_input else "")
        
        def cancel(e):
            dialog.open = False
            self.page.update()
            if dialog in self.page.overlay:
                self.page.overlay.remove(dialog)
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Replace all rows?", weight=ft.FontWeight.W_600),
            content=ft.Text(
                "This will delete all existing rows and replace them with the pasted content.",
                size=14,
                color=DesignTokens.TEXT_SECONDARY,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=cancel),
                ft.ElevatedButton(
                    "Replace",
                    on_click=do_replace,
                    style=ft.ButtonStyle(
                        bgcolor=DesignTokens.ACCENT_DANGER,
                        color=DesignTokens.TEXT_PRIMARY,
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _build_log_section(self) -> ft.Container:
        """Build the live log section with improved styling."""
        self._log_view = ft.ListView(
            controls=[],
            spacing=0,
            auto_scroll=True,
            expand=True,
        )
        
        # Empty state placeholder
        self._empty_log_state = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.TERMINAL_OUTLINED,
                        size=32,
                        color=DesignTokens.TEXT_MUTED,
                    ),
                    ft.Container(height=DesignTokens.SPACING_SM),
                    ft.Text(
                        "No activity yet",
                        size=14,
                        color=DesignTokens.TEXT_TERTIARY,
                    ),
                    ft.Text(
                        "Build logs will appear here",
                        size=12,
                        color=DesignTokens.TEXT_MUTED,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=4,
            ),
            alignment=ft.Alignment(0, 0),
            expand=True,
        )
        
        # Log container that switches between empty state and log view
        # Internal scroll only - container expands to fill available space
        self._log_container = ft.Container(
            content=self._empty_log_state,
            expand=True,  # Fill available vertical space
            border_radius=DesignTokens.RADIUS_MD,
            bgcolor=DesignTokens.BG_SURFACE,
            padding=DesignTokens.SPACING_MD,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,  # Prevent overflow
        )
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(
                                "Build Log",
                                size=18,
                                weight=ft.FontWeight.W_700,
                                color=DesignTokens.TEXT_PRIMARY,
                            ),
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_color=DesignTokens.TEXT_MUTED,
                                icon_size=20,
                                tooltip="Clear log",
                                on_click=lambda _: self._clear_log(),
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=DesignTokens.RADIUS_SM),
                                ),
                            ),
                        ],
                    ),
                    ft.Container(height=DesignTokens.SPACING_SM),
                    self._log_container,
                ],
                spacing=0,
                expand=True,  # Column expands
            ),
            padding=DesignTokens.SPACING_LG,
            border_radius=DesignTokens.RADIUS_LG,
            bgcolor=DesignTokens.BG_CARD,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=12,
                color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK),
                offset=ft.Offset(0, 4),
            ),
            expand=True,  # flex-1 equivalent - fills remaining space
        )
    
    # Maximum log entries to prevent memory leak with long builds
    MAX_LOG_ENTRIES = 500
    LOG_TRIM_COUNT = 200  # Keep this many entries when trimming
    
    # Track log entry count for alternating row colors
    _log_entry_index: int = 0
    
    def _add_log_entry(self, message: str, level: str = "info") -> None:
        """Add a log entry to the log view with automatic rotation and alternating colors."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Switch from empty state to log view on first entry
        if self._log_container and self._log_container.content == self._empty_log_state:
            self._log_container.content = self._log_view
        
        # Color based on level
        color_map = {
            "info": DesignTokens.LOG_INFO,
            "success": DesignTokens.LOG_SUCCESS,
            "warning": DesignTokens.LOG_WARNING,
            "error": DesignTokens.LOG_ERROR,
            "progress": DesignTokens.LOG_PROGRESS,
        }
        color = color_map.get(level, DesignTokens.LOG_INFO)
        
        # Icon based on level
        icon_map = {
            "info": ft.Icons.INFO_OUTLINE,
            "success": ft.Icons.CHECK_CIRCLE_OUTLINE,
            "warning": ft.Icons.WARNING_AMBER_OUTLINED,
            "error": ft.Icons.ERROR_OUTLINE,
            "progress": ft.Icons.TRENDING_UP,
        }
        icon = icon_map.get(level, ft.Icons.CIRCLE)
        
        # Alternating row background
        self._log_entry_index += 1
        row_bg = DesignTokens.LOG_BG_ALT if self._log_entry_index % 2 == 0 else "transparent"
        
        entry = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        timestamp,
                        size=11,
                        color=DesignTokens.LOG_TIMESTAMP,
                        font_family=DesignTokens.FONT_MONO,
                        width=65,
                    ),
                    ft.Icon(icon, size=14, color=color),
                    ft.Text(
                        message,
                        size=12,
                        color=color,
                        font_family=DesignTokens.FONT_MONO,
                        expand=True,
                        no_wrap=False,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.Padding.symmetric(vertical=6, horizontal=10),
            border_radius=4,
            bgcolor=row_bg,
        )
        
        if self._log_view:
            # Log rotation: prevent memory leak with very long builds
            if len(self._log_view.controls) >= self.MAX_LOG_ENTRIES:
                # Keep only the most recent entries
                self._log_view.controls = self._log_view.controls[-self.LOG_TRIM_COUNT:]
            
            self._log_view.controls.append(entry)
    
    def _clear_log(self) -> None:
        """Clear all log entries and show empty state."""
        if self._log_view:
            self._log_view.controls.clear()
            self._log_entry_index = 0
            # Show empty state again
            if self._log_container:
                self._log_container.content = self._empty_log_state
            self.page.update()
    
    def _on_build_click(self, e: ft.ControlEvent) -> None:
        """
        Handle build button click - NON-BLOCKING async execution.
        
        Key Pattern: Using page.run_task() for long-running operations
        ----------------------------------------------------------------
        - page.run_task() schedules async work without blocking the UI thread
        - Allows the Flet event loop to process UI updates during the build
        - Progress callbacks can trigger immediate page.update() calls
        """
        if self.is_building:
            return

        # Run the async build process without freezing the UI
        self.page.run_task(self._run_build_process)
    
    async def _run_build_process(self) -> None:
        """Run the build process asynchronously."""
        if self.is_building:
            return
        
        self.is_building = True
        self._set_building_state(True)
        
        try:
            # RELOAD CONFIG - ensure fresh settings from disk
            from src.config.config_manager import SettingsManager
            from src.config import Config as GlobalConfig
            
            sm = SettingsManager()
            sm.reload()  # Force reload from disk to get latest saved settings
            GlobalConfig.POLLINATIONS_API_KEY = sm.get("POLLINATIONS_API_KEY", "")
            GlobalConfig.CURRENT_LANG = sm.get("CURRENT_LANG", "DE")
            GlobalConfig.VOICE = sm.get("VOICE", "en-US-JennyNeural")
            GlobalConfig.FETCH_IMAGES = sm.get("FETCH_IMAGES", True)
            GlobalConfig.FETCH_AUDIO = sm.get("FETCH_AUDIO", True)
            self._perf_mode = sm.get("PERFORMANCE_MODE", False)
            
            # Check CSV exists
            if not os.path.exists(Config.CSV_FILE):
                self._show_error_dialog(
                    "File Not Found",
                    f"Cannot find {Config.CSV_FILE}\n\nPlease ensure vocabulary.csv is in the project root."
                )
                return
            
            self._add_log_entry("Starting build process...", "info")
            self._update_progress(0, "Initializing...")
            self.page.update()
            
            # Create builder with thread-safe progress callback
            builder = AnkiDeckBuilder(
                language=Config.CURRENT_LANG,
                progress_callback=self._enqueue_progress
            )
            
            self._add_log_entry(f"Language: {Config.CURRENT_LANG}", "info")
            self._add_log_entry(f"Voice: {Config.VOICE}", "info")
            self.page.update()
            
            # Start polling progress queue on UI thread
            self._start_progress_polling()

            # Run the build in a background thread to avoid UI freezes
            success, output_path, stats = await asyncio.to_thread(
                self._run_build_sync,
                builder,
                Config.CSV_FILE,
            )

            if success:
                self._add_log_entry("Build completed successfully!", "success")
                self._update_progress(100, "Complete!")
                self.page.update()
                self._add_log_entry(f"Deck exported to: {output_path}", "success")
                self._add_log_entry("💡 Tip: If card layout looks wrong in Anki, delete the old deck and re-import", "info")
                self._show_success_dialog(output_path, stats)
            else:
                self._add_log_entry("Build failed!", "error")
                self._show_error_dialog("Build Failed", "The build process did not complete successfully.")
        
        except Exception as e:
            self._add_log_entry(f"Error: {str(e)}", "error")
            self._show_error_dialog("Build Error", f"An error occurred during build:\n\n{str(e)}")
        
        finally:
            self.is_building = False
            self._set_building_state(False)
            self.page.update()

    def _run_build_sync(self, builder: AnkiDeckBuilder, csv_file: str) -> tuple:
        """Run build and export in a background thread."""
        try:
            success = asyncio.run(builder.build(csv_file))
            if not success:
                return False, "", {}
            builder.export()
            output_path = os.path.join(
                Config.OUTPUT_DIR,
                f"ankitect_{Config.CURRENT_LANG.lower()}.apkg"
            )
            return True, os.path.abspath(output_path), builder.stats.get_all()
        except Exception:
            return False, "", {}
    
    def _enqueue_progress(self, data: Dict[str, Any]) -> None:
        """Enqueue progress updates from background thread."""
        try:
            self._progress_queue.put_nowait(data)
        except Exception:
            pass

    def _handle_progress(self, data: Dict[str, Any]) -> None:
        """
        Handle progress callback from the builder - THREAD-SAFE UI UPDATES.
        
        Key Pattern: Async-safe UI updates from callbacks
        ---------------------------------------------------
        - Builder runs async tasks that emit progress events
        - This callback is invoked from the builder's context
        - page.update() is called immediately to refresh UI
        - Safe to call from async context in Flet
        
        Args:
            data: Progress payload with event, message, value
        """
        event = data.get("event", "")
        message = data.get("message", "")
        value = data.get("value", 0)
        
        if event == "log":
            # Determine log level from message content
            level = "info"
            if "error" in message.lower() or "⚠️" in message:
                level = "warning"
            elif "[OK]" in message or "success" in message.lower():
                level = "success"
            elif "[WARN]" in message:
                level = "warning"

            if self._perf_mode and level == "info":
                self._info_log_counter += 1
                if self._info_log_counter % 10 != 0:
                    self._schedule_ui_update()
                    return
            self._pending_logs.append({"message": message, "level": level})
        elif event == "progress":
            self._pending_progress = {"value": value, "message": message}

        self._schedule_ui_update()

    def _start_progress_polling(self) -> None:
        """Start polling progress queue on UI thread."""
        if self._queue_polling:
            return
        self._queue_polling = True
        self.page.run_task(self._poll_progress_queue)

    async def _poll_progress_queue(self) -> None:
        """Poll progress queue and apply updates on UI thread."""
        try:
            while self.is_building or not self._progress_queue.empty():
                drained = 0
                while True:
                    try:
                        item = self._progress_queue.get_nowait()
                    except queue.Empty:
                        break
                    self._handle_progress(item)
                    drained += 1

                # Let UI breathe even if no updates
                await asyncio.sleep(0.05 if drained else 0.1)
        finally:
            self._queue_polling = False

    def _schedule_ui_update(self) -> None:
        """Schedule a throttled UI update to reduce redraw frequency."""
        if self._ui_update_scheduled:
            return
        self._ui_update_scheduled = True
        self.page.run_task(self._flush_ui_updates)

    async def _flush_ui_updates(self) -> None:
        """Apply pending logs/progress updates in a single UI refresh."""
        try:
            elapsed = time.monotonic() - self._last_ui_update_ts
            if elapsed < self._min_ui_update_interval:
                await asyncio.sleep(self._min_ui_update_interval - elapsed)

            # Flush logs
            if self._pending_logs:
                for item in self._pending_logs:
                    self._add_log_entry(item["message"], item["level"])
                self._pending_logs.clear()

            # Flush progress
            if self._pending_progress:
                self._update_progress(
                    self._pending_progress.get("value", 0),
                    self._pending_progress.get("message", ""),
                )
                self._pending_progress = None

            self._last_ui_update_ts = time.monotonic()
            self.page.update()
        except Exception:
            pass
        finally:
            self._ui_update_scheduled = False
    
    def _update_progress(self, value: float, message: str = "") -> None:
        """Update the progress bar and text."""
        if self._progress_bar:
            self._progress_bar.value = value / 100.0
        
        if self._progress_text:
            self._progress_text.value = f"{value:.0f}%"
        
        if self._status_text and message:
            self._status_text.value = message
    
    def _set_building_state(self, building: bool) -> None:
        """Set the UI state for building with improved styling."""
        if self._build_button:
            self._build_button.disabled = building
            if building:
                self._build_button.content = ft.Row(
                    controls=[
                        ft.ProgressRing(
                            width=22, 
                            height=22, 
                            stroke_width=2.5, 
                            color=DesignTokens.TEXT_PRIMARY
                        ),
                        ft.Text(
                            "Building...", 
                            size=15, 
                            weight=ft.FontWeight.W_600
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=12,
                )
            else:
                self._build_button.content = ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.ROCKET_LAUNCH_ROUNDED, size=20),
                        ft.Text(
                            "Start Build", 
                            size=15, 
                            weight=ft.FontWeight.W_600
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                )
    
    def _show_success_dialog(self, output_path: str, stats: Dict[str, Any]) -> None:
        """Show the success dialog with build results."""
        words = stats.get('words_processed', 0)
        images = stats.get('images_success', 0)
        audio = stats.get('audio_word_success', 0)
        
        def close_dialog(e):
            dialog.open = False
            self.page.update()  # Force update state first
            # Safe removal
            if dialog in self.page.overlay:
                self.page.overlay.remove(dialog)
            self.page.update()
        
        def open_folder(e):
            folder = os.path.dirname(output_path)
            try:
                import platform
                import subprocess
                system = platform.system()
                if system == "Windows":
                    os.startfile(folder)
                elif system == "Darwin":  # macOS
                    subprocess.run(["open", folder], check=False)
                else:  # Linux
                    subprocess.run(["xdg-open", folder], check=False)
            except Exception:
                pass
            close_dialog(e)
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CHECK_CIRCLE, color=DesignTokens.ACCENT_SUCCESS, size=28),
                    ft.Text("Build Complete!", weight=ft.FontWeight.W_700, size=18),
                ],
                spacing=12,
            ),
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Your Anki deck has been successfully created!",
                        size=14,
                        color=DesignTokens.TEXT_SECONDARY,
                    ),
                    ft.Container(height=DesignTokens.SPACING_MD),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row([
                                    ft.Icon(ft.Icons.BOOK, size=18, color=DesignTokens.TEXT_TERTIARY),
                                    ft.Text(f"Words: {words}", size=14, color=DesignTokens.TEXT_PRIMARY),
                                ], spacing=10),
                                ft.Row([
                                    ft.Icon(ft.Icons.IMAGE, size=18, color=DesignTokens.TEXT_TERTIARY),
                                    ft.Text(f"Images: {images}", size=14, color=DesignTokens.TEXT_PRIMARY),
                                ], spacing=10),
                                ft.Row([
                                    ft.Icon(ft.Icons.AUDIOTRACK, size=18, color=DesignTokens.TEXT_TERTIARY),
                                    ft.Text(f"Audio files: {audio}", size=14, color=DesignTokens.TEXT_PRIMARY),
                                ], spacing=10),
                            ],
                            spacing=8,
                        ),
                        padding=DesignTokens.SPACING_MD,
                        border_radius=DesignTokens.RADIUS_MD,
                        bgcolor=DesignTokens.BG_SURFACE,
                    ),
                    ft.Container(height=DesignTokens.SPACING_MD),
                    ft.Text(
                        "Output file:",
                        size=12,
                        color=DesignTokens.TEXT_TERTIARY,
                    ),
                    ft.Container(
                        content=ft.Text(
                            output_path,
                            size=12,
                            color=DesignTokens.LOG_PROGRESS,
                            font_family=DesignTokens.FONT_MONO,
                            selectable=True,
                        ),
                        padding=DesignTokens.SPACING_SM,
                        border_radius=DesignTokens.RADIUS_SM,
                        bgcolor=DesignTokens.BG_SURFACE,
                    ),
                ],
                tight=True,
                spacing=6,
            ),
            actions=[
                ft.TextButton(
                    "Open Folder", 
                    on_click=open_folder,
                    style=ft.ButtonStyle(color=DesignTokens.ACCENT_SECONDARY),
                ),
                ft.ElevatedButton(
                    "Close", 
                    on_click=close_dialog,
                    style=ft.ButtonStyle(
                        bgcolor=DesignTokens.ACCENT_PRIMARY,
                        color=DesignTokens.TEXT_PRIMARY,
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _show_error_dialog(self, title: str, message: str) -> None:
        """Show an error dialog with improved styling."""
        def close_dialog(e):
            dialog.open = False
            self.page.update()
            if dialog in self.page.overlay:
                self.page.overlay.remove(dialog)
            self.page.update()
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=DesignTokens.ACCENT_DANGER, size=28),
                    ft.Text(title, weight=ft.FontWeight.W_700, size=18),
                ],
                spacing=12,
            ),
            content=ft.Text(
                message,
                size=14,
                color=DesignTokens.TEXT_SECONDARY,
            ),
            actions=[
                ft.ElevatedButton(
                    "Close", 
                    on_click=close_dialog,
                    style=ft.ButtonStyle(
                        bgcolor=DesignTokens.ACCENT_DANGER,
                        color=DesignTokens.TEXT_PRIMARY,
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _on_file_picked(self, e) -> None:
        """Import CSV file by copying to project root."""
        import shutil
        
        try:
            # Copy file asynchronously
            self.page.run_task(self._import_csv_async, source_path)
        except Exception as e:
            self._show_error_dialog("Import Failed", f"Failed to import CSV: {str(e)}")
    
    async def _import_csv_async(self, source_path: str) -> None:
        """Import CSV file asynchronously."""
        import shutil
        
        try:
            # Copy file in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, shutil.copy, source_path, Config.CSV_FILE)
            
            # Update CSV status indicator
            self._csv_status_icon.name = ft.Icons.CHECK_CIRCLE
            self._csv_status_icon.color = DesignTokens.ACCENT_SUCCESS
            self._csv_status_text.value = "vocabulary.csv: Found"
            
            # Show success snackbar
            self._show_snackbar("CSV imported successfully!", icon=ft.Icons.CHECK_CIRCLE)
            
            self.page.update()
        except Exception as e:
            self._show_error_dialog("Import Failed", f"Failed to import CSV: {str(e)}")

    def _clear_paste_input(self) -> None:
        """Clear the paste input field."""
        if self._paste_input:
            self._paste_input.value = ""
            self.page.update()

    def _import_csv_text(self, text: str) -> None:
        """Append CSV rows from pasted text into vocabulary.csv."""
        self._write_pasted_csv(text, mode="append")

    def _replace_csv_text(self, text: str) -> None:
        """Replace all rows in vocabulary.csv with pasted text."""
        self._write_pasted_csv(text, mode="replace")

    def _write_pasted_csv(self, text: str, mode: str) -> None:
        """Parse pasted CSV rows and write to vocabulary.csv."""
        raw = (text or "").strip()
        if not raw:
            self._show_snackbar("Paste CSV rows first.", error=True, icon=ft.Icons.WARNING_AMBER)
            return

        csv_path = Config.CSV_FILE
        file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0

        try:
            header = self._read_csv_header(csv_path) if file_exists else list(self.DEFAULT_COLUMNS)
            header, normalized_rows = self._parse_pasted_rows(raw, header)

            if not normalized_rows:
                self._show_snackbar("Only header detected — nothing to import.", error=True, icon=ft.Icons.INFO_OUTLINE)
                return

            write_mode = "w" if mode == "replace" else ("a" if file_exists else "w")
            with open(csv_path, write_mode, encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, delimiter="|", quotechar='"', quoting=csv.QUOTE_MINIMAL)
                writer.writerow(header)
                for row in normalized_rows:
                    writer.writerow(row)

            # Update status indicator
            if self._csv_status_icon and self._csv_status_text:
                self._csv_status_icon.name = ft.Icons.CHECK_CIRCLE
                self._csv_status_icon.color = DesignTokens.ACCENT_SUCCESS
                self._csv_status_text.value = "vocabulary.csv: Found"

            action = "Replaced" if mode == "replace" else "Imported"
            self._show_snackbar(
                f"{action} {len(normalized_rows)} row(s). Open Workbench and reload to see them.",
                icon=ft.Icons.CHECK_CIRCLE,
            )
            self._clear_paste_input()
            self.page.update()

        except Exception as e:
            self._show_error_dialog("Paste Import Failed", f"Failed to parse CSV: {str(e)}")

    def _parse_pasted_rows(self, raw: str, header: List[str]) -> tuple[List[str], List[List[str]]]:
        """Parse pasted CSV rows and return header + normalized rows."""
        reader = csv.reader(io.StringIO(raw), delimiter="|", quotechar='"', doublequote=True)
        rows = [row for row in reader if any(cell.strip() for cell in row)]

        if not rows:
            self._show_snackbar("No valid CSV rows found.", error=True, icon=ft.Icons.ERROR_OUTLINE)
            return header, []

        # Skip header row if pasted
        first_row = [c.strip() for c in rows[0]]
        if len(first_row) == len(header) and all(
            a.lower() == b.lower() for a, b in zip(first_row, header)
        ):
            rows = rows[1:]

        if not rows:
            return header, []

        normalized_rows = []
        for row in rows:
            if len(row) > len(header):
                self._show_error_dialog(
                    "CSV Format Error",
                    f"Row has {len(row)} fields but expected {len(header)}.",
                )
                return header, []
            if len(row) < len(header):
                row = row + [""] * (len(header) - len(row))
            row = [TextParser.normalize_unicode(cell) for cell in row]
            normalized_rows.append(row)

        return header, normalized_rows

    def _read_csv_header(self, csv_path: str) -> List[str]:
        """Read header row from existing CSV file."""
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f, delimiter="|", quotechar='"', doublequote=True)
            for row in reader:
                if any(cell.strip() for cell in row):
                    return [cell.strip() for cell in row]
        return list(self.DEFAULT_COLUMNS)
    
    def _show_snackbar(self, message: str, error: bool = False, icon: str = None) -> None:
        """Show a snackbar notification with improved styling."""
        snackbar = ft.SnackBar(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        icon or (ft.Icons.ERROR_OUTLINE if error else ft.Icons.CHECK_CIRCLE_OUTLINE),
                        color=DesignTokens.TEXT_PRIMARY,
                        size=20,
                    ),
                    ft.Text(
                        message, 
                        color=DesignTokens.TEXT_PRIMARY,
                        size=14,
                    ),
                ],
                spacing=12,
            ),
            bgcolor=DesignTokens.ACCENT_DANGER if error else DesignTokens.ACCENT_SUCCESS,
            duration=3500,
        )
        # Clean up old snackbars
        for ctrl in list(self.page.overlay):
            if isinstance(ctrl, ft.SnackBar):
                self.page.overlay.remove(ctrl)
        self.page.overlay.append(snackbar)
        snackbar.open = True
        self.page.update()


def create_dashboard_view(page: ft.Page) -> ft.Container:
    """
    Factory function to create the dashboard view.
    
    Args:
        page: Flet page instance
        
    Returns:
        Container with the dashboard view
    """
    dashboard = DashboardView(page)
    return dashboard.container
