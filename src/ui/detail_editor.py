"""
Detail Editor View — extracted from WorkbenchView
---------------------------------------------------

Manages the right-side detail panel for editing a single vocabulary row.
Owns field creation, audio generation/playback, image generation, and
expand/collapse state for the three collapsible sections.
"""

import asyncio
import hashlib
import os
import platform
import re
import subprocess
import tempfile
from typing import Callable, Dict, Optional

import flet as ft
import pandas as pd

from src.fetchers import AudioFetcher, ImageFetcher
from src.ui.theme import DesignTokens
from src.utils.logger import get_logger


class DetailEditorView:
    """
    Self-contained editor panel for a single vocabulary row.

    Parameters
    ----------
    page : ft.Page
        Flet page (needed for ``update`` / ``run_task`` / ``overlay``).
    audio_fetcher : AudioFetcher
        Service for generating TTS audio files.
    image_fetcher : ImageFetcher
        Service for generating images from prompts.
    on_field_change : Callable[[str, str], None]
        Called when any editable field value changes.
        ``(key, new_value)`` — the parent handles DataFrame writes,
        dirty-tracking, save-button state, and preview updates.
    show_snackbar : Callable
        ``(message, *, error=False, icon=None)`` — show feedback.
    set_preview_image : Callable[[Optional[str]], None]
        Set (or clear) the card-preview image path.
    """

    _logger = get_logger("detail_editor")

    def __init__(
        self,
        page: ft.Page,
        audio_fetcher: AudioFetcher,
        image_fetcher: ImageFetcher,
        on_field_change: Callable[[str, str], None],
        show_snackbar: Callable,
        set_preview_image: Callable[[Optional[str]], None],
    ) -> None:
        self.page = page
        self._audio_fetcher = audio_fetcher
        self._image_fetcher = image_fetcher
        self._on_field_change = on_field_change
        self._show_snackbar = show_snackbar
        self._set_preview_image = set_preview_image

        # ---- state ----
        self._fields: Dict[str, ft.TextField] = {}
        self._image_container: Optional[ft.Container] = None
        self._current_audio_path: Optional[str] = None
        self._last_audio_key: Optional[str] = None
        self._audio_loading: Dict[str, ft.ProgressRing] = {}
        self._audio_status_indicators: Dict[str, ft.Container] = {}
        self._image_gen_button: Optional[ft.IconButton] = None
        self._image_prompt_field: Optional[ft.TextField] = None
        self._is_generating_image: bool = False
        self._audio_player: Optional[ft.Audio] = None
        self._image_loading: Optional[ft.ProgressRing] = None
        self._sections_expanded: bool = False
        self._on_rebuild: Optional[Callable[[], None]] = None

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def fields(self) -> Dict[str, ft.TextField]:
        """Currently registered text-fields keyed by column name."""
        return self._fields

    @property
    def sections_expanded(self) -> bool:
        return self._sections_expanded

    # ------------------------------------------------------------------
    # Public build helpers
    # ------------------------------------------------------------------

    def build_placeholder(self) -> ft.Container:
        """Return the "Select a Word" placeholder container."""
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.TOUCH_APP_ROUNDED, size=48, color=DesignTokens.TEXT_MUTED),
                            ft.Text(
                                "Select a Word",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                                color=DesignTokens.TEXT_SECONDARY,
                            ),
                            ft.Text(
                                "Click on a row to view and edit details",
                                size=13,
                                color=DesignTokens.TEXT_TERTIARY,
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
            bgcolor=ft.Colors.with_opacity(0.03, DesignTokens.TEXT_PRIMARY),
        )

    def build_content(self, row: pd.Series, row_index: int) -> ft.Container:
        """Build the full edit-form for *row* at *row_index*."""
        # Reset per-row state
        self._fields.clear()
        self._audio_loading.clear()
        self._audio_status_indicators.clear()

        # Parse context sentences
        context = str(row.get("ContextSentences", ""))
        sentences = [s.strip() for s in re.split(r'<br\s*/?>|\n', context) if s.strip()]
        while len(sentences) < 3:
            sentences.append("")

        # Image preview
        self._image_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.IMAGE_ROUNDED, size=48, color=DesignTokens.TEXT_MUTED),
                    ft.Text("Click 'Generate Image' to preview", size=12, color=DesignTokens.TEXT_TERTIARY),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            height=180,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.05, DesignTokens.TEXT_PRIMARY),
            alignment=ft.Alignment(0, 0),
        )

        # ── Section 1: Core Info (always visible) ──
        core_section = ft.Column(
            controls=[
                self._create_field_with_audio(
                    "Target Word", "TargetWord",
                    str(row.get("TargetWord", "")),
                ),
                self._create_simple_field(row, "Meaning", "Meaning", multiline=True, min_lines=2, max_lines=4),
                self._create_simple_field(row, "Context Translation", "ContextTranslation", multiline=True, min_lines=2, max_lines=3),
                self._create_field_with_image_gen(
                    "Image Prompt", "ImagePrompt",
                    str(row.get("ImagePrompt", "")),
                ),
            ],
            spacing=0,
        )

        # ── Section 2: Grammar & Linguistics (expandable) ──
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
                        ft.Icon(ft.Icons.BOOK, size=18, color=DesignTokens.ACCENT_SECONDARY),
                        ft.Text("Grammar & Linguistics", size=14, weight=ft.FontWeight.W_500),
                    ],
                    spacing=8,
                ),
                controls=[
                    ft.Container(content=grammar_fields, padding=ft.Padding(left=10, right=10, top=5, bottom=10))
                ],
                expanded=self._sections_expanded,
                bgcolor=ft.Colors.with_opacity(0.05, DesignTokens.TEXT_PRIMARY),
                collapsed_bgcolor=ft.Colors.with_opacity(0.03, DesignTokens.TEXT_PRIMARY),
            ),
            padding=ft.Padding.only(top=5, bottom=5),
        )

        # ── Section 3: Context Sentences (expandable) ──
        context_fields = ft.Column(
            controls=[
                self._create_field_with_audio(
                    "Sentence 1", "Sentence_1", sentences[0],
                    multiline=True, min_lines=2, max_lines=3,
                ),
                self._create_field_with_audio(
                    "Sentence 2", "Sentence_2", sentences[1],
                    multiline=True, min_lines=2, max_lines=3,
                ),
                self._create_field_with_audio(
                    "Sentence 3", "Sentence_3", sentences[2],
                    multiline=True, min_lines=2, max_lines=3,
                ),
            ],
            spacing=5,
        )

        context_section = ft.Container(
            content=ft.ExpansionTile(
                title=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.CHAT_BUBBLE, size=18, color=DesignTokens.ACCENT_SUCCESS),
                        ft.Text("Context Sentences", size=14, weight=ft.FontWeight.W_500),
                    ],
                    spacing=8,
                ),
                controls=[
                    ft.Container(content=context_fields, padding=ft.Padding(left=10, right=10, top=5, bottom=10))
                ],
                expanded=self._sections_expanded,
                bgcolor=ft.Colors.with_opacity(0.05, DesignTokens.TEXT_PRIMARY),
                collapsed_bgcolor=ft.Colors.with_opacity(0.03, DesignTokens.TEXT_PRIMARY),
            ),
            padding=ft.Padding.only(top=5, bottom=5),
        )

        # ── Section 4: Metadata (expandable) ──
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
                        ft.Icon(ft.Icons.INFO, size=18, color=DesignTokens.ACCENT_PRIMARY),
                        ft.Text("Metadata", size=14, weight=ft.FontWeight.W_500),
                    ],
                    spacing=8,
                ),
                controls=[
                    ft.Container(content=metadata_fields, padding=ft.Padding(left=10, right=10, top=5, bottom=10))
                ],
                expanded=self._sections_expanded,
                bgcolor=ft.Colors.with_opacity(0.05, DesignTokens.TEXT_PRIMARY),
                collapsed_bgcolor=ft.Colors.with_opacity(0.03, DesignTokens.TEXT_PRIMARY),
            ),
            padding=ft.Padding.only(top=5, bottom=5),
        )

        # ── Assemble ──
        detail_content = ft.Column(
            controls=[
                # Header with expand toggle
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text(
                                "Edit Word",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                                color=DesignTokens.TEXT_PRIMARY,
                            ),
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.Icons.UNFOLD_MORE if not self._sections_expanded else ft.Icons.UNFOLD_LESS,
                                icon_size=20,
                                icon_color=DesignTokens.TEXT_SECONDARY,
                                tooltip="Expand all" if not self._sections_expanded else "Collapse all",
                                on_click=lambda _: self._on_toggle_expand_click(),
                            ),
                            ft.Text(
                                f"#{row_index + 1}",
                                size=12,
                                color=DesignTokens.TEXT_TERTIARY,
                            ),
                        ],
                    ),
                    padding=ft.Padding.only(bottom=15),
                ),
                core_section,
                ft.Container(height=5),
                grammar_section,
                context_section,
                metadata_section,
                ft.Container(height=10),
                ft.Text("Image Preview", size=14, weight=ft.FontWeight.BOLD, color=DesignTokens.TEXT_SECONDARY),
                ft.Container(height=5),
                self._image_container,
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        return ft.Container(
            content=detail_content,
            expand=True,
            padding=15,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.03, DesignTokens.TEXT_PRIMARY),
        )

    # ------------------------------------------------------------------
    # Expand / collapse
    # ------------------------------------------------------------------

    def _on_toggle_expand_click(self) -> None:
        """Internal handler wired to the toggle button inside the form."""
        self._sections_expanded = not self._sections_expanded
        if self._on_rebuild:
            self._on_rebuild()

    def set_rebuild_callback(self, callback: Callable[[], None]) -> None:
        """
        Register a callback the parent uses to re-render the detail panel
        when the expand/collapse state changes.
        """
        self._on_rebuild = callback

    # ------------------------------------------------------------------
    # Field factories
    # ------------------------------------------------------------------

    def _create_simple_field(
        self,
        row: pd.Series,
        label: str,
        key: str,
        multiline: bool = False,
        min_lines: int = 1,
        max_lines: int = 1,
    ) -> ft.Container:
        value = str(row.get(key, ""))
        field = ft.TextField(
            value=value,
            label=label,
            multiline=multiline,
            min_lines=min_lines,
            max_lines=max_lines,
            border_color=DesignTokens.TEXT_MUTED,
            focused_border_color=DesignTokens.ACCENT_PRIMARY,
            label_style=ft.TextStyle(color=DesignTokens.TEXT_SECONDARY),
            text_style=ft.TextStyle(color=DesignTokens.TEXT_PRIMARY),
            cursor_color=DesignTokens.ACCENT_PRIMARY,
            expand=True,
            on_change=lambda e, k=key: self._on_field_change(k, e.control.value),
        )
        self._fields[key] = field
        return ft.Container(
            content=ft.Row(controls=[field], expand=True),
            padding=ft.Padding.only(bottom=10),
        )

    def _create_compact_field(
        self,
        row: pd.Series,
        label: str,
        key: str,
    ) -> ft.Container:
        value = str(row.get(key, ""))
        field = ft.TextField(
            value=value,
            label=label,
            border_color=DesignTokens.TEXT_MUTED,
            focused_border_color=DesignTokens.ACCENT_PRIMARY,
            label_style=ft.TextStyle(color=DesignTokens.TEXT_SECONDARY, size=12),
            text_style=ft.TextStyle(color=DesignTokens.TEXT_PRIMARY, size=13),
            cursor_color=DesignTokens.ACCENT_PRIMARY,
            dense=True,
            on_change=lambda e, k=key: self._on_field_change(k, e.control.value),
        )
        self._fields[key] = field
        return ft.Container(content=field, expand=True)

    def _create_field_with_audio(
        self,
        label: str,
        key: str,
        value: str,
        multiline: bool = False,
        min_lines: int = 1,
        max_lines: int = 1,
    ) -> ft.Container:
        field = ft.TextField(
            value=value,
            label=label,
            multiline=multiline,
            min_lines=min_lines,
            max_lines=max_lines,
            border_color=DesignTokens.TEXT_MUTED,
            focused_border_color=DesignTokens.ACCENT_PRIMARY,
            label_style=ft.TextStyle(color=DesignTokens.TEXT_SECONDARY),
            text_style=ft.TextStyle(color=DesignTokens.TEXT_PRIMARY),
            cursor_color=DesignTokens.ACCENT_PRIMARY,
            expand=True,
            on_change=lambda e, k=key: self._on_field_change(k, e.control.value),
        )
        self._fields[key] = field

        loading = ft.ProgressRing(width=16, height=16, stroke_width=2, visible=False)
        self._audio_loading[key] = loading

        status_indicator = ft.Container(content=None, width=20, height=20)
        self._audio_status_indicators[key] = status_indicator

        audio_btn = ft.IconButton(
            icon=ft.Icons.VOLUME_UP_ROUNDED,
            icon_color=DesignTokens.ACCENT_TEAL,
            icon_size=20,
            tooltip="Generate & Play Audio",
            on_click=lambda e, k=key, f=field: self._on_generate_audio(k, f.value),
        )

        return ft.Container(
            content=ft.Row(
                controls=[field, loading, status_indicator, audio_btn],
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
        field = ft.TextField(
            value=value,
            label=label,
            multiline=True,
            min_lines=2,
            max_lines=4,
            border_color=DesignTokens.TEXT_MUTED,
            focused_border_color=DesignTokens.ACCENT_PRIMARY,
            label_style=ft.TextStyle(color=DesignTokens.TEXT_SECONDARY),
            text_style=ft.TextStyle(color=DesignTokens.TEXT_PRIMARY),
            cursor_color=DesignTokens.ACCENT_PRIMARY,
            expand=True,
            on_change=lambda e, k=key: self._on_field_change(k, e.control.value),
        )
        self._fields[key] = field
        self._image_prompt_field = field

        self._image_gen_button = ft.IconButton(
            icon=ft.Icons.AUTO_AWESOME,
            icon_color=DesignTokens.ACCENT_PRIMARY,
            icon_size=20,
            tooltip="Generate Image",
            on_click=lambda e: self._on_generate_image(
                self._image_prompt_field.value if self._image_prompt_field else ""
            ),
        )

        return ft.Container(
            content=ft.Row(
                controls=[field, self._image_gen_button],
                spacing=5,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            ),
            padding=ft.Padding.only(bottom=10),
        )

    # ------------------------------------------------------------------
    # Audio generation & playback
    # ------------------------------------------------------------------

    def _on_generate_audio(self, key: str, text: str) -> None:
        if not text or not text.strip():
            self._show_snackbar("No text to generate audio for", error=True)
            return
        self.page.run_task(self._generate_audio_async, key, text)

    async def _generate_audio_async(self, key: str, text: str) -> None:
        self._last_audio_key = key
        indicator = self._audio_status_indicators.get(key)
        try:
            if key in self._audio_loading:
                self._audio_loading[key].visible = True
            if indicator:
                indicator.content = ft.ProgressRing(width=14, height=14, stroke_width=2)
            self.page.update()

            temp_dir = tempfile.gettempdir()
            audio_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            temp_path = os.path.join(temp_dir, f"ankitect_audio_{audio_hash}.mp3")

            success = await self._audio_fetcher.fetch(text, temp_path, volume="+30%")

            if success and os.path.exists(temp_path):
                self._current_audio_path = temp_path
                if indicator:
                    indicator.content = ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=16, color=DesignTokens.ACCENT_SUCCESS)
                self.page.update()
                self._play_audio_file(temp_path)
                self._show_snackbar("Audio generated successfully!")
            else:
                if indicator:
                    indicator.content = ft.Icon(ft.Icons.ERROR_ROUNDED, size=16, color=DesignTokens.ACCENT_DANGER)
                self._show_snackbar("Failed to generate audio", error=True)

        except Exception as e:
            if indicator:
                indicator.content = ft.Icon(ft.Icons.ERROR_ROUNDED, size=16, color=DesignTokens.ACCENT_DANGER)
            self._show_snackbar(f"Error: {str(e)}", error=True)

        finally:
            if key in self._audio_loading:
                self._audio_loading[key].visible = False
            self.page.update()
            if indicator:
                self.page.run_task(self._auto_clear_status, key)

    def _play_audio_file(self, file_path: str) -> None:
        try:
            abs_path = os.path.abspath(file_path)
            if self._audio_player:
                try:
                    self._audio_player.pause()
                except Exception:
                    pass
                self.page.overlay[:] = [
                    ctrl for ctrl in self.page.overlay
                    if not isinstance(ctrl, ft.Audio)
                ]

            self._audio_player = ft.Audio(
                src=abs_path,
                autoplay=True,
                volume=1.0,
                balance=0,
                on_state_changed=lambda e: self._on_audio_state_changed(e),
            )
            self.page.overlay.append(self._audio_player)
            self.page.update()

        except Exception:
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
        key = self._last_audio_key
        if key and key in self._audio_status_indicators:
            indicator = self._audio_status_indicators[key]
            state = str(e.data) if e.data else ""
            if "completed" in state.lower():
                indicator.content = ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=16, color=DesignTokens.ACCENT_SUCCESS)
                self.page.update()
                self.page.run_task(self._auto_clear_status, key)
            elif "playing" in state.lower():
                indicator.content = ft.Icon(ft.Icons.PLAY_CIRCLE_ROUNDED, size=16, color=DesignTokens.ACCENT_TEAL_LIGHT)
                self.page.update()

    async def _auto_clear_status(self, key: str) -> None:
        await asyncio.sleep(4)
        if key in self._audio_status_indicators:
            self._audio_status_indicators[key].content = None
            self.page.update()

    # ------------------------------------------------------------------
    # Image generation
    # ------------------------------------------------------------------

    def _on_generate_image(self, prompt: str) -> None:
        if self._is_generating_image:
            return
        if not prompt or not prompt.strip():
            self._show_snackbar("No prompt to generate image from", error=True)
            return
        self.page.run_task(self._generate_image_async, prompt)

    async def _generate_image_async(self, prompt: str) -> None:
        try:
            self._is_generating_image = True
            if self._image_gen_button:
                self._image_gen_button.disabled = True
            if self._image_container:
                self._image_container.content = ft.Column(
                    controls=[
                        ft.ProgressRing(width=40, height=40, stroke_width=3),
                        ft.Text("Generating image...", size=12, color=DesignTokens.ACCENT_PRIMARY),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                )
            self.page.update()

            temp_dir = tempfile.gettempdir()
            img_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
            temp_path = os.path.join(temp_dir, f"ankitect_img_{img_hash}.jpg")

            success = await self._image_fetcher.fetch(prompt, temp_path)

            if success and os.path.exists(temp_path):
                abs_image_path = os.path.abspath(temp_path)
                if self._image_container:
                    self._image_container.content = ft.Image(
                        src=abs_image_path,
                        fit=ft.BoxFit.CONTAIN,
                        border_radius=10,
                        width=300,
                        height=170,
                    )
                    self.page.update()
                self._set_preview_image(abs_image_path)
                self._show_snackbar("Image generated successfully!")
            else:
                if self._image_container:
                    self._image_container.content = ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.ERROR_OUTLINE, size=48, color=DesignTokens.ACCENT_DANGER),
                            ft.Text("Failed to generate image", size=12, color=DesignTokens.ACCENT_DANGER),
                            ft.Text("Check API key in settings", size=10, color=DesignTokens.TEXT_TERTIARY),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                    )
                self._show_snackbar("Failed to generate image - check API key", error=True)

        except Exception as e:
            if self._image_container:
                self._image_container.content = ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.ERROR_OUTLINE, size=48, color=DesignTokens.ACCENT_DANGER),
                        ft.Text(f"Error: {str(e)[:40]}", size=11, color=DesignTokens.ACCENT_DANGER),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                )
            self._show_snackbar(f"Error: {str(e)}", error=True)

        finally:
            self._is_generating_image = False
            if self._image_gen_button:
                self._image_gen_button.disabled = False
            self.page.update()
