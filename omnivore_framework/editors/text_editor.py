import os

import wx

from omnivore_framework import OmnivoreEditor
from omnivore_framework.filesystem import fsopen as open

import logging
log = logging.getLogger(__name__)


class TextEditor(OmnivoreEditor):
    name = "text_editor"

    @property
    def is_dirty(self):
        return not self.control.IsEmpty()

    @property
    def can_copy(self):
        return self.control.CanCopy()

    @property
    def can_paste(self):
        return self.control.CanPaste()

    @property
    def can_undo(self):
        return self.control.CanUndo()

    @property
    def can_redo(self):
        return self.control.CanRedo()

    def create_control(self, parent):
        return wx.TextCtrl(parent, -1, style=wx.TE_MULTILINE)

    def load(self, path, mime_info, args=None):
        with open(path, 'r') as fh:
            text = fh.read()

        self.control.SetValue(text)
        self.tab_name = os.path.basename(path)
        if args is not None:
            size = int(args.get('size', -1))
            if size > 0:
                font = self.control.GetFont()
                font.SetPointSize(size)
                self.control.SetFont(font)

    @classmethod
    def can_edit_mime_exact(cls, mime_type):
        return mime_type == "text/plain"

    @classmethod
    def can_edit_mime_generic(cls, mime_type):
        return mime_type.startswith("text/")


class DebugTextEditor(TextEditor):
    name = "debug"

    menubar_desc = [
    ["File", ["New", "new_file"], "open_file", ["Open Recent", "open_recent"], None, "save_file", "save_as", None, "quit"],
    ["Edit", "undo", "redo", None, "copy", "cut", "paste", "paste_rectangular", ["Paste Special", "paste_as_text", "paste_as_hex"], None, "prefs"],
    ["Debug", None, None, None, "debug_text_counting", None, None, None, "debug_text_last_digit", None, "debug_text_size"],
    ["Dynamic", "debug_text_last_digit_dyn"],
    ["Help", "about"],
    ]

    toolbar_desc = [
    "new_file", "open_file", "save_file", None, "undo", "redo", None, "copy", "cut", "paste", "paste_as_text", "paste_as_hex",
    ]

    def load(self, *args, **kwargs):
        TextEditor.load(self, *args, **kwargs)
        self.tab_name = "DEBUG " + self.tab_name

    # won't automatically match anything; must force this editor with the -t
    # command line flag
    @classmethod
    def can_edit_mime_exact(cls, mime_type):
        return False

    @classmethod
    def can_edit_mime_generic(cls, mime_type):
        return mime_type.startswith("text/")
