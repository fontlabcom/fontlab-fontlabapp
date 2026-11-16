# this_file: tests_docs/test_site.py
"""Check the actual generated payload, routes and public source boundaries."""
import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'docs'
PREFIX = '/fontlab-fontlabapp/'
PAGES = ['index.html', 'installation/index.html', 'domains-and-usage/index.html', 'plugmix/index.html', 'development-and-limits/index.html', 'licence/index.html', 'guides/api-map/index.html', 'guides/background-family/index.html', 'guides/runtime-reference/index.html']


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.ids = set()
        self.links = []
        self.text = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        for name in ('href', 'src'):
            if name in attrs:
                self.links.append(attrs[name])

    def handle_data(self, data):
        self.text.append(data)


GUIDE_BODY_HASHES = {'api-map': '311d6882114d4b5fbde14fbf5080ccfab54476d563d84d7dc33a112f16007f35', 'background-family': 'd55418ca1b20226df16e67020a2821130c4900e6c009dea888616e9f9a2ce6c5'}
# b2959925ec7f: reviewed addition of the public fontui.follow_history export.
# cb1cdca: reviewed core.sharing row, writer element_shared re-export and fontui.native constants (Tasks 2-4).
# TMetrics speed: reviewed internal fontui._font_reads row.
# Object JSON: reviewed objects.json_data row.
API_MAP_HISTORY_SERVICE_BODY_HASH = '6df5d2b74375d812890eb9253b7e5bcde5d8caacada996adb5f92f148e052889'
API_MAP_SHARING_ADDITIONS = (
    ('| objects | 335 |', '| objects | 333 |'),
    ('| internal | 77 |', '| internal | 76 |'),
    ('| **Total** | **1025** |', '| **Total** | **1022** |'),
    ('| fontlabapp.objects.json_data | objects | DATA_TYPE, Envelope, GLYPHS_UNDO_TEXT, Item, KINDS, MIME_TYPE, NEEDS_91, PARTIAL_TEXT, Pasted, SHAPES_UNDO_TEXT, as_qbytearray, available, copy_to_clipboard, decode, describe, drop_unicodes, export, filter_layers, load_file, only_glyphs, paste_glyphs, paste_shapes, read_clipboard, rename_glyphs, require_available, save_file, set_advance_width, unicodes, unique_glyph_names, unique_name | FontLab 9.1 object JSON: parse, edit, copy, save and paste glyphs, layers, elements and contours with Undo. | ', ''),
    ('| fontlabapp.fontui._font_reads | internal | FontReads | Whole-font reads that TMetrics keeps while typing and drops on refresh, font change or master change. | ', ''),
    ('collect, element_shared, fmt,', 'collect, fmt,'),
    ('settle, sharing_operation, shown,', 'settle, shown,'),
    ('| fontlabapp.core.sharing | objects | element_shared, sharing_operation | Whether a contour edit would change another glyph: component users of a base glyph do not count as shared outline. | ', ''),
    ('| fontlabapp.fontui.native | objects | Browser, GEOMETRY_ERRORS, ICON_BATCH, ICON_BLIND_ROWS, ICON_FALLBACK_ROWS, ICON_MARGIN, LOG |', '| fontlabapp.fontui.native | objects | Browser |'),
)


class SiteTests(unittest.TestCase):
    def test_all_generated_internal_links_and_fragments_resolve(self):
        for path in SITE.rglob('*.html'):
            for link in Page(path.read_text()).links:
                url = urlsplit(link)
                if url.scheme or url.netloc:
                    continue
                target = unquote(url.path)
                if target.startswith('/'):
                    self.assertTrue(target.startswith(PREFIX), (path, link))
                    dest = SITE / target.removeprefix(PREFIX)
                else:
                    dest = path.parent / target if target else path
                if dest.is_dir():
                    dest = dest / 'index.html'
                self.assertTrue(dest.is_file(), (path, link, dest))
                self.assertTrue(dest.resolve().is_relative_to(SITE.resolve()), link)
                if url.fragment and dest.suffix == '.html':
                    self.assertIn(unquote(url.fragment), Page(dest.read_text()).ids, (path, link))

    def test_pages_have_light_menu_footer_local_search_and_correct_canonical(self):
        for route in PAGES:
            page = Page((SITE / route).read_text())
            with self.subTest(route=route):
                self.assertEqual([attrs.get('mode') for tag, attrs in page.tags if tag == 'fontlab-menu'], ['light'])
                self.assertEqual([attrs.get('mode') for tag, attrs in page.tags if tag == 'fontlab-footer'], ['light'])
                self.assertEqual([attrs.get('data-md-color-scheme') for tag, attrs in page.tags if tag == 'body'], ['default'])
                search = [attrs for tag, attrs in page.tags if attrs.get('data-md-component') == 'search-query']
                self.assertEqual(len(search), 1)
                self.assertFalse(any(attrs.get('data-md-component') == 'palette' for _, attrs in page.tags))
                canonical = [attrs['href'] for tag, attrs in page.tags if attrs.get('rel') == 'canonical']
                self.assertEqual(canonical, ['https://fontlabcom.github.io/fontlab-fontlabapp/' + route.removesuffix('index.html')])

    def test_search_indexes_every_authored_page(self):
        search = json.loads((SITE / 'search/search_index.json').read_text())
        locations = {row['location'].split('#')[0] for row in search['docs']}
        self.assertEqual(locations, {p.removesuffix('index.html') for p in PAGES})
        text = ' '.join(row['text'] for row in search['docs'])
        for term in ('CurrentGlyph', 'Hide All', 'N86', 'INCOMPLETE', 'Stem Thickness', '1025'):
            self.assertIn(term, text)

    def test_attribution_downloads_are_exact_and_no_private_payload_is_published(self):
        for name in ('LICENSE', 'NOTICE', 'examples/LICENSE-native-ui'):
            self.assertEqual((ROOT / name).read_bytes(), (SITE / 'assets' / Path(name).name).read_bytes())
        self.assertTrue((SITE / '.nojekyll').is_file())
        private_markers = (b'/Users/', b'/Volumes/', b'/private/', b'ghp_', b'github_pat_', b'-----BEGIN PRIVATE KEY-----')
        sources = [path.read_bytes() for folder in ('src', 'Scripts', 'glyphs', 'examples') if (ROOT / folder).is_dir() for path in (ROOT / folder).rglob('*.py')]
        for path in SITE.rglob('*'):
            if path.is_file():
                self.assertNotIn('.DS_Store', path.parts)
                self.assertNotIn(path.suffix, ('.py', '.pyi', '.vfpy', '.whl', '.zip'))
                payload = path.read_bytes()
                for marker in private_markers:
                    self.assertFalse(marker in payload, (path, marker))
                for source in sources:
                    if len(source) > 80:
                        self.assertFalse(source in payload, path)

    def test_workflow_builds_every_main_push_and_requalifies_immutable_output(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/docs.yml').read_text())
        events = workflow.get('on', workflow.get(True))
        self.assertEqual(events['push'], {'branches': ['main']})
        self.assertNotIn('concurrency', workflow)
        build = workflow['jobs']['build']
        verify = workflow['jobs']['qualify-generated-output']
        self.assertNotIn('concurrency', build)
        self.assertEqual(verify['needs'], 'build')
        self.assertEqual(build['outputs']['epoch'], '${{ steps.epoch.outputs.value }}')
        for job, epoch in ((build, '${{ steps.epoch.outputs.value }}'), (verify, '${{ needs.build.outputs.epoch }}')):
            build_step = next(s for s in job['steps'] if s.get('run') == 'sh src_docs/build.sh')
            self.assertEqual(build_step['env']['SOURCE_DATE_EPOCH'], epoch)
        self.assertEqual(verify['steps'][0]['with']['ref'], '${{ needs.build.outputs.sha }}')
        self.assertEqual(verify['permissions'], {'contents': 'read'})
        for job in (build, verify):
            runs = '\n'.join(step.get('run', '') for step in job['steps'])
            self.assertIn('sh src_docs/build.sh', runs)
            self.assertIn('--require-hashes -r src_docs/requirements.txt', runs)
        self.assertIn('git diff --exit-code HEAD -- docs', '\n'.join(s.get('run', '') for s in verify['steps']))
        self.assertIn('git ls-files --others -- docs', '\n'.join(s.get('run', '') for s in verify['steps']))
        self.assertFalse(any('publish.sh' in s.get('run', '') for s in verify['steps']))

    def test_private_pages_hold_removes_automatic_request_and_permission(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/docs.yml').read_text())
        self.assertNotIn('pages', workflow['permissions'])
        for name, job in workflow['jobs'].items():
            with self.subTest(job=name):
                self.assertNotIn('pages', job['permissions'])
                commands = '\n'.join(step.get('run', '') for step in job['steps'])
                self.assertNotIn('request-pages.sh', commands)
                self.assertNotIn('/pages/builds', commands)

    def test_complete_module_reporter_and_native_limit_contracts_are_present(self):
        import ast
        import hashlib

        def rendered(route):
            return re.sub(r'\s+', ' ', ''.join(Page((SITE / route / 'index.html').read_text()).text))

        module_map = (ROOT / 'src_docs/md/guides/api-map.md').read_text()
        rows = [line.split('|')[1].strip().strip('`') for line in module_map.splitlines() if line.startswith('| `fontlabapp')]
        actual = set()
        for path in (ROOT / 'src/fontlabapp').rglob('*.py'):
            parts = list(path.relative_to(ROOT / 'src').with_suffix('').parts)
            if parts[-1] == '__init__':
                parts.pop()
            actual.add('.'.join(parts))
        self.assertEqual(len(rows), 1025)
        self.assertEqual(set(rows), actual)
        self.assertEqual(len(rows), len(set(rows)))
        api = rendered('guides/api-map')
        for row in rows:
            self.assertIn(row, api)
        readme = (ROOT / 'README.md').read_text()
        reporter_table = readme.split('| Reporter | Overlay |', 1)[1].split('\n\n', 1)[0]
        reporters = [line.split('|')[1].strip() for line in reporter_table.splitlines() if line.startswith('| ')][1:]
        self.assertEqual(len(reporters), 39)
        plugin_text = rendered('plugmix')
        for name in reporters + ['Delete Small Paths', 'Step and Repeat', 'Smart Select', 'Zoom to Selection', 'View > Reporters', 'Hide All', 'OwnedMenus', 'current native placement, dispatch and teardown remain unverified']:
            self.assertIn(name, plugin_text)
        for name in ('api-map', 'background-family'):
            source = (ROOT / 'src_docs/md/guides' / (name + '.md')).read_text().split('---\n', 2)[-1]
            canonical = re.sub(r'\s+', ' ', re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', source).replace('`', '')).strip()
            if name == 'api-map':
                self.assertEqual(hashlib.sha256(canonical.encode()).hexdigest(), API_MAP_HISTORY_SERVICE_BODY_HASH)
                addition = 'font_browser, follow_history, font_info_editor'
                self.assertEqual(canonical.count(addition), 1)
                canonical = canonical.replace(addition, 'font_browser, font_info_editor', 1)
                for added, frozen in API_MAP_SHARING_ADDITIONS:
                    self.assertEqual(canonical.count(added), 1)
                    canonical = canonical.replace(added, frozen, 1)
            self.assertEqual(hashlib.sha256(canonical.encode()).hexdigest(), GUIDE_BODY_HASHES[name])
        background = rendered('guides/background-family')
        for term in ('N86', 'N92', 'INCOMPLETE', 'Undo', 'Output', 'ShapeImpl::assignStyle'):
            self.assertIn(term, background)
        reference = rendered('guides/runtime-reference')
        for term in ('CurrentGlyph', 'PartialWriteError', 'Issue 210', 'Native qualification remains pending', 'offline test coverage'):
            self.assertIn(term, reference)
        public = ast.parse((ROOT / 'src/fontlabapp/__init__.py').read_text())
        exports = next(ast.literal_eval(node.value) for node in public.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == '__all__' for target in node.targets))
        for name in exports:
            self.assertIn(name, api)
