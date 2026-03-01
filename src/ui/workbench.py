"""
Workbench View - Master-Detail Editor for Vocabulary Data
----------------------------------------------------------

Provides a DataTable for browsing vocabulary and a detail panel for editing.
Includes AI tools for regenerating images and audio.
Features live card preview for instant visual feedback.
"""

import asyncio
import math
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import flet as ft
import pandas as pd

from src.config import (
    Config,
    SettingsManager,
)
from src.fetchers import AudioFetcher, ImageFetcher
from src.utils.logger import get_logger
from src.services import VocabularyService
from src.ui.card_preview import CardPreviewView, create_card_preview
from src.ui.detail_editor import DetailEditorView
from src.ui.style_editor import StyleEditorView
from src.ui.theme import DesignTokens, show_snackbar
from src.ui.card_sections_editor import CardSectionsEditor
from src.ui.card_types_editor import CardTypesEditor


class WorkbenchView:
    """
    Master-Detail view for editing vocabulary data.
    
    Displays vocabulary in a DataTable (master) and provides
    editable fields in a detail panel when a row is selected.
    Includes AI tools for image and audio generation.
    Features live Anki card preview.
    """
    
    _logger = get_logger("workbench")
    
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
        
        # Search state
        self._search_query: str = ""
        self._search_field: Optional[ft.TextField] = None
        self._filtered_indices: Optional[List[int]] = None  # None = no filter active
        
        # Card preview component
        self._card_preview: Optional[CardPreviewView] = None
        
        # Detail editor (extracted component)
        self._detail_editor = DetailEditorView(
            page=self.page,
            audio_fetcher=self._audio_fetcher,
            image_fetcher=self._image_fetcher,
            on_field_change=self._on_field_change,
            show_snackbar=self._show_snackbar,
            set_preview_image=lambda path: (
                self._card_preview.set_preview_image(path) if self._card_preview else None
            ),
        )
        self._detail_editor.set_rebuild_callback(self._rebuild_detail_panel)

        # Settings
        self._settings = SettingsManager()
        self._performance_mode: bool = self._settings.get("PERFORMANCE_MODE", False)

        # Sections editor (extracted component)
        self._sections_editor = CardSectionsEditor(
            page=self.page,
            settings=self._settings,
            on_save=lambda: self._update_card_preview(),
        )

        self._card_types_editor: Optional[CardTypesEditor] = None

        # Style editor (extracted component)
        self._style_editor = StyleEditorView(
            page=self.page,
            settings=self._settings,
            schedule_preview_update=self._schedule_preview_update,
            update_card_preview=lambda: self._update_card_preview(),
        )

        # Preview debounce
        self._preview_update_version: int = 0
        self._preview_debounce_ms: int = 500  # increased for performance

        # Builder drawer state
        self._show_builder: bool = False
        self._builder_drawer: Optional[ft.Container] = None
        self._builder_tab_body: Optional[ft.Container] = None
        self._builder_tab_buttons: Dict[str, ft.TextButton] = {}
        self._active_builder_tab: str = "Sections"
        self._builder_toggle_btn: Optional[ft.IconButton] = None

        # Main layout references
        self._main_row: Optional[ft.Row] = None
        self._master_container: Optional[ft.Container] = None

        # Responsive layout state
        self._is_narrow: bool = False
        self._breakpoint_width: int = 900  # below this, stack vertically
        self._detail_inner_row: Optional[ft.Row] = None
        self._detail_inner_col: Optional[ft.Column] = None

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
        """Load vocabulary data via VocabularyService."""
        try:
            success = self._vocab_service.load()
            if success:
                # Use direct reference (not copy) for fast in-place editing
                self.df = self._vocab_service.get_dataframe_ref()
            else:
                self.df = pd.DataFrame()
        except Exception as e:
            self._logger.error(f"Error loading vocabulary: {e}")
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
    
    def _build_view(self) -> ft.Container:
        """Build the main workbench layout: 2-column + builder drawer."""
        if self.df is None or self.df.empty:
            return self._build_empty_state()
        
        # Build master table
        master_panel = self._build_master_panel()

        # Build detail panel (initially empty)
        self._detail_panel = self._detail_editor.build_placeholder()

        # Build card preview panel
        if not self._card_preview:
            self._card_preview = create_card_preview(self.page)

        # Preview container (lives next to detail editor)
        self._preview_container = ft.Container(
            content=self._card_preview.build(),
            expand=True,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.02, DesignTokens.TEXT_PRIMARY),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        self._live_preview_switch = ft.Switch(
            value=self._live_preview_enabled,
            label="Live",
            on_change=self._on_live_preview_toggle,
        )
        self._preview_refresh_btn = ft.TextButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.REFRESH, size=14, color=DesignTokens.TEXT_SECONDARY),
                    ft.Text("Refresh", size=11, color=DesignTokens.TEXT_SECONDARY),
                ],
                spacing=4,
            ),
            on_click=lambda _: self._refresh_preview_now(),
        )

        self._preview_panel = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.PREVIEW, size=14, color=DesignTokens.TEXT_SECONDARY),
                            ft.Text("Preview", size=12, weight=ft.FontWeight.W_600,
                                    color=DesignTokens.TEXT_SECONDARY),
                            ft.Container(expand=True),
                            self._live_preview_switch,
                            self._preview_refresh_btn,
                        ],
                        spacing=6,
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=4),
                    self._preview_container,
                ],
                expand=True,
                spacing=0,
            ),
            expand=True,
            padding=10,
        )

        # Build the builder drawer (hidden by default)
        self._builder_drawer = self._build_builder_drawer()

        # Detail + Preview side by side (or stacked on narrow screens)
        self._detail_editor_container = ft.Container(
            content=self._detail_panel, expand=True,
        )
        self._detail_with_preview = self._build_detail_with_preview()

        # Main layout containers
        self._master_container = ft.Container(
            content=master_panel, expand=3, padding=10,
        )
        self._detail_container = ft.Container(
            content=self._detail_with_preview, expand=7, padding=ft.Padding.only(left=10, top=10, bottom=10),
        )

        self._main_row = ft.Row(
            controls=[
                self._master_container,
                self._detail_container,
                self._builder_drawer,
            ],
            spacing=0,
            expand=True,
        )

        top_bar = self._build_layout_toolbar()

        # Wire up responsive resize
        self._check_responsive_layout()
        self.page.on_resized = self._on_page_resized

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
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

    def _build_detail_with_preview(self) -> ft.Control:
        """Build the detail editor + preview layout. Uses Row on wide, Column on narrow."""
        if self._is_narrow:
            return ft.Column(
                controls=[
                    ft.Container(content=self._detail_editor_container, expand=True),
                    ft.Container(content=self._preview_panel, height=350),
                ],
                spacing=6,
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            )
        else:
            return ft.Row(
                controls=[
                    ft.Container(content=self._detail_editor_container, expand=5),
                    ft.Container(content=self._preview_panel, expand=4),
                ],
                spacing=6,
                expand=True,
            )

    def _check_responsive_layout(self) -> None:
        """Check current window width and update layout mode."""
        try:
            width = self.page.width or 1280
        except Exception:
            width = 1280
        new_narrow = width < self._breakpoint_width
        if new_narrow != self._is_narrow:
            self._is_narrow = new_narrow
            self._apply_responsive_layout()

    def _on_page_resized(self, e: ft.ControlEvent) -> None:
        """Handle window resize for responsive layout."""
        self._check_responsive_layout()

    def _apply_responsive_layout(self) -> None:
        """Apply responsive layout changes."""
        if not self._detail_container:
            return
        new_layout = self._build_detail_with_preview()
        self._detail_container.content = new_layout
        # On narrow screens, stack main panels vertically too
        if self._is_narrow and self._main_row:
            self._master_container.expand = True
            self._detail_container.expand = True
            self._main_row.wrap = True
        elif self._main_row:
            self._master_container.expand = 3
            self._detail_container.expand = 7
            self._main_row.wrap = False
        try:
            self.page.update()
        except Exception:
            pass
    
    
    def _build_empty_state(self) -> ft.Container:
        """Build empty state when no data is available."""
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, size=64, color=DesignTokens.TEXT_MUTED),
                    ft.Text(
                        "No Vocabulary Data",
                        size=24,
                        weight=ft.FontWeight.BOLD,
                        color=DesignTokens.TEXT_SECONDARY,
                    ),
                    ft.Text(
                        f"Place your vocabulary.csv file in the project root",
                        size=14,
                        color=DesignTokens.TEXT_TERTIARY,
                    ),
                    ft.Container(height=20),
                    ft.ElevatedButton(
                        "Reload Data",
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
            color=DesignTokens.TEXT_SECONDARY,
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
                    ft.ControlState.DEFAULT: DesignTokens.TEXT_PRIMARY,
                    ft.ControlState.DISABLED: DesignTokens.TEXT_TERTIARY,
                },
                bgcolor={
                    ft.ControlState.DEFAULT: DesignTokens.ACCENT_SUCCESS,
                    ft.ControlState.HOVERED: DesignTokens.ACCENT_SUCCESS,
                    ft.ControlState.DISABLED: ft.Colors.with_opacity(0.3, DesignTokens.ACCENT_SUCCESS),
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
                        color=DesignTokens.TEXT_PRIMARY,
                    ),
                    ft.Container(expand=True),
                    self._status_text,
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_color=DesignTokens.TEXT_SECONDARY,
                        tooltip="Reload data",
                        on_click=lambda _: self._reload_data(),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                spacing=10,
            ),
            padding=ft.Padding.only(bottom=10),
        )

        # Search field
        self._search_field = ft.TextField(
            hint_text="Search words... (press Enter)",
            prefix_icon=ft.Icons.SEARCH,
            border_color=DesignTokens.TEXT_MUTED,
            focused_border_color=DesignTokens.ACCENT_PRIMARY,
            hint_style=ft.TextStyle(color=DesignTokens.TEXT_TERTIARY, size=13),
            text_style=ft.TextStyle(color=DesignTokens.TEXT_PRIMARY, size=13),
            cursor_color=DesignTokens.ACCENT_PRIMARY,
            dense=True,
            on_submit=lambda e: self._on_search_submit(e.control.value),
            suffix=ft.IconButton(
                icon=ft.Icons.CLEAR,
                icon_size=16,
                icon_color=DesignTokens.TEXT_TERTIARY,
                tooltip="Clear search",
                on_click=lambda _: self._on_search_clear(),
            ),
        )
        search_bar = ft.Container(
            content=self._search_field,
            padding=ft.Padding.only(bottom=8),
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
            bgcolor=ft.Colors.with_opacity(0.03, DesignTokens.TEXT_PRIMARY),
            padding=10,
        )
        
        return ft.Container(
            content=ft.Column(
                controls=[header, search_bar, pagination_controls, table_container],
                spacing=0,
                expand=True,
            ),
            expand=True,
        )

    def _get_active_df(self) -> pd.DataFrame:
        """Get the DataFrame filtered by current search, or full df if no search."""
        if self.df is None or self.df.empty:
            return pd.DataFrame()
        if self._filtered_indices is not None:
            return self.df.iloc[self._filtered_indices]
        return self.df

    def _get_status_text(self) -> str:
        """Return a status text for the table state."""
        if self.df is None or self.df.empty:
            return ""
        total = len(self.df)
        active_df = self._get_active_df()
        active_count = len(active_df)
        start, end = self._get_visible_range()
        if self._filtered_indices is not None:
            return f"{active_count}/{total} matches (showing {start}-{end})"
        return f"{total} words loaded (showing {start}-{end})"

    def _get_page_count(self) -> int:
        """Get total page count based on current page size."""
        active = self._get_active_df()
        if active.empty:
            return 1
        return max(1, math.ceil(len(active) / self._page_size))

    def _get_visible_range(self) -> tuple:
        """Get the visible row range (1-based, inclusive)."""
        active = self._get_active_df()
        if active.empty:
            return (0, 0)
        start = self._current_page * self._page_size
        end = min(start + self._page_size, len(active))
        return (start + 1, end)

    def _get_visible_df(self) -> pd.DataFrame:
        """Return the current page slice of the active (possibly filtered) DataFrame."""
        active = self._get_active_df()
        if active.empty:
            return pd.DataFrame()
        start = self._current_page * self._page_size
        end = min(start + self._page_size, len(active))
        return active.iloc[start:end]

    def _build_pagination_controls(self) -> ft.Container:
        """Build pagination UI for the vocabulary table."""
        self._page_prev_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT,
            icon_color=DesignTokens.TEXT_SECONDARY,
            tooltip="Previous page",
            on_click=lambda _: self._on_page_prev(),
        )
        self._page_next_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT,
            icon_color=DesignTokens.TEXT_SECONDARY,
            tooltip="Next page",
            on_click=lambda _: self._on_page_next(),
        )
        self._page_label = ft.Text("", size=12, color=DesignTokens.TEXT_SECONDARY)

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
            border_color=DesignTokens.TEXT_MUTED,
            focused_border_color=DesignTokens.ACCENT_PRIMARY,
            label_style=ft.TextStyle(color=DesignTokens.TEXT_SECONDARY),
            text_style=ft.TextStyle(color=DesignTokens.TEXT_PRIMARY),
        )
        self._page_size_dropdown.on_select = self._on_page_size_change

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

    def _on_search_submit(self, query: str) -> None:
        """Handle search submission (Enter key)."""
        query = query.strip()
        if not query:
            self._on_search_clear()
            return
        
        self._search_query = query
        if self.df is not None and not self.df.empty:
            query_lower = query.lower()
            search_cols = ["TargetWord", "Meaning"]
            mask = pd.Series([False] * len(self.df), index=self.df.index)
            for col in search_cols:
                if col in self.df.columns:
                    mask |= self.df[col].astype(str).str.lower().str.contains(query_lower, na=False)
            self._filtered_indices = list(self.df.index[mask])
        else:
            self._filtered_indices = []
        
        self._current_page = 0
        self._refresh_table()
    
    def _on_search_clear(self) -> None:
        """Clear the search filter."""
        self._search_query = ""
        self._filtered_indices = None
        if self._search_field:
            self._search_field.value = ""
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
        # Targeted update: only refresh the table, not the whole page
        try:
            self._data_table.update()
        except Exception:
            self.page.update()
    
    def _build_data_table(self) -> ft.DataTable:
        """Build the DataTable with vocabulary data."""
        # Create columns
        columns = [
            ft.DataColumn(
                ft.Text(col, weight=ft.FontWeight.BOLD, color=DesignTokens.TEXT_SECONDARY),
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
                            color=DesignTokens.TEXT_PRIMARY,
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
            border=ft.border.all(1, DesignTokens.BORDER_DIM),
            border_radius=10,
            vertical_lines=ft.BorderSide(1, DesignTokens.BORDER_DIM),
            horizontal_lines=ft.BorderSide(1, DesignTokens.BORDER_DIM),
            heading_row_color=ft.Colors.with_opacity(0.05, DesignTokens.TEXT_PRIMARY),
            heading_row_height=50,
            data_row_min_height=45,
            data_row_max_height=60,
            show_checkbox_column=not self._performance_mode,
            column_spacing=20,
        )
    
    def _rebuild_detail_panel(self) -> None:
        """Rebuild the detail panel (called by DetailEditorView on expand toggle)."""
        if self.selected_row_index is not None and self.df is not None:
            self._detail_editor_container.content = self._detail_editor.build_content(
                self.df.iloc[self.selected_row_index], self.selected_row_index
            )
            self.page.update()

    def _build_builder_drawer(self) -> ft.Container:
        """Build the Builder drawer with tabbed content (Sections / Styles / Types)."""
        # Build tab contents
        sections_content = self._sections_editor.build()
        styles_content = self._style_editor.build()
        types_content = self._build_card_types_editor()

        self._builder_tabs = {
            "Sections": sections_content,
            "Styles": styles_content,
            "Types": types_content,
        }

        self._builder_tab_body = ft.Container(
            content=self._builder_tabs[self._active_builder_tab],
            expand=True,
            padding=ft.Padding.only(top=8),
        )

        # Build tab bar
        tab_icons = {
            "Sections": ft.Icons.VIEW_LIST,
            "Styles": ft.Icons.PALETTE,
            "Types": ft.Icons.CATEGORY,
        }
        tab_bar = ft.Row(controls=[], spacing=4, wrap=True)
        for name in self._builder_tabs:
            btn = ft.TextButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(tab_icons.get(name, ft.Icons.TAB), size=14),
                        ft.Text(name, size=12),
                    ],
                    spacing=4,
                ),
                on_click=lambda e, n=name: self._set_builder_tab(n),
            )
            self._builder_tab_buttons[name] = btn
            tab_bar.controls.append(btn)

        self._update_builder_tab_styles()

        drawer_header = ft.Row(
            controls=[
                ft.Icon(ft.Icons.BUILD, size=18, color=DesignTokens.ACCENT_PRIMARY),
                ft.Text(
                    "Deck Builder",
                    size=15,
                    weight=ft.FontWeight.BOLD,
                    color=DesignTokens.TEXT_PRIMARY,
                ),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_size=18,
                    icon_color=DesignTokens.TEXT_SECONDARY,
                    tooltip="Close builder",
                    on_click=lambda _: self._toggle_builder_drawer(),
                ),
            ],
            spacing=8,
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    drawer_header,
                    ft.Divider(height=1, color=DesignTokens.BORDER_DIM),
                    tab_bar,
                    self._builder_tab_body,
                ],
                spacing=6,
                expand=True,
            ),
            width=480,
            visible=self._show_builder,
            padding=12,
            border_radius=ft.BorderRadius.only(top_left=12, bottom_left=12),
            bgcolor=ft.Colors.with_opacity(0.04, DesignTokens.TEXT_PRIMARY),
            border=ft.border.only(left=ft.BorderSide(1, DesignTokens.BORDER_DIM)),
        )

    def _set_builder_tab(self, name: str) -> None:
        """Switch the active tab in the builder drawer."""
        self._active_builder_tab = name
        if self._builder_tab_body:
            self._builder_tab_body.content = self._builder_tabs.get(name)
        self._update_builder_tab_styles()
        self.page.update()

    def _update_builder_tab_styles(self) -> None:
        """Update visual state of builder tab buttons."""
        for tab_name, btn in self._builder_tab_buttons.items():
            is_active = tab_name == self._active_builder_tab
            btn.style = ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.DEFAULT: ft.Colors.with_opacity(
                        0.12 if is_active else 0.02, DesignTokens.TEXT_PRIMARY
                    ),
                },
                color={
                    ft.ControlState.DEFAULT: (
                        DesignTokens.TEXT_PRIMARY if is_active
                        else DesignTokens.TEXT_SECONDARY
                    ),
                },
                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                shape=ft.RoundedRectangleBorder(radius=8),
            )

    def _toggle_builder_drawer(self) -> None:
        """Show or hide the builder drawer."""
        self._show_builder = not self._show_builder
        if self._builder_drawer:
            self._builder_drawer.visible = self._show_builder
        if self._builder_toggle_btn:
            self._builder_toggle_btn.icon_color = (
                DesignTokens.ACCENT_PRIMARY if self._show_builder
                else DesignTokens.TEXT_SECONDARY
            )
        self.page.update()

    def _build_layout_toolbar(self) -> ft.Container:
        """Build toolbar with save, reload, and builder toggle."""
        self._builder_toggle_btn = ft.IconButton(
            icon=ft.Icons.BUILD,
            icon_size=20,
            icon_color=(
                DesignTokens.ACCENT_PRIMARY if self._show_builder
                else DesignTokens.TEXT_SECONDARY
            ),
            tooltip="Toggle Deck Builder",
            on_click=lambda _: self._toggle_builder_drawer(),
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    self._builder_toggle_btn,
                    ft.Text("Builder", size=12, color=DesignTokens.TEXT_SECONDARY),
                    ft.Container(expand=True),
                    self._save_button,
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_color=DesignTokens.TEXT_SECONDARY,
                        tooltip="Reload data",
                        on_click=lambda _: self._reload_data(),
                    ),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.START,
            ),
            padding=10,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.02, DesignTokens.TEXT_PRIMARY),
        )

    def _build_card_types_editor(self) -> ft.Container:
        """Build the card types editor panel."""
        self._card_types_editor = CardTypesEditor(
            self.page,
            on_save=self._refresh_preview_now,
        )
        return self._card_types_editor.container

    def _build_placeholder_panel(self, title: str, description: str, icon: str) -> ft.Container:
        """Build a placeholder panel for upcoming features."""
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(icon, size=36, color=DesignTokens.TEXT_MUTED),
                    ft.Text(title, size=14, weight=ft.FontWeight.W_600, color=DesignTokens.TEXT_SECONDARY),
                    ft.Text(description, size=11, color=DesignTokens.TEXT_TERTIARY, text_align=ft.TextAlign.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
            ),
            height=160,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.02, DesignTokens.TEXT_PRIMARY),
            alignment=ft.Alignment(0, 0),
            padding=10,
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
            self._detail_editor_container.content = self._detail_editor.build_placeholder()
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
        self._detail_editor_container.content = self._detail_editor.build_content(
            self.df.iloc[row_index], row_index
        )

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
            self._vocab_service.mark_dirty()
            
            # Handle special case for Sentence fields (they might be in ContextSentences)
            if key.startswith("Sentence_"):
                # Sentences are stored in ContextSentences, we update individual sentence
                self._update_sentence_field(key, value)
            elif key in self.df.columns:
                self.df.at[self.selected_row_index, key] = value
            
            # Update save button visual state
            self._update_save_button_state()
            
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

        try:
            self.page.run_task(_debounced)
        except Exception:
            pass  # Silently ignore if page is not ready
    
    def _update_card_preview(self, force: bool = False) -> None:
        """Update the card preview with current row data."""
        if not force and (self._performance_mode or not self._live_preview_enabled):
            return
        if self._card_preview and self.selected_row_index is not None and self.df is not None:
            row_data = self.df.iloc[self.selected_row_index].to_dict()
            self._card_preview.update_preview(row_data)
            # Targeted update: only refresh the preview container, not the whole page
            try:
                if self._preview_container:
                    self._preview_container.update()
            except Exception:
                self.page.update()

    def _refresh_preview_now(self) -> None:
        """Manual refresh for preview when live updates are off."""
        self._update_card_preview(force=True)

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
    
    def _on_save_click(self) -> None:
        """Handle save button click - runs async save."""
        self.page.run_task(self._save_data_with_feedback)
    
    async def _save_data_with_feedback(self) -> None:
        """Save data with UI feedback (async)."""
        success = await self.save_data_async()
        
        if success:
            self._has_unsaved_changes = False
            self._update_save_button_state()
            self._show_snackbar("Project saved successfully!", icon=ft.Icons.CHECK_CIRCLE)
        else:
            self._show_snackbar("Failed to save project", error=True)
    
    def _show_snackbar(self, message: str, error: bool = False, icon: str = None) -> None:
        """Show a snackbar notification."""
        show_snackbar(self.page, message, error=error, icon=icon)
    
    def _update_save_button_state(self) -> None:
        """Update save button appearance based on unsaved changes state."""
        if not self._save_button:
            return
        if self._has_unsaved_changes:
            self._save_button.content = ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SAVE, size=16),
                    ft.Text("Save Project *", size=13, weight=ft.FontWeight.BOLD),
                ],
                spacing=5,
            )
            self._save_button.style = ft.ButtonStyle(
                color={
                    ft.ControlState.DEFAULT: DesignTokens.TEXT_PRIMARY,
                    ft.ControlState.DISABLED: DesignTokens.TEXT_TERTIARY,
                },
                bgcolor={
                    ft.ControlState.DEFAULT: "#FFB74D",
                    ft.ControlState.HOVERED: "#FFA726",
                    ft.ControlState.DISABLED: ft.Colors.with_opacity(0.3, "#FFB74D"),
                },
                padding=ft.Padding.symmetric(horizontal=15, vertical=10),
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation={
                    ft.ControlState.DEFAULT: 3,
                    ft.ControlState.HOVERED: 6,
                },
            )
        else:
            self._save_button.content = ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SAVE, size=16),
                    ft.Text("Save Project", size=13),
                ],
                spacing=5,
            )
            self._save_button.style = ft.ButtonStyle(
                color={
                    ft.ControlState.DEFAULT: DesignTokens.TEXT_PRIMARY,
                    ft.ControlState.DISABLED: DesignTokens.TEXT_TERTIARY,
                },
                bgcolor={
                    ft.ControlState.DEFAULT: DesignTokens.ACCENT_SUCCESS,
                    ft.ControlState.HOVERED: DesignTokens.ACCENT_SUCCESS,
                    ft.ControlState.DISABLED: ft.Colors.with_opacity(0.3, DesignTokens.ACCENT_SUCCESS),
                },
                padding=ft.Padding.symmetric(horizontal=15, vertical=10),
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation={
                    ft.ControlState.DEFAULT: 2,
                    ft.ControlState.HOVERED: 4,
                },
            )
    
    def _reload_data(self) -> None:
        """Reload data from CSV (with unsaved changes confirmation)."""
        if self._has_unsaved_changes:
            def _confirm_reload(e):
                self.page.close(dlg)
                self._do_reload()
            
            def _cancel(e):
                self.page.close(dlg)
            
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Unsaved Changes"),
                content=ft.Text(
                    "You have unsaved changes. Reload and discard them?"
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=_cancel),
                    ft.TextButton("Reload", on_click=_confirm_reload),
                ],
            )
            self.page.open(dlg)
            return
        self._do_reload()
    
    def _do_reload(self) -> None:
        """Perform the actual data reload and view rebuild."""
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

    
    def save_data(self) -> bool:
        """
        Save the current DataFrame via VocabularyService.
        
        Returns:
            True if save was successful, False otherwise
        """
        if self.df is None or self.df.empty:
            return False
        return self._vocab_service.save()
    
    async def save_data_async(self) -> bool:
        """
        Save the current DataFrame via VocabularyService (async).
        
        Returns:
            True if save was successful, False otherwise
        """
        if self.df is None or self.df.empty:
            return False
        return await self._vocab_service.save_async()
    
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
