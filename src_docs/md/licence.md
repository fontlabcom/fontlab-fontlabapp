---
this_file: src_docs/md/licence.md
---

# Licence and attribution

## Licence

Licensed under Apache-2.0; all Python sources in `fontlabapp.fontui` also carry Apache-2.0 SPDX identifiers (Issue 204). Bundled third-party code keeps its MIT and BSD-3-Clause notices, and the external native UI example keeps its [proprietary licence](assets/LICENSE-native-ui), so the distribution expression is `Apache-2.0 AND MIT AND BSD-3-Clause AND LicenseRef-Proprietary`. See [LICENSE](assets/LICENSE), [NOTICE](assets/NOTICE) and [MIGRATION.json](https://github.com/fontlabcom/fontlab-fontlabapp/blob/a5a8732e4cdf2cd5a5bfb75f51f33708868cdec3/MIGRATION.json) for source-specific terms and attribution. Retained legacy sources and historical receipts do not grant permission to copy unlicensed third-party bodies into public artifacts.

Raise Ascender reports queued native glyph updates instead of refusing every edit.
FontLab may change those glyphs’ modification dates (issue 8537); the panel retains
that warning even if the edit fails. Source and history-scope checks still apply.
Complete native preservation remains unverified.

Perpendicular Guides discloses queued glyph IDs and FontLab issue 8537’s possible
modification-date changes before writing. A nonempty queue alone does not refuse
the action. Source/history guards remain; native preservation is unverified.

Perpendicular Guides retains ordinary append and finalization failures together
in `fontlabapp.core.history.glyphs.PartialWriteError.errors`. A failure does not imply rollback;
inspect the font and Edit > Undo before another write. Native qualification remains open.

`select_glyphs(add=True)` adds missing glyph names without clearing existing
selection. Already-selected glyphs, including partial duplicate chart-cell
selections, are untouched. If a native addition fails, earlier additions remain
and the original exception propagates. Replacement mode still clears first.


## Exact legal downloads

- [Apache 2.0 licence](assets/LICENSE)
- [Component attribution and retained terms](assets/NOTICE)
- [Proprietary native UI example terms](assets/LICENSE-native-ui)

The distribution expression is `Apache-2.0 AND MIT AND BSD-3-Clause AND LicenseRef-Proprietary`. Component-specific and proprietary example terms remain in force; this documentation grants no broader rights. The site renders maintained prose and public usage snippets, never private implementation bodies, native example code, fonts or private corpora.


## Current English browser payload

The [browser-component record](assets/current-frontend-notices.json) binds the retained MaterialX 10.1.8 browser assets to exact upstream notices, package archives and source maps. Product terms above remain unchanged.

The [English-only omission manifest](assets/english-search-omissions.json) binds all 35 unused lunr-languages 1.20.0 helpers, including Wordcut and TinySegmenter. The build rejects theme/search-language, corpus, vendor-set/hash and local HTML-reference drift before removing them. Nine core vendor assets remain byte-identical. Historical complete outputs remain recovery evidence; omitted helpers are not represented as currently distributed or relicensed.

The main source map retains 211 preferred sources, including 128 exact NPM source matches; the worker map retains 13 sources, including Lunr 2.3.9. The exact clipboard distribution embeds its dependencies; select, good-listener and delegate retain their upstream README MIT link and Zeno Rocha attribution, without invented standalone licence text or dates. CSS maps retain source names without embedded source bodies.

Material Design icons retain the Pictogrammers notice and Apache 2.0 icon terms or specifically stated underlying terms; code is MIT. Font Awesome Free retains Fonticons attribution and CC-BY 4.0 terms. Octicons retains GitHub's MIT notice; Lucide retains ISC and inherited notices. Of 45 observed ordered SVG path tuples, 43 match installed MaterialX icon path tuples exactly, including `fontawesome/solid/caret-down.svg` used by `--md-version-icon`. Its unchanged CSS header identifies Font Awesome Free 7.1.0, Copyright 2025 Fonticons, Inc., and CC-BY-4.0 icon terms; the full Font Awesome notice remains available below. The official Font Awesome 7.1.0 NPM caret SVG has different raw path bytes from the installed icon and CSS. The two unmatched Lucide focus/download tuples retain their pinned SCSS attribution. No unchanged-primary SVG, whole-geometry or optimizer-recipe equivalence is claimed.

FontLab's shared theme and external font responses remain external HTTPS services. Their implementation/font bytes are not copied into this payload; reference notices below do not freeze future responses. Build dependencies and local/hosted publication have separate qualification.

| Component / retained terms | Version | Exact full notice or upstream README licence section |
| --- | --- | --- |
| clipboard | 2.0.11 | [LICENSE.txt](assets/current-frontend/clipboard/LICENSE.txt) |
| tiny-emitter | 2.1.0 | [LICENSE.txt](assets/current-frontend/tiny-emitter/LICENSE.txt) |
| escape-html | 1.0.3 | [LICENSE.txt](assets/current-frontend/escape-html/LICENSE.txt) |
| focus-visible | 5.2.1 | [LICENSE.md.txt](assets/current-frontend/focus-visible/LICENSE.md.txt) |
| rxjs | 7.8.2 | [LICENSE.txt.txt](assets/current-frontend/rxjs/LICENSE.txt.txt) |
| tslib | 2.7.0 | [LICENSE.txt.txt](assets/current-frontend/tslib/LICENSE.txt.txt); [CopyrightNotice.txt.txt](assets/current-frontend/tslib/CopyrightNotice.txt.txt) |
| lunr | 2.3.9 | [LICENSE.txt](assets/current-frontend/lunr/LICENSE.txt) |
| material-design-color | 2.3.2 | [LICENSE.txt](assets/current-frontend/material-design-color/LICENSE.txt) |
| @mdi/svg | 7.4.47 | [LICENSE.txt](assets/current-frontend/@mdi-svg/LICENSE.txt) |
| @fortawesome/fontawesome-free | 7.1.0 | [LICENSE.txt.txt](assets/current-frontend/@fortawesome-fontawesome-free/LICENSE.txt.txt) |
| @primer/octicons | 19.25.0 | [LICENSE.txt](assets/current-frontend/@primer-octicons/LICENSE.txt) |
| lucide-static | 1.11.0 | [LICENSE.txt](assets/current-frontend/lucide-static/LICENSE.txt) |
| select | 1.1.2 | [readme.md.txt](assets/current-frontend/select/readme.md.txt) |
| good-listener | 1.2.2 | [readme.md.txt](assets/current-frontend/good-listener/readme.md.txt) |
| delegate | 3.2.0 | [readme.md.txt](assets/current-frontend/delegate/readme.md.txt) |
| MaterialX10.1.8 | retained terms | [materialx-10.1.8-LICENSE.txt](assets/current-frontend/retained/materialx-10.1.8-LICENSE.txt) |
| Retained corresponding terms | retained terms | [apache-2.0.txt.txt](assets/current-frontend/retained/apache-2.0.txt.txt) |
| Retained corresponding terms | retained terms | [cc-by-4.0.txt.txt](assets/current-frontend/retained/cc-by-4.0.txt.txt) |
| Retained corresponding terms | retained terms | [w3c-focus-visible.txt.txt](assets/current-frontend/retained/w3c-focus-visible.txt.txt) |
| Retained corresponding terms | retained terms | [mit-basecoat-css.txt.txt](assets/current-frontend/retained/mit-basecoat-css.txt.txt) |
| Retained corresponding terms | retained terms | [mit-daisyui.txt.txt](assets/current-frontend/retained/mit-daisyui.txt.txt) |
| Retained corresponding terms | retained terms | [mit-tailwindcss.txt.txt](assets/current-frontend/retained/mit-tailwindcss.txt.txt) |
| Retained corresponding terms | retained terms | [ofl-roboto.txt.txt](assets/current-frontend/retained/ofl-roboto.txt.txt) |
| Retained corresponding terms | retained terms | [ofl-robotomono.txt.txt](assets/current-frontend/retained/ofl-robotomono.txt.txt) |
