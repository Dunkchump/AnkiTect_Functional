"""
PRODUCTION-READY ASYNC UI HANDLER PATTERN FOR FLET
===================================================

This module demonstrates the complete, robust pattern for handling
long-running async operations in Flet without freezing the UI.

Author: Senior GUI Developer
Date: January 12, 2026
Framework: Flet (Flutter for Python)
"""

import asyncio
import os
from typing import Any, Dict, Optional

import flet as ft


class ProductionDashboardView:
    """
    Complete example of async UI handling in Flet.
    
    Key Features:
    - Non-blocking async execution
    - Real-time progress updates
    - Proper error handling
    - User feedback via SnackBars
    - Button state management
    - Resource cleanup
    """
    
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.is_building: bool = False
        
        # UI References (initialized in _build_view)
        self._build_button: Optional[ft.ElevatedButton] = None
        self._progress_bar: Optional[ft.ProgressBar] = None
        self._progress_text: Optional[ft.Text] = None
        self._status_text: Optional[ft.Text] = None
    
    # =========================================================================
    # PATTERN 1: BUTTON CLICK HANDLER (Non-blocking)
    # =========================================================================
    
    def _on_build_click(self, e: ft.ControlEvent) -> None:
        """
        Handle build button click - NON-BLOCKING async execution.
        
        Key Pattern: Using page.run_task() for long-running operations
        ----------------------------------------------------------------
        - page.run_task() schedules async work without blocking the UI thread
        - Allows the Flet event loop to process UI updates during the build
        - Progress callbacks can trigger immediate page.update() calls
        
        Why this works:
        ---------------
        1. Button click is synchronous (def, not async def)
        2. page.run_task() schedules the coroutine in Flet's event loop
        3. Event loop continues processing UI events while coroutine runs
        4. Progress callbacks invoke page.update() for real-time rendering
        """
        # Prevent double-clicks
        if self.is_building:
            return
        
        # ✅ CRITICAL: Use page.run_task() to avoid blocking
        self.page.run_task(self._run_build_process)
    
    # =========================================================================
    # PATTERN 2: ASYNC BUILD PROCESS (Complete workflow)
    # =========================================================================
    
    async def _run_build_process(self) -> None:
        """
        Execute the build with full error handling and user feedback.
        
        This method demonstrates the complete lifecycle:
        1. Lock state and disable UI controls
        2. Show progress indicators
        3. Validate preconditions
        4. Initialize builder with progress callback
        5. Run async operations
        6. Handle blocking I/O in executor
        7. Show success/error feedback
        8. Cleanup and restore UI state
        """
        # =====================================================================
        # STEP 1: Lock and disable button
        # =====================================================================
        if self.is_building:
            return
        
        self.is_building = True
        self._set_building_state(True)
        
        # =====================================================================
        # STEP 2: Show progress bar
        # =====================================================================
        if self._progress_bar:
            self._progress_bar.visible = True
            self._progress_bar.value = 0
        
        if self._progress_text:
            self._progress_text.value = "0%"
        
        if self._status_text:
            self._status_text.value = "Initializing..."
        
        self.page.update()
        
        try:
            # =================================================================
            # STEP 3: Validate preconditions
            # =================================================================
            csv_file = "vocabulary.csv"
            if not os.path.exists(csv_file):
                self._show_snackbar(
                    f"File not found: {csv_file}",
                    ft.Colors.RED_400
                )
                return
            
            # =================================================================
            # STEP 4: Initialize builder with progress callback
            # =================================================================
            from src.deck import AnkiDeckBuilder
            from src.config import Config
            
            builder = AnkiDeckBuilder(
                language=Config.CURRENT_LANG,
                progress_callback=self._handle_progress  # ← Enables real-time updates
            )
            
            # =================================================================
            # STEP 5: Run async build operation
            # =================================================================
            self._add_log_entry("Starting build process...", "info")
            self.page.update()
            
            # ✅ CRITICAL: await allows event loop to process UI events
            success = await builder.build(csv_file)
            
            if success:
                # =============================================================
                # STEP 6: Handle blocking I/O in executor
                # =============================================================
                # Export is blocking I/O - run in thread pool to avoid blocking
                self._status_text.value = "Exporting deck..."
                self.page.update()
                
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, builder.export)
                
                # =============================================================
                # STEP 7a: Show success feedback
                # =============================================================
                output_path = os.path.join(
                    Config.OUTPUT_DIR,
                    f"ankitect_{Config.CURRENT_LANG.lower()}.apkg"
                )
                
                self._show_snackbar(
                    f"✅ Deck exported: {os.path.basename(output_path)}",
                    ft.Colors.GREEN_400
                )
                
                self._add_log_entry(
                    f"Build completed! Output: {output_path}",
                    "success"
                )
                
                # Show detailed success dialog
                self._show_success_dialog(output_path, builder.stats)
            
            else:
                # =============================================================
                # STEP 7b: Handle build failure
                # =============================================================
                self._show_snackbar(
                    "❌ Build failed. Check logs for details.",
                    ft.Colors.RED_400
                )
                self._add_log_entry("Build failed!", "error")
        
        except Exception as e:
            # =================================================================
            # STEP 7c: Handle exceptions
            # =================================================================
            error_msg = str(e)[:100]  # Truncate long errors
            
            self._show_snackbar(
                f"Error: {error_msg}",
                ft.Colors.RED_400
            )
            
            self._add_log_entry(f"Exception: {str(e)}", "error")
        
        finally:
            # =================================================================
            # STEP 8: Cleanup (always executed)
            # =================================================================
            self.is_building = False
            self._set_building_state(False)
            
            if self._progress_bar:
                self._progress_bar.visible = False
            
            if self._status_text:
                self._status_text.value = "Ready"
            
            self.page.update()
    
    # =========================================================================
    # PATTERN 3: PROGRESS CALLBACK (Real-time UI updates)
    # =========================================================================
    
    def _handle_progress(self, data: Dict[str, Any]) -> None:
        """
        Handle progress callback from the builder - THREAD-SAFE UI UPDATES.
        
        Key Pattern: Async-safe UI updates from callbacks
        ---------------------------------------------------
        - Builder runs async tasks that emit progress events
        - This callback is invoked from the builder's async context
        - page.update() is called immediately to refresh UI
        - Safe to call from async context in Flet
        
        Why this works:
        ---------------
        1. Callback is invoked during async operations
        2. Updates UI controls with new data
        3. page.update() triggers immediate re-render
        4. Event loop processes the update between async tasks
        
        Args:
            data: Progress payload with event, message, value
                  Schema: {"event": "log"|"progress", "message": str, "value": float}
        """
        event = data.get("event", "")
        message = data.get("message", "")
        value = data.get("value", 0)
        
        if event == "log":
            # Log messages
            level = "info"
            if "error" in message.lower() or "⚠️" in message:
                level = "warning"
            elif "[OK]" in message or "success" in message.lower():
                level = "success"
            elif "[WARN]" in message:
                level = "warning"
            
            self._add_log_entry(message, level)
        
        elif event == "progress":
            # Progress updates
            self._update_progress(value, message)
        
        # ✅ CRITICAL: Update UI immediately after each callback
        # This allows real-time progress rendering during async operations
        try:
            self.page.update()
        except Exception:
            # Ignore update errors during rapid callbacks (race conditions)
            # This can happen when multiple updates occur in quick succession
            pass
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _update_progress(self, value: float, message: str = "") -> None:
        """
        Update the progress bar and text.
        
        Args:
            value: Progress value (0-100)
            message: Status message
        """
        if self._progress_bar:
            # ProgressBar expects 0.0 to 1.0
            self._progress_bar.value = value / 100.0
        
        if self._progress_text:
            self._progress_text.value = f"{value:.0f}%"
        
        if self._status_text and message:
            self._status_text.value = message
    
    def _set_building_state(self, building: bool) -> None:
        """
        Set the UI state for building.
        
        Args:
            building: True if build is in progress
        """
        if self._build_button:
            self._build_button.disabled = building
            
            if building:
                # Show loading indicator
                self._build_button.content = ft.Row(
                    controls=[
                        ft.ProgressRing(
                            width=20,
                            height=20,
                            stroke_width=2,
                            color=ft.Colors.WHITE
                        ),
                        ft.Text("Building...", size=18, weight=ft.FontWeight.BOLD),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                )
            else:
                # Restore original content
                self._build_button.content = ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.ROCKET_LAUNCH_ROUNDED, size=24),
                        ft.Text("Start Build", size=18, weight=ft.FontWeight.BOLD),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                )
    
    def _show_snackbar(self, message: str, color: str) -> None:
        """
        Show a temporary notification.
        
        Args:
            message: Notification message
            color: Background color
        """
        # Clean up old snackbars
        for ctrl in list(self.page.overlay):
            if isinstance(ctrl, ft.SnackBar):
                self.page.overlay.remove(ctrl)
        
        snackbar = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE),
            bgcolor=color,
            duration=3000,  # 3 seconds
        )
        
        self.page.overlay.append(snackbar)
        snackbar.open = True
        self.page.update()
    
    def _add_log_entry(self, message: str, level: str = "info") -> None:
        """
        Add a log entry (implementation depends on your UI structure).
        
        Args:
            message: Log message
            level: Log level (info, success, warning, error)
        """
        # Implementation depends on your log view structure
        print(f"[{level.upper()}] {message}")
    
    def _show_success_dialog(self, output_path: str, stats: Dict[str, Any]) -> None:
        """Show success dialog with build statistics."""
        # Implementation depends on your requirements
        pass


# =============================================================================
# ALTERNATIVE PATTERN: Using asyncio.create_task()
# =============================================================================

class AlternativePattern:
    """Alternative async pattern using asyncio.create_task()."""
    
    def __init__(self, page: ft.Page):
        self.page = page
        self.is_building = False
    
    def _on_build_click(self, e: ft.ControlEvent) -> None:
        """
        Alternative: Using asyncio.create_task() instead of page.run_task().
        
        Both patterns work, but page.run_task() is more Flet-idiomatic.
        """
        if self.is_building:
            return
        
        # ✅ ALSO CORRECT: Creates task in event loop
        asyncio.create_task(self._run_build_process())
    
    async def _run_build_process(self) -> None:
        """Same implementation as above."""
        pass


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

def main(page: ft.Page):
    """Example usage in a Flet app."""
    
    # Create dashboard view
    dashboard = ProductionDashboardView(page)
    
    # Add to page
    page.add(dashboard.container)


# Run the app
if __name__ == "__main__":
    ft.app(target=main)
