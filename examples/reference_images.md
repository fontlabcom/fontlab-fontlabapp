---
this_file: examples/reference_images.md
---

# Font reference artwork

Run Font Reference Image Viewer or Font Reference Image Viewer - Bounded Zoom
from Tools in FontLab. The complete paired source workflows open local reference
images, zoom around the scroll center, fit the viewport, restore native size and
print on explicit action. No font data is read or changed. Open cancel and image
decode failure preserve the current view.

Free zoom keeps its scale when leaving Fit and prints the native image at the
printer origin. Bounded Zoom keeps the original threshold overshoot, its original
Normal action enablement behavior and its Fit-exit reset. Its print path only
writes an aspect-fit PDF inside the viewer-owned temporary directory. Closing
removes that temporary output. File/printer/help dialogs are owned and async.
Menus are local to the viewer; no new application event loop or Qt runtime is
started. Native PythonQt/printer and full-font acceptance remain pending.

```python
from fly.ap.qt.images.viewer.model import show_bounded
show_bounded()
```
