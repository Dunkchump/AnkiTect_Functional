"""
Card Sections Editor UI Component
----------------------------------

Provides a UI for configuring which card sections are visible
and their display order through drag-and-drop or arrow buttons.
"""

import flet as ft
from typing import Any, Callable, Dict, List, Optional

from ..config import (
    SettingsManager,
    CARD_SECTIONS,
    get_default_enabled,
    get_default_order,
    validate_sections_config,
)


class CardSectionsEditor:
    """
    UI component for editing card sections configuration.
    
    Allows users to:
    - Enable/disable individual sections
    - Reorder sections using up/down buttons
    - Preview the effect on card layout
    - Save configuration to settings
    """
    
    def __init__(
        self, 
        page: ft.Page,
        on_change: Optional[Callable[[Dict[str, bool], List[str]], None]] = None,
        on_save: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Initialize the sections editor.
        
        Args:
            page: Flet page instance
            on_change: Callback when sections change (enabled, order)
            on_save: Callback when settings are saved
        """
        self.page = page
        self.settings = SettingsManager()
        self._on_change = on_change
        self._on_save = on_save
        
        # Load current configuration
        self._sections_enabled: Dict[str, bool] = self.settings.get(
            "CARD_SECTIONS_ENABLED", 
            get_default_enabled()
        )
        self._sections_order: List[str] = self.settings.get(
            "CARD_SECTIONS_ORDER",
            get_default_order()
        )
        
        # Validate loaded config
        self._sections_enabled, self._sections_order = validate_sections_config(
            self._sections_enabled,
            self._sections_order
        )
        
        # Track changes
        self._has_changes: bool = False
        
        # UI references
        self._section_list: Optional[ft.Column] = None
        self._save_button: Optional[ft.ElevatedButton] = None
        self._container: Optional[ft.Container] = None
        
        # Build the view
        self._build_view()
    
    @property
    def container(self) -> ft.Container:
        """Get the main container for this component."""
        return self._container
    
    @property
    def sections_enabled(self) -> Dict[str, bool]:
        """Get current enabled state of sections."""
        return self._sections_enabled.copy()
    
    @property
    def sections_order(self) -> List[str]:
        """Get current order of sections."""
        return self._sections_order.copy()
    
    def _build_view(self) -> None:
        """Build the complete editor view."""
        # Section list
        self._section_list = ft.Column(
            controls=self._build_section_items(),
            spacing=4,
            scroll=ft.ScrollMode.AUTO,
        )
        
        # Save button
        self._save_button = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SAVE_ROUNDED, size=18),
                    ft.Text("Save Layout", size=14, weight=ft.FontWeight.W_500),
                ],
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            style=ft.ButtonStyle(
                color={
                    ft.ControlState.DEFAULT: ft.Colors.WHITE,
                    ft.ControlState.DISABLED: ft.Colors.WHITE38,
                },
                bgcolor={
                    ft.ControlState.DEFAULT: ft.Colors.TEAL_700,
                    ft.ControlState.HOVERED: ft.Colors.TEAL_600,
                    ft.ControlState.DISABLED: ft.Colors.with_opacity(0.3, ft.Colors.TEAL_700),
                },
                padding=ft.Padding.symmetric(horizontal=20, vertical=12),
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=self._on_save_click,
        )
        
        # Reset button
        reset_button = ft.TextButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.RESTORE, size=16, color=ft.Colors.WHITE54),
                    ft.Text("Reset to Default", size=12, color=ft.Colors.WHITE54),
                ],
                spacing=4,
            ),
            on_click=self._on_reset_click,
        )
        
        # Header
        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.VIEW_AGENDA_ROUNDED, size=24, color=ft.Colors.TEAL_200),
                    ft.Column(
                        controls=[
                            ft.Text(
                                "Card Layout",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                            ft.Text(
                                "Enable/disable sections and reorder them",
                                size=12,
                                color=ft.Colors.WHITE54,
                            ),
                        ],
                        spacing=2,
                    ),
                ],
                spacing=12,
            ),
            padding=ft.Padding.only(bottom=15),
        )
        
        # Instructions
        instructions = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=ft.Colors.AMBER_200),
                    ft.Text(
                        "Required sections cannot be disabled. Use arrows to reorder.",
                        size=11,
                        color=ft.Colors.AMBER_200,
                    ),
                ],
                spacing=6,
            ),
            padding=ft.Padding.only(bottom=10),
        )
        
        # Main content
        content = ft.Column(
            controls=[
                header,
                instructions,
                ft.Container(
                    content=self._section_list,
                    bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.WHITE),
                    border_radius=10,
                    padding=10,
                    expand=True,
                ),
                ft.Container(height=15),
                ft.Row(
                    controls=[
                        reset_button,
                        ft.Container(expand=True),
                        self._save_button,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            expand=True,
        )
        
        self._container = ft.Container(
            content=content,
            padding=20,
            border_radius=12,
            bgcolor="#1A1A1A",
            expand=True,
        )
    
    def _build_section_items(self) -> List[ft.Control]:
        """Build list of section item controls."""
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
        # Checkbox for enabling/disabling
        checkbox = ft.Checkbox(
            value=enabled,
            disabled=required,
            on_change=lambda e, sid=section_id: self._on_toggle_section(sid, e.control.value),
            active_color=ft.Colors.TEAL_400,
            check_color=ft.Colors.WHITE,
        )
        
        # Up button
        up_btn = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_UP,
            icon_size=18,
            icon_color=ft.Colors.WHITE54 if not is_first else ft.Colors.WHITE12,
            disabled=is_first,
            on_click=lambda e, sid=section_id: self._on_move_section(sid, -1),
            tooltip="Move up",
            style=ft.ButtonStyle(
                padding=ft.Padding.all(4),
            ),
        )
        
        # Down button
        down_btn = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_DOWN,
            icon_size=18,
            icon_color=ft.Colors.WHITE54 if not is_last else ft.Colors.WHITE12,
            disabled=is_last,
            on_click=lambda e, sid=section_id: self._on_move_section(sid, 1),
            tooltip="Move down",
            style=ft.ButtonStyle(
                padding=ft.Padding.all(4),
            ),
        )
        
        # Required badge
        required_badge = ft.Container(
            content=ft.Text("Required", size=9, color=ft.Colors.AMBER_200),
            bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.AMBER),
            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
            border_radius=4,
            visible=required,
        )
        
        # Section info
        section_info = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(f"{icon} {name}", size=13, weight=ft.FontWeight.W_500,
                               color=ft.Colors.WHITE if enabled else ft.Colors.WHITE38),
                        required_badge,
                    ],
                    spacing=8,
                ),
                ft.Text(
                    description,
                    size=10,
                    color=ft.Colors.WHITE38 if enabled else ft.Colors.WHITE12,
                ),
            ],
            spacing=2,
            expand=True,
        )
        
        return ft.Container(
            content=ft.Row(
                controls=[
                    checkbox,
                    section_info,
                    up_btn,
                    down_btn,
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE) if enabled else ft.Colors.TRANSPARENT,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )
    
    def _refresh_list(self) -> None:
        """Refresh the section list UI."""
        if self._section_list:
            self._section_list.controls = self._build_section_items()
            self.page.update()
        
        # Notify change callback
        if self._on_change:
            self._on_change(self._sections_enabled, self._sections_order)
    
    def _mark_changed(self) -> None:
        """Mark that changes have been made."""
        self._has_changes = True
    
    def _on_toggle_section(self, section_id: str, enabled: bool) -> None:
        """Handle section toggle."""
        section = CARD_SECTIONS.get(section_id)
        if section and section.required:
            return  # Cannot disable required sections
        
        self._sections_enabled[section_id] = enabled
        self._mark_changed()
        self._refresh_list()
    
    def _on_move_section(self, section_id: str, direction: int) -> None:
        """
        Handle section move.
        
        Args:
            section_id: The section to move
            direction: -1 for up, +1 for down
        """
        try:
            current_idx = self._sections_order.index(section_id)
            new_idx = current_idx + direction
            
            if 0 <= new_idx < len(self._sections_order):
                # Swap positions
                self._sections_order[current_idx], self._sections_order[new_idx] = \
                    self._sections_order[new_idx], self._sections_order[current_idx]
                
                self._mark_changed()
                self._refresh_list()
        except ValueError:
            pass  # Section not found
    
    def _on_save_click(self, e: ft.ControlEvent) -> None:
        """Handle save button click."""
        try:
            # Validate before saving
            validated_enabled, validated_order = validate_sections_config(
                self._sections_enabled,
                self._sections_order
            )
            
            # Save to settings
            self.settings.set("CARD_SECTIONS_ENABLED", validated_enabled)
            self.settings.set("CARD_SECTIONS_ORDER", validated_order)
            
            self._has_changes = False
            self._show_snackbar("Card layout saved successfully!", success=True)
            
            # Notify save callback
            if self._on_save:
                self._on_save()
                
        except Exception as ex:
            self._show_snackbar(f"Error saving: {str(ex)}", success=False)
    
    def _on_reset_click(self, e: ft.ControlEvent) -> None:
        """Handle reset button click."""
        self._sections_enabled = get_default_enabled()
        self._sections_order = get_default_order()
        self._mark_changed()
        self._refresh_list()
        self._show_snackbar("Reset to default layout", success=True)
    
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
        # Clean up old snackbars
        for ctrl in list(self.page.overlay):
            if isinstance(ctrl, ft.SnackBar):
                self.page.overlay.remove(ctrl)
        self.page.overlay.append(snackbar)
        snackbar.open = True
        self.page.update()


def create_card_sections_editor(
    page: ft.Page,
    on_change: Optional[Callable[[Dict[str, bool], List[str]], None]] = None,
    on_save: Optional[Callable[[], None]] = None,
) -> ft.Container:
    """
    Factory function to create the card sections editor.
    
    Args:
        page: Flet page instance
        on_change: Optional callback for changes
        on_save: Optional callback for save
        
    Returns:
        Container with the sections editor
    """
    editor = CardSectionsEditor(page, on_change, on_save)
    return editor.container
