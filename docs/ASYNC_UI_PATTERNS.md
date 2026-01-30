# Async UI Patterns for Flet (Flutter for Python)

## Problem Statement

When running long-running async operations (like `builder.build()`) directly from a button callback, the UI thread freezes and progress updates are not rendered until the entire process completes.

## Solution: Non-Blocking Async Execution

### Pattern 1: Using `page.run_task()` (Recommended for Flet)

```python
def _on_build_click(self, e: ft.ControlEvent) -> None:
    """Handle build button click - NON-BLOCKING execution."""
    if self.is_building:
        return

    # ✅ CORRECT: Schedules async work without blocking UI
    self.page.run_task(self._run_build_process)

async def _run_build_process(self) -> None:
    """The actual build logic."""
    self.is_building = True
    self._set_building_state(True)

    try:
        # Long-running async operation
        builder = AnkiDeckBuilder(
            language=Config.CURRENT_LANG,
            progress_callback=self._handle_progress  # ← Critical!
        )

        success = await builder.build(Config.CSV_FILE)

        if success:
            # Show success notification
            self._show_snackbar("Build completed!", ft.Colors.GREEN_400)
        else:
            self._show_snackbar("Build failed!", ft.Colors.RED_400)

    except Exception as e:
        self._show_snackbar(f"Error: {str(e)}", ft.Colors.RED_400)

    finally:
        self.is_building = False
        self._set_building_state(False)
        self.page.update()
```

### Pattern 2: Using `asyncio.create_task()` (Alternative)

```python
def _on_build_click(self, e: ft.ControlEvent) -> None:
    """Alternative using asyncio.create_task()."""
    if self.is_building:
        return

    # ✅ ALSO CORRECT: Creates task in event loop
    asyncio.create_task(self._run_build_process())
```

## Key Concepts

### 1. **Why `page.run_task()` Works**

- **Non-Blocking**: Schedules the coroutine in Flet's event loop without waiting
- **Event Loop Integration**: Allows UI events to be processed during async operations
- **Flet-Native**: Designed specifically for Flet's async architecture

### 2. **Progress Callback Pattern**

The builder emits progress events that trigger immediate UI updates:

```python
def _handle_progress(self, data: Dict[str, Any]) -> None:
    """
    CRITICAL: This callback is invoked from builder's async context.
    Must update UI immediately to show real-time progress.
    """
    event = data.get("event", "")
    message = data.get("message", "")
    value = data.get("value", 0)

    if event == "log":
        self._add_log_entry(message, level="info")
    elif event == "progress":
        self._update_progress(value, message)

    # ✅ CRITICAL: Update UI immediately after each callback
    try:
        self.page.update()
    except Exception:
        pass  # Ignore race conditions during rapid updates
```

### 3. **Button State Management**

```python
def _set_building_state(self, building: bool) -> None:
    """Disable button during build to prevent double-clicks."""
    if self._build_button:
        self._build_button.disabled = building

        if building:
            # Show loading indicator
            self._build_button.content = ft.Row([
                ft.ProgressRing(width=20, height=20),
                ft.Text("Building...", size=18),
            ])
        else:
            # Restore original content
            self._build_button.content = ft.Row([
                ft.Icon(ft.Icons.ROCKET_LAUNCH_ROUNDED, size=24),
                ft.Text("Start Build", size=18),
            ])
```

### 4. **SnackBar Notifications**

```python
def _show_snackbar(self, message: str, color: str) -> None:
    """Show a temporary notification."""
    snackbar = ft.SnackBar(
        content=ft.Text(message, color=ft.Colors.WHITE),
        bgcolor=color,
        duration=3000,  # 3 seconds
    )
    self.page.overlay.append(snackbar)
    snackbar.open = True
    self.page.update()
```

## Complete Example: Robust `_on_build_click` Handler

```python
def _on_build_click(self, e: ft.ControlEvent) -> None:
    """
    Handle build button click - PRODUCTION-READY PATTERN.

    Features:
    - Non-blocking async execution
    - Button state management
    - Progress bar visibility
    - Error handling with user feedback
    - Automatic cleanup
    """
    if self.is_building:
        return

    # Schedule async work without blocking
    self.page.run_task(self._run_build_process)

async def _run_build_process(self) -> None:
    """Execute the build with full error handling."""
    if self.is_building:
        return

    # 1. Lock and disable button
    self.is_building = True
    self._set_building_state(True)

    # 2. Show progress bar
    if self._progress_bar:
        self._progress_bar.visible = True
        self._progress_bar.value = 0

    self.page.update()

    try:
        # 3. Validate preconditions
        if not os.path.exists(Config.CSV_FILE):
            self._show_snackbar(
                f"File not found: {Config.CSV_FILE}",
                ft.Colors.RED_400
            )
            return

        # 4. Initialize builder with progress callback
        builder = AnkiDeckBuilder(
            language=Config.CURRENT_LANG,
            progress_callback=self._handle_progress  # ← Enables real-time updates
        )

        # 5. Run the build (non-blocking)
        success = await builder.build(Config.CSV_FILE)

        if success:
            # 6. Export (blocking I/O - run in executor)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, builder.export)

            # 7. Show success notification
            output_path = os.path.join(
                Config.OUTPUT_DIR,
                f"ankitect_{Config.CURRENT_LANG.lower()}.apkg"
            )
            self._show_snackbar(
                f"✅ Deck exported: {os.path.basename(output_path)}",
                ft.Colors.GREEN_400
            )
            self._show_success_dialog(output_path, builder.stats)
        else:
            # 8. Handle failure
            self._show_snackbar(
                "❌ Build failed. Check logs.",
                ft.Colors.RED_400
            )

    except Exception as e:
        # 9. Handle exceptions
        error_msg = str(e)[:100]  # Truncate long errors
        self._show_snackbar(
            f"Error: {error_msg}",
            ft.Colors.RED_400
        )
        self._add_log_entry(f"Exception: {str(e)}", "error")

    finally:
        # 10. Cleanup (always executed)
        self.is_building = False
        self._set_building_state(False)

        if self._progress_bar:
            self._progress_bar.visible = False

        self.page.update()
```

## Common Pitfalls and Solutions

### ❌ WRONG: Direct `await` in synchronous callback

```python
def _on_build_click(self, e: ft.ControlEvent) -> None:
    # ❌ SyntaxError: 'await' outside async function
    await self._run_build_process()
```

### ❌ WRONG: Blocking the event loop

```python
async def _on_build_click(self, e: ft.ControlEvent) -> None:
    # ❌ FREEZES UI: Blocks event loop until complete
    await builder.build(Config.CSV_FILE)
    self.page.update()  # Only called AFTER build finishes
```

### ✅ CORRECT: Using `page.run_task()`

```python
def _on_build_click(self, e: ft.ControlEvent) -> None:
    # ✅ Non-blocking: UI stays responsive
    self.page.run_task(self._run_build_process)
```

### ✅ CORRECT: Progress callback with immediate updates

```python
def _handle_progress(self, data: Dict[str, Any]) -> None:
    self._update_progress(data.get("value", 0))
    self.page.update()  # ✅ Update immediately
```

## Running Blocking Operations

For CPU-intensive or I/O-blocking operations that aren't async:

```python
# ✅ Run blocking code in thread pool
loop = asyncio.get_event_loop()
result = await loop.run_in_executor(None, blocking_function, arg1, arg2)
```

Example:

```python
# Export is blocking I/O - run in executor
await loop.run_in_executor(None, builder.export)
```

## Summary

| Pattern                            | Use Case              | Blocks UI?          |
| ---------------------------------- | --------------------- | ------------------- |
| `page.run_task(coro)`              | Long async operations | ❌ No               |
| `asyncio.create_task(coro)`        | Background tasks      | ❌ No               |
| `await coro` in sync function      | N/A                   | ⚠️ Syntax Error     |
| `await coro` in async callback     | Direct await          | ✅ Yes - Freezes UI |
| `loop.run_in_executor(None, func)` | Blocking I/O          | ❌ No               |

## Recommended Architecture

```
Button Click (Sync)
    ↓
page.run_task() → Schedules async work
    ↓
Async Build Process
    ↓
Progress Callbacks → Immediate page.update()
    ↓
UI Updates in Real-Time ✨
```

This architecture ensures:

- ✅ Non-blocking UI
- ✅ Real-time progress updates
- ✅ Proper error handling
- ✅ Resource cleanup
- ✅ User feedback via SnackBars
