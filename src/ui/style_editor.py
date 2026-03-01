"""
Style Editor View — extracted from WorkbenchView
--------------------------------------------------

Manages the CSS/appearance style editor for Anki card templates.
Owns color fields, palette swatches, presets, debounced saves,
and live preview integration.
"""

import asyncio
from typing import Callable, Dict, Optional

import flet as ft

from src.config import SettingsManager
from src.templates import CardTemplates
from src.ui.theme import DesignTokens
from src.utils.logger import get_logger


class StyleEditorView:
    """
    Self-contained style editor for card appearance.

    Parameters
    ----------
    page : ft.Page
        Flet page for ``update()`` / ``run_task()``.
    settings : SettingsManager
        Reads/writes ``CARD_STYLE`` key.
    schedule_preview_update : Callable[[], None]
        Debounced card-preview refresh owned by the parent.
    update_card_preview : Callable[[], None]
        Immediate card-preview refresh (e.g. on preset apply).
    """

    _logger = get_logger("style_editor")

    def __init__(
        self,
        page: ft.Page,
        settings: SettingsManager,
        schedule_preview_update: Callable[[], None],
        update_card_preview: Callable[[], None],
    ) -> None:
        self.page = page
        self._settings = settings
        self._schedule_preview_update = schedule_preview_update
        self._update_card_preview = update_card_preview

        # State
        self._style_fields: Dict[str, ft.TextField] = {}
        self._style_previews: Dict[str, ft.Container] = {}
        self._style_status: Optional[ft.Text] = None
        self._active_style_key: Optional[str] = None
        self._style_update_version: int = 0
        self._style_debounce_ms: int = 350

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self) -> ft.Container:
        """Build the styles editor widget. Returns a Container."""
        style = self._get_style_config()
        self._style_fields.clear()
        self._style_previews.clear()

        self._style_status = ft.Text("Saved", size=10, color=DesignTokens.TEXT_TERTIARY)

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

        # ---- local helpers ----

        def swatch(color: str, key: str) -> ft.Container:
            return ft.Container(
                width=16, height=16, border_radius=4,
                bgcolor=color,
                border=ft.border.all(1, DesignTokens.BORDER_SUBTLE),
                on_click=lambda e, c=color, k=key: self._set_style_color(k, c),
            )

        def color_field(label: str, key: str) -> ft.Column:
            field = ft.TextField(
                value=style.get(key, ""),
                label=label,
                border_color=DesignTokens.TEXT_MUTED,
                focused_border_color=DesignTokens.ACCENT_PRIMARY,
                label_style=ft.TextStyle(color=DesignTokens.TEXT_SECONDARY, size=11),
                text_style=ft.TextStyle(color=DesignTokens.TEXT_PRIMARY, size=12),
                dense=True,
                on_blur=lambda e, k=key: self._on_style_change(k, e.control.value),
                on_submit=lambda e, k=key: self._on_style_change(k, e.control.value),
                on_change=lambda e, k=key: self._on_style_change_if_valid(k, e.control.value),
            )
            self._style_fields[key] = field

            preview = ft.Container(
                width=18, height=18, border_radius=4,
                bgcolor=style.get(key, "#000000"),
                border=ft.border.all(1, DesignTokens.BORDER_SUBTLE),
            )
            self._style_previews[key] = preview

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
                    ft.Icon(ft.Icons.RESTORE, size=14, color=DesignTokens.ACCENT_TEAL),
                    ft.Text("Reset Styles", size=11, color=DesignTokens.ACCENT_TEAL),
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
                                    width=10, height=10, border_radius=2,
                                    bgcolor=c,
                                    border=ft.border.all(1, DesignTokens.BORDER_SUBTLE),
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
                    bgcolor={ft.ControlState.DEFAULT: ft.Colors.with_opacity(0.02, DesignTokens.TEXT_PRIMARY)},
                ),
            )

        # ---- tabs ----

        base_tab = ft.Column(
            controls=[
                ft.Text("Base colors", size=11, color=DesignTokens.TEXT_SECONDARY),
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
                ft.Text("Card shape", size=11, color=DesignTokens.TEXT_SECONDARY),
                ft.Text("Radius", size=11, color=DesignTokens.TEXT_SECONDARY),
                ft.Slider(
                    min=0, max=24, divisions=24,
                    value=float(style.get("card_radius", "12").replace("px", "") or 12),
                    label="{value}px",
                    on_change=lambda e: self._on_style_change("card_radius", f"{int(e.control.value)}px"),
                ),
                ft.Text("Shadow", size=11, color=DesignTokens.TEXT_SECONDARY),
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
                ft.Text("German gender gradients", size=11, color=DesignTokens.TEXT_SECONDARY),
                color_field("DER Start", "der_start"),
                color_field("DER End", "der_end"),
                color_field("DIE Start", "die_start"),
                color_field("DIE End", "die_end"),
                color_field("DAS Start", "das_start"),
                color_field("DAS End", "das_end"),
                color_field("None Start", "none_start"),
                color_field("None End", "none_end"),
                ft.Text("English header gradient", size=11, color=DesignTokens.TEXT_SECONDARY),
                color_field("EN Start", "en_start"),
                color_field("EN End", "en_end"),
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        )

        presets_tab = ft.Column(
            controls=[
                ft.Text("Presets", size=11, color=DesignTokens.TEXT_SECONDARY),
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
                            0.12 if is_active else 0.02, DesignTokens.TEXT_PRIMARY
                        )
                    },
                    color={
                        ft.ControlState.DEFAULT: DesignTokens.TEXT_PRIMARY if is_active else DesignTokens.TEXT_SECONDARY
                    },
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    shape=ft.RoundedRectangleBorder(radius=8),
                )
            if self.page:
                self.page.update()

        tab_bar = ft.Row(controls=[], spacing=6, wrap=True)

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
                            ft.Text("Styles", size=14, weight=ft.FontWeight.W_600, color=DesignTokens.TEXT_PRIMARY),
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
            bgcolor=ft.Colors.with_opacity(0.02, DesignTokens.TEXT_PRIMARY),
            expand=True,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_style_config(self) -> Dict[str, str]:
        style = self._settings.get("CARD_STYLE", CardTemplates.DEFAULT_STYLE)
        return CardTemplates.normalize_style(style)

    def _on_style_change(self, key: str, value: str) -> None:
        style = self._get_style_config()
        style[key] = value
        self._settings.set("CARD_STYLE", style, persist=False)
        if self._style_status:
            self._style_status.value = "Editing..."
            self._style_status.color = DesignTokens.TEXT_SECONDARY
        if key in self._style_previews:
            self._style_previews[key].bgcolor = value
        self._schedule_preview_update()
        self._schedule_style_save()

    def _on_style_change_if_valid(self, key: str, value: str) -> None:
        if not value:
            return
        if value.startswith("#") and len(value) in (4, 7):
            # Skip if value hasn't actually changed
            current = self._get_style_config()
            if current.get(key) == value:
                return
            self._on_style_change(key, value)

    def _set_active_style_key(self, key: str) -> None:
        self._active_style_key = key
        self.page.update()

    def _apply_palette_color(self, color: str) -> None:
        if not self._active_style_key:
            return
        if self._active_style_key in self._style_fields:
            self._style_fields[self._active_style_key].value = color
        self._on_style_change(self._active_style_key, color)

    def _set_style_color(self, key: str, color: str) -> None:
        if key in self._style_fields:
            self._style_fields[key].value = color
        self._on_style_change(key, color)

    def _apply_style_preset(self, name: str, presets: Dict[str, Dict[str, str]]) -> None:
        base = CardTemplates.DEFAULT_STYLE.copy()
        override = presets.get(name, {})
        base.update(override)
        self._settings.set("CARD_STYLE", base)
        self._update_style_fields_from_config(base)
        self._update_card_preview()
        self.page.update()

    def _on_reset_styles(self, e: ft.ControlEvent) -> None:
        default_style = CardTemplates.DEFAULT_STYLE.copy()
        self._settings.set("CARD_STYLE", default_style)
        self._update_style_fields_from_config(default_style)
        self._update_card_preview()
        self.page.update()

    def _update_style_fields_from_config(self, style: Dict[str, str]) -> None:
        for key, field in self._style_fields.items():
            if key in style:
                field.value = style[key]
        for key, preview in self._style_previews.items():
            if key in style:
                preview.bgcolor = style[key]
        if self._style_status:
            self._style_status.value = "Saved"
            self._style_status.color = DesignTokens.TEXT_TERTIARY

    def _schedule_style_save(self) -> None:
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
                self._style_status.color = DesignTokens.TEXT_TERTIARY
            if self.page:
                self.page.update()

        try:
            self.page.run_task(_debounced)
        except Exception:
            pass
