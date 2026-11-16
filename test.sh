#!/bin/sh
# this_file: test.sh
# Full suite with no setup: sibling checkouts of Fontport and Glyport are
# installed editable and Fly's source is put on PYTHONPATH when they exist
# (the tests for the FontParts editors, Glyport and Fly skip or fail without them).
set -eu
here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
cd "$here"
set -- "$@"
if [ ! -f "$here/../fontlab-python-pens/pyproject.toml" ]; then
    echo "test.sh: no fontlab-python-pens checkout found." >&2
    echo "Place it at $here/../fontlab-python-pens (the suite installs it editable)." >&2
    exit 2
fi
extra="--with-editable $here[test] --with-editable $here/../fontlab-python-pens"
for peer in fontlab-fontport fontlab-glyport; do
    if [ -f "$here/../$peer/pyproject.toml" ]; then
        extra="$extra --with-editable $here/../$peer"
    fi
done
if [ -d "$here/../fontlab-fly/src" ]; then
    PYTHONPATH="$here/../fontlab-fly/src${PYTHONPATH:+:$PYTHONPATH}"
    export PYTHONPATH
fi
# Physical Qt geometry tests assume offscreen; a caller-chosen platform wins.
QT_QPA_PLATFORM="${QT_QPA_PLATFORM-offscreen}"
export QT_QPA_PLATFORM
# $extra is split on purpose: one flag pair per peer.
# shellcheck disable=SC2086
exec uv run --no-project $extra python -m pytest "$@"
