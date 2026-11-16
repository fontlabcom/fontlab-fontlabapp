# this_file: tests/qt_dialogs_doubles.py
"""Small injected dialog double; no native APIs or application instance."""


class Dialog:
    Information = 1

    def __init__(self, *args):
        self.events = [("construct", args)]
        self.fail = None
        self.accepted = 1
        self.files = ("one", "two")

    def event(self, name, *args):
        self.events.append((name, *args))
        if self.fail == name:
            raise ValueError(name)

    def setText(self, value):
        self.event("text", value)

    def setInformativeText(self, value):
        self.event("informative", value)

    def setIcon(self, value):
        self.event("icon", value)

    def setDetailedText(self, value):
        self.event("detail", value)

    def setStandardButtons(self, value):
        self.event("buttons", value)

    def setWindowTitle(self, value):
        self.event("title", value)

    def setDirectory(self, value):
        self.event("directory", value)

    def setModal(self, value):
        self.event("modal", value)

    def show(self):
        self.event("show")

    def close(self):
        self.event("close")

    def deleteLater(self):
        self.event("delete")

    def exec(self):
        self.event("exec")
        return self.accepted

    def selectedFiles(self):
        self.event("files")
        return self.files
