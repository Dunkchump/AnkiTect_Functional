"""
Card Sections Editor UI Component
----------------------------------

Provides a compact UI for configuring which card sections are visible
and their display order. Auto-saves on every change.
"""

import flet as ft
from typing import Callable, Dict, List, Optional

from .theme import DesignTokens
from ..config import (
    SettingsManager,
    CARD_SECTIONS,
    get_default_enabled,
    get_default_order,
    validate_sections_config,
)


class CardSectionsEditor:
    """
    Compact card-layout editor: toggle sections, reorder, apply presets.
    Auto-persists every change and fires *on_save* so the host can
    refresh the preview.
    """

    def __init__(
        self,
        page: ft.Page,
        settings: SettingsManager,
        on_save: Optional[Callable[[], None]] = None,
    ) -> None:
        self.page = page
        self._settings = settings
        self._on_save = on_save

        # Load & validate
        self._sections_enabled: Dict[str, bool] = self._settings.get(
            "CARD_SECTIONS_ENABLED", get_default_enabled()
        )
        self._sections_order: List[str] = self._settings.get(
            "CARD_SECTIONS_ORDER", get_default_order()
        )
        self._sections_enabled, self._sections_order = validate_sections_config(
            self._sections_enabled, self._sections_order
        )

        # UI refs filled by build()
        self._sections_list: Optional[ft.Column] = None
        self._status_text: Optional[ft.Text] = None
        self._summary_chip: Optional[ft.Container] = None

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def build(self) -> ft.Container:
        """Return the ready-to-use container."""
        self._sections_list = ft.Column(
            controls=self._build_section_items(),
            spacing=6,
        )

        self._status_text = ft.Text(
            "Saved", size=10, color=DesignTokens.TEXT_TERTIARY,
        )

        enabled_count = sum(1 for v in self._sections_enabled.values() if v)
        total_count = len(self._sections_order)
        self._summary_chip = ft.Container(
            content=ft.Text(
                f"{enabled_count}/{total_count} enabled",
                size=10,
                color=DesignTokens.TEXT_SECONDARY,
            ),
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.08, DesignTokens.TEXT_PRIMARY),
        )

        reset_btn = ft.TextButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.RESTORE, size=14, color=DesignTokens.ACCENT_TEAL),
                    ft.Text("Reset Order", size=11, color=DesignTokens.ACCENT_TEAL),
                ],
                spacing=4,
            ),
            on_click=self._on_reset_click,
        )

        preset_min = self._preset_button("Minimal", ft.Icons.TUNE, self._on_preset_minimal)
        preset_full = self._preset_button("Full", ft.Icons.DASHBOARD, self._on_preset_full)

        return ft.Container(
            content=ft.Column(
                controls=[
                    # Header row
                    ft.Row(
                        controls=[
                            ft.Text(
                                "Card Layout",
                                size=14,
                                weight=ft.FontWeight.W_600,
                                color=DesignTokens.TEXT_PRIMARY,
                            ),
                            ft.Container(expand=True),
                            self._summary_chip,
                            ft.Container(width=6),
                            self._status_text,
                            reset_btn,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=6),
                    # Instructions
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=12, color=DesignTokens.ACCENT_WARNING),
                            ft.Text(
                                "Required sections cannot be disabled. Use arrows to reorder.",
                                size=10,
                                color=DesignTokens.ACCENT_WARNING,
                            ),
                        ],
                        spacing=6,
                    ),
                    ft.Container(height=4),
                    # Presets
                    ft.Row(
                        controls=[
                            ft.Text("Presets", size=11, color=DesignTokens.TEXT_SECONDARY),
                            preset_min,
                            preset_full,
                        ],
                        spacing=6,
                    ),
                    ft.Container(height=8),
                    # Section list
                    ft.Container(
                        content=self._sections_list,
                        bgcolor=ft.Colors.with_opacity(0.03, DesignTokens.TEXT_PRIMARY),
                        border_radius=8,
                        padding=8,
                    ),
                ],
                spacing=6,
            ),
            padding=10,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.02, DesignTokens.TEXT_PRIMARY),
        )

    @property
    def sections_enabled(self) -> Dict[str, bool]:
        return self._sections_enabled.copy()

    @property
    def sections_order(self) -> List[str]:
        return self._sections_order.copy()

    # ------------------------------------------------------------------
    # Internal – build helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _preset_button(label: str, icon: str, on_click) -> ft.OutlinedButton:
        return ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(icon, size=14, color=DesignTokens.TEXT_SECONDARY),
                    ft.Text(label, size=12, color=DesignTokens.TEXT_SECONDARY),
                ],
                spacing=6,
            ),
            height=28,
            style=ft.ButtonStyle(
                color={ft.ControlState.DEFAULT: DesignTokens.TEXT_SECONDARY},
                bgcolor={ft.ControlState.DEFAULT: ft.Colors.with_opacity(0.02, DesignTokens.TEXT_PRIMARY)},
                side={ft.ControlState.DEFAULT: ft.BorderSide(1, DesignTokens.BORDER_SUBTLE)},
                padding=ft.Padding.symmetric(horizontal=10, vertical=0),
            ),
            on_click=on_click,
        )

    def _build_section_items(self) -> List[ft.Control]:
        items = []
        for idx, section_id in enumerate(self._sections_order):
            section = CARD_SECTIONS.get(section_id)
            if not section:
                continue
            items.append(
                self._build_section_item(
                    section_id=section_id,
                    name=section.name,
                    icon=section.icon,
                    description=section.description,
                    required=section.required,
                    enabled=self._sections_enabled.get(section_id, True),
                    is_first=(idx == 0),
                    is_last=(idx == len(self._sections_order) - 1),
                )
            )
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
        toggle = ft.Switch(
            value=enabled,
            disabled=required,
            on_change=lambda e, sid=section_id: self._on_toggle_section(sid, e.control.value),
            active_color=DesignTokens.ACCENT_TEAL_LIGHT,
        )

        up_btn = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_UP,
            icon_size=16,
            icon_color=DesignTokens.TEXT_SECONDARY if not is_first else DesignTokens.BORDER_SUBTLE,
            disabled=is_first,
            on_click=lambda e, sid=section_id: self._on_move_section(sid, -1),
            tooltip="Move up",
            style=ft.ButtonStyle(padding=ft.Padding.all(2)),
        )

        down_btn = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_DOWN,
            icon_size=16,
            icon_color=DesignTokens.TEXT_SECONDARY if not is_last else DesignTokens.BORDER_SUBTLE,
            disabled=is_last,
            on_click=lambda e, sid=section_id: self._on_move_section(sid, 1),
            tooltip="Move down",
            style=ft.ButtonStyle(padding=ft.Padding.all(2)),
        )

        required_badge = ft.Container(
            content=ft.Text("Required", size=8, color=DesignTokens.ACCENT_WARNING),
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
                    color=DesignTokens.TEXT_PRIMARY if enabled else DesignTokens.TEXT_TERTIARY,
                ),
                required_badge,
            ],
            spacing=6,
        )
        desc_text = ft.Text(
            description,
            size=10,
            color=DesignTokens.TEXT_TERTIARY if enabled else DesignTokens.TEXT_MUTED,
        )
        section_info = ft.Column(
            controls=[title_row, desc_text],
            spacing=2,
            expand=True,
        )

        return ft.Container(
            content=ft.Row(
                controls=[toggle, section_info, up_btn, down_btn],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            border_radius=8,
            bgcolor=(
                ft.Colors.with_opacity(0.06, DesignTokens.TEXT_PRIMARY)
                if enabled
                else ft.Colors.with_opacity(0.02, DesignTokens.TEXT_PRIMARY)
            ),
            border=ft.border.all(1, DesignTokens.BORDER_DIM),
        )

    # ------------------------------------------------------------------
    # Internal – state mutations (auto-save)
    # ------------------------------------------------------------------

    def _refresh_and_persist(self) -> None:
        """Rebuild list, persist to settings, refresh preview."""
        validated_enabled, validated_order = validate_sections_config(
            self._sections_enabled, self._sections_order
        )
        self._sections_enabled = validated_enabled
        self._sections_order = validated_order

        self._settings.set("CARD_SECTIONS_ENABLED", validated_enabled)
        self._settings.set("CARD_SECTIONS_ORDER", validated_order)

        if self._sections_list:
            self._sections_list.controls = self._build_section_items()

        # Update summary chip
        if self._summary_chip and self._summary_chip.content:
            enabled_count = sum(1 for v in self._sections_enabled.values() if v)
            total_count = len(self._sections_order)
            self._summary_chip.content.value = f"{enabled_count}/{total_count} enabled"

        if self._status_text:
            self._status_text.value = "Saved"
            self._status_text.color = DesignTokens.TEXT_TERTIARY

        self.page.update()

        if self._on_save:
            self._on_save()

    def _on_toggle_section(self, section_id: str, enabled: bool) -> None:
        section = CARD_SECTIONS.get(section_id)
        if section and section.required:
            return
        self._sections_enabled[section_id] = enabled
        self._refresh_and_persist()

    def _on_move_section(self, section_id: str, direction: int) -> None:
        try:
            idx = self._sections_order.index(section_id)
            new_idx = idx + direction
            if 0 <= new_idx < len(self._sections_order):
                self._sections_order[idx], self._sections_order[new_idx] = (
                    self._sections_order[new_idx],
                    self._sections_order[idx],
                )
                self._refresh_and_persist()
        except ValueError:
            pass

    def _on_reset_click(self, e: ft.ControlEvent) -> None:
        self._sections_enabled = get_default_enabled()
        self._sections_order = get_default_order()
        self._refresh_and_persist()

    def _on_preset_minimal(self, e: ft.ControlEvent) -> None:
        for sid, sec in CARD_SECTIONS.items():
            self._sections_enabled[sid] = sec.required
        self._sections_order = get_default_order()
        self._refresh_and_persist()

    def _on_preset_full(self, e: ft.ControlEvent) -> None:
        for sid in CARD_SECTIONS:
            self._sections_enabled[sid] = True
        self._sections_order = get_default_order()
        self._refresh_and_persist()
