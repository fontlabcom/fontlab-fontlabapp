# this_file: examples/font_browser.py
"""Run inside FontLab with the fontui extra and ufoLib2 installed.

Creates a detached demonstration model and owned widgets only. Replace the
fixture with explicitly acquired live FontParts models to browse documents.
Retain `browser` and call browser.close() before replacing this script's handle.
"""

from ufoLib2 import Font

from fly.ap.fontui import font_browser

font = Font()
font.info.familyName = "Browser demonstration"
font.info.styleName = "Regular"
glyph = font.newGlyph("A")
glyph.width = 600
pen = glyph.getPen()
pen.moveTo((50, 0))
pen.lineTo((300, 700))
pen.lineTo((550, 0))
pen.closePath()

browser = font_browser([font])
browser.widget.resize(850, 1000)
browser.widget.show()
