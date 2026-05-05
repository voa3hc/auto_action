# Action Editor (Tkinter + pyautogui)

A lightweight Python GUI tool to **build, save, and execute UI automation steps** such as mouse clicks, mouse moves, and keyboard input.

---

## Features

- ✅ Scrollable action list (add / remove / reorder)
- ✅ Actions:
  - **Click** (mouse click at X,Y)
  - **Mouse Move** (move mouse to X,Y)
  - **Send Key** (press keys, hotkeys, or type text)
- ✅ **Ctrl key** → Pick current mouse position into selected row
- ✅ **ESC key** → Stop execution (emergency stop)
- ✅ Drag & drop row reordering
- ✅ Per‑action delay
- ✅ Start delay, repeat count, loop forever
- ✅ Save / Load actions to **JSON**
- ✅ Live mouse position in status bar

---

## Requirements

```bash
pip install pyautogui pynput
