# this_file: tests/test_editable_choices.py
"""Native edit acknowledgements must retain commit-once and error timing."""
from types import SimpleNamespace as NS
import pytest
import fontlabapp.qt.choices as shared


class Edit:
    def __init__(self, modified=True, fail=None):
        self.modified, self.fail, self.events = modified, fail, []
    def record(self, *event):
        self.events.append(event)
        if event[0] == self.fail: raise RuntimeError(event[0])
    def isModified(self):
        self.record('modified')
        return self.modified
    def setModified(self, flag):
        self.record('ack', flag)
        self.modified = flag
    def lineEdit(self):
        self.record('lineEdit')
        return self
    def setEditText(self, text): self.record('text', text)
    def setEditable(self, flag): self.record('editable', flag)
    def setInsertPolicy(self, policy): self.record('policy', policy)


@pytest.mark.parametrize('args', [(), (0,), (0, 'extra'), ('match',), ('',)])
def test_activation_ignores_string_overload_and_acknowledges_other_native_picks(args):
    edit = Edit()
    assert shared.accept_activation(edit, args) is not bool(args and isinstance(args[0], str))
    assert edit.events == ([] if args and isinstance(args[0], str) else [('lineEdit',), ('ack', False)])


@pytest.mark.parametrize('modified', [False, True])
def test_commit_consumes_only_modified_edit_once(modified):
    edit = Edit(modified)
    assert shared.consume_commit(edit) is modified
    expected = [('modified',)] + ([('ack', False)] if modified else [])
    assert edit.events == expected
    assert not shared.consume_commit(edit)
    assert not edit.modified


@pytest.mark.parametrize('text', ['', 'choice', 'a&b', 'NBSP\u00a0LS\u2028PS\u2029', '𝄞'])
def test_programmatic_combo_text_preserves_exact_string_and_acknowledges_after_write(text):
    edit = Edit()
    shared.set_combo_text(edit, text)
    assert edit.events == [('text', text), ('lineEdit',), ('ack', False)]


def test_configure_makes_combo_editable_before_setting_noinsert_policy():
    edit = Edit()
    shared.configure_combo(edit, 17)
    assert edit.events == [('editable', True), ('policy', 17)]


@pytest.mark.parametrize('function,fail', [('activation','lineEdit'),('activation','ack'),
                                         ('commit','modified'),('commit','ack'),
                                         ('text','text'),('text','lineEdit'),('text','ack'),
                                         ('configure','editable'),('configure','policy')])
def test_native_failure_propagates_without_later_operations(function, fail):
    edit = Edit(fail=fail)
    actions = {'activation': lambda: shared.accept_activation(edit, (1,)),
               'commit': lambda: shared.consume_commit(edit),
               'text': lambda: shared.set_combo_text(edit, 'unchanged'),
               'configure': lambda: shared.configure_combo(edit, 17)}
    with pytest.raises(RuntimeError, match=fail): actions[function]()
    assert edit.events[-1][0] == fail
