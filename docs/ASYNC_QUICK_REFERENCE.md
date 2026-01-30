# FLET ASYNC UI PATTERNS - QUICK REFERENCE

## Running Long Async Tasks Without Freezing the UI

---

## ✅ THE SOLUTION (2 Lines)

```python
def _on_build_click(self, e: ft.ControlEvent) -> None:
    """Button click handler - NON-BLOCKING."""
    self.page.run_task(self._run_build_process)  # ← Magic happens here

async def _run_build_process(self) -> None:
    """Your long-running async work."""
    builder = AnkiDeckBuilder(progress_callback=self._handle_progress)
    await builder.build("vocabulary.csv")
```

---

## 🔑 KEY CONCEPTS

### 1. **Non-Blocking Execution**

```python
# ❌ WRONG: Freezes UI
async def _on_build_click(self, e):
    await builder.build()  # UI frozen until complete

# ✅ CORRECT: UI stays responsive
def _on_build_click(self, e):
    self.page.run_task(self._run_build_process)  # Returns immediately
```

### 2. **Real-Time Progress Updates**

```python
def _handle_progress(self, data: Dict[str, Any]) -> None:
    """Called during async operations - updates UI immediately."""
    self._update_progress(data.get("value", 0))
    self.page.update()  # ← Triggers immediate re-render
```

### 3. **Button State Management**

```python
# Disable during build
self._build_button.disabled = True
self.page.update()

# Re-enable after build
self._build_button.disabled = False
self.page.update()
```

---

## 📋 COMPLETE HANDLER TEMPLATE

```python
def _on_build_click(self, e: ft.ControlEvent) -> None:
    """Handle build button click."""
    if self.is_building:
        return
    self.page.run_task(self._run_build_process)

async def _run_build_process(self) -> None:
    """Execute build with full error handling."""
    self.is_building = True
    self._build_button.disabled = True
    self._progress_bar.visible = True
    self.page.update()

    try:
        # Initialize with progress callback
        builder = AnkiDeckBuilder(
            language="EN",
            progress_callback=self._handle_progress
        )

        # Run async build
        success = await builder.build("vocabulary.csv")

        if success:
            # Run blocking export in executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, builder.export)

            # Show success
            self._show_snackbar("Build complete!", ft.Colors.GREEN_400)
        else:
            self._show_snackbar("Build failed!", ft.Colors.RED_400)

    except Exception as e:
        self._show_snackbar(f"Error: {str(e)}", ft.Colors.RED_400)

    finally:
        # Cleanup
        self.is_building = False
        self._build_button.disabled = False
        self._progress_bar.visible = False
        self.page.update()

def _handle_progress(self, data: Dict[str, Any]) -> None:
    """Handle progress updates from builder."""
    if data.get("event") == "progress":
        value = data.get("value", 0)
        self._progress_bar.value = value / 100.0
        self._progress_text.value = f"{value:.0f}%"
        self.page.update()  # ← Critical!
```

---

## 🛠️ HELPER METHODS

### SnackBar Notification

```python
def _show_snackbar(self, message: str, color: str) -> None:
    """Show temporary notification."""
    snackbar = ft.SnackBar(
        content=ft.Text(message, color=ft.Colors.WHITE),
        bgcolor=color,
        duration=3000,
    )
    self.page.overlay.append(snackbar)
    snackbar.open = True
    self.page.update()
```

### Run Blocking I/O

```python
# ✅ CORRECT: Run in executor to avoid blocking
loop = asyncio.get_event_loop()
result = await loop.run_in_executor(None, blocking_function, arg1, arg2)
```

---

## ⚠️ COMMON PITFALLS

| ❌ WRONG                                 | ✅ CORRECT                           |
| ---------------------------------------- | ------------------------------------ |
| `await builder.build()` in sync callback | `self.page.run_task(self._build)`    |
| `async def _on_build_click` → freezes UI | `def _on_build_click` → non-blocking |
| No `page.update()` in progress callback  | Call `page.update()` immediately     |
| Forget `finally` cleanup                 | Always use `try/finally`             |

---

## 🎯 WHY IT WORKS

```
User clicks button
        ↓
_on_build_click() [sync, returns immediately]
        ↓
page.run_task() schedules coroutine
        ↓
Event loop continues processing UI events
        ↓
_run_build_process() executes
        ↓
Progress callbacks → page.update() → UI refreshes
        ↓
Build completes, cleanup runs
```

---

## 📚 SEE ALSO

- **Full Documentation**: [ASYNC_UI_PATTERNS.md](./ASYNC_UI_PATTERNS.md)
- **Complete Example**: [ASYNC_PATTERN_EXAMPLE.py](./ASYNC_PATTERN_EXAMPLE.py)
- **Current Implementation**: [src/ui/dashboard.py](../src/ui/dashboard.py)

---

## 🚀 QUICK START

1. **Button handler**: Use `page.run_task()`
2. **Progress callback**: Pass to builder, call `page.update()`
3. **Cleanup**: Use `try/finally` block
4. **Blocking I/O**: Use `loop.run_in_executor()`

**That's it! Your UI will stay responsive while processing thousands of items. ✨**
