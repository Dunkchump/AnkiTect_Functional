"""Shared design tokens and UI utilities for consistent styling across views."""

import flet as ft


class DesignTokens:
    """Centralized design tokens for the entire application."""

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
    ACCENT_PRIMARY = "#7C4DFF"
    ACCENT_PRIMARY_HOVER = "#9E7AFF"
    ACCENT_SECONDARY = "#536DFE"
    ACCENT_DANGER = "#E57373"
    ACCENT_DANGER_HOVER = "#EF9A9A"
    ACCENT_SUCCESS = "#81C784"
    ACCENT_WARNING = "#FFB74D"
    ACCENT_TEAL = "#14B8A6"
    ACCENT_TEAL_LIGHT = "#5EEAD4"

    # Borders / Dividers
    BORDER_SUBTLE = "#2A2A2C"
    BORDER_DIM = "#FFFFFF1A"        # white 10%
    BORDER_LIGHT = "#FFFFFF3D"      # white 24%

    # Surface overlays
    SURFACE_OVERLAY_2 = "#FFFFFF05"   # white 2%
    SURFACE_OVERLAY_3 = "#FFFFFF08"   # white 3%
    SURFACE_OVERLAY_5 = "#FFFFFF0D"   # white 5%
    SURFACE_OVERLAY_6 = "#FFFFFF0F"   # white 6%
    SURFACE_OVERLAY_8 = "#FFFFFF14"   # white 8%
    SURFACE_OVERLAY_12 = "#FFFFFF1F"  # white 12%

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


def show_snackbar(page: ft.Page, message: str, error: bool = False, icon: str = None) -> None:
    """
    Show a snackbar notification — shared utility for all views.

    Args:
        page: Flet page instance
        message: Notification text
        error: True for error styling, False for success
        icon: Optional icon override
    """
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
        open=True,
    )
    page.overlay.append(snackbar)
    page.update()
