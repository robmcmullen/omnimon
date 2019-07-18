""" Action definitions for Jumpman Task

"""
import os
import sys

import wx
import numpy as np

from sawx.ui.dialogs import prompt_for_hex, prompt_for_string, ChooseOnePlusCustomDialog
from sawx.utils.textutil import text_to_int

from .. import errors
from ..commands import SetRangeValueCommand
from ..viewers.actions import ViewerAction


import logging
log = logging.getLogger(__name__)


def trigger_dialog(event, segment_viewer, obj):
    model = segment_viewer.segment.jumpman_playfield_model
    possible_labels = model.get_triggers()
    label = model.get_trigger_label(obj.trigger_function)
    if label is None and obj.trigger_function:
        custom_value = "%04x" % obj.trigger_function
    else:
        custom_value = ""
    dlg = ChooseOnePlusCustomDialog(event.task.window.control, list(possible_labels.keys()), label, custom_value, "Choose Trigger Function", "Select one trigger function or enter custom address", "Trigger Addr (hex)")
    if dlg.ShowModal() == wx.ID_OK:
        label, addr = dlg.get_selected()
        if label is not None:
            addr = possible_labels[label]
        else:
            try:
                addr = text_to_int(addr, "hex")
            except ValueError:
                event.task.window.error("Invalid address %s" % addr)
                addr = None
    else:
        addr = None
    dlg.Destroy()
    return addr


class JumpmanBaseCommand(SetRangeValueCommand):
    def __init__(self, segment, ranges, data, keep_objects_selected=True):
         super().__init__(segment, ranges, data)
         self.keep_objects_selected = keep_objects_selected

    def set_undo_flags(self, flags):
        # FIXME: need to add new flags to control rebuilding of objects, etc?
        flags.byte_values_changed = True

    def do_change(self, editor, undo):
        retval = super().do_change(editor, undo)
        level = self.segment.jumpman_playfield_model
        level.generate_display_objects(self.keep_objects_selected)
        level.cached_screen = None
        log.debug(f"Jumpman do command {self.ui_name}: {level}")
        return retval

    def undo_change(self, editor, undo):
        super().undo_change(editor, undo)
        level = self.segment.jumpman_playfield_model
        level.generate_display_objects(self.keep_objects_selected)
        level.cached_screen = None
        log.debug(f"Jumpman undo command {self.ui_name}: {level}")


class MoveHarvestGridCommand(JumpmanBaseCommand):
    short_name = "move_harvest_grid"
    ui_name = "Move Harvest Grid"

    def __init__(self, segment, dx, dy):
         super().__init__(segment, [(0x46, 0x48)], None)
         self.dx = dx
         self.dy = dy

    def get_data(self, orig):
        return (self.dx, self.dy)


class CreateObjectCommand(JumpmanBaseCommand):
    short_name = "create_jumpman_obj"
    ui_name = "Create Object"


class MoveObjectCommand(JumpmanBaseCommand):
    short_name = "move_jumpman_obj"
    ui_name = "Move Object"


class FlipVerticalCommand(JumpmanBaseCommand):
    short_name = "vflip_jumpman_obj"
    ui_name = "Flip Vertically"


class FlipHorizontalCommand(JumpmanBaseCommand):
    short_name = "hflip_jumpman_obj"
    ui_name = "Flip Horizontally"


class ClearTriggerCommand(JumpmanBaseCommand):
    short_name = "cleartrigger_jumpman_obj"
    ui_name = "Clear Trigger Function"


class SetTriggerCommand(JumpmanBaseCommand):
    short_name = "settrigger_jumpman_obj"
    ui_name = "Set Trigger Function"


class AssemblyChangedCommand(JumpmanBaseCommand):
    short_name = "jumpman_custom_code"
    ui_name = "Reassemble Custom Code"
