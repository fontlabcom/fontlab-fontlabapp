---
this_file: src_docs/md/index.md
---

# FontLab App


`fontlab-fontlabapp` provides the `fontlabapp` package: shared FontLab application, UI, drawing, reporting and guarded editing helpers. It supplies reusable mechanics for Fly, Fontport, Glyport and FontLab scripts. Python 3.11 arm64 is the host target. The package declares Python >=3.11 and requires fontlab-python-pens>=1.0.0. Fontport remains optional through the fontport extra.

The host-free `smallcap_consistency` engine reports exporting case counts, missing and orphan smallcaps, legacy capital/lowercase coverage and two-sided kerning-group differences. The `legacy_lowercase_without_smallcaps` section independently requires an exporting `.sc` glyph even when modern `.smcp` coverage passes. `smallcap_capture.current_report()` lazily captures the current font and master within a shared three-second budget. Export scope is explicitly the `public.skipExportGlyphs` compatibility policy; unknown mappings and ambiguous groups are disclosed. Native qualification remains pending.

Pure utility modules load outside FontLab. Native operations require FontLab's `fontlab`, `FL`, `fontgate`, `fontpr` and PythonQt APIs as used by each operation. Native modules and panels load on demand. General UI belongs here; FontParts/UFO adapters belong in Fontport; Glyphs.app compatibility belongs in Glyport. App never imports Glyport. Optional Fontport imports are confined to `fontui`;
base App still installs without Fontport. Scriptmix scripts and App's own `Scripts/` access App through `fly.ap`.


## Find the right surface

- [Install and use App](installation.md) with the host interpreter and lazy imports.
- [Domains and shared UI](domains-and-usage.md) separates App, Fontport and Glyport responsibilities.
- [Plugmix](plugmix.md) retains all 39 reporter descriptions and four other plugin kinds.
- [Complete API map](guides/api-map.md) lists all 1025 modules and their public names.
- [Complete runtime reference](guides/runtime-reference.md) retains every usage, migration and writer qualification from the maintained README.
- [Background tools](guides/background-family.md) retain their explicit N86 HOLD and N92 source-review blocker.

Source and ordinary Qt checks do not establish native FontLab behavior. Private Pages configuration and publication remain owner-held.
