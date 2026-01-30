"""
AnkiTect: Modern GUI Application
--------------------------------

A macOS-inspired Flet interface for the AnkiTect deck builder.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path for absolute imports
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import flet as ft
from typing import Callable, Dict, Optional

from src.ui.workbench import WorkbenchView
from src.ui.dashboard import DashboardView
from src.ui.settings import SettingsView


# =============================================================================
# NAVIGATION RAIL (SIDEBAR)
# =============================================================================

def create_navigation_rail(
    on_change: Callable[[int], None],
    selected_index: int = 0
) -> ft.NavigationRail:
    """
    Create the main navigation sidebar.
    
    Args:
        on_change: Callback when navigation selection changes
        selected_index: Currently selected index
        
    Returns:
        Configured NavigationRail control
    """
    return ft.NavigationRail(
        selected_index=selected_index,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=200,
        extended=True,
        group_alignment=-0.9,  # Align items toward top
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.Icons.DASHBOARD_OUTLINED,
                selected_icon=ft.Icons.DASHBOARD_ROUNDED,
                label="Dashboard",
                padding=ft.Padding.symmetric(vertical=8),
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.BUILD_OUTLINED,
                selected_icon=ft.Icons.BUILD_ROUNDED,
                label="Workbench",
                padding=ft.Padding.symmetric(vertical=8),
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.SETTINGS_OUTLINED,
                selected_icon=ft.Icons.SETTINGS_ROUNDED,
                label="Settings",
                padding=ft.Padding.symmetric(vertical=8),
            ),
        ],
        on_change=lambda e: on_change(e.control.selected_index),
        bgcolor="transparent",
    )


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class AnkiTectApp:
    """Main application controller."""
    
    def __init__(self, page: ft.Page) -> None:
        """
        Initialize the application.
        
        Args:
            page: Flet page instance
        """
        self.page = page
        self._setup_page()
        self._init_views()
        self._build_ui()
    
    def _setup_page(self) -> None:
        """Configure page settings and theme."""
        self.page.title = "AnkiTect"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = "#121212"  # Deep dark gray (not dirty black)
        self.page.theme = ft.Theme(
            color_scheme_seed="#7C4DFF",  # Slightly desaturated purple
            font_family="Inter, Roboto, Segoe UI, sans-serif",
        )
        self.page.padding = 0
        self.page.spacing = 0
        self.page.window.min_width = 1000
        self.page.window.min_height = 650
        self.page.window.width = 1280
        self.page.window.height = 850
    
    def _init_views(self) -> None:
        """Initialize all view containers."""
        # Create dashboard view with page reference for build process
        self.dashboard = DashboardView(self.page)
        
        # Create workbench view with page reference for updates
        self.workbench = WorkbenchView(self.page)
        
        # Create settings view with page reference
        self.settings = SettingsView(self.page)
        
        self.views: Dict[int, ft.Container] = {
            0: self.dashboard.container,
            1: self.workbench.container,
            2: self.settings.container,
        }
        self.current_view_index: int = 0        
        # Set up drag & drop handler for CSV files
        self.page.on_drop = self._on_file_drop
    
    def _on_file_drop(self, e) -> None:
        """Handle file drop events."""
        if e.data:
            # FileDrop event returns file paths as data
            file_path = e.data
            if file_path.lower().endswith('.csv'):
                # Import CSV through dashboard
                self.dashboard._import_csv(file_path)
            else:
                self.dashboard._show_snackbar("Please drop a CSV file", error=True)    
    def _build_ui(self) -> None:
        """Build the main UI layout."""
        # Content area container with subtle shadow
        self.content_area = ft.Container(
            content=self.views[0],
            expand=True,
            padding=24,
            border_radius=ft.BorderRadius.only(
                top_left=16,
                bottom_left=16,
            ),
            bgcolor="#1A1A1B",  # Slightly lighter surface for depth
            shadow=ft.BoxShadow(
                spread_radius=-2,
                blur_radius=24,
                color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK),
                offset=ft.Offset(-6, 0),
            ),
        )
        
        # Navigation rail
        self.nav_rail = create_navigation_rail(
            on_change=self._on_nav_change,
            selected_index=0,
        )
        
        # Sidebar container with branding
        sidebar = ft.Container(
            content=ft.Column(
                controls=[
                    # App branding header
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.AUTO_AWESOME,
                                    color=ft.Colors.INDIGO_200,
                                    size=28,
                                ),
                                ft.Text(
                                    "AnkiTect",
                                    size=20,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.WHITE,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=10,
                        ),
                        padding=ft.Padding.only(top=20, bottom=10),
                    ),
                    ft.Divider(height=1, color=ft.Colors.WHITE10),
                    # Navigation rail
                    ft.Container(
                        content=self.nav_rail,
                        expand=True,
                    ),
                    # Version info at bottom
                    ft.Container(
                        content=ft.Text(
                            "v1.0.0",
                            size=11,
                            color=ft.Colors.WHITE24,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        padding=ft.Padding.only(bottom=20),
                        alignment=ft.Alignment(0, 0),
                    ),
                ],
                spacing=0,
            ),
            width=220,
            bgcolor="#161617",  # Deep dark sidebar
        )
        
        # Main layout: Sidebar + Content
        main_layout = ft.Row(
            controls=[
                sidebar,
                ft.VerticalDivider(width=1, color=ft.Colors.WHITE10),
                self.content_area,
            ],
            spacing=0,
            expand=True,
        )
        
        self.page.add(main_layout)
    
    def _on_nav_change(self, index: int) -> None:
        """
        Handle navigation selection change.
        
        Args:
            index: Selected navigation index
        """
        if index == self.current_view_index:
            return
        
        self.current_view_index = index
        self.content_area.content = self.views[index]
        self.page.update()
    
    def navigate_to(self, index: int) -> None:
        """
        Programmatically navigate to a view.
        
        Args:
            index: View index to navigate to
        """
        if 0 <= index < len(self.views):
            self.nav_rail.selected_index = index
            self._on_nav_change(index)


def main(page: ft.Page) -> None:
    """
    Main entry point for Flet application.
    
    Args:
        page: Flet page instance
    """
    import os
    os.makedirs("media", exist_ok=True)
    # CRITICAL: This allows the app to serve files from the media directory
    page.mount_file_path = os.path.abspath("media")
    
    try:
        app = AnkiTectApp(page)
    except Exception:
        import traceback
        error_text = traceback.format_exc()
        page.add(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("UI failed to стартовать", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400),
                        ft.Text("Скопируйте эту ошибку и пришлите мне:", size=12, color=ft.Colors.WHITE70),
                        ft.Container(
                            content=ft.Text(error_text, size=11, selectable=True, color=ft.Colors.WHITE70),
                            padding=10,
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
                            border_radius=8,
                        ),
                    ],
                    spacing=10,
                ),
                padding=20,
            )
        )
        page.update()


if __name__ == "__main__":
    ft.run(main)
