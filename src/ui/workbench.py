"""
Workbench View - Master-Detail Editor for Vocabulary Data
----------------------------------------------------------

Provides a DataTable for browsing vocabulary and a detail panel for editing.
Includes AI tools for regenerating images and audio.
Features live card preview for instant visual feedback.
"""

import asyncio
import hashlib
import math
import os
import platform
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import flet as ft
import pandas as pd

from src.config import (
    Config,
    SettingsManager,
    CARD_SECTIONS,
    get_default_enabled,
    get_default_order,
    validate_sections_config,
)
from src.fetchers import AudioFetcher, ImageFetcher
from src.utils.parsing import TextParser
from src.services import VocabularyService
from src.ui.card_preview import CardPreviewView, create_card_preview
from src.ui.card_types_editor import CardTypesEditor
from src.templates import CardTemplates


class WorkbenchView:
    """
    Master-Detail view for editing vocabulary data.
    
    Displays vocabulary in a DataTable (master) and provides
    editable fields in a detail panel when a row is selected.
    Includes AI tools for image and audio generation.
    Features live Anki card preview.
    """
    
    # Columns to display in the master table
    DISPLAY_COLUMNS: List[str] = ["TargetWord"]
    MAX_CELL_LENGTH: int = 50
    
    def __init__(self, page: ft.Page) -> None:
        """
        Initialize the Workbench view.
        
        Args:
            page: Flet page instance for updates
        """
        self.page = page
        self.df: Optional[pd.DataFrame] = None
        self.selected_row_index: Optional[int] = None
        
        # UI References
        self._data_table: Optional[ft.DataTable] = None
        self._detail_panel: Optional[ft.Container] = None
        self._status_text: Optional[ft.Text] = None
        self._save_button: Optional[ft.ElevatedButton] = None
        self._page_label: Optional[ft.Text] = None
        self._page_prev_btn: Optional[ft.IconButton] = None
        self._page_next_btn: Optional[ft.IconButton] = None
        self._page_size_dropdown: Optional[ft.Dropdown] = None
        
        # Detail panel fields
        self._fields: Dict[str, ft.TextField] = {}
        
        # Media preview references
        self._image_container: Optional[ft.Container] = None
        self._audio_status: Optional[ft.Text] = None
        self._current_audio_path: Optional[str] = None
        
        # Loading indicators
        self._image_loading: Optional[ft.ProgressRing] = None
        self._audio_loading: Dict[str, ft.ProgressRing] = {}
        self._image_gen_button: Optional[ft.ElevatedButton] = None
        self._image_prompt_field: Optional[ft.TextField] = None
        self._is_generating_image: bool = False
        
        # Internal audio player (Flet native)
        self._audio_player: Optional[ft.Audio] = None
        
        # Fetchers
        self._audio_fetcher = AudioFetcher()
        self._image_fetcher = ImageFetcher()
        
        # Vocabulary service (supports CSV and SQLite backends)
        self._vocab_service = VocabularyService()
        
        # Track unsaved changes
        self._has_unsaved_changes: bool = False

        # Pagination state
        self._page_size: int = 100
        self._current_page: int = 0
        self._page_row_indices: List[int] = []
        self._last_selected_row_index: Optional[int] = None
        
        # Card preview component
        self._card_preview: Optional[CardPreviewView] = None

        # Deck layout settings (moved from Settings)
        self._settings = SettingsManager()
        self._performance_mode: bool = self._settings.get("PERFORMANCE_MODE", False)
        self._sections_enabled: Dict[str, bool] = self._settings.get(
            "CARD_SECTIONS_ENABLED",
            get_default_enabled(),
        )
        self._sections_order: List[str] = self._settings.get(
            "CARD_SECTIONS_ORDER",
            get_default_order(),
        )
        self._sections_enabled, self._sections_order = validate_sections_config(
            self._sections_enabled,
            self._sections_order,
        )

        # Deck layout UI references
        self._sections_list: Optional[ft.Column] = None
        self._layout_status: Optional[ft.Text] = None
        self._card_types_editor: Optional[CardTypesEditor] = None

        # Style editor references
        self._style_fields: Dict[str, ft.TextField] = {}
        self._style_status: Optional[ft.Text] = None
        self._active_style_key: Optional[str] = None
        self._preview_update_version: int = 0
        self._style_update_version: int = 0
        self._preview_debounce_ms: int = 200
        self._style_debounce_ms: int = 350

        # Layout toggles
        self._swap_master_preview: bool = False
        self._show_master: bool = True
        self._show_detail: bool = True
        self._show_builder: bool = True
        self._show_layout_controls: bool = False
        self._panel_weights: Dict[str, int] = {
            "master": 2,
            "detail": 5,
            "builder": 7,
        }

        self._panel_buttons: Dict[str, ft.TextButton] = {}
        self._panel_sliders: Dict[str, ft.Slider] = {}

        # Main layout references
        self._main_row: Optional[ft.Row] = None
        self._master_container: Optional[ft.Container] = None
        self._builder_container: Optional[ft.Container] = None

        # Live preview controls
        self._live_preview_enabled: bool = True
        self._live_preview_switch: Optional[ft.Switch] = None
        self._preview_refresh_btn: Optional[ft.TextButton] = None
        self._live_preview_threshold: int = 1000
        
        # Build the view
        self._load_data()
        self._live_preview_enabled = self._get_default_live_preview()
        self._container = self._build_view()
    
    @property
    def container(self) -> ft.Container:
        """Get the main container for this view."""
        return self._container
    
    def _load_data(self) -> None:
        """Load vocabulary data from CSV."""
        csv_path = Path(Config.CSV_FILE)
        
        if not csv_path.exists():
            self.df = pd.DataFrame()
            self._current_page = 0
            self._live_preview_enabled = self._get_default_live_preview()
            self._adjust_page_size_for_perf()
            return
        
        try:
            self.df = pd.read_csv(csv_path, sep='|', encoding='utf-8-sig').fillna('')
            self.df.columns = self.df.columns.str.strip()
            self._current_page = 0
            self._live_preview_enabled = self._get_default_live_preview()
            self._adjust_page_size_for_perf()
        except Exception as e:
            print(f"Error loading CSV: {e}")
            self.df = pd.DataFrame()
            self._current_page = 0
            self._live_preview_enabled = self._get_default_live_preview()
            self._adjust_page_size_for_perf()
    
    def _truncate_text(self, text: str, max_length: int = None) -> str:
        """Truncate text to max length with ellipsis."""
        max_len = max_length or self.MAX_CELL_LENGTH
        text = str(text).strip()
        if len(text) > max_len:
            return text[:max_len - 3] + "..."
        return text
    
    def _play_audio_file(self, file_path: str) -> None:
        """Play an audio file using Flet's native Audio control."""
        try:
            # Ensure absolute path for Flet Audio
            abs_path = os.path.abspath(file_path)
            
            # Remove existing audio player if any
            if self._audio_player:
                try:
                    self._audio_player.pause()
                    if self._audio_player in self.page.overlay:
                        self.page.overlay.remove(self._audio_player)
                except Exception:
                    pass
            
            # Create new audio player with the file
            self._audio_player = ft.Audio(
                src=abs_path,
                autoplay=True,
                volume=1.0,
                balance=0,
                on_state_changed=lambda e: self._on_audio_state_changed(e),
            )
            
            # Add to page overlay for playback
            self.page.overlay.append(self._audio_player)
            self.page.update()
            
        except Exception as ex:
            # Fallback to system player if ft.Audio fails
            try:
                system = platform.system()
                abs_path = os.path.abspath(file_path)
                if system == "Windows":
                    os.startfile(abs_path)
                elif system == "Darwin":
                    subprocess.run(["afplay", abs_path], check=False)
                else:
                    subprocess.run(["xdg-open", abs_path], check=False)
            except Exception:
                pass
    
    def _on_audio_state_changed(self, e: ft.ControlEvent) -> None:
        """Handle audio player state changes."""
        if self._audio_status:
            state = str(e.data) if e.data else ""
            if "completed" in state.lower():
                self._audio_status.value = "✓ Playback complete"
                self._audio_status.color = ft.Colors.GREEN_400
            elif "playing" in state.lower():
                self._audio_status.value = "▶ Playing..."
                self._audio_status.color = ft.Colors.TEAL_400
            self.page.update()
    
    def _build_view(self) -> ft.Container:
        """Build the main workbench layout."""
        if self.df is None or self.df.empty:
            return self._build_empty_state()
        
        # Build master table
        master_panel = self._build_master_panel()

        # Build detail panel (initially empty)
        self._detail_panel = self._build_detail_panel()

        # Build card preview panel
        if not self._card_preview:
            self._card_preview = create_card_preview(self.page)

        # Detail container (middle column)
        self._detail_container = ft.Container(
            content=self._detail_panel,
            expand=True,
        )

        # Deck builder panel (right column)
        builder_panel = self._build_builder_panel()

        # Main layout containers
        self._master_container = ft.Container(content=master_panel, expand=3, padding=10)
        self._detail_container = ft.Container(content=self._detail_panel, expand=5, padding=10)
        self._builder_container = ft.Container(content=builder_panel, expand=6, padding=10)

        self._main_row = ft.Row(
            controls=[],
            spacing=10,
            expand=True,
        )
        self._apply_layout_order()

        top_bar = self._build_layout_toolbar()

        return ft.Container(
            content=ft.Column(
                controls=[
                    top_bar,
                    self._main_row,
                ],
                spacing=10,
                expand=True,
            ),
            expand=True,
        )
    
    
    def _build_empty_state(self) -> ft.Container:
        """Build empty state when no data is available."""
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, size=64, color=ft.Colors.WHITE24),
                    ft.Text(
                        "No Vocabulary Data",
                        size=24,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE54,
                    ),
                    ft.Text(
                        f"Place your vocabulary.csv file in the project root",
                        size=14,
                        color=ft.Colors.WHITE38,
                    ),
                    ft.Container(height=20),
                    ft.ElevatedButton(
                        text="Reload Data",
                        icon=ft.Icons.REFRESH,
                        on_click=lambda _: self._reload_data(),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10,
            ),
            expand=True,
            alignment=ft.Alignment(0, 0),
        )
    
    def _build_master_panel(self) -> ft.Container:
        """Build the master table panel."""
        # Status bar
        self._status_text = ft.Text(
            self._get_status_text(),
            size=12,
            color=ft.Colors.WHITE54,
        )
        
        # Save button with elevation
        self._save_button = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SAVE, size=16),
                    ft.Text("Save Project", size=13),
                ],
                spacing=5,
            ),
            style=ft.ButtonStyle(
                color={
                    ft.ControlState.DEFAULT: ft.Colors.WHITE,
                    ft.ControlState.DISABLED: ft.Colors.WHITE38,
                },
                bgcolor={
                    ft.ControlState.DEFAULT: ft.Colors.GREEN_700,
                    ft.ControlState.HOVERED: ft.Colors.GREEN_600,
                    ft.ControlState.DISABLED: ft.Colors.with_opacity(0.3, ft.Colors.GREEN_700),
                },
                padding=ft.Padding.symmetric(horizontal=15, vertical=10),
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation={
                    ft.ControlState.DEFAULT: 2,
                    ft.ControlState.HOVERED: 4,
                },
            ),
            on_click=lambda _: self._on_save_click(),
        )
        
        # Header row
        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        "Vocabulary",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    ),
                    ft.Container(expand=True),
                    self._status_text,
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_color=ft.Colors.WHITE54,
                        tooltip="Reload data",
                        on_click=lambda _: self._reload_data(),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                spacing=10,
            ),
            padding=ft.Padding.only(bottom=10),
        )
        
        # Build data table
        self._data_table = self._build_data_table()

        # Pagination controls
        pagination_controls = self._build_pagination_controls()
        
        # Wrap table in scrollable container
        table_container = ft.Container(
            content=ft.Column(
                controls=[self._data_table],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=True,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.WHITE),
            padding=10,
        )
        
        return ft.Container(
            content=ft.Column(
                controls=[header, pagination_controls, table_container],
                spacing=0,
                expand=True,
            ),
            expand=True,
        )

    def _get_status_text(self) -> str:
        """Return a status text for the table state."""
        if self.df is None or self.df.empty:
            return ""
        total = len(self.df)
        start, end = self._get_visible_range()
        return f"{total} words loaded (showing {start}-{end})"

    def _get_page_count(self) -> int:
        """Get total page count based on current page size."""
        if self.df is None or self.df.empty:
            return 1
        return max(1, math.ceil(len(self.df) / self._page_size))

    def _get_visible_range(self) -> tuple:
        """Get the visible row range (1-based, inclusive)."""
        if self.df is None or self.df.empty:
            return (0, 0)
        start = self._current_page * self._page_size
        end = min(start + self._page_size, len(self.df))
        return (start + 1, end)

    def _get_visible_df(self) -> pd.DataFrame:
        """Return the current page slice of the DataFrame."""
        if self.df is None or self.df.empty:
            return pd.DataFrame()
        start = self._current_page * self._page_size
        end = min(start + self._page_size, len(self.df))
        return self.df.iloc[start:end]

    def _build_pagination_controls(self) -> ft.Container:
        """Build pagination UI for the vocabulary table."""
        self._page_prev_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT,
            icon_color=ft.Colors.WHITE54,
            tooltip="Previous page",
            on_click=lambda _: self._on_page_prev(),
        )
        self._page_next_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT,
            icon_color=ft.Colors.WHITE54,
            tooltip="Next page",
            on_click=lambda _: self._on_page_next(),
        )
        self._page_label = ft.Text("", size=12, color=ft.Colors.WHITE54)

        self._page_size_dropdown = ft.Dropdown(
            value=str(self._page_size),
            width=110,
            options=[
                ft.dropdown.Option("50"),
                ft.dropdown.Option("100"),
                ft.dropdown.Option("200"),
                ft.dropdown.Option("500"),
            ],
            label="Rows",
            border_color=ft.Colors.WHITE24,
            focused_border_color=ft.Colors.INDIGO_200,
            label_style=ft.TextStyle(color=ft.Colors.WHITE54),
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
        )
        self._page_size_dropdown.on_change = self._on_page_size_change

        self._update_pagination_ui()

        return ft.Container(
            content=ft.Row(
                controls=[
                    self._page_prev_btn,
                    self._page_next_btn,
                    self._page_label,
                    ft.Container(expand=True),
                    self._page_size_dropdown,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.Padding.only(bottom=8),
        )

    def _update_pagination_ui(self) -> None:
        """Update pagination label and button states."""
        page_count = self._get_page_count()
        if self._page_label:
            self._page_label.value = f"Page {self._current_page + 1}/{page_count}"
        if self._page_prev_btn:
            self._page_prev_btn.disabled = self._current_page <= 0
        if self._page_next_btn:
            self._page_next_btn.disabled = self._current_page >= (page_count - 1)
        if self._status_text:
            self._status_text.value = self._get_status_text()

    def _on_page_prev(self) -> None:
        """Navigate to previous page."""
        if self._current_page > 0:
            self._current_page -= 1
            self._refresh_table()

    def _on_page_next(self) -> None:
        """Navigate to next page."""
        if self._current_page < self._get_page_count() - 1:
            self._current_page += 1
            self._refresh_table()

    def _on_page_size_change(self, e: ft.ControlEvent) -> None:
        """Handle page size change and reset to first page."""
        try:
            self._page_size = int(e.control.value)
        except Exception:
            self._page_size = 100
        self._current_page = 0
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Refresh table rows based on current pagination state."""
        if not self._data_table:
            return
        new_table = self._build_data_table()
        self._data_table.rows = new_table.rows
        # Restore selection if selected row is visible in current page
        if self.selected_row_index is not None:
            local_idx = self._get_local_row_index(self.selected_row_index)
            if local_idx is not None and local_idx < len(self._data_table.rows):
                self._data_table.rows[local_idx].selected = True
        self._update_pagination_ui()
        self.page.update()
    
    def _build_data_table(self) -> ft.DataTable:
        """Build the DataTable with vocabulary data."""
        # Create columns
        columns = [
            ft.DataColumn(
                ft.Text(col, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE70),
            )
            for col in self.DISPLAY_COLUMNS
        ]
        
        # Create rows
        rows = []
        self._page_row_indices = []
        visible_df = self._get_visible_df()
        for row in visible_df.itertuples(index=True, name="Row"):
            idx = row.Index
            self._page_row_indices.append(idx)
            cells = []
            for col in self.DISPLAY_COLUMNS:
                attr = col if hasattr(row, col) else col.replace(" ", "_")
                value = getattr(row, attr, "")
                cells.append(
                    ft.DataCell(
                        ft.Text(
                            self._truncate_text(str(value)),
                            size=13,
                            color=ft.Colors.WHITE,
                        ),
                        on_tap=lambda e, i=idx: self._on_row_tap(i),
                    )
                )
            
            data_row = ft.DataRow(
                cells=cells,
                selected=False,
                on_select_change=lambda e, i=idx: self._on_row_selected(i, e),
            )
            rows.append(data_row)
        
        return ft.DataTable(
            columns=columns,
            rows=rows,
            border=ft.border.all(1, ft.Colors.WHITE10),
            border_radius=10,
            vertical_lines=ft.BorderSide(1, ft.Colors.WHITE10),
            horizontal_lines=ft.BorderSide(1, ft.Colors.WHITE10),
            heading_row_color=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
            heading_row_height=50,
            data_row_min_height=45,
            data_row_max_height=60,
            show_checkbox_column=not self._performance_mode,
            column_spacing=20,
        )
    
    def _build_detail_panel(self) -> ft.Container:
        """Build the detail panel (initially showing placeholder)."""
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.TOUCH_APP_ROUNDED, size=48, color=ft.Colors.WHITE24),
                            ft.Text(
                                "Select a Word",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE54,
                            ),
                            ft.Text(
                                "Click on a row to view and edit details",
                                size=13,
                                color=ft.Colors.WHITE38,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=10,
                        expand=True,
                    ),
                ],
                expand=True,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            expand=True,
            padding=20,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.WHITE),
        )

    def _build_builder_panel(self) -> ft.Container:
        """Build the Deck Builder panel with layout editor and preview."""
        # Preview container
        self._preview_container = ft.Container(
            content=self._card_preview.build(),
            expand=True,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.WHITE),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        builder_header = ft.Row(
            controls=[
                ft.Icon(ft.Icons.AUTO_FIX_HIGH, size=20, color=ft.Colors.INDIGO_200),
                ft.Text(
                    "Deck Builder",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                ),
            ],
            spacing=8,
        )

        self._live_preview_switch = ft.Switch(
            value=self._live_preview_enabled,
            label="Live preview",
            on_change=self._on_live_preview_toggle,
        )
        self._preview_refresh_btn = ft.TextButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.REFRESH, size=14, color=ft.Colors.WHITE70),
                    ft.Text("Refresh preview", size=12, color=ft.Colors.WHITE70),
                ],
                spacing=6,
            ),
            on_click=lambda _: self._refresh_preview_now(),
        )

        builder_left = ft.Container(
            content=ft.Column(
                controls=[
                    builder_header,
                    ft.Container(height=8),
                    self._build_layout_editor(),
                    ft.Container(height=10),
                    self._build_styles_editor(),
                    ft.Container(height=10),
                    self._build_card_types_editor(),
                ],
                spacing=0,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=6,
        )

        preview_right = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("Live Preview", size=12, color=ft.Colors.WHITE70),
                            ft.Container(expand=True),
                            self._live_preview_switch,
                            self._preview_refresh_btn,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=6),
                    self._preview_container,
                ],
                expand=True,
                spacing=0,
            ),
            expand=4,
        )

        return ft.Container(
            content=ft.Row(
                controls=[builder_left, preview_right],
                spacing=10,
                expand=True,
            ),
            expand=True,
        )

    def _build_layout_toolbar(self) -> ft.Container:
        """Build toolbar for panel visibility and sizing."""
        layout_toggle_btn = ft.IconButton(
            icon=ft.Icons.TUNE,
            icon_color=ft.Colors.WHITE70,
            tooltip="Layout controls",
            on_click=self._toggle_layout_controls,
        )

        def panel_button(label: str, key: str, icon: str) -> ft.TextButton:
            btn = ft.TextButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(icon, size=14, color=ft.Colors.WHITE70),
                        ft.Text(label, size=12, color=ft.Colors.WHITE70),
                    ],
                    spacing=6,
                ),
                on_click=lambda e, k=key: self._toggle_panel_visibility(k),
                style=ft.ButtonStyle(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    shape=ft.RoundedRectangleBorder(radius=8),
                ),
            )
            self._panel_buttons[key] = btn
            return btn

        def panel_slider(label: str, key: str) -> ft.Column:
            slider = ft.Slider(
                min=1,
                max=10,
                divisions=9,
                value=self._panel_weights.get(key, 5),
                label="{value}",
                on_change=lambda e, k=key: self._on_panel_weight_change(k, e.control.value),
            )
            self._panel_sliders[key] = slider
            return ft.Column(
                controls=[
                    ft.Text(label, size=11, color=ft.Colors.WHITE54),
                    slider,
                ],
                spacing=2,
                expand=True,
            )

        top_row = ft.Row(
            controls=[
                layout_toggle_btn,
                ft.Text("Layout", size=12, color=ft.Colors.WHITE70),
                ft.Container(expand=True),
                self._save_button,
                ft.IconButton(
                    icon=ft.Icons.REFRESH,
                    icon_color=ft.Colors.WHITE54,
                    tooltip="Reload data",
                    on_click=lambda _: self._reload_data(),
                ),
            ],
            spacing=8,
            alignment=ft.MainAxisAlignment.START,
        )

        buttons_row = ft.Row(
            controls=[
                ft.Text("Panels", size=12, color=ft.Colors.WHITE54),
                panel_button("Vocabulary", "master", ft.Icons.LIST_ALT),
                panel_button("Editor", "detail", ft.Icons.EDIT_NOTE),
                panel_button("Builder", "builder", ft.Icons.AUTO_FIX_HIGH),
                ft.Container(expand=True),
                ft.TextButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SWAP_HORIZ, size=14, color=ft.Colors.WHITE70),
                            ft.Text("Swap Vocab/Builder", size=12, color=ft.Colors.WHITE70),
                        ],
                        spacing=6,
                    ),
                    on_click=self._toggle_swap_panels,
                ),
            ],
            spacing=8,
            alignment=ft.MainAxisAlignment.START,
        )

        sliders_row = ft.Row(
            controls=[
                panel_slider("Vocab Width", "master"),
                panel_slider("Editor Width", "detail"),
                panel_slider("Builder Width", "builder"),
            ],
            spacing=10,
            expand=True,
        )

        self._update_panel_controls_state()

        controls_block = ft.Column(
            controls=[buttons_row, sliders_row],
            spacing=6,
            visible=self._show_layout_controls,
        )

        return ft.Container(
            content=ft.Column(
                controls=[top_row, controls_block],
                spacing=6,
            ),
            padding=10,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.WHITE),
        )

    def _build_card_types_editor(self) -> ft.Container:
        """Build the card types editor panel."""
        self._card_types_editor = CardTypesEditor(
            self.page,
            on_save=self._refresh_preview_now,
        )
        return self._card_types_editor.container

    def _build_layout_editor(self) -> ft.Container:
        """Build the layout editor for card sections."""
        # Validate config
        self._sections_enabled, self._sections_order = validate_sections_config(
            self._sections_enabled,
            self._sections_order,
        )

        self._sections_list = ft.Column(
            controls=self._build_section_items(),
            spacing=6,
        )

        self._layout_status = ft.Text(
            "Saved",
            size=10,
            color=ft.Colors.WHITE38,
        )

        enabled_count = sum(1 for k, v in self._sections_enabled.items() if v)
        total_count = len(self._sections_order)
        summary_chip = ft.Container(
            content=ft.Text(
                f"{enabled_count}/{total_count} enabled",
                size=10,
                color=ft.Colors.WHITE70,
            ),
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
        )

        reset_sections_btn = ft.TextButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.RESTORE, size=14, color=ft.Colors.TEAL_200),
                    ft.Text("Reset Order", size=11, color=ft.Colors.TEAL_200),
                ],
                spacing=4,
            ),
            on_click=self._on_reset_sections_click,
        )

        preset_min_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.TUNE, size=14, color=ft.Colors.WHITE70),
                    ft.Text("Minimal", size=12, color=ft.Colors.WHITE70),
                ],
                spacing=6,
            ),
            height=28,
            style=ft.ButtonStyle(
                color={ft.ControlState.DEFAULT: ft.Colors.WHITE70},
                bgcolor={ft.ControlState.DEFAULT: ft.Colors.with_opacity(0.02, ft.Colors.WHITE)},
                side={ft.ControlState.DEFAULT: ft.BorderSide(1, ft.Colors.WHITE12)},
                padding=ft.Padding.symmetric(horizontal=10, vertical=0),
            ),
            on_click=self._on_preset_minimal,
        )
        preset_full_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.DASHBOARD, size=14, color=ft.Colors.WHITE70),
                    ft.Text("Full", size=12, color=ft.Colors.WHITE70),
                ],
                spacing=6,
            ),
            height=28,
            style=ft.ButtonStyle(
                color={ft.ControlState.DEFAULT: ft.Colors.WHITE70},
                bgcolor={ft.ControlState.DEFAULT: ft.Colors.with_opacity(0.02, ft.Colors.WHITE)},
                side={ft.ControlState.DEFAULT: ft.BorderSide(1, ft.Colors.WHITE12)},
                padding=ft.Padding.symmetric(horizontal=10, vertical=0),
            ),
            on_click=self._on_preset_full,
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(
                                "Card Layout",
                                size=14,
                                weight=ft.FontWeight.W_600,
                                color=ft.Colors.WHITE,
                            ),
                            ft.Container(expand=True),
                            summary_chip,
                            ft.Container(width=6),
                            self._layout_status,
                            reset_sections_btn,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=6),
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=12, color=ft.Colors.AMBER_200),
                            ft.Text(
                                "Required sections cannot be disabled. Use arrows to reorder.",
                                size=10,
                                color=ft.Colors.AMBER_200,
                            ),
                        ],
                        spacing=6,
                    ),
                    ft.Container(height=4),
                    ft.Row(
                        controls=[
                            ft.Text("Presets", size=11, color=ft.Colors.WHITE54),
                            preset_min_btn,
                            preset_full_btn,
                        ],
                        spacing=6,
                    ),
                    ft.Container(height=8),
                    ft.Container(
                        content=self._sections_list,
                        bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.WHITE),
                        border_radius=8,
                        padding=8,
                    ),
                ],
                spacing=6,
            ),
            padding=10,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.WHITE),
        )


    def _build_placeholder_panel(self, title: str, description: str, icon: str) -> ft.Container:
        """Build a placeholder panel for upcoming features."""
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(icon, size=36, color=ft.Colors.WHITE24),
                    ft.Text(title, size=14, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE70),
                    ft.Text(description, size=11, color=ft.Colors.WHITE38, text_align=ft.TextAlign.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
            ),
            height=160,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.WHITE),
            alignment=ft.Alignment(0, 0),
            padding=10,
        )

    def _build_styles_editor(self) -> ft.Container:
        """Build styles editor for card appearance."""
        style = self._get_style_config()
        self._style_fields.clear()

        self._style_status = ft.Text("Saved", size=10, color=ft.Colors.WHITE38)

        presets = {
            "Classic": {},
            "Dark": {
                "card_bg": "#121212",
                "container_bg": "#1b1b1b",
                "text_color": "#e6e6e6",
                "label_color": "#9aa0a6",
                "definition_color": "#ffffff",
                "section_border": "#2a2a2a",
                "card_shadow": "0 4px 14px rgba(0,0,0,0.35)",
            },
            "Warm": {
                "card_bg": "#fff7ed",
                "container_bg": "#fffaf4",
                "text_color": "#2f2a26",
                "label_color": "#b08968",
                "definition_color": "#3b2f2f",
                "section_border": "#f1e3d3",
            },
            "Minimal": {
                "card_bg": "#f8fafc",
                "container_bg": "#ffffff",
                "text_color": "#1f2937",
                "label_color": "#94a3b8",
                "definition_color": "#111827",
                "section_border": "#e2e8f0",
                "card_shadow": "0 1px 6px rgba(0,0,0,0.08)",
            },
        }

        palette = [
            "#111827", "#334155", "#64748b", "#e2e8f0", "#ffffff", "#0ea5e9",
            "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#14b8a6", "#f472b6",
        ]

        def swatch(color: str, key: str) -> ft.Container:
            return ft.Container(
                width=16,
                height=16,
                border_radius=4,
                bgcolor=color,
                border=ft.border.all(1, ft.Colors.WHITE12),
                on_click=lambda e, c=color, k=key: self._set_style_color(k, c),
            )

        def color_field(label: str, key: str) -> ft.Column:
            field = ft.TextField(
                value=style.get(key, ""),
                label=label,
                border_color=ft.Colors.WHITE24,
                focused_border_color=ft.Colors.INDIGO_200,
                label_style=ft.TextStyle(color=ft.Colors.WHITE54, size=11),
                text_style=ft.TextStyle(color=ft.Colors.WHITE, size=12),
                dense=True,
                on_blur=lambda e, k=key: self._on_style_change(k, e.control.value),
                on_submit=lambda e, k=key: self._on_style_change(k, e.control.value),
                on_change=lambda e, k=key: self._on_style_change_if_valid(k, e.control.value),
            )
            self._style_fields[key] = field

            preview = ft.Container(
                width=18,
                height=18,
                border_radius=4,
                bgcolor=style.get(key, "#000000"),
                border=ft.border.all(1, ft.Colors.WHITE12),
            )

            return ft.Column(
                controls=[
                    ft.Row(controls=[preview, field], spacing=8),
                    ft.Row(controls=[swatch(c, key) for c in palette], spacing=6, wrap=True),
                ],
                spacing=4,
            )

        reset_btn = ft.TextButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.RESTORE, size=14, color=ft.Colors.TEAL_200),
                    ft.Text("Reset Styles", size=11, color=ft.Colors.TEAL_200),
                ],
                spacing=4,
            ),
            on_click=self._on_reset_styles,
        )

        def preset_button(name: str, preset: Dict[str, str]) -> ft.TextButton:
            preview_style = CardTemplates.DEFAULT_STYLE.copy()
            preview_style.update(preset)
            preview_colors = [
                preview_style.get("card_bg", "#ffffff"),
                preview_style.get("container_bg", "#ffffff"),
                preview_style.get("text_color", "#111827"),
            ]
            return ft.TextButton(
                content=ft.Row(
                    controls=[
                        ft.Text(name, size=12),
                        ft.Row(
                            controls=[
                                ft.Container(
                                    width=10,
                                    height=10,
                                    border_radius=2,
                                    bgcolor=c,
                                    border=ft.border.all(1, ft.Colors.WHITE12),
                                )
                                for c in preview_colors
                            ],
                            spacing=4,
                        ),
                    ],
                    spacing=8,
                ),
                on_click=lambda e, n=name: self._apply_style_preset(n, presets),
                style=ft.ButtonStyle(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    shape=ft.RoundedRectangleBorder(radius=8),
                    bgcolor={ft.ControlState.DEFAULT: ft.Colors.with_opacity(0.02, ft.Colors.WHITE)},
                ),
            )

        base_tab = ft.Column(
            controls=[
                ft.Text("Base colors", size=11, color=ft.Colors.WHITE54),
                color_field("Card Background", "card_bg"),
                color_field("Container Background", "container_bg"),
                color_field("Text Color", "text_color"),
                color_field("Header Text", "header_text"),
                color_field("Label Color", "label_color"),
                color_field("Definition Color", "definition_color"),
                color_field("Section Border", "section_border"),
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        )

        layout_tab = ft.Column(
            controls=[
                ft.Text("Card shape", size=11, color=ft.Colors.WHITE54),
                ft.Text("Radius", size=11, color=ft.Colors.WHITE54),
                ft.Slider(
                    min=0,
                    max=24,
                    divisions=24,
                    value=float(style.get("card_radius", "12").replace("px", "") or 12),
                    label="{value}px",
                    on_change=lambda e: self._on_style_change("card_radius", f"{int(e.control.value)}px"),
                ),
                ft.Text("Shadow", size=11, color=ft.Colors.WHITE54),
                ft.Dropdown(
                    value=style.get("card_shadow", CardTemplates.DEFAULT_STYLE["card_shadow"]),
                    options=[
                        ft.dropdown.Option("none"),
                        ft.dropdown.Option("0 1px 6px rgba(0,0,0,0.08)"),
                        ft.dropdown.Option("0 2px 10px rgba(0,0,0,0.05)"),
                        ft.dropdown.Option("0 4px 14px rgba(0,0,0,0.2)"),
                    ],
                    on_select=lambda e: self._on_style_change("card_shadow", e.control.value),
                ),
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        )

        gradients_tab = ft.Column(
            controls=[
                ft.Text("German gender gradients", size=11, color=ft.Colors.WHITE54),
                color_field("DER Start", "der_start"),
                color_field("DER End", "der_end"),
                color_field("DIE Start", "die_start"),
                color_field("DIE End", "die_end"),
                color_field("DAS Start", "das_start"),
                color_field("DAS End", "das_end"),
                color_field("None Start", "none_start"),
                color_field("None End", "none_end"),
                ft.Text("English header gradient", size=11, color=ft.Colors.WHITE54),
                color_field("EN Start", "en_start"),
                color_field("EN End", "en_end"),
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        )

        presets_tab = ft.Column(
            controls=[
                ft.Text("Presets", size=11, color=ft.Colors.WHITE54),
                ft.Row(
                    controls=[preset_button(name, preset) for name, preset in presets.items()],
                    spacing=8,
                    wrap=True,
                ),
            ],
            spacing=10,
        )

        tabs_map = {
            "Base": base_tab,
            "Layout": layout_tab,
            "Gradients": gradients_tab,
            "Presets": presets_tab,
        }

        tab_buttons: Dict[str, ft.TextButton] = {}
        body_container = ft.Container(content=base_tab, expand=True)

        def set_tab(name: str) -> None:
            body_container.content = tabs_map[name]
            for tab_name, btn in tab_buttons.items():
                is_active = tab_name == name
                btn.style = ft.ButtonStyle(
                    bgcolor={
                        ft.ControlState.DEFAULT: ft.Colors.with_opacity(
                            0.12 if is_active else 0.02, ft.Colors.WHITE
                        )
                    },
                    color={
                        ft.ControlState.DEFAULT: ft.Colors.WHITE if is_active else ft.Colors.WHITE70
                    },
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    shape=ft.RoundedRectangleBorder(radius=8),
                )
            if self.page:
                self.page.update()

        tab_bar = ft.Row(
            controls=[],
            spacing=6,
            wrap=True,
        )

        for name in tabs_map.keys():
            btn = ft.TextButton(
                content=ft.Text(name, size=12),
                on_click=lambda e, n=name: set_tab(n),
            )
            tab_buttons[name] = btn
            tab_bar.controls.append(btn)

        set_tab("Base")

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("Styles", size=14, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                            ft.Container(expand=True),
                            self._style_status,
                            reset_btn,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=6),
                    tab_bar,
                    ft.Container(height=6),
                    body_container,
                ],
                spacing=6,
                expand=True,
            ),
            padding=10,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.WHITE),
            expand=True,
        )

    def _get_style_config(self) -> Dict[str, str]:
        """Get merged style config."""
        style = self._settings.get("CARD_STYLE", CardTemplates.DEFAULT_STYLE)
        return CardTemplates.normalize_style(style)

    def _on_style_change(self, key: str, value: str) -> None:
        """Handle style change and update preview."""
        style = self._get_style_config()
        style[key] = value
        self._settings.set("CARD_STYLE", style, persist=False)
        if self._style_status:
            self._style_status.value = "Editing..."
            self._style_status.color = ft.Colors.WHITE54
        self._schedule_preview_update()
        self._schedule_style_save()

    def _on_style_change_if_valid(self, key: str, value: str) -> None:
        """Update style only when hex looks valid to avoid lag."""
        if not value:
            return
        if value.startswith("#") and len(value) in (4, 7):
            self._on_style_change(key, value)

    def _set_active_style_key(self, key: str) -> None:
        """Set active style key for palette application."""
        self._active_style_key = key
        self.page.update()

    def _apply_palette_color(self, color: str) -> None:
        """Apply palette color to active field."""
        if not self._active_style_key:
            return
        if self._active_style_key in self._style_fields:
            self._style_fields[self._active_style_key].value = color
        self._on_style_change(self._active_style_key, color)

    def _set_style_color(self, key: str, color: str) -> None:
        """Set a color from palette and update UI."""
        if key in self._style_fields:
            self._style_fields[key].value = color
        self._on_style_change(key, color)

    def _apply_style_preset(self, name: str, presets: Dict[str, Dict[str, str]]) -> None:
        """Apply a style preset and refresh editor."""
        base = CardTemplates.DEFAULT_STYLE.copy()
        override = presets.get(name, {})
        base.update(override)
        self._settings.set("CARD_STYLE", base)
        if self._builder_container:
            self._builder_container.content = self._build_builder_panel()
        self._update_card_preview()
        self.page.update()

    def _on_reset_styles(self, e: ft.ControlEvent) -> None:
        """Reset styles to defaults."""
        self._settings.set("CARD_STYLE", CardTemplates.DEFAULT_STYLE.copy())
        if self._builder_container:
            self._builder_container.content = self._build_builder_panel()
        self._update_card_preview()
        self.page.update()

    def _build_section_items(self) -> List[ft.Control]:
        """Build list of section item controls for card layout."""
        items = []

        for idx, section_id in enumerate(self._sections_order):
            section = CARD_SECTIONS.get(section_id)
            if not section:
                continue

            is_enabled = self._sections_enabled.get(section_id, True)
            is_first = idx == 0
            is_last = idx == len(self._sections_order) - 1

            item = self._build_section_item(
                section_id=section_id,
                name=section.name,
                icon=section.icon,
                description=section.description,
                required=section.required,
                enabled=is_enabled,
                is_first=is_first,
                is_last=is_last,
            )
            items.append(item)

        return items

    def _build_section_item(
        self,
        section_id: str,
        name: str,
        icon: str,
        description: str,
        required: bool,
        enabled: bool,
        is_first: bool,
        is_last: bool,
    ) -> ft.Container:
        """Build a single section item control."""
        toggle = ft.Switch(
            value=enabled,
            disabled=required,
            on_change=lambda e, sid=section_id: self._on_toggle_section(sid, e.control.value),
            active_color=ft.Colors.TEAL_400,
        )

        up_btn = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_UP,
            icon_size=16,
            icon_color=ft.Colors.WHITE54 if not is_first else ft.Colors.WHITE12,
            disabled=is_first,
            on_click=lambda e, sid=section_id: self._on_move_section(sid, -1),
            tooltip="Move up",
            style=ft.ButtonStyle(padding=ft.Padding.all(2)),
        )

        down_btn = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_DOWN,
            icon_size=16,
            icon_color=ft.Colors.WHITE54 if not is_last else ft.Colors.WHITE12,
            disabled=is_last,
            on_click=lambda e, sid=section_id: self._on_move_section(sid, 1),
            tooltip="Move down",
            style=ft.ButtonStyle(padding=ft.Padding.all(2)),
        )

        required_badge = ft.Container(
            content=ft.Text("Required", size=8, color=ft.Colors.AMBER_200),
            bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.AMBER),
            padding=ft.Padding.symmetric(horizontal=5, vertical=1),
            border_radius=3,
            visible=required,
        )

        title_row = ft.Row(
            controls=[
                ft.Text(
                    f"{icon} {name}",
                    size=12,
                    weight=ft.FontWeight.W_500,
                    color=ft.Colors.WHITE if enabled else ft.Colors.WHITE38,
                ),
                required_badge,
            ],
            spacing=6,
        )
        description_text = ft.Text(
            description,
            size=10,
            color=ft.Colors.WHITE38 if enabled else ft.Colors.WHITE24,
        )
        section_info = ft.Column(
            controls=[title_row, description_text],
            spacing=2,
            expand=True,
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    toggle,
                    section_info,
                    up_btn,
                    down_btn,
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.WHITE) if enabled else ft.Colors.with_opacity(0.02, ft.Colors.WHITE),
            border=ft.border.all(1, ft.Colors.WHITE10),
        )

    def _refresh_sections_list(self) -> None:
        """Refresh the sections list UI and persist changes."""
        if self._sections_list:
            self._sections_list.controls = self._build_section_items()
        self._mark_layout_dirty()
        self._persist_sections_config()
        self.page.update()

    def _persist_sections_config(self) -> None:
        """Persist card sections config and refresh preview."""
        validated_enabled, validated_order = validate_sections_config(
            self._sections_enabled,
            self._sections_order,
        )
        self._sections_enabled = validated_enabled
        self._sections_order = validated_order
        self._settings.set("CARD_SECTIONS_ENABLED", validated_enabled)
        self._settings.set("CARD_SECTIONS_ORDER", validated_order)
        if self._layout_status:
            self._layout_status.value = "Saved"
            self._layout_status.color = ft.Colors.WHITE38
        self._update_card_preview()

    def _mark_layout_dirty(self) -> None:
        """Update layout status to indicate saving in progress."""
        if self._layout_status:
            self._layout_status.value = "Saving..."
            self._layout_status.color = ft.Colors.AMBER_200

    def _on_toggle_section(self, section_id: str, enabled: bool) -> None:
        """Handle section toggle."""
        section = CARD_SECTIONS.get(section_id)
        if section and section.required:
            return
        self._sections_enabled[section_id] = enabled
        self._refresh_sections_list()

    def _on_move_section(self, section_id: str, direction: int) -> None:
        """Handle section move (direction: -1=up, +1=down)."""
        try:
            current_idx = self._sections_order.index(section_id)
            new_idx = current_idx + direction
            if 0 <= new_idx < len(self._sections_order):
                self._sections_order[current_idx], self._sections_order[new_idx] = (
                    self._sections_order[new_idx],
                    self._sections_order[current_idx],
                )
                self._refresh_sections_list()
        except ValueError:
            pass

    def _on_reset_sections_click(self, e: ft.ControlEvent) -> None:
        """Handle reset sections button click."""
        self._sections_enabled = get_default_enabled()
        self._sections_order = get_default_order()
        self._refresh_sections_list()

    def _on_preset_minimal(self, e: ft.ControlEvent) -> None:
        """Enable only required sections."""
        for section_id, section in CARD_SECTIONS.items():
            self._sections_enabled[section_id] = True if section.required else False
        self._sections_order = get_default_order()
        self._refresh_sections_list()

    def _on_preset_full(self, e: ft.ControlEvent) -> None:
        """Enable all sections."""
        for section_id in CARD_SECTIONS.keys():
            self._sections_enabled[section_id] = True
        self._sections_order = get_default_order()
        self._refresh_sections_list()
    
    def _build_detail_content(self, row_index: int) -> ft.Container:
        """Build the detail panel content for a selected row."""
        row = self.df.iloc[row_index]
        
        # Clear existing fields
        self._fields.clear()
        self._audio_loading.clear()
        
        # Get sentences from ContextSentences (unified parsing: <br> and \n)
        context = str(row.get("ContextSentences", ""))
        sentences = [s.strip() for s in re.split(r'<br\s*/?>|\n', context) if s.strip()]
        while len(sentences) < 3:
            sentences.append("")
        
        # Image preview container
        self._image_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.IMAGE_ROUNDED, size=48, color=ft.Colors.WHITE24),
                    ft.Text("Click 'Generate Image' to preview", size=12, color=ft.Colors.WHITE38),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            height=180,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
            alignment=ft.Alignment(0, 0),
        )
        
        # Audio status
        self._audio_status = ft.Text(
            "Use 🔊 buttons to generate audio",
            size=11,
            color=ft.Colors.WHITE38,
        )
        
        # Audio section
        audio_section = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.AUDIOTRACK, color=ft.Colors.TEAL_200, size=24),
                    ft.Column(
                        controls=[
                            ft.Text("Audio Preview", size=14, color=ft.Colors.WHITE70),
                            self._audio_status,
                        ],
                        spacing=2,
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
                spacing=10,
            ),
            padding=12,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
        )
        
        # ===== SECTION 1: CORE INFO (Always visible) =====
        core_section = ft.Column(
            controls=[
                self._create_field_with_audio(
                    "Target Word", "TargetWord",
                    str(row.get("TargetWord", "")),
                ),
                self._create_simple_field(row, "Meaning", "Meaning", multiline=True, min_lines=2, max_lines=4),
                self._create_simple_field(row, "Context Translation", "ContextTranslation", multiline=True, min_lines=2, max_lines=3),
                
                # Image Prompt with generate button
                self._create_field_with_image_gen(
                    "Image Prompt", "ImagePrompt",
                    str(row.get("ImagePrompt", "")),
                ),
            ],
            spacing=0,
        )
        
        # ===== SECTION 2: GRAMMAR & LINGUISTICS (Expandable) =====
        grammar_fields = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        self._create_compact_field(row, "IPA", "IPA"),
                        self._create_compact_field(row, "Part of Speech", "Part_of_Speech"),
                    ],
                    spacing=10,
                ),
                ft.Row(
                    controls=[
                        self._create_compact_field(row, "Gender", "Gender"),
                        self._create_compact_field(row, "Morphology", "Morphology"),
                    ],
                    spacing=10,
                ),
                self._create_simple_field(row, "Nuance", "Nuance", multiline=True, min_lines=2, max_lines=4),
            ],
            spacing=5,
        )
        
        grammar_section = ft.Container(
            content=ft.ExpansionTile(
                title=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.BOOK, size=18, color=ft.Colors.BLUE_200),
                        ft.Text("Grammar & Linguistics", size=14, weight=ft.FontWeight.W_500),
                    ],
                    spacing=8,
                ),
                controls=[
                    ft.Container(content=grammar_fields, padding=ft.Padding(left=10, right=10, top=5, bottom=10))
                ],
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                collapsed_bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.WHITE),
            ),
            padding=ft.Padding.only(top=5, bottom=5),
        )
        
        # ===== SECTION 3: CONTEXT (Expandable) =====
        context_fields = ft.Column(
            controls=[
                self._create_field_with_audio(
                    "Sentence 1", "Sentence_1",
                    sentences[0],
                    multiline=True, min_lines=2, max_lines=3,
                ),
                self._create_field_with_audio(
                    "Sentence 2", "Sentence_2",
                    sentences[1],
                    multiline=True, min_lines=2, max_lines=3,
                ),
                self._create_field_with_audio(
                    "Sentence 3", "Sentence_3",
                    sentences[2],
                    multiline=True, min_lines=2, max_lines=3,
                ),
            ],
            spacing=5,
        )
        
        context_section = ft.Container(
            content=ft.ExpansionTile(
                title=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.CHAT_BUBBLE, size=18, color=ft.Colors.GREEN_200),
                        ft.Text("Context Sentences", size=14, weight=ft.FontWeight.W_500),
                    ],
                    spacing=8,
                ),
                controls=[
                    ft.Container(content=context_fields, padding=ft.Padding(left=10, right=10, top=5, bottom=10))
                ],
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                collapsed_bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.WHITE),
            ),
            padding=ft.Padding.only(top=5, bottom=5),
        )
        
        # ===== SECTION 4: METADATA (Expandable) =====
        metadata_fields = ft.Column(
            controls=[
                self._create_simple_field(row, "Etymology", "Etymology", multiline=True, min_lines=2, max_lines=4),
                self._create_simple_field(row, "Mnemonic", "Mnemonic", multiline=True, min_lines=2, max_lines=4),
                self._create_simple_field(row, "Analogues", "Analogues", multiline=True, min_lines=2, max_lines=3),
                self._create_compact_field(row, "Tags", "Tags"),
            ],
            spacing=5,
        )
        
        metadata_section = ft.Container(
            content=ft.ExpansionTile(
                title=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.INFO, size=18, color=ft.Colors.PURPLE_200),
                        ft.Text("Metadata", size=14, weight=ft.FontWeight.W_500),
                    ],
                    spacing=8,
                ),
                controls=[
                    ft.Container(content=metadata_fields, padding=ft.Padding(left=10, right=10, top=5, bottom=10))
                ],
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                collapsed_bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.WHITE),
            ),
            padding=ft.Padding.only(top=5, bottom=5),
        )
        
        # Detail content
        detail_content = ft.Column(
            controls=[
                # Header
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text(
                                "Edit Word",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                            ft.Container(expand=True),
                            ft.Text(
                                f"#{row_index + 1}",
                                size=12,
                                color=ft.Colors.WHITE38,
                            ),
                        ],
                    ),
                    padding=ft.Padding.only(bottom=15),
                ),
                
                # Core section (always visible)
                core_section,
                
                ft.Container(height=5),
                
                # Expandable sections
                grammar_section,
                context_section,
                metadata_section,
                
                ft.Container(height=10),
                
                # Media previews section
                ft.Text("Media Preview", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE70),
                ft.Container(height=5),
                self._image_container,
                ft.Container(height=10),
                audio_section,
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        
        return ft.Container(
            content=detail_content,
            expand=True,
            padding=15,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.WHITE),
        )
    
    def _create_simple_field(
        self,
        row: pd.Series,
        label: str,
        key: str,
        multiline: bool = False,
        min_lines: int = 1,
        max_lines: int = 1,
    ) -> ft.Container:
        """Create a simple text field without buttons."""
        value = str(row.get(key, ""))
        
        field = ft.TextField(
            value=value,
            label=label,
            multiline=multiline,
            min_lines=min_lines,
            max_lines=max_lines,
            border_color=ft.Colors.WHITE24,
            focused_border_color=ft.Colors.INDIGO_200,
            label_style=ft.TextStyle(color=ft.Colors.WHITE54),
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
            cursor_color=ft.Colors.INDIGO_200,
            expand=True,
            on_change=lambda e, k=key: self._on_field_change(k, e.control.value),
        )
        self._fields[key] = field
        
        return ft.Container(
            content=ft.Row(
                controls=[field],
                expand=True,
            ),
            padding=ft.Padding.only(bottom=10),
        )
    
    def _create_compact_field(
        self,
        row: pd.Series,
        label: str,
        key: str,
    ) -> ft.Container:
        """Create a compact text field for 2-column layouts."""
        value = str(row.get(key, ""))
        
        field = ft.TextField(
            value=value,
            label=label,
            border_color=ft.Colors.WHITE24,
            focused_border_color=ft.Colors.INDIGO_200,
            label_style=ft.TextStyle(color=ft.Colors.WHITE54, size=12),
            text_style=ft.TextStyle(color=ft.Colors.WHITE, size=13),
            cursor_color=ft.Colors.INDIGO_200,
            dense=True,
            on_change=lambda e, k=key: self._on_field_change(k, e.control.value),
        )
        self._fields[key] = field
        
        return ft.Container(
            content=field,
            expand=True,
        )
    
    def _create_field_with_audio(
        self,
        label: str,
        key: str,
        value: str,
        multiline: bool = False,
        min_lines: int = 1,
        max_lines: int = 1,
    ) -> ft.Container:
        """Create a text field with an audio generation button."""
        field = ft.TextField(
            value=value,
            label=label,
            multiline=multiline,
            min_lines=min_lines,
            max_lines=max_lines,
            border_color=ft.Colors.WHITE24,
            focused_border_color=ft.Colors.INDIGO_200,
            label_style=ft.TextStyle(color=ft.Colors.WHITE54),
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
            cursor_color=ft.Colors.INDIGO_200,
            expand=True,
            on_change=lambda e, k=key: self._on_field_change(k, e.control.value),
        )
        self._fields[key] = field
        
        # Loading indicator
        loading = ft.ProgressRing(width=16, height=16, stroke_width=2, visible=False)
        self._audio_loading[key] = loading
        
        # Audio button
        audio_btn = ft.IconButton(
            icon=ft.Icons.VOLUME_UP_ROUNDED,
            icon_color=ft.Colors.TEAL_200,
            icon_size=20,
            tooltip=f"Generate & Play Audio",
            on_click=lambda e, k=key, f=field: self._on_generate_audio(k, f.value),
        )
        
        return ft.Container(
            content=ft.Row(
                controls=[
                    field,
                    loading,
                    audio_btn,
                ],
                spacing=5,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            ),
            padding=ft.Padding.only(bottom=10),
        )
    
    def _create_field_with_image_gen(
        self,
        label: str,
        key: str,
        value: str,
    ) -> ft.Container:
        """Create the ImagePrompt field with generate button."""
        field = ft.TextField(
            value=value,
            label=label,
            multiline=True,
            min_lines=2,
            max_lines=4,
            border_color=ft.Colors.WHITE24,
            focused_border_color=ft.Colors.INDIGO_200,
            label_style=ft.TextStyle(color=ft.Colors.WHITE54),
            text_style=ft.TextStyle(color=ft.Colors.WHITE),
            cursor_color=ft.Colors.INDIGO_200,
            expand=True,
            on_change=lambda e, k=key: self._on_field_change(k, e.control.value),
        )
        self._fields[key] = field
        
        # Store field reference for button callback to get current value
        self._image_prompt_field = field
        
        # Image button (similar to audio button)
        self._image_gen_button = ft.IconButton(
            icon=ft.Icons.AUTO_AWESOME,
            icon_color=ft.Colors.PURPLE_200,
            icon_size=20,
            tooltip="Generate Image",
            on_click=lambda e: self._on_generate_image(self._image_prompt_field.value if self._image_prompt_field else ""),
        )
        
        return ft.Container(
            content=ft.Row(
                controls=[
                    field,
                    self._image_gen_button,
                ],
                spacing=5,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            ),
            padding=ft.Padding.only(bottom=10),
        )
    
    def _on_row_selected(self, row_index: int, event: ft.ControlEvent) -> None:
        """Handle row selection in the data table."""
        selected = bool(event.data) and str(event.data).lower() != "false"
        self._set_selected_row(row_index, selected)

    def _on_row_tap(self, row_index: int) -> None:
        """Handle row tap to select and preview without checkbox."""
        self._set_selected_row(row_index, True)

    def _get_local_row_index(self, global_index: int) -> Optional[int]:
        """Map a global DataFrame index to the current page row index."""
        try:
            return self._page_row_indices.index(global_index)
        except ValueError:
            return None

    def _set_selected_row(self, row_index: int, selected: bool) -> None:
        """Set selected row state and refresh detail/preview."""
        if not selected:
            self.selected_row_index = None
            self._detail_container.content = self._build_detail_panel()
            if self._data_table:
                for row in self._data_table.rows:
                    row.selected = False
            if self._card_preview:
                self._card_preview.set_preview_image(None)
                self._card_preview.set_preview_audio(None)
                self._card_preview.update_preview({})
            if self._status_text:
                self._status_text.value = self._get_status_text()
            self.page.update()
            return

        self._last_selected_row_index = self.selected_row_index
        self.selected_row_index = row_index
        self._detail_container.content = self._build_detail_content(row_index)

        if self._data_table:
            # Update only previously selected row (if visible)
            if self._last_selected_row_index is not None:
                prev_local = self._get_local_row_index(self._last_selected_row_index)
                if prev_local is not None and prev_local < len(self._data_table.rows):
                    self._data_table.rows[prev_local].selected = False

            # Select new row if visible in current page
            new_local = self._get_local_row_index(row_index)
            if new_local is not None and new_local < len(self._data_table.rows):
                self._data_table.rows[new_local].selected = True

        word = self.df.iloc[row_index].get("TargetWord", "") if self.df is not None else ""
        if self._status_text:
            self._status_text.value = f"Editing: {word}"

        if self._card_preview and self.df is not None:
            self._card_preview.set_preview_image(None)
            self._card_preview.set_preview_audio(None)
            row_data = self.df.iloc[row_index].to_dict()
            self._card_preview.update_preview(row_data)

        self.page.update()
    
    def _on_field_change(self, key: str, value: str) -> None:
        """Handle field value change - update DataFrame in memory."""
        if self.selected_row_index is not None and self.df is not None:
            self._has_unsaved_changes = True
            
            # Handle special case for Sentence fields (they might be in ContextSentences)
            if key.startswith("Sentence_"):
                # Sentences are stored in ContextSentences, we update individual sentence
                self._update_sentence_field(key, value)
            elif key in self.df.columns:
                self.df.at[self.selected_row_index, key] = value
            
            # Update card preview for real-time feedback
            self._schedule_preview_update()

    def _schedule_preview_update(self) -> None:
        """Debounce preview updates to avoid UI lag on rapid changes."""
        if self._performance_mode or not self._live_preview_enabled:
            return
        self._preview_update_version += 1
        version = self._preview_update_version

        async def _debounced() -> None:
            await asyncio.sleep(self._preview_debounce_ms / 1000)
            if version != self._preview_update_version:
                return
            self._update_card_preview()

        asyncio.create_task(_debounced())

    def _schedule_style_save(self) -> None:
        """Debounce style persistence to avoid frequent disk writes."""
        self._style_update_version += 1
        version = self._style_update_version

        async def _debounced() -> None:
            await asyncio.sleep(self._style_debounce_ms / 1000)
            if version != self._style_update_version:
                return
            current = self._settings.get("CARD_STYLE", CardTemplates.DEFAULT_STYLE)
            self._settings.set("CARD_STYLE", current, persist=True)
            if self._style_status:
                self._style_status.value = "Saved"
                self._style_status.color = ft.Colors.WHITE38
            if self.page:
                self.page.update()

        asyncio.create_task(_debounced())
    
    def _update_card_preview(self, force: bool = False) -> None:
        """Update the card preview with current row data."""
        if not force and (self._performance_mode or not self._live_preview_enabled):
            return
        if self._card_preview and self.selected_row_index is not None and self.df is not None:
            row_data = self.df.iloc[self.selected_row_index].to_dict()
            self._card_preview.update_preview(row_data)
            self.page.update()

    def _refresh_preview_now(self) -> None:
        """Manual refresh for preview when live updates are off."""
        self._update_card_preview(force=True)
        self.page.update()

    def _get_default_live_preview(self) -> bool:
        """Determine default live preview state based on dataset size and perf mode."""
        if self._performance_mode:
            return False
        if self.df is None:
            return True
        return len(self.df) <= self._live_preview_threshold

    def _adjust_page_size_for_perf(self) -> None:
        """Adjust page size based on dataset size and performance mode."""
        if self._performance_mode:
            self._page_size = min(self._page_size, 50)
            return
        if self.df is None:
            return
        if len(self.df) > 5000:
            self._page_size = min(self._page_size, 50)
        elif len(self.df) > 2000:
            self._page_size = min(self._page_size, 100)

    def _on_live_preview_toggle(self, e: ft.ControlEvent) -> None:
        """Handle live preview toggle."""
        self._live_preview_enabled = bool(e.control.value)
        if self._live_preview_enabled:
            self._update_card_preview(force=True)
        self.page.update()
    
    def _update_sentence_field(self, key: str, value: str) -> None:
        """Update a sentence field in the ContextSentences column."""
        if self.selected_row_index is None or self.df is None:
            return
        
        # Get current context sentences (unified parsing: <br> and \n)
        context = str(self.df.at[self.selected_row_index, "ContextSentences"])
        sentences = [s.strip() for s in re.split(r'<br\s*/?>|\n', context) if s.strip()]
        
        # Ensure we have at least 3 sentence slots
        while len(sentences) < 3:
            sentences.append("")
        
        # Determine which sentence to update
        if key == "Sentence_1":
            sentences[0] = value
        elif key == "Sentence_2":
            sentences[1] = value
        elif key == "Sentence_3":
            sentences[2] = value
        
        # Rejoin and update
        self.df.at[self.selected_row_index, "ContextSentences"] = "<br>".join(sentences)
    
    def _on_generate_audio(self, key: str, text: str) -> None:
        """Handle audio generation button click."""
        print(f"[DEBUG] _on_generate_audio called for key='{key}', text='{text[:30] if text else 'None'}...'")
        if not text or not text.strip():
            self._show_snackbar("No text to generate audio for", error=True)
            return
        
        # Run async generation
        self.page.run_task(self._generate_audio_async, key, text)
    
    async def _generate_audio_async(self, key: str, text: str) -> None:
        """Generate audio asynchronously."""
        # Show loading
        if key in self._audio_loading:
            self._audio_loading[key].visible = True
        if self._audio_status:
            self._audio_status.value = f"Generating audio for {key}..."
            self._audio_status.color = ft.Colors.AMBER_400
        self.page.update()
        
        try:
            # Create temp file
            temp_dir = tempfile.gettempdir()
            audio_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            temp_path = os.path.join(temp_dir, f"ankitect_audio_{audio_hash}.mp3")
            
            # Generate audio
            success = await self._audio_fetcher.fetch(text, temp_path, volume="+30%")
            
            if success and os.path.exists(temp_path):
                self._current_audio_path = temp_path
                
                if self._audio_status:
                    self._audio_status.value = f"✓ Audio generated! Playing..."
                    self._audio_status.color = ft.Colors.GREEN_400
                    self.page.update()  # Immediate update
                
                # Play audio using cross-platform approach
                self._play_audio_file(temp_path)
                
                self._show_snackbar(f"Audio generated successfully!")
            else:
                if self._audio_status:
                    self._audio_status.value = "✗ Failed to generate audio"
                    self._audio_status.color = ft.Colors.RED_400
                self._show_snackbar("Failed to generate audio", error=True)
        
        except Exception as e:
            if self._audio_status:
                self._audio_status.value = f"✗ Error: {str(e)[:30]}"
                self._audio_status.color = ft.Colors.RED_400
            self._show_snackbar(f"Error: {str(e)}", error=True)
        
        finally:
            # Hide loading
            if key in self._audio_loading:
                self._audio_loading[key].visible = False
            self.page.update()
    
    def _on_generate_image(self, prompt: str) -> None:
        """Handle image generation button click."""
        print(f"[DEBUG] _on_generate_image called with prompt: '{prompt[:50] if prompt else 'None'}...'")
        
        if self._is_generating_image:
            print("[DEBUG] Already generating, skipping")
            return  # Prevent double-click
        
        if not prompt or not prompt.strip():
            self._show_snackbar("No prompt to generate image from", error=True)
            return
        
        print(f"[DEBUG] Starting async image generation")
        # Run async generation
        self.page.run_task(self._generate_image_async, prompt)
    
    async def _generate_image_async(self, prompt: str) -> None:
        """Generate image asynchronously."""
        print(f"[DEBUG] _generate_image_async started")
        # Prevent double-click and show loading state
        self._is_generating_image = True
        
        # Disable button - it's now an IconButton
        if self._image_gen_button:
            self._image_gen_button.disabled = True
        
        # Update image container to show loading
        if self._image_container:
            self._image_container.content = ft.Column(
                controls=[
                    ft.ProgressRing(width=40, height=40, stroke_width=3),
                    ft.Text("Generating image...", size=12, color=ft.Colors.INDIGO_200),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            )
        self.page.update()
        
        try:
            # Create temp file
            temp_dir = tempfile.gettempdir()
            img_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
            temp_path = os.path.join(temp_dir, f"ankitect_img_{img_hash}.jpg")
            print(f"[DEBUG] Generating image to: {temp_path}")
            
            # Generate image
            success = await self._image_fetcher.fetch(prompt, temp_path)
            print(f"[DEBUG] Image generation result: {success}, file exists: {os.path.exists(temp_path)}")
            
            if success and os.path.exists(temp_path):
                print(f"[DEBUG] Image generated successfully, updating container")
                # Update image container with the generated image
                # Use absolute path for Flet
                abs_image_path = os.path.abspath(temp_path)
                print(f"[DEBUG] Setting image src to: {abs_image_path}")
                if self._image_container:
                    self._image_container.content = ft.Image(
                        src=abs_image_path,
                        fit=ft.BoxFit.CONTAIN,
                        border_radius=10,
                        width=300,
                        height=170,
                    )
                    self.page.update()  # Immediate update to show image
                
                # Update card preview with the image
                if self._card_preview:
                    self._card_preview.set_preview_image(abs_image_path)
                
                self._show_snackbar("Image generated successfully!")
            else:
                print(f"[DEBUG] Image generation failed")
                if self._image_container:
                    self._image_container.content = ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.ERROR_OUTLINE, size=48, color=ft.Colors.RED_400),
                            ft.Text("Failed to generate image", size=12, color=ft.Colors.RED_400),
                            ft.Text("Check API key in settings", size=10, color=ft.Colors.WHITE38),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                    )
                self._show_snackbar("Failed to generate image - check API key", error=True)
        
        except Exception as e:
            if self._image_container:
                self._image_container.content = ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.ERROR_OUTLINE, size=48, color=ft.Colors.RED_400),
                        ft.Text(f"Error: {str(e)[:40]}", size=11, color=ft.Colors.RED_400),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                )
            self._show_snackbar(f"Error: {str(e)}", error=True)
        
        finally:
            # Re-enable button
            self._is_generating_image = False
            
            if self._image_gen_button:
                self._image_gen_button.disabled = False
            
            self.page.update()
    
    def _on_save_click(self) -> None:
        """Handle save button click - runs async save."""
        self.page.run_task(self._save_data_with_feedback)
    
    async def _save_data_with_feedback(self) -> None:
        """Save data with UI feedback (async)."""
        success = await self.save_data_async()
        
        if success:
            self._has_unsaved_changes = False
            self._show_snackbar("Project saved successfully!", icon=ft.Icons.CHECK_CIRCLE)
        else:
            self._show_snackbar("Failed to save project", error=True)
    
    def _show_snackbar(self, message: str, error: bool = False, icon: str = None) -> None:
        """Show a snackbar notification."""
        snackbar = ft.SnackBar(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        icon or (ft.Icons.ERROR if error else ft.Icons.INFO),
                        color=ft.Colors.WHITE,
                        size=18,
                    ),
                    ft.Text(message, color=ft.Colors.WHITE),
                ],
                spacing=10,
            ),
            bgcolor=ft.Colors.RED_700 if error else ft.Colors.GREEN_700,
            duration=3000,
        )
        # Clean up old snackbars to prevent memory leak
        for ctrl in list(self.page.overlay):
            if isinstance(ctrl, ft.SnackBar):
                self.page.overlay.remove(ctrl)
        self.page.overlay.append(snackbar)
        snackbar.open = True
        self.page.update()
    
    def _reload_data(self) -> None:
        """Reload data from CSV."""
        self._performance_mode = self._settings.get("PERFORMANCE_MODE", False)
        self._load_data()
        self.selected_row_index = None
        self._last_selected_row_index = None
        self._has_unsaved_changes = False

        if self._live_preview_switch:
            self._live_preview_switch.value = self._live_preview_enabled
        if self._page_size_dropdown:
            self._page_size_dropdown.value = str(self._page_size)
        
        # Rebuild the entire view
        new_container = self._build_view()
        self._container.content = new_container.content
        self.page.update()

    def _apply_layout_order(self) -> None:
        """Apply panel order based on swap toggle."""
        if not self._main_row or not self._master_container or not self._builder_container:
            return
        # Adjust expands based on visibility and weights
        if self._show_master:
            self._master_container.expand = self._panel_weights.get("master", 2)
        if self._show_detail:
            self._detail_container.expand = self._panel_weights.get("detail", 5)
        if self._show_builder:
            self._builder_container.expand = self._panel_weights.get("builder", 7)
        if self._swap_master_preview:
            controls = []
            if self._show_builder:
                controls.append(self._builder_container)
            if self._show_detail:
                controls.append(self._detail_container)
            if self._show_master:
                controls.append(self._master_container)
            self._main_row.controls = controls
        else:
            controls = []
            if self._show_master:
                controls.append(self._master_container)
            if self._show_detail:
                controls.append(self._detail_container)
            if self._show_builder:
                controls.append(self._builder_container)
            self._main_row.controls = controls

        self._update_panel_controls_state()

    def _toggle_swap_panels(self, e: ft.ControlEvent) -> None:
        """Swap Vocabulary and Preview panels."""
        self._swap_master_preview = not self._swap_master_preview
        self._apply_layout_order()
        self.page.update()

    def _toggle_panel_visibility(self, panel_key: str) -> None:
        """Show or hide a panel by key."""
        visible_map = {
            "master": self._show_master,
            "detail": self._show_detail,
            "builder": self._show_builder,
        }
        if visible_map.get(panel_key, True):
            # Prevent hiding the last visible panel
            visible_count = sum(1 for v in visible_map.values() if v)
            if visible_count <= 1:
                return
        if panel_key == "master":
            self._show_master = not self._show_master
        elif panel_key == "detail":
            self._show_detail = not self._show_detail
        elif panel_key == "builder":
            self._show_builder = not self._show_builder
        self._apply_layout_order()
        self.page.update()

    def _on_panel_weight_change(self, panel_key: str, value: float) -> None:
        """Handle width slider change for a panel."""
        self._panel_weights[panel_key] = int(value)
        self._apply_layout_order()
        self.page.update()

    def _update_panel_controls_state(self) -> None:
        """Update toggle button and slider states based on visibility."""
        states = {
            "master": self._show_master,
            "detail": self._show_detail,
            "builder": self._show_builder,
        }
        for key, btn in self._panel_buttons.items():
            is_on = states.get(key, True)
            btn.style = ft.ButtonStyle(
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                shape=ft.RoundedRectangleBorder(radius=8),
                bgcolor={
                    ft.ControlState.DEFAULT: ft.Colors.with_opacity(0.12, ft.Colors.INDIGO_400)
                    if is_on
                    else ft.Colors.with_opacity(0.02, ft.Colors.WHITE)
                },
            )
        for key, slider in self._panel_sliders.items():
            slider.disabled = not states.get(key, True)

    def _toggle_layout_controls(self, e: ft.ControlEvent) -> None:
        """Show or hide layout controls panel."""
        self._show_layout_controls = not self._show_layout_controls
        if self._container:
            self._container.content = self._build_view().content
        self.page.update()

    
    def save_data(self) -> bool:
        """
        Save the current DataFrame back to CSV (sync wrapper for compatibility).
        
        Returns:
            True if save was successful, False otherwise
        """
        if self.df is None or self.df.empty:
            return False
        
        try:
            csv_path = Path(Config.CSV_FILE)
            self.df.to_csv(csv_path, sep='|', index=False, encoding='utf-8-sig')
            return True
        except Exception as e:
            print(f"Error saving CSV: {e}")
            return False
    
    async def save_data_async(self) -> bool:
        """
        Save the current DataFrame back to CSV (non-blocking async version).
        
        Runs the actual save in an executor to avoid blocking the UI.
        
        Returns:
            True if save was successful, False otherwise
        """
        if self.df is None or self.df.empty:
            return False
        
        try:
            loop = asyncio.get_event_loop()
            # Run sync I/O in executor to not block event loop
            await loop.run_in_executor(None, self._save_data_sync)
            return True
        except Exception as e:
            print(f"Error saving CSV: {e}")
            return False
    
    def _save_data_sync(self) -> None:
        """Internal sync save method for executor."""
        csv_path = Path(Config.CSV_FILE)
        self.df.to_csv(csv_path, sep='|', index=False, encoding='utf-8-sig')
    
    def get_selected_word(self) -> Optional[Dict[str, Any]]:
        """Get the currently selected word data."""
        if self.selected_row_index is None or self.df is None:
            return None
        return self.df.iloc[self.selected_row_index].to_dict()


def create_workbench_view(page: ft.Page) -> ft.Container:
    """
    Factory function to create the workbench view.
    
    Args:
        page: Flet page instance
        
    Returns:
        Container with the workbench view
    """
    workbench = WorkbenchView(page)
    return workbench.container
