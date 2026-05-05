import json
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Optional dependency (used for real mouse position + executing actions)
try:
    import pyautogui
    pyautogui.FAILSAFE = True  # Move mouse to top-left to abort automation
except Exception:
    pyautogui = None

if pyautogui is None:
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], check=True)
        import pyautogui
        pyautogui.FAILSAFE = True
    except Exception as e:
        print(f"Failed to install dependencies: {e}")

# Global hotkey support (ESC to stop even when app not focused)
try:
    from pynput import keyboard as pynput_keyboard
except Exception:
    pynput_keyboard = None

if pynput_keyboard is None:
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], check=True)
        from pynput import keyboard as pynput_keyboard
    except Exception as e:
        print(f"Failed to install dependencies: {e}")


def parse_xy(text: str):
    """
    Parse coordinates from a variety of text formats.

    Accepts values like "1300 x 1200", "1300,1200", "1300 1200", or "(1300, 1200)".
    Returns a tuple of integers (x, y) or raises ValueError when the input is invalid.
    """
    t = text.strip().lower()
    for ch in "()[]":
        t = t.replace(ch, "")
    t = t.replace("x", " ").replace(",", " ")
    parts = [p for p in t.split() if p]
    if len(parts) < 2:
        raise ValueError(f"Need two numbers for X and Y, input {text}")
    x = int(float(parts[0]))
    y = int(float(parts[1]))

    return x, y


class ActionRow:
    """A row in the action list that contains an action type, parameters, and delay."""

    ACTIONS = ["Click", "Mouse Move", "Send Key"]

    def __init__(self, parent, index, remove_callback, reorder_callback, status_setter, set_active_callback):
        """Create an action row widget and wire its interaction callbacks."""
        self.parent = parent
        self.remove_callback = remove_callback
        self.reorder_callback = reorder_callback
        self.status_setter = status_setter
        self.set_active_callback = set_active_callback
        self.frame = tk.Frame(parent, bd=0)

        # Drag handle
        self.drag_handle = tk.Label(self.frame, text="≡", width=2, cursor="fleur")
        self.drag_handle.grid(row=0, column=0, padx=(2, 4))
        self.drag_handle.bind("<ButtonPress-1>", self._drag_start)
        self.drag_handle.bind("<B1-Motion>", self._drag_motion)
        self.drag_handle.bind("<ButtonRelease-1>", self._drag_end)

        # Index label
        self.lbl_index = tk.Label(self.frame, width=4, anchor="center")
        self.lbl_index.grid(row=0, column=1, padx=5)

        # Action type combobox
        self.action_var = tk.StringVar(value="Click")
        self.cmb_action = ttk.Combobox(
            self.frame,
            textvariable=self.action_var,
            values=self.ACTIONS,
            width=14,
            state="readonly"
        )
        self.cmb_action.grid(row=0, column=2, padx=5)

        # Parameter entry field
        self.param_entry = tk.Entry(self.frame, width=18)
        self.param_entry.insert(0, "1300 x 1200")
        self.param_entry.grid(row=0, column=3, padx=5)
        self.param_entry.bind("<FocusIn>", lambda e: self.set_active_callback(self))
        self.param_entry.bind("<Button-1>", lambda e: self.set_active_callback(self))

        # Per-row delay entry
        self.delay_var = tk.StringVar(value="0.0")
        self.delay_entry = tk.Entry(self.frame, width=8, textvariable=self.delay_var)
        self.delay_entry.grid(row=0, column=4, padx=5)

        # Remove button
        self.btn_remove = tk.Button(self.frame, text="-", width=3, command=self.remove)
        self.btn_remove.grid(row=0, column=6, padx=5)

        self._dragging = False
        self._drag_last_y = None

        self.update_index(index)

    def update_index(self, index):
        """Update the displayed row index label."""
        self.lbl_index.config(text=str(index))

    def highlight(self, on=True):
        """Highlight or reset the row background for visual feedback."""
        bg = "#d9edf7" if on else self.parent.cget("bg")
        self.frame.config(bg=bg)
        for w in (self.drag_handle, self.lbl_index, self.btn_remove):
            try:
                w.config(bg=bg)
            except Exception:
                pass

    def get_data(self):
        """Return the row data payload, normalizing the delay value."""
        try:
            d = float(self.delay_var.get().strip() or "0")
            if d < 0:
                d = 0.0
        except Exception:
            d = 0.0

        return {
            "action": self.action_var.get(),
            "param": self.param_entry.get().strip(),
            "delay": d
        }

    def set_data(self, data):
        """Populate the row fields from a saved action dictionary."""
        self.action_var.set(data.get("action", "Click"))
        self.param_entry.delete(0, tk.END)
        self.param_entry.insert(0, data.get("param", "0 x 0"))
        self.delay_var.set(str(data.get("delay", 0.0)))

    def remove(self):
        """Remove this row from the UI and notify the application."""
        self.remove_callback(self)
        self.frame.destroy()

    def pick_mouse(self):
        """Use the current mouse position to fill the row's parameter field."""
        x, y = self._get_mouse_pos()
        self.param_entry.delete(0, tk.END)
        self.param_entry.insert(0, f"{x} x {y}")
        self.status_setter(f"Picked position: {x} x {y}")

    def set_highlight(self, enabled: bool, color: str):
        """Apply or remove a highlight color on the row and its child widgets."""
        bg = color if enabled else self.frame.master.cget("bg")
        self.frame.configure(bg=bg)
        for w in self.frame.winfo_children():
            try:
                w.configure(bg=bg)
            except tk.TclError:
                pass

    def _get_mouse_pos(self):
        """Return the current mouse position using pyautogui if available, else Tkinter pointer coords."""
        if pyautogui is not None:
            p = pyautogui.position()
            return int(p.x), int(p.y)
        x = self.frame.winfo_pointerx()
        y = self.frame.winfo_pointery()
        return int(x), int(y)

    # ---- Drag & Drop ----
    def _drag_start(self, event):
        """Begin drag operation and provide visual drag feedback."""
        self._dragging = True
        self._drag_last_y = event.y_root
        self.highlight(True)
        self.status_setter("Drag to reorder...")

    def _drag_motion(self, event):
        """Notify the application to attempt a reorder as the mouse moves."""
        if not self._dragging:
            return
        self.reorder_callback(self, event.y_root)

    def _drag_end(self, event):
        """Finish the drag operation and restore the row appearance."""
        if not self._dragging:
            return
        self._dragging = False
        self._drag_last_y = None
        self.highlight(False)
        self.status_setter("Ready")


class ActionApp(tk.Tk):
    """Main application window for editing and running action sequences."""

    def __init__(self):
        """Initialize the main application, build the UI, and start mouse tracking."""
        super().__init__()
        self.title("Action Editor")
        self.geometry("540x600")

        self.actions = []
        self._runner_thread = None
        self._stop_event = threading.Event()
        self._mouse_update_job = None

        self.create_menu()
        self.create_toolbar()
        self.create_main_ui()
        self.create_status_bar()

        self.active_row = None
        self._ctrl_down = False
        self._global_ctrl_down = False

        self.setup_hotkeys()

        self.ROW_BG_NORMAL = self.scrollable_frame.cget("bg")
        self.ROW_BG_ACTIVE = "#cce5ff"

        for _ in range(3):
            self.add_action()

        self.start_mouse_status_updates()

    # ---------------- UI ----------------
    def create_menu(self):
        """Build the application menu bar with file, action, and help commands."""
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New", command=self.new_project)
        file_menu.add_command(label="Load JSON...", command=self.load_json)
        file_menu.add_command(label="Save JSON...", command=self.save_json)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_exit)

        action_menu = tk.Menu(menubar, tearoff=0)
        action_menu.add_command(label="Add Action", command=self.add_action)
        action_menu.add_separator()
        action_menu.add_command(label="Run", command=self.run_actions)
        action_menu.add_command(label="Stop", command=self.stop_actions)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.about)

        menubar.add_cascade(label="File", menu=file_menu)
        menubar.add_cascade(label="Action", menu=action_menu)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def create_toolbar(self):
        """Create the toolbar for run settings, delay, repeat, and loop options."""
        bar = tk.Frame(self)
        bar.pack(fill="x", padx=10, pady=(8, 0))

        tk.Label(bar, text="Start delay (s):").pack(side="left")
        self.start_delay_var = tk.StringVar(value="2.0")
        tk.Entry(bar, width=8, textvariable=self.start_delay_var).pack(side="left", padx=(4, 12))

        tk.Label(bar, text="Repeat:").pack(side="left")
        self.repeat_var = tk.StringVar(value="1")
        tk.Entry(bar, width=6, textvariable=self.repeat_var).pack(side="left", padx=(4, 12))

        self.loop_var = tk.BooleanVar(value=False)
        tk.Checkbutton(bar, text="Loop forever", variable=self.loop_var).pack(side="left", padx=(0, 12))

        self.btn_run = tk.Button(bar, text="Run", width=10, command=self.run_actions)
        self.btn_run.pack(side="left", padx=(0, 8))

        self.btn_stop = tk.Button(bar, text="Stop", width=10, command=self.stop_actions, state="disabled")
        self.btn_stop.pack(side="left")

        tipFrame = tk.Frame(self)
        tipFrame.pack(fill="x", padx=10, pady=(8, 0))
        tip_msg = (
            "Tips:\n"
            "    ESC to stop run, Ctrl to update (X,Y) parameter\n"
            "    Send Key format: 1|enter|hotkey:ctrl+v|hotkey:alt+tab|type:VIN123456789\n"
        )
        tk.Label(tipFrame, text=tip_msg, anchor="w", justify="left").pack(fill="x")

    def create_main_ui(self):
        """Create the main scrollable action list UI and add controls."""
        container = tk.Frame(self)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        header = tk.Frame(container)
        header.pack(fill="x")

        tk.Label(header, text="", width=2).grid(row=0, column=0)
        tk.Label(header, text="#", width=4).grid(row=0, column=1)
        tk.Label(header, text="Actions", width=16).grid(row=0, column=2)
        tk.Label(header, text="Parameter (X x Y)", width=20).grid(row=0, column=3)
        tk.Label(header, text="Delay (s)", width=10).grid(row=0, column=4)
        tk.Label(header, text="", width=6).grid(row=0, column=5)
        tk.Label(header, text="", width=3).grid(row=0, column=6)

        self.canvas = tk.Canvas(container)
        self.scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self._canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

        btn_add = tk.Button(
            container,
            text=" + ",
            command=self.add_action
        )
        btn_add.pack(anchor="sw", pady=6)

    def create_status_bar(self):
        """Create a status bar at the bottom of the window."""
        self.status = tk.Label(self, text="Status: Ready", anchor="w", relief="sunken")
        self.status.pack(fill="x", side="bottom")
        self.status.pack_propagate(False)

    # ---------------- Status / Mouse ----------------
    def set_status(self, text):
        """Update the text shown in the status bar."""
        self.status.config(text=f"Status: {text}")

    def start_mouse_status_updates(self):
        """Start periodic updates to display the current mouse position."""
        def update():
            try:
                x, y = self.get_mouse_pos()
                self.status.config(text=f"Status: current mouse position: {x} x {y}")
            except Exception:
                pass
            self._mouse_update_job = self.after(120, update)

        if self._mouse_update_job is None:
            update()

    def get_mouse_pos(self):
        """Return the current mouse coordinates from pyautogui or Tkinter."""
        if pyautogui is not None:
            p = pyautogui.position()
            return int(p.x), int(p.y)
        x = self.winfo_pointerx()
        y = self.winfo_pointery()
        return int(x), int(y)

    # ---------------- Actions list operations ----------------
    def add_action(self):
        """Add a new action row to the list."""
        row = ActionRow(
            self.scrollable_frame,
            len(self.actions) + 1,
            remove_callback=self.remove_action,
            reorder_callback=self.reorder_on_drag,
            status_setter=self.set_status,
            set_active_callback=self.set_active_row
        )

        row.frame.pack(fill="x", pady=2)
        self.actions.append(row)
        self.refresh_indices()

    def remove_action(self, row):
        """Remove an action row from the list and refresh indices."""
        if row is self.active_row:
            self.remove_active_row()
            return
        if row in self.actions:
            row.frame.destroy()
            self.actions.remove(row)
            self.refresh_indices()

    def refresh_indices(self):
        """Recalculate and update index labels for each action row."""
        for i, row in enumerate(self.actions, start=1):
            row.update_index(i)

    def repack_rows(self):
        """Repack rows to reflect their current order in the UI."""
        for row in self.actions:
            row.frame.pack_forget()
        for row in self.actions:
            row.frame.pack(fill="x", pady=2)
        self.refresh_indices()

    # ---------------- Drag & drop reorder ----------------
    def reorder_on_drag(self, dragged_row, y_root):
        """Reorder rows based on the current drag position."""
        frame_y = self.scrollable_frame.winfo_rooty()
        y = y_root - frame_y

        mids = []
        for r in self.actions:
            if not r.frame.winfo_ismapped():
                continue
            ry = r.frame.winfo_y()
            rh = r.frame.winfo_height() or 1
            mids.append((r, ry + rh / 2))

        if len(mids) < 2:
            return

        target_row = min(mids, key=lambda t: abs(t[1] - y))[0]
        if target_row is dragged_row:
            return

        i_from = self.actions.index(dragged_row)
        i_to = self.actions.index(target_row)
        self.actions.insert(i_to, self.actions.pop(i_from))
        self.repack_rows()

        self._autoscroll_if_needed(y_root)

    def _autoscroll_if_needed(self, y_root):
        """Scroll the canvas automatically when dragging near the edges."""
        c_top = self.canvas.winfo_rooty()
        c_bot = c_top + self.canvas.winfo_height()
        margin = 30
        if y_root < c_top + margin:
            self.canvas.yview_scroll(-1, "units")
        elif y_root > c_bot - margin:
            self.canvas.yview_scroll(1, "units")

    # ---------------- Save/Load JSON ----------------
    def get_project_data(self):
        """Collect the current project settings and action rows for saving."""
        actions = [row.get_data() for row in self.actions]
        return {
            "version": 1,
            "settings": {
                "start_delay": float(self.start_delay_var.get() or 0),
                "repeat": int(float(self.repeat_var.get() or 1)),
                "loop": bool(self.loop_var.get())
            },
            "actions": actions
        }

    def apply_project_data(self, data):
        """Load project settings and actions from a saved JSON structure."""
        for r in list(self.actions):
            r.frame.destroy()
        self.actions.clear()

        s = data.get("settings", {})
        self.start_delay_var.set(str(s.get("start_delay", 2.0)))
        self.repeat_var.set(str(s.get("repeat", 1)))
        self.loop_var.set(bool(s.get("loop", False)))

        for item in data.get("actions", []):
            self.add_action()
            self.actions[-1].set_data(item)
        self.repack_rows()

    def save_json(self):
        """Open a file dialog and save the current project to JSON."""
        path = filedialog.asksaveasfilename(
            title="Save actions to JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            data = self.get_project_data()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo("Saved", f"Saved to:{path}")
        except Exception as e:
            messagebox.showerror("Save failed", str(e))

    def load_json(self):
        """Open a file dialog and load a project from JSON."""
        path = filedialog.askopenfilename(
            title="Load actions from JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.apply_project_data(data)
            messagebox.showinfo("Loaded", f"Loaded from:{path}")
        except Exception as e:
            messagebox.showerror("Load failed", str(e))

    def new_project(self):
        """Reset the current project to a new empty action list."""
        if messagebox.askyesno("New", "Clear all actions?"):
            for r in list(self.actions):
                r.frame.destroy()
            self.actions.clear()
            for _ in range(3):
                self.add_action()
            self.start_delay_var.set("2.0")
            self.repeat_var.set("1")
            self.loop_var.set(False)
            self.set_status("New project created")

    # ---------------- Execute actions (pyautogui) ----------------
    def run_actions(self):
        """Start executing the current action list in a background thread."""
        if self._runner_thread and self._runner_thread.is_alive():
            messagebox.showwarning("Running", "Already running. Click Stop first.")
            return

        if pyautogui is None:
            messagebox.showerror(
                "pyautogui not available",
                "pyautogui is not installed or cannot be loaded."
                "Install with: pip install pyautogui"
            )
            return

        try:
            start_delay = float(self.start_delay_var.get() or 0)
            if start_delay < 0:
                start_delay = 0.0
        except Exception:
            start_delay = 0.0

        try:
            repeat = int(float(self.repeat_var.get() or 1))
            if repeat < 1:
                repeat = 1
        except Exception:
            repeat = 1

        loop_forever = bool(self.loop_var.get())
        action_data = [row.get_data() for row in self.actions]

        try:
            for a in action_data:
                act = a.get("action", "")
                if act in ("Click", "Mouse Move"):
                    _ = parse_xy(a.get("param", ""))
                elif act == "Send Key":
                    if not a.get("param", "").strip():
                        raise ValueError("Send Key parameter cannot be empty.")
        except Exception as e:
            messagebox.showerror("Invalid parameter", f"Please fix action parameters.{e}")
            return

        self._stop_event.clear()
        self.btn_run.config(state="disabled")
        self.btn_stop.config(state="normal")

        def worker():
            try:
                t0 = time.time()
                while time.time() - t0 < start_delay:
                    if self._stop_event.is_set():
                        return
                    remaining = start_delay - (time.time() - t0)
                    self.safe_status(f"Starting in {remaining:.1f}s (move mouse to top-left to FAILSAFE)")
                    time.sleep(0.05)

                self.safe_status("Running... (Stop button available; FAILSAFE active)")

                iteration = 0
                while True:
                    iteration += 1
                    if not loop_forever and iteration > repeat:
                        break

                    for idx, a in enumerate(action_data, start=1):
                        if self._stop_event.is_set():
                            return

                        action = a.get("action", "Click")
                        param = a.get("param", "")
                        delay = float(a.get("delay", 0.0) or 0.0)
                        if delay < 0:
                            delay = 0.0

                        if action in ("Click", "Mouse Move"):
                            x, y = parse_xy(param)
                            self.safe_status(f"Step {idx}/{len(action_data)}: {action} @ {x},{y} (delay {delay}s)")

                        if action == "Mouse Move":
                            pyautogui.moveTo(x, y)
                        elif action == "Click":
                            pyautogui.click(x, y)
                        elif action == "Send Key":
                            p = (param or "").strip()
                            if p.lower().startswith("type:"):
                                text = p[5:]
                                pyautogui.write(text)
                            elif p.lower().startswith("hotkey:"):
                                combo = p[7:].strip()
                                combo = combo.replace(",", "+")
                                keys = [k.strip() for k in combo.split("+") if k.strip()]
                                if not keys:
                                    raise ValueError("hotkey: requires keys, e.g. hotkey:ctrl+v")
                                pyautogui.hotkey(*keys)
                            else:
                                pyautogui.press(p)

                        t1 = time.time()
                        while time.time() - t1 < delay:
                            if self._stop_event.is_set():
                                return
                            time.sleep(0.02)

                self.safe_status("Done")
            except Exception as e:
                self.safe_status("Stopped with error")
                self.safe_messagebox_error("Run failed", str(e))
            finally:
                self.after(0, lambda: self.btn_run.config(state="normal"))
                self.after(0, lambda: self.btn_stop.config(state="disabled"))

        self._runner_thread = threading.Thread(target=worker, daemon=True)
        self._runner_thread.start()

    def stop_actions(self):
        """Signal the running action thread to stop."""
        self._stop_event.set()
        self.set_status("Stopping...")

    # Thread-safe UI helpers
    def safe_status(self, text):
        """Schedule a status bar update from a worker thread."""
        self.after(0, lambda: self.set_status(text))

    def safe_messagebox_error(self, title, msg):
        """Show an error messagebox from a worker thread."""
        self.after(0, lambda: messagebox.showerror(title, msg))

    # ---------------- Scroll helpers ----------------
    def _on_mousewheel(self, event):
        """Handle vertical scrolling on Windows and macOS mouse wheel events."""
        delta = -1 * int(event.delta / 120) if event.delta else 0
        if delta == 0:
            delta = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(delta, "units")

    def _on_mousewheel_linux(self, event):
        """Handle Linux mouse wheel scroll events from Button-4 and Button-5."""
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")

    # ---------------- Other ----------------
    def about(self):
        """Show the About dialog describing the Action Editor."""
        msg = (
            "Action Editor\n"
            "Features:\n"
            "- Live mouse position\n"
            "- Save/Load JSON\n"
            "- Execute Click/Mouse Move via pyautogui\n"
            "- Drag & drop reorder\n"
            "- Delay/Repeat/Loop\n"
            "Safety:\n"
            "- pyautogui FAILSAFE enabled (move mouse to top-left)."
        )
        messagebox.showinfo("About", msg)

    def on_exit(self):
        """Stop any running action thread and close the application."""
        self.stop_actions()
        try:
            if getattr(self, "_hotkey_listener", None):
                self._hotkey_listener.stop()
        except Exception:
            pass
        self.destroy()

    def setup_hotkeys(self):
        """Bind keyboard shortcuts and optional global ESC support."""
        self.bind_all("<Escape>", lambda e: self.stop_actions())
        self.bind_all("<KeyPress-Control_L>", self._on_ctrl_press)
        self.bind_all("<KeyRelease-Control_L>", self._on_ctrl_release)
        self.bind_all("<KeyPress-Control_R>", self._on_ctrl_press)
        self.bind_all("<KeyRelease-Control_R>", self._on_ctrl_release)

        self._hotkey_listener = None
        if pynput_keyboard is None:
            self.set_status("ESC stops when window focused (install 'pynput' for global ESC).")
            return

        def on_press(key):
            try:
                if key == pynput_keyboard.Key.esc:
                    self.after(0, self.stop_actions)
            except Exception:
                pass

        self._hotkey_listener = pynput_keyboard.Listener(on_press=on_press)
        self._hotkey_listener.daemon = True
        self._hotkey_listener.start()

    def set_active_row(self, row):
        """Highlight the active row and update the current selection state."""
        if self.active_row and self.active_row is not row:
            self.active_row.set_highlight(False, self.ROW_BG_ACTIVE)
        self.active_row = row
        self.active_row.set_highlight(True, self.ROW_BG_ACTIVE)
        try:
            idx = self.actions.index(row) + 1
            self.set_status(f"Selected row #{idx} (Press Ctrl to Pick)")
        except Exception:
            self.set_status("Selected row (Press Ctrl to Pick)")

    def remove_active_row(self):
        """Remove the currently selected row and select the next available row."""
        row = self.active_row
        if row is None:
            return

        try:
            idx = self.actions.index(row)
        except ValueError:
            self.active_row = None
            self.set_status("Active row not found")
            return

        try:
            row.set_highlight(False, self.ROW_BG_ACTIVE)
        except Exception:
            pass

        row.frame.destroy()
        self.actions.pop(idx)

        new_active = None
        if self.actions:
            if idx < len(self.actions):
                new_active = self.actions[idx]
            else:
                new_active = self.actions[-1]

        self.active_row = None

        if new_active:
            self.set_active_row(new_active)
            try:
                new_idx = self.actions.index(new_active) + 1
                self.set_status(f"Removed row. Selected row #{new_idx}")
            except Exception:
                self.set_status("Removed row")
        else:
            self.set_status("Removed last row")

        self.refresh_indices()

    def pick_to_active_row(self):
        """Fill the active row parameter with the current mouse position."""
        if not self.active_row:
            self.set_status("No active row. Click a Parameter box first.")
            return
        x, y = self.get_mouse_pos()
        self.active_row.param_entry.delete(0, tk.END)
        self.active_row.param_entry.insert(0, f"{x} x {y}")
        self.set_status(f"Picked position to row: {x} x {y}")

    def _on_ctrl_press(self, event=None):
        """Handle Ctrl press to pick the mouse position into the active row."""
        if self._ctrl_down:
            return
        self._ctrl_down = True
        self.pick_to_active_row()

    def _on_ctrl_release(self, event=None):
        """Reset control key state when Ctrl is released."""
        self._ctrl_down = False


if __name__ == "__main__":
    app = ActionApp()
    app.mainloop()
