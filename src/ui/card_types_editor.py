"""
Card Types Editor UI Component
------------------------------

Provides a UI for configuring which card types are enabled
and their display order through drag-and-drop or arrow buttons.
"""

import flet as ft
from typing import Callable, Dict, List, Optional

from ..config import (
    SettingsManager,
    CARD_TYPES,
    get_default_card_types_enabled,
    get_default_card_types_order,
    validate_card_types_config,
)


class CardTypesEditor:
    """
    UI component for editing card types configuration.

    Allows users to:
    - Enable/disable individual card types
    - Reorder card types using up/down buttons
    - Save configuration to settings
    """

    def __init__(
        self,
        page: ft.Page,
        on_change: Optional[Callable[[Dict[str, bool], List[str]], None]] = None,
        on_save: Optional[Callable[[], None]] = None,
    ) -> None:
        self.page = page
        self.settings = SettingsManager()
        self._on_change = on_change
        self._on_save = on_save

        # Load current configuration
        self._types_enabled: Dict[str, bool] = self.settings.get(
            "CARD_TYPES_ENABLED",
            get_default_card_types_enabled(),
        )
        self._types_order: List[str] = self.settings.get(
            "CARD_TYPES_ORDER",
            get_default_card_types_order(),
        )

        # Validate loaded config
        self._types_enabled, self._types_order = validate_card_types_config(
            self._types_enabled,
            self._types_order,
        )

        self._has_changes: bool = False

        self._type_list: Optional[ft.Column] = None
        self._save_button: Optional[ft.ElevatedButton] = None
        self._container: Optional[ft.Container] = None

        self._build_view()

    @property
    def container(self) -> ft.Container:
        return self._container

    @property
    def types_enabled(self) -> Dict[str, bool]:
        return self._types_enabled.copy()

    @property
    def types_order(self) -> List[str]:
        return self._types_order.copy()

    def _build_view(self) -> None:
        self._type_list = ft.Column(
            controls=self._build_type_items(),
            spacing=4,
            scroll=ft.ScrollMode.AUTO,
        )

        self._save_button = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SAVE_ROUNDED, size=18),
                    ft.Text("Save Card Types", size=14, weight=ft.FontWeight.W_500),
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

        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.STYLE_ROUNDED, size=24, color=ft.Colors.TEAL_200),
                    ft.Column(
                        controls=[
                            ft.Text(
                                "Card Types",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                            ft.Text(
                                "Enable/disable card types and reorder them",
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

        instructions = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=ft.Colors.AMBER_200),
                    ft.Text(
                        "Required card types cannot be disabled. Use arrows to reorder.",
                        size=11,
                        color=ft.Colors.AMBER_200,
                    ),
                ],
                spacing=6,
            ),
            padding=ft.Padding.only(bottom=10),
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

        content = ft.Column(
            controls=[
                header,
                instructions,
                ft.Row(
                    controls=[
                        ft.Text("Presets", size=11, color=ft.Colors.WHITE54),
                        preset_min_btn,
                        preset_full_btn,
                    ],
                    spacing=6,
                ),
                ft.Container(height=6),
                ft.Container(
                    content=self._type_list,
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

    def _build_type_items(self) -> List[ft.Control]:
        items: List[ft.Control] = []

        for idx, type_id in enumerate(self._types_order):
            card_type = CARD_TYPES.get(type_id)
            if not card_type:
                continue

            is_enabled = self._types_enabled.get(type_id, True)
            is_first = idx == 0
            is_last = idx == len(self._types_order) - 1

            item = self._build_type_item(
                type_id=type_id,
                name=card_type.name,
                icon=card_type.icon,
                description=card_type.description,
                required=card_type.required,
                enabled=is_enabled,
                is_first=is_first,
                is_last=is_last,
            )
            items.append(item)

        return items

    def _build_type_item(
        self,
        type_id: str,
        name: str,
        icon: str,
        description: str,
        required: bool,
        enabled: bool,
        is_first: bool,
        is_last: bool,
    ) -> ft.Container:
        checkbox = ft.Checkbox(
            value=enabled,
            disabled=required,
            on_change=lambda e, tid=type_id: self._on_toggle_type(tid, e.control.value),
            active_color=ft.Colors.TEAL_400,
            check_color=ft.Colors.WHITE,
        )

        up_btn = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_UP,
            icon_size=18,
            icon_color=ft.Colors.WHITE54 if not is_first else ft.Colors.WHITE12,
            disabled=is_first,
            on_click=lambda e, tid=type_id: self._on_move_type(tid, -1),
            tooltip="Move up",
            style=ft.ButtonStyle(
                padding=ft.Padding.all(4),
            ),
        )

        down_btn = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_DOWN,
            icon_size=18,
            icon_color=ft.Colors.WHITE54 if not is_last else ft.Colors.WHITE12,
            disabled=is_last,
            on_click=lambda e, tid=type_id: self._on_move_type(tid, 1),
            tooltip="Move down",
            style=ft.ButtonStyle(
                padding=ft.Padding.all(4),
            ),
        )

        required_badge = ft.Container(
            content=ft.Text("Required", size=9, color=ft.Colors.AMBER_200),
            bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.AMBER),
            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
            border_radius=4,
            visible=required,
        )

        type_info = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            f"{icon} {name}",
                            size=13,
                            weight=ft.FontWeight.W_500,
                            color=ft.Colors.WHITE if enabled else ft.Colors.WHITE38,
                        ),
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
                    type_info,
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
        if self._type_list:
            self._type_list.controls = self._build_type_items()
            self.page.update()

        if self._on_change:
            self._on_change(self._types_enabled, self._types_order)

    def _mark_changed(self) -> None:
        self._has_changes = True

    def _on_toggle_type(self, type_id: str, enabled: bool) -> None:
        card_type = CARD_TYPES.get(type_id)
        if card_type and card_type.required:
            return

        self._types_enabled[type_id] = enabled
        self._mark_changed()
        self._refresh_list()

    def _on_move_type(self, type_id: str, direction: int) -> None:
        try:
            current_idx = self._types_order.index(type_id)
            new_idx = current_idx + direction

            if 0 <= new_idx < len(self._types_order):
                self._types_order[current_idx], self._types_order[new_idx] = (
                    self._types_order[new_idx],
                    self._types_order[current_idx],
                )

                self._mark_changed()
                self._refresh_list()
        except ValueError:
            pass

    def _on_save_click(self, e: ft.ControlEvent) -> None:
        try:
            validated_enabled, validated_order = validate_card_types_config(
                self._types_enabled,
                self._types_order,
            )

            self.settings.set("CARD_TYPES_ENABLED", validated_enabled)
            self.settings.set("CARD_TYPES_ORDER", validated_order)

            self._has_changes = False
            self._show_snackbar("Card types saved successfully!", success=True)

            if self._on_save:
                self._on_save()

        except Exception as ex:
            self._show_snackbar(f"Error saving: {str(ex)}", success=False)

    def _on_reset_click(self, e: ft.ControlEvent) -> None:
        self._types_enabled = get_default_card_types_enabled()
        self._types_order = get_default_card_types_order()
        self._mark_changed()
        self._refresh_list()
        self._show_snackbar("Reset to default card types", success=True)

    def _on_preset_minimal(self, e: ft.ControlEvent) -> None:
        """Enable only required card types (minimal preset)."""
        for type_id, card_type in CARD_TYPES.items():
            self._types_enabled[type_id] = bool(card_type.required)
        self._mark_changed()
        self._refresh_list()
        self._show_snackbar("Applied minimal preset", success=True)

    def _on_preset_full(self, e: ft.ControlEvent) -> None:
        """Enable all card types (full preset)."""
        for type_id in CARD_TYPES.keys():
            self._types_enabled[type_id] = True
        self._mark_changed()
        self._refresh_list()
        self._show_snackbar("Applied full preset", success=True)

    def _show_snackbar(self, message: str, success: bool = True) -> None:
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
        for ctrl in list(self.page.overlay):
            if isinstance(ctrl, ft.SnackBar):
                self.page.overlay.remove(ctrl)
        self.page.overlay.append(snackbar)
        snackbar.open = True
        self.page.update()


def create_card_types_editor(
    page: ft.Page,
    on_change: Optional[Callable[[Dict[str, bool], List[str]], None]] = None,
    on_save: Optional[Callable[[], None]] = None,
) -> ft.Container:
    editor = CardTypesEditor(page, on_change, on_save)
    return editor.container
