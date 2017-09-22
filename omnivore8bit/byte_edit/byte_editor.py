# Standard library imports.
import sys
import os

# Major package imports.
import wx
import wx.lib.agw.aui as aui
import numpy as np
import json

# Enthought library imports.
from traits.api import Any, Bool, Int, Str, List, Dict, Event, Enum, Instance, File, Unicode, Property, provides, on_trait_change
from pyface.key_pressed_event import KeyPressedEvent

# Local imports.
from omnivore.framework.editor import FrameworkEditor
from omnivore.framework.actions import *
from omnivore.utils.file_guess import FileMetadata
from omnivore8bit.arch.machine import Machine, Atari800
from omnivore8bit.utils.segmentutil import SegmentData, DefaultSegment, AnticFontSegment
from omnivore8bit.utils.searchutil import known_searchers
from omnivore.utils.processutil import run_detach

from omnivore8bit.viewers import SegmentViewer
from omnivore8bit.viewers.hex import HexEditViewer
from omnivore8bit.viewers.char import CharViewer

from actions import *
from commands import PasteCommand
from linked_base import LinkedBase

import logging
log = logging.getLogger(__name__)


class ByteEditor(FrameworkEditor):
    """ The toolkit specific implementation of a ByteEditor.  See the
    IByteEditor interface for the API documentation.
    """

    #### 'IPythonEditor' interface ############################################

    obj = Instance(File)

    #### traits

    grid_range_selected = Bool

    emulator_label = Unicode("Run Emulator")

#    segment_parser_label = Property(Unicode)
    segment_parser_label = Unicode("whatever")

    ### View traits

    can_copy_baseline = Bool

    can_trace = Bool(False)

    can_resize_document = Bool(False)

    has_origin = Bool(False)

    # This is a flag to help set the cursor to the center row when the cursor
    # is moved in a different editor. Some editors can't use SetFocus inside an
    # event handler, so the focus could still be set on one editor even though
    # the user clicked on another. This results in the first editor not getting
    # centered unless this flag is checked also.
    pending_focus = Any(None)  # Flag to help

    center_base = Instance(LinkedBase)

    focused_base = Instance(LinkedBase)

    linked_bases = List(LinkedBase)

    viewers = List(SegmentViewer)

    #### Events ####

    changed = Event

    key_pressed = Event(KeyPressedEvent)

    # Class attributes (not traits)

    searchers = known_searchers

    rect_select = False

    #### trait default values

    def _style_default(self):
        return np.zeros(len(self), dtype=np.uint8)

    def _segments_default(self):
        r = SegmentData(self.bytes,self.style)
        return list([DefaultSegment(r, 0)])

    def _program_memory_map_default(self):
        return dict()

    #### trait property getters

    def _get_segment_parser_label(self):
        return self.document.segment_parser.menu_name if self.document is not None else "<parser type>"

    # Convenience functions

    @property
    def section_name(self):
        if self.focused_base is not None:
            return str(self.focused_base.segment)
        if self.center_base is not None:
            return str(self.center_base.segment)
        return ""

    ###########################################################################
    # 'FrameworkEditor' interface.
    ###########################################################################

    def create(self, parent):
        SegmentedDocument.init_emulators(self)
        Machine.one_time_init(self)
        self.control = self._create_control(parent)
        self.task.emulator_changed = self.document
        self.task.machine_menu_changed = self.focused_base.machine

    def from_metadata_dict(self, e):
        if 'linked_bases' in e:
            # restore list of linked bases
            pass
        if 'initial segment' in e:
            self.initial_segment = e['initial segment']
        if 'diff highlight' in e:
            self.diff_highlight = bool(e['diff highlight'])

    def to_metadata_dict(self, mdict, document):
        mdict["diff highlight"] = self.diff_highlight
        if document == self.document:
            # If we're saving the document currently displayed, save the
            # display parameters too.
            mdict["segment view params"] = dict(self.segment_view_params)  # shallow copy, but only need to get rid of Traits dict wrapper

    def rebuild_document_properties(self):
        log.debug("rebuilding document %s" % str(self.document))
        if not self.document.has_baseline:
            self.use_self_as_baseline(self.document)
        FrameworkEditor.rebuild_document_properties(self)
        self.find_segment()
        self.update_emulator()
        self.compare_to_baseline()
        self.can_resize_document = self.document.can_resize

    def process_preference_change(self, prefs):
        log.debug("%s processing preferences change" % self.task.name)
        #self.machine.set_text_font(prefs.text_font)

    @property
    def document_length(self):
        return len(self.segment)

    def process_paste_data_object(self, data_obj, cmd_cls=None):
        bytes, extra = self.get_numpy_from_data_object(data_obj)
        ranges, indexes = self.get_selected_ranges_and_indexes()
        if extra and (extra[0] == "numpy,multiple" or extra[0] == "numpy"):
            source_indexes, style, where_comments, comments = extra[1:5]
        else:
            source_indexes = style = where_comments = comments = None
        if cmd_cls is None:
            cmd_cls = PasteCommand
        cmd = cmd_cls(self.segment, ranges, self.cursor_index, bytes, source_indexes, style, where_comments, comments)
        self.process_command(cmd)

    def get_numpy_from_data_object(self, data_obj):
        # Full list of valid data formats:
        #
        # >>> import wx
        # >>> [x for x in dir(wx) if x.startswith("DF_")]
        # ['DF_BITMAP', 'DF_DIB', 'DF_DIF', 'DF_ENHMETAFILE', 'DF_FILENAME',
        # 'DF_HTML', 'DF_INVALID', 'DF_LOCALE', 'DF_MAX', 'DF_METAFILE',
        # 'DF_OEMTEXT', 'DF_PALETTE', 'DF_PENDATA', 'DF_PRIVATE', 'DF_RIFF',
        # 'DF_SYLK', 'DF_TEXT', 'DF_TIFF', 'DF_UNICODETEXT', 'DF_WAVE']
        extra = None
        if wx.DF_TEXT in data_obj.GetAllFormats():
            value = data_obj.GetText().encode('utf-8')
        elif wx.DF_UNICODETEXT in data_obj.GetAllFormats():  # for windows
            value = data_obj.GetText().encode('utf-8')
        else:
            value = data_obj.GetData().tobytes()
            fmt = data_obj.GetPreferredFormat()
            if fmt.GetId() == "numpy,columns":
                r, c, value = value.split(",", 2)
                extra = fmt.GetId(), int(r), int(c)
            elif fmt.GetId() == "numpy":
                len1, value = value.split(",", 1)
                len1 = int(len1)
                value, j = value[0:len1], value[len1:]
                style, where_comments, comments = self.restore_selected_index_metadata(j)
                extra = fmt.GetId(), None, style, where_comments, comments
            elif fmt.GetId() == "numpy,multiple":
                len1, len2, value = value.split(",", 2)
                len1 = int(len1)
                len2 = int(len2)
                split1 = len1
                split2 = len1 + len2
                value, index_string, j = value[0:split1], value[split1:split2], value[split2:]
                indexes = np.fromstring(index_string, dtype=np.uint32)
                style, where_comments, comments = self.restore_selected_index_metadata(j)
                extra = fmt.GetId(), indexes, style, where_comments, comments
        bytes = np.fromstring(value, dtype=np.uint8)
        return bytes, extra

    supported_clipboard_data_objects = [
        wx.CustomDataObject("numpy,multiple"),
        wx.CustomDataObject("numpy"),
        wx.CustomDataObject("numpy,columns"),
        wx.TextDataObject(),
        ]

    def create_clipboard_data_object(self):
        ranges, indexes = self.get_selected_ranges_and_indexes()
        metadata = self.get_selected_index_metadata(indexes)
        if len(ranges) == 1:
            r = ranges[0]
            data = self.segment[r[0]:r[1]]
            s1 = data.tostring()
            metadata = self.get_selected_index_metadata(indexes)
            data_obj = wx.CustomDataObject("numpy")
            s = "%d,%s%s" % (len(s1), s1, metadata)
            data_obj.SetData(s)
        elif np.alen(indexes) > 0:
            data = self.segment[indexes]
            s1 = data.tostring()
            s2 = indexes.tostring()
            metadata = self.get_selected_index_metadata(indexes)
            data_obj = wx.CustomDataObject("numpy,multiple")
            s = "%d,%d,%s%s%s" % (len(s1), len(s2), s1, s2, metadata)
            data_obj.SetData(s)
        else:
            data_obj = None
        if data_obj is not None:
            text = " ".join(["%02x" % i for i in data])
            text_obj = wx.TextDataObject()
            text_obj.SetText(text)
            c = wx.DataObjectComposite()
            c.Add(data_obj)
            c.Add(text_obj)
            return c
        return None

    def show_data_object_stats(self, data_obj, copy=True):
        try:
            fmt = data_obj.GetFormat()
        except AttributeError:
            fmt = data_obj.GetPreferredFormat()
        if fmt.GetId() == "numpy,columns":
            d = self.get_data_object_by_format(data_obj, fmt)
            value = d.GetData().tobytes()
            r, c, value = value.split(",", 2)
            size = int(r) * int(c)
        elif fmt.GetId() == "numpy":
            d = self.get_data_object_by_format(data_obj, fmt)
            value = d.GetData().tobytes()
            size, _ = value.split(",", 1)
            size = int(size)
        elif fmt.GetId() == "numpy,multiple":
            d = self.get_data_object_by_format(data_obj, fmt)
            value = d.GetData().tobytes()
            size, _, _ = value.split(",", 2)
            size = int(size)
        else:
            FrameworkEditor.show_data_object_stats(self, data_obj)
            return
        self.task.status_bar.message = "%s $%x bytes (%d decimal)" % ("Copied" if copy else "Pasted", size, size)

    def get_selected_index_metadata(self, indexes):
        """Return serializable string containing style information"""
        style = self.segment.get_style_at_indexes(indexes)
        r_orig = self.segment.get_style_ranges(comment=True)
        comments = self.segment.get_comments_at_indexes(indexes)
        log.debug("after get_comments_at_indexes: %s" % str(comments))
        metadata = [style.tolist(), comments[0].tolist(), comments[1]]
        j = json.dumps(metadata)
        return j

    def restore_selected_index_metadata(self, metastr):
        metadata = json.loads(metastr)
        style = np.asarray(metadata[0], dtype=np.uint8)
        where_comments = np.asarray(metadata[1], dtype=np.int32)
        return style, where_comments, metadata[2]

    def check_document_change(self):
        if self.last_cursor_index != self.cursor_index or self.last_anchor_start_index != self.anchor_start_index or self.last_anchor_end_index != self.anchor_end_index:
            self.document.change_count += 1
            self.update_cursor_history()

    def rebuild_ui(self):
        log.debug("rebuilding focused_base: %s" % str(self.focused_base))
        self.focused_base.recalc_event = True

    def get_cursor_state(self):
        return self.segment, self.cursor_index

    def restore_cursor_state(self, state):
        segment, index = state
        number = self.document.find_segment_index(segment)
        if number < 0:
            log.error("tried to restore cursor to a deleted segment? %s" % segment)
        else:
            if number != self.segment_number:
                self.view_segment_number(number)
            self.index_clicked(index, 0, None)
        log.debug(self.cursor_history)

    def refresh_panes(self):
        log.debug("refresh_panes called")

    @on_trait_change('document.emulator_change_event')
    def update_emulator(self):
        emu = self.document.emulator
        if emu is None:
            emu = self.document.get_system_default_emulator(self.task)
        if not self.document.is_known_emulator(emu):
            self.document.add_emulator(self.task, emu)
        self.emulator_label = "Run using '%s'" % emu['name']

    def run_emulator(self):
        emu = self.document.emulator
        if not emu:
            emu = self.document.get_system_default_emulator(self.task)
        if self.dirty:
            if not self.save():
                return
        exe = emu['exe']
        args = emu['args']
        fspath = self.document.filesystem_path()
        if fspath is not None:
            try:
                run_detach(exe, args, fspath, "%s")
            except RuntimeError, e:
                self.window.error("Failed launching %s %s\n\nError: %s" % (exe, args, str(e)), "%s Emulator Error" % emu['name'])
        else:
            self.window.error("Can't run emulator on:\n\n%s\n\nDocument is not on local filesystem" % self.document.uri, "%s Emulator Error" % emu['name'])

    def find_segment_parser(self, parsers, segment_name=None):
        self.document.parse_segments(parsers)
        self.find_segment(segment_name)

    def find_first_valid_segment_index(self):
        return 0

    def find_segment(self, segment_name=None, segment=None, refresh=False):
        if segment_name is not None:
            index = self.document.find_segment_index_by_name(segment_name)
        elif segment is not None:
            index = self.document.find_segment_index(segment)
        else:
            index = self.find_first_valid_segment_index()
        if index < 0:
            index = 0
        self.segment_parser = self.document.segment_parser
        if refresh:
            self.view_segment_number(index)
        else:
            self.segment_number = index
            self.segment_parser = self.document.segment_parser
            self.segment = self.document.segments[index]

            self.focused_base.segment = self.segment
            self.select_none(refresh=False)
            self.task.segment_selected = self.segment_number

    def set_segment_parser(self, parser):
        self.find_segment_parser([parser])
        self.rebuild_ui()

    def view_segment_number(self, number):
        doc = self.document
        num = number if number < len(doc.segments) else len(doc.segments) - 1
        if num != self.segment_number:
            old_segment = self.segment
            if old_segment is not None:
                self.save_segment_view_params(old_segment)
            self.segment = doc.segments[num]
            self.focused_base.segment = segment
            self.adjust_selection(old_segment)
            self.segment_number = num
            self.invalidate_search()
            self.view_segment_set_width(self.segment)
            self.reconfigure_panes()
            self.show_trace()
            if self.segment_list is not None:
                self.segment_list.SetSelection(self.segment_number)
            else:
                self.sidebar.refresh_active()
            self.task.status_bar.message = "Switched to segment %s" % str(self.segment)
            self.task.update_window_title()
        self.task.segment_selected = self.segment_number

    def get_extra_segment_savers(self, segment):
        savers = []
        for v in self.viewers:
            savers.extend(v.get_extra_segment_savers(segment))
        return savers

    def save_segment(self, saver, uri):
        try:
            bytes = saver.encode_data(self.segment, self)
            saver = lambda a,b: bytes
            self.document.save_to_uri(uri, self, saver, save_metadata=False)
        except Exception, e:
            log.error("%s: %s" % (uri, str(e)))
            #self.window.error("Error trying to save:\n\n%s\n\n%s" % (uri, str(e)), "File Save Error")
            raise

    def show_trace(self):
        """Highlight the current trace after switching to a new segment

        """
        if self.can_trace:
            self.disassembly.update_trace_in_segment()
            self.document.change_count += 1

    def invalidate_search(self):
        self.task.change_minibuffer_editor(self)

    def compare_to_baseline(self):
        if self.diff_highlight and self.document.has_baseline:
            self.document.update_baseline()

    def adjust_selection(self, old_segment):
        """Adjust the selection of the current segment so that it is limited to the
        bounds of the new segment.
        
        If the current selection is entirely out of bounds of the new segment,
        all the selection indexes will be set to zero.
        """
        # find byte index of view into master array
        g = self.document.container_segment
        s = self.segment
        global_offset = g.get_raw_index(0)
        new_offset = s.get_raw_index(0)
        old_offset = old_segment.get_raw_index(0)

        self.restore_segment_view_params(s)
        self.selected_ranges = s.get_style_ranges(selected=True)
        if self.selected_ranges:
            # Arbitrarily puth the anchor on the last selected range
            last = self.selected_ranges[-1]
            self.anchor_initial_start_index = self.anchor_start_index = last[0]
            self.anchor_initial_end_index = self.anchor_end_index = last[1]
        g.clear_style_bits(selected=True)
        self.document.change_count += 1
        self.highlight_selected_ranges()

    def highlight_selected_ranges(self):
        s = self.segment
        s.clear_style_bits(selected=True)
        s.set_style_ranges(self.selected_ranges, selected=True)
        self.document.change_count += 1
        self.can_copy_baseline = self.can_copy and self.baseline_present

    def convert_ranges(self, from_style, to_style):
        s = self.segment
        ranges = s.get_style_ranges(**from_style)
        s.clear_style_bits(**from_style)
        s.clear_style_bits(**to_style)
        s.set_style_ranges(ranges, **to_style)
        self.selected_ranges = s.get_style_ranges(selected=True)
        self.document.change_count += 1

    def get_label_at_index(self, index):
        return self.byte_edit.table.get_label_at_index(index)

    def get_label_of_ranges(self, ranges):
        labels = []
        for start, end in ranges:
            if start > end:
                start, end = end, start
            labels.append("%s-%s" % (self.get_label_at_index(start), self.get_label_at_index(end - 1)))
        return ", ".join(labels)

    def get_label_of_first_byte(self, ranges):
        labels = []
        for start, end in ranges:
            if start > end:
                start, end = end, start
            labels.append(self.get_label_at_index(start))
        return ", ".join(labels)

    def get_segments_from_selection(self, size=-1):
        s = self.segment
        segments = []

        # Get the selected ranges directly from the segment style data, because
        # the individual range entries in self.selected_ranges can be out of
        # order or overlapping
        ranges = s.get_style_ranges(selected=True)
        if len(ranges) == 1:
            seg_start, seg_end = ranges[0]
            if size < 0:
                size = seg_end - seg_start
            for start in range(seg_start, seg_end, size):
                end = min(seg_end, start + size)
                segment = DefaultSegment(s.rawdata[start:end], s.start_addr + start)
                segments.append(segment)
        elif len(ranges) > 1:
            # If there are multiple selections, use an indexed segment
            indexes = []
            for start, end in ranges:
                indexes.extend(range(start, end))
            if size < 0:
                size = len(indexes)
            for i in range(0, len(indexes), size):
                raw = s.rawdata.get_indexed(indexes[i:i + size])
                segment = DefaultSegment(raw, s.start_addr + indexes[i])
                segments.append(segment)
        return segments

    def get_selected_status_message(self):
        if not self.selected_ranges:
            return ""
        if len(self.selected_ranges) == 1:
            r = self.selected_ranges
            first = r[0][0]
            last = r[0][1]
            num = abs(last - first)
            if num == 1: # python style, 4:5 indicates a single byte
                return "[1 byte selected %s]" % self.get_label_of_ranges(r)
            elif num > 0:
                return "[%d bytes selected %s]" % (num, self.get_label_of_ranges(r))
        else:
            return "[%d ranges selected]" % (len(self.selected_ranges))

    def show_status_message(self, msg):
        s = self.get_selected_status_message()
        if s:
            msg = "%s %s" % (msg, s)
        self.task.status_bar.message = msg

    def add_user_segment(self, segment, update=True):
        self.document.add_user_segment(segment)
        self.added_segment(segment, update)

    def added_segment(self, segment, update=True):
        if update:
            self.update_segments_ui()
            if self.segment_list is not None:
                self.segment_list.ensure_visible(segment)
        self.metadata_dirty = True

    def delete_user_segment(self, segment):
        self.document.delete_user_segment(segment)
        self.view_segment_number(self.segment_number)
        self.update_segments_ui()
        self.metadata_dirty = True

    def find_in_user_segment(self, base_index):
        for s in self.document.user_segments:
            try:
                index = s.get_index_from_base_index(base_index)
                return s, index
            except IndexError:
                continue
        for s in self.document.segment_parser.segments[1:]:
            try:
                index = s.get_index_from_base_index(base_index)
                return s, index
            except IndexError:
                continue
        return None, None

    def ensure_visible(self, flags):
        #self.index_clicked(start, 0, None)
        log.debug("flags: %s" % str(flags))
        self.focused_base.ensure_visible_index = flags

    def update_history(self):
#        history = document.undo_stack.serialize()
#        self.window.application.save_log(str(history), "command_log", ".log")
        if self.undo_history is not None:
            self.undo_history.update_history()
        self.sidebar.refresh_active()

    def mark_index_range_changed(self, index_range):
        self.disassembly.restart_disassembly(index_range[0])

    def get_goto_action_in_segment(self, addr_dest):
        if addr_dest >= 0:
            segment_start = self.segment.start_addr
            segment_num = -1
            addr_index = addr_dest - segment_start
            segments = self.document.find_segments_in_range(addr_dest)
            if addr_dest < segment_start or addr_dest > segment_start + len(self.segment):
                # segment_num, segment_dest, addr_index = self.editor.document.find_segment_in_range(addr_dest)
                if not segments:
                    msg = "Address $%04x not in any segment" % addr_dest
                    addr_dest = -1
                else:
                    # Don't chose a default segment, just show the sub menu
                    msg = None
            else:
                msg = "Go to $%04x" % addr_dest
            if msg:
                action = GotoIndexAction(name=msg, enabled=True, segment_num=segment_num, addr_index=addr_index, task=self.task, active_editor=self)
            else:
                action = None
        else:
            msg = "No address to jump to"
            action = GotoIndexAction(name=msg, enabled=False, task=self.task)
        return action

    def get_goto_actions_other_segments(self, addr_dest):
        """Add sub-menu to popup list for segments that have the same address
        """
        goto_actions = []
        segments = self.document.find_segments_in_range(addr_dest)
        if len(segments) > 0:
            other_segment_actions = ["Go to $%04x in Other Segment..." % addr_dest]
            for segment_num, segment_dest, addr_index in segments:
                if segment_dest == self.segment:
                    continue
                msg = str(segment_dest)
                action = GotoIndexAction(name=msg, enabled=True, segment_num=segment_num, addr_index=addr_index, task=self.task, active_editor=self)
                other_segment_actions.append(action)
            if len(other_segment_actions) > 1:
                # found another segment other than itself
                goto_actions.append(other_segment_actions)
        return goto_actions

    def get_goto_actions_same_byte(self, index):
        """Add sub-menu to popup list for for segments that have the same raw
        index (index into the base array) as the index into the current segment
        """
        goto_actions = []
        raw_index = self.segment.get_raw_index(index)
        segments = self.document.find_segments_with_raw_index(raw_index)
        if len(segments) > 0:
            other_segment_actions = ["Go to Same Byte in Other Segment..."]
            for segment_num, segment_dest, addr_index in segments:
                if segment_dest == self.segment:
                    continue
                msg = str(segment_dest)
                action = GotoIndexAction(name=msg, enabled=True, segment_num=segment_num, addr_index=addr_index, task=self.task, active_editor=self)
                other_segment_actions.append(action)
            if len(other_segment_actions) > 1:
                # found another segment other than itself
                goto_actions.append(other_segment_actions)
        return goto_actions

    def common_popup_actions(self):
        return [CutAction, CopyAction, ["Copy Special", CopyDisassemblyAction, CopyCommentsAction, CopyAsReprAction, CopyAsCBytesAction], PasteAction, ["Paste Special", PasteAndRepeatAction, PasteCommentsAction], None, SelectAllAction, SelectNoneAction, ["Mark Selection As", MarkSelectionAsCodeAction, MarkSelectionAsDataAction, MarkSelectionAsUninitializedDataAction, MarkSelectionAsDisplayListAction, MarkSelectionAsJumpmanLevelAction, MarkSelectionAsJumpmanHarvestAction], None, GetSegmentFromSelectionAction, RevertToBaselineAction, None, AddCommentPopupAction, RemoveCommentPopupAction, AddLabelPopupAction, RemoveLabelPopupAction]

    def change_bytes(self, start, end, bytes, pretty=None):
        """Convenience function to perform a ChangeBytesCommand
        """
        self.document.change_count += 1
        cmd = CoalescingChangeByteCommand(self.segment, start, end, bytes)
        if pretty:
            cmd.pretty_name = pretty
        self.process_command(cmd)

    def popup_visible(self):
        log.debug("checking sidebar: popup visible? %s" % self.sidebar.control.has_popup())
        return self.sidebar.control.has_popup()

    def clear_popup(self):
        log.debug("clearing popup")
        self.sidebar.control.clear_popup()

    ###########################################################################
    # Trait handlers.
    ###########################################################################

    ###########################################################################
    # Private interface.
    ###########################################################################

    def _create_control(self, parent):
        """ Creates the toolkit-specific control for the widget. """

        panel = wx.Panel(parent, style=wx.BORDER_NONE)

        # AUI Manager is the direct child of the task
        self.mgr = aui.AuiManager()

        # tell AuiManager to manage this frame
        self.mgr.SetManagedWindow(panel)

        self.center_base = LinkedBase(editor=self)
        self.linked_bases.append(self.center_base)
        self.focused_base = self.center_base
        print("c=%s, f=%s" % (id(self.center_base), id(self.focused_base)))

        default_viewer = HexEditViewer.create(panel, self.center_base)
        self.byte_edit = default_viewer.control
        self.viewers.append(default_viewer)
        self.mgr.AddPane(self.byte_edit, aui.AuiPaneInfo().Name("center_pane").CenterPane().MinimizeButton(True))

        viewer = CharViewer.create(panel, self.center_base)
        self.viewers.append(viewer)
        self.mgr.AddPane(viewer.control, aui.AuiPaneInfo().Name("char").Right().MinimizeButton(True))

        try:
            self.segment_list = self.window.get_dock_pane('byte_edit.segments').control
        except AttributeError:
            self.segment_list = None
        try:
            self.undo_history = self.window.get_dock_pane('byte_edit.undo').control
        except AttributeError:
            self.undo_history = None
        self.sidebar = self.window.get_dock_pane('byte_edit.sidebar')

        ##########################################
        # Events.
        ##########################################

        # Load the editor's contents.
        self.load()

        self.mgr.Update()

        return panel