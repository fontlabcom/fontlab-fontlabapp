---
this_file: src_docs/md/plugmix.md
---

# Plugmix reporters and plugins

## Plugmix

`fontlabapp.plugmix` adds native FontLab 9 plugins: reporter overlays, an
undoable filter, a dockable palette, a native tool and a General menu command.
It uses PythonQt and native per-canvas painters when available, with
`fontlabapp.qt.painting.editor.EditorPainters` on older builds. It imports no
PySide2 and no Glyphs emulation. Importing it does not need FontLab.

Install it once per FontLab session from your own `initScript.py`:

Install [Fly and its matching providers](https://github.com/fontlabcom/fontlab-fly#install)
separately in the same interpreter before plugin startup; Fly 1.3.0 or later
is required. App's source installer writes its startup block without installing
or checking Fly. If Fly is missing, the generated block prints
`FontLab plugins startup:` and skips activation.

```python
try:
    from fly.ap.plugmix import install; install()
except Exception as error: print(f"Plugmix startup: {error}")
```

The Scripts in `fontlab-python-plugmix` (`Install Plugmix Menu`, `Duplicate
Anchor Rings`) call the same `install()`. It appends a View > Reporters submenu
with one checkable action per reporter, a separator and `Hide All` (turns every
reporter off), adds `Plugmix: Delete Small
Paths…` to the Glyph menu, `Plugmix: Step and Repeat Panel` and
`Plugmix: Tool Smart Select` to the Window menu, and `Plugmix: Zoom to
Selection` to the View menu. Choices are saved in
`~/Library/Application Support/FontLab/FontLab 9/Data/fontlab-plugmix.json`
(`enabled`, `enabled_filters`, `enabled_palettes`, `enabled_tools`,
`enabled_general`, last-used `params`). `install(config_dir=...)` selects
another directory. `fontlabapp.plugmix.boot.uninstall()` removes actions,
overlays and panels and keeps the saved choices. Filters, tools and General
plugins start enabled; palettes start hidden. No font data is written.

| Kind | Plugin | Behaviour |
| --- | --- | --- |
| Filter | Delete Small Paths | Deletes closed contours whose flattened path or bounds area is below the threshold (default 400 units²) in selected glyphs of the current master, in one geometry Undo step. Skips shared or transformed outlines and automatic layers. |
| Palette | Step and Repeat | Duplicates selected contours of the active glyph `count` more times, each shifted by another (dx, dy), in one geometry Undo step. Refuses shared or transformed outlines and two zero offsets. |
| Tool | Smart Select | Drag a rectangle to select whole contours touched by any node; Shift toggles. Selection only; it never changes outlines. |
| General | Zoom to Selection | Fits the active glyph's selected nodes in the canvas with a margin. |

Native Tool activation, drag mapping, overlay lifetime, General actions and
font events were verified in FontLab 9. Shortcut handling and keyboard cursor
mapping were later corrected from native findings and still need an in-app
recheck. The palette refresh key reads the glyph modification timestamp and
node selection; confirm that edits outside Plugmix advance that timestamp in
your build.

| Reporter | Overlay |
| --- | --- |
| Duplicate Anchor Rings | Red/yellow rings for every anchor pair less than one unit apart |
| Node Indexes | Contour index beside every node |
| Selected Node Coordinates | Coordinates beside selected nodes |
| Two Point Distance | Segment, length and angle for exactly two selected nodes |
| Off-curve Handles Outside Bounds | Handles beyond the on-curve bounding rectangle |
| Center Lines | Advance/2, x-height/2 and cap-height/2 lines |
| Vertical Metrics | Labelled ascender, descender, x-height, cap-height and baseline |
| Angled Handles | Rings on handles off the horizontal, vertical and italic axes |
| Crosshair | Long guides through selected nodes; no mouse tracking |
| Tops and Bottoms | Rings and y labels at the highest and lowest on-curves |
| Segment Length | Straight and flattened curve lengths |
| Glyph Focus | Shade outside the advance box between descender and ascender |
| Emphasise Selected Handles | Accent lines and rings for handles next to selected nodes |
| Anchor Cloud | Names and positions of the current glyph's anchors (local anchors only) |
| RSB Line | Advance boundary with RSB and LSB labels |
| Unitizer | Vertical grid at UPM / 18 |
| Nodes Close to Zones | Rings on on-curves near zone edges or metric heights |
| Imprecise Italic Angle | Straight segments within 2° of the slant but not on it |
| Smooth Node Angles | Handle-angle mismatch and length ratio at smooth nodes |
| Node Count | Total on- and off-curve nodes; components excluded |
| All Angles | Angle of each straight segment from vertical, mod 180°; components excluded |
| Smart Plumblines | Centre lines through each contour's and the selection's extents; components excluded |
| Show Stems | Rings and span widths along a scan line at half x-height; components excluded |
| Speed Punk | Colour-ramped curvature comb; components excluded |
| Show Rotated | Outline turned 180° about its bounds centre; components excluded |
| Blindfold | Opaque blocks hide the strip from 70 units under the descender up to the baseline, and everything from x-height up to 70 units over the ascender (`band = "cap_height"` for cap height); the band between baseline and that height stays visible |
| Show Label Color | Bar in the glyph's mark colour under the descender (`placement` baseline or body), slanted by the italic angle; layer marks are not distinguished |
| Show Glyphs In Label Color | Glyph and component outlines filled in the mark colour, counters open |
| Show Character | The glyph's first Unicode as 100 px text above the glyph; hidden below 20% zoom; no base-name lookup |
| Rekha Viewer | Head-line bar for Devanagari, Bengali and Gurmukhi letters, moved by `rekha` and `rekha_stop` anchors; suffixed or interrupted anchors are not supported |
| Show Export Status | Red cross over the body of a glyph that is set not to export |
| Show Background | Outlines of the glyph's background layer filled in pale blue (alpha 0.3), counters open; background components are not shown |
| Color Toner | Each component filled in translucent black (`darken = 0.15`, wrapped into 0..1) so composed parts stand out from drawn outlines |
| Show Global Glyph | Contours of a helper glyph named `_global` behind every other glyph: closed paths orange outline with faint fill, open paths blue outline with faint fill; its components are not shown and it is not drawn on itself |
| Show Siblings | Look-alike Latin letters (c/e/o, b/p, d/q/u, h/l/n/r/a) filled in green behind the glyph, fainter in larger groups; Latin groups only |
| Show Kerning Group Reference | Members of the glyph's left kerning class drawn on top of each other as small (0.2) teal silhouettes 150 units left of the glyph, and of its right class 150 units right of it, baseline at half x-height; opacity is 0.8 divided by the class size (floor 0.04), so crowded classes read denser. Left-to-right text only. Very large classes are truncated: at most 32 glyphs are requested, alternating left and right |
| Kern Indicator | Displayed kerning of the pairs touching the glyph, above each junction (orange positive, blue negative); shown only between 3% and 90% zoom |
| Show Interpolation | For each other compatible master, the glyph blended halfway (`factor = 0.5`) node by node between the shown layer and that master, filled in dark magenta (alpha 0.25), counters open; components are not drawn (neither the shown layer's nor the masters'); no instances, anchors or recentering, and masters with the same coordinates are skipped |
| Stem Thickness | Wherever the mouse is (no proximity limit), a line across the outline from the outline point nearest it, perpendicular to it, to the nearer crossing more than 1 unit away, labelled with its rounded length; nothing at a corner where the ray runs along the outline; own contours only, no guide command or modifier key |

Center Lines, Vertical Metrics, Crosshair, Tops and Bottoms, RSB Line,
Unitizer, Node Count, Smart Plumblines, Show Stems, Speed Punk, Show Rotated,
Show Label Color, Show Glyphs In Label Color, Show Character, Rekha Viewer,
Show Background, Color Toner, Show Global Glyph, Show Siblings, Show Kerning
Group Reference and Show Interpolation draw under the native glyph layer when native
canvas painters are available; the rest draw over it, and on older builds all
draw over the canvas.
The original seven reporters, native canvas drawing and all 18 pre-revision
reporters were checked in FontLab 9; Glyph Focus and the revised slant and unit
grid have offline coverage only. Node Count, All Angles, Smart Plumblines, Show
Stems, Speed Punk, Show Rotated, Blindfold, Show Label Color, Show Glyphs In
Label Color, Show Character, Rekha Viewer, Show Export Status, Show Background,
Color Toner, Show Global Glyph, Show Siblings, Show Kerning Group Reference,
Kern Indicator, Show Interpolation and Stem Thickness have offline test coverage
only.

Write a reporter by subclassing `fontlabapp.plugmix.Reporter` with a unique
`name`, a `title` and a pure `compute(snapshot)` that returns `Mark` objects
(`ring`, `line`, `polyline`, `polygon`, `text`) in glyph units; pixel sizes are
view pixels. Set `layer = "background"` to paint under the glyph layer.
An error raised by `compute` or `requested_glyphs` goes to the error sink
once per reporter and message until Plugmix is uninstalled. Every snapshot also carries `identity` (name, Unicodes, raw mark, mark RGB,
export flag) and `view.px_per_unit`; either is None when it cannot be read,
and the read error goes to the plugin error sink once. Mark RGB uses HSL lightness
0.65, so it differs slightly from FontLab's flag swatches (inferred, unverified
natively). Offline coverage only.
Opt-in class flags add costlier data: `needs_components` gives `components`
(base name, transform and decomposed base contours, nested up to 8 levels),
`needs_background` gives `background` (the mask's contours, `()` when empty,
None when there is none), and `needs_masters` gives `masters` (each master's
contours, anchors, advance and a `compatible` flag that compares contour
count, node count per contour and on/off-curve pattern with the shown layer,
ignoring components and open/closed state). Components and masters are cached
per glyph revision and shared by all reporters; components also re-check
their base glyphs. Master outlines may lag until the foreground glyph's
`lastModified` moves, which is unverified natively. The background is read on
every paint. An empty component layer means the master that owns the shown
layer. Metrics also come from that master. Zones and the italic angle need a
master switch to read, so when the shown layer belongs to another master the
zones are empty and the italic slant is the current master's.
Skipped components and failed reads go to the error sink once.
Offline coverage only.
`needs_kerning` gives `kerning_groups` (the classes used when the glyph is a
pair's first member, `left`, and second member, `right`, with their
members), read on every paint because a class edit may not move the glyph's
timestamp. Override `requested_glyphs(identity, kerning_groups=None)` to name up to 32 other
glyphs; `others` maps each one that exists to its own unselected contours
(components skipped), cached per requested glyph's revision. Both use the
master that owns the shown layer. `needs_neighbours` gives
`view.neighbours`: the previous and next glyph on the same line as
`(name, kerning)`, kerning in font units as displayed (0 when kerning
processing is off). Which glyph stores a pair's kerning is inferred,
unverified natively. Neighbours need the native canvas painter backend; with
EditorPainters, or when the view scale is unusable, they are None.
Offline coverage only.
`needs_mouse` gives `view.mouse`, the cursor in the glyph's own units
(`canvas.mousePosition()` mapped back through the glyph and text-block
transforms), or None when the map is not invertible. While any enabled
reporter asks for it, one event filter watches the active glyph window and
flushes (`updateScreenRect` plus `updateViewport`) at most once per 16 ms after
mouse moves, ending with a flush after the last move. The filter goes when the last such reporter is disabled, when the
active canvas changes or closes, and on `uninstall()`. Only the watched canvas
gets a mouse; with EditorPainters it is None. Whether moves reach the filter
under every tool is unverified natively.
Offline coverage only.
Third-party packages publish plugin classes in the `fontlabapp.plugmix`
entry-point group.


## Current reporter menu ownership

View > Reporters uses sorted bare display labels, with a separator and Hide All at the end. Hide All saves the disabled reporter state and resynchronises checkmarks; a failed save retains the previous persisted state. Boot installs this submenu after the other plugin kinds. `fontlabapp.qt.menus.OwnedMenus` owns the submenu and its action tokens. Removing a submenu removes its owned tokens before Qt deletes their parent, including removal requested during a child callback. Standalone Qt and PythonQt-shaped regression checks cover this lifecycle; current native placement, dispatch and teardown remain unverified.

## Planned plugin ownership (Issue 210)

The `fontlabapp.plugmix` APIs above are current Issue 209 source. Issue 210 requests framework, scaffolding, discovery, registration and lifecycle under `fontlabapp.plugins`, with concrete bundles in Plugmix Extensions. Keep existing APIs usable until all callers migrate. Qualify bundle discovery, Reporters palette and View > Reporters, toolbar and Tools > Tool, Window > Panels, and a preservation-safe `initScript.py` installer hook. The target path is not yet a supported current import.
