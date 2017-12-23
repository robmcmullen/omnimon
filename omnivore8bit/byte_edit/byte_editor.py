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
from omnivore.utils.processutil import run_detach

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

    task_arguments = Str("hex,bitmap,char,disassembly")

    grid_range_selected = Bool

    emulator_label = Unicode("Run Emulator")

#    segment_parser_label = Property(Unicode)
    segment_parser_label = Unicode("whatever")

    initial_segment = Any(None)

    initial_font_segment = Any(None)

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

    focused_viewer = Any(None)  # should be Instance(SegmentViewer), but creates circular imports

    linked_bases = List(LinkedBase)

    viewers = List(Any)

    #### Events ####

    changed = Event

    focused_viewer_changed_event = Event

    key_pressed = Event(KeyPressedEvent)

    # Class attributes (not traits)

    rect_select = False

    pane_creation_count = 0

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
    def segment(self):
        return self.focused_viewer.linked_base.segment

    @property
    def segment_number(self):
        return self.focused_viewer.linked_base.segment_number

    @property
    def section_name(self):
        return str(self.segment)

    @property
    def document_length(self):
        return len(self.segment)


    ###########################################################################
    # 'FrameworkEditor' interface.
    ###########################################################################

    def create(self, parent):
        SegmentedDocument.init_emulators(self)
        Machine.one_time_init(self)
        self.control = self._create_control(parent)
        self.task.emulator_changed = self.document
        self.task.machine_menu_changed = self.focused_viewer.linked_base.machine
        self.focused_viewer_changed_event = self.focused_viewer

    def from_metadata_dict(self, e):
        log.debug("metadata: %s" % str(e))
        if 'linked_bases' in e:
            # restore list of linked bases
            pass
        if 'initial segment' in e:
            self.initial_segment = e['initial segment']
        if 'initial font segment' in e:
            self.initial_font_segment = e['initial font segment']
        if 'diff highlight' in e:
            self.diff_highlight = bool(e['diff highlight'])
        self.focused_viewer.linked_base.from_metadata_dict(e)
        for v in self.viewers:
            v.from_metadata_dict(e)

    def to_metadata_dict(self, mdict, document):
        mdict["diff highlight"] = self.diff_highlight
        self.focused_viewer.linked_base.to_metadata_dict(mdict, document)
        # if document == self.document:
        #     # If we're saving the document currently displayed, save the
        #     # display parameters too.
        #     mdict["segment view params"] = dict(self.segment_view_params)  # shallow copy, but only need to get rid of Traits dict wrapper

    def rebuild_document_properties(self):
        log.debug("rebuilding document %s" % str(self.document))
        if not self.document.has_baseline:
            self.use_self_as_baseline(self.document)
        FrameworkEditor.rebuild_document_properties(self)
        self.focused_viewer.linked_base.find_segment(self.initial_segment)
        self.update_emulator()
        self.compare_to_baseline()
        self.can_resize_document = self.document.can_resize

    # def init_view_properties(self):
    #     if self.initial_font_segment:
    #         self.focused_viewer.linked_base.machine.change_font_data(self.initial_font_segment)

    def process_preference_change(self, prefs):
        log.debug("%s processing preferences change" % self.task.name)
        #self.machine.set_text_font(prefs.text_font)

    def process_paste_data_object(self, data_obj, cmd_cls=None):
        bytes, extra = self.get_numpy_from_data_object(data_obj)
        ranges, indexes = self.get_selected_ranges_and_indexes()
        if extra:
            if extra[0] == "numpy,multiple" or extra[0] == "numpy":
                source_indexes, style, where_comments, comments = extra[1:5]
            else:
                if not self.focused_viewer.process_paste_data(extra, bytes, cmd_cls):
                    raise RuntimeError("Unsupported data object type %s" % extra[0])
                return
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
        return self.focused_viewer.create_clipboard_data_object()

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
        self.document.change_count += 1
        self.update_cursor_history()

    def rebuild_ui(self):
        log.debug("rebuilding focused_base: %s" % str(self.focused_viewer.linked_base))
        self.document.recalc_event = True

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

    def reconfigure_panes(self):
        self.update_pane_names()

    def update_pane_names(self):
        for viewer in self.viewers:
            viewer.update_caption()
        self.mgr.RefreshCaptions()

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

    def view_segment_number(self, number):
        self.focused_viewer.linked_base.view_segment_number(number)

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

    ##### Search

    def invalidate_search(self):
        self.task.change_minibuffer_editor(self)

    @property
    def searchers(self):
        search_order = []
        found = set()
        for v in self.viewers:
            for s in v.searchers:
                # searchers may depend on the viewer (like the disassembly)
                # or they may be generic to the segment
                if s.pretty_name not in found:
                    search_order.append(s)
                    found.add(s.pretty_name)
        log.debug("search order: %s" % [s.pretty_name for s in search_order])
        return search_order

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

        self.focused_viewer.linked_base.restore_segment_view_params(s)
        self.selected_ranges = s.get_style_ranges(selected=True)
        if self.selected_ranges:
            # Arbitrarily puth the anchor on the last selected range
            last = self.selected_ranges[-1]
            self.anchor_initial_start_index = self.anchor_start_index = last[0]
            self.anchor_initial_end_index = self.anchor_end_index = last[1]
        g.clear_style_bits(selected=True)
        self.highlight_selected_ranges()

    def highlight_selected_ranges(self):
        self.document.change_count += 1
        self.focused_viewer.highlight_selected_ranges()
        self.can_copy_baseline = self.can_copy and self.baseline_present

    def get_optimized_selected_ranges(self):
        """ Get the list of monotonically increasing, non-overlapping selected
        ranges
        """
        return self.focused_viewer.get_optimized_selected_ranges(self.selected_ranges)

    def convert_ranges(self, from_style, to_style):
        s = self.segment
        ranges = s.get_style_ranges(**from_style)
        s.clear_style_bits(**from_style)
        s.clear_style_bits(**to_style)
        s.set_style_ranges(ranges, **to_style)
        self.selected_ranges = s.get_style_ranges(selected=True)
        self.document.change_count += 1

    def get_label_at_index(self, index):
        return self.focused_viewer.linked_base.segment.label(index)

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

    def update_segments_ui(self):
        # Note: via profiling, it turns out that this is a very heavyweight
        # call, producing hundreds of thousands of trait notifier events. This
        # should only be called when the number of segments or document has
        # changed. If only the segment being viewed is changed, just set the
        # task.segment_selected trait
        log.debug("update_segments_ui costs a lot of time!!!!!!")
        self.sidebar.recalc_active()
        if self.focused_viewer.linked_base.segment_parser is not None:
            self.segment_parser_label = self.focused_viewer.linked_base.segment_parser.menu_name
        else:
            self.segment_parser_label = "No parser"
        self.task.segments_changed = self.document.segments
        self.task.segment_selected = self.segment_number

    def find_in_user_segment(self, base_index):
        # FIXME: Profiling shows this as a big bottleneck when there are
        # comments. It inefficiently loops over segments, then the call to
        # get_index_from_base is super slow in atrcopy because of all the
        # calculations and dereferences needed to compute the index. That
        # probably needs to be cached.
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
        self.focused_viewer.linked_base.ensure_visible_index = flags

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
        copy_special = [CopyAsReprAction, CopyAsCBytesAction]
        for v in self.task.known_viewers:
            copy_special.extend(v.copy_special)
        copy_special.sort(key=lambda a:a().name)  # name is a trait, so only exists on an instance, not the class
        copy_special[0:0] = ["Copy Special"]  # sub-menu title

        return [CutAction, CopyAction, copy_special, PasteAction, ["Paste Special", PasteAndRepeatAction, PasteCommentsAction], None, SelectAllAction, SelectNoneAction, ["Mark Selection As", MarkSelectionAsCodeAction, MarkSelectionAsDataAction, MarkSelectionAsUninitializedDataAction, MarkSelectionAsDisplayListAction, MarkSelectionAsJumpmanLevelAction, MarkSelectionAsJumpmanHarvestAction], None, GetSegmentFromSelectionAction, RevertToBaselineAction, None, AddCommentPopupAction, RemoveCommentPopupAction, AddLabelPopupAction, RemoveLabelPopupAction]

    def do_popup(self, control, popup):
        # The popup event may happen on a control that isn't the focused
        # viewer, and the focused_viewer needs to point to that control for
        # actions to work in the correct viewer. The focus needs to be forced
        # to that control, we can't necessarily count on the ActivatePane call
        # to work before the popup.
        self.focused_viewer = control.segment_viewer
        ret = FrameworkEditor.do_popup(self, control, popup)
        wx.CallAfter(self.force_focus, control.segment_viewer)
        return ret

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

    def add_viewer(self, viewer_cls, linked=True):
        if linked:
            machine = None
        else:
            machine = center_base.machine.clone_machine()
        center_viewer = self.viewers[0]
        center_base = center_viewer.linked_base
        viewer = viewer_cls.create(self.control, center_base, machine)
        viewer.pane_info.Right().Layer(10)
        self.viewers.append(viewer)
        self.mgr.AddPane(viewer.control, viewer.pane_info)
        center_base.force_data_model_update()
        self.update_pane_names()
        self.mgr.Update()

    def replace_center_viewer(self, viewer_cls):
        center_viewer = self.viewers[0]
        center_base = center_viewer.linked_base
        viewer = viewer_cls.create(self.control, center_base, center_base.machine)
        viewer.pane_info.CenterPane()

        self.mgr.ClosePane(center_viewer.pane_info)

        # Need to replace the first viewer here, because explicitly closing the
        # pane above doesn't trigger an AUI_PANE_CLOSE event
        self.viewers[0] = viewer
        log.debug("viewers after replacing center pane: %s" % str(self.viewers))
        self.mgr.AddPane(viewer.control, viewer.pane_info)
        center_base.force_data_model_update()
        self.mgr.Update()

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
        self.mgr = aui.AuiManager(agwFlags=aui.AUI_MGR_ALLOW_ACTIVE_PANE)
        art = self.mgr.GetArtProvider()
        art.SetMetric(aui.AUI_DOCKART_GRADIENT_TYPE, aui.AUI_GRADIENT_NONE)
        art.SetColor(aui.AUI_DOCKART_ACTIVE_CAPTION_COLOUR, art.GetColor(aui.AUI_DOCKART_ACTIVE_CAPTION_GRADIENT_COLOUR))
        panel.Bind(aui.framemanager.EVT_AUI_PANE_ACTIVATED, self.on_pane_active)
        panel.Bind(aui.framemanager.EVT_AUI_PANE_CLOSE, self.on_pane_close)


        # tell AuiManager to manage this frame
        self.mgr.SetManagedWindow(panel)

        center_base = LinkedBase(editor=self)
        self.linked_bases.append(center_base)

        hex_viewer = self.task.find_viewer_by_name("hex")
        char_viewer = self.task.find_viewer_by_name("char")
        bitmap_viewer = self.task.find_viewer_by_name("bitmap")
        disassembly_viewer = self.task.find_viewer_by_name("disassembly")
        comments_viewer = self.task.find_viewer_by_name("comments")
        undo_viewer = self.task.find_viewer_by_name("undo")
        segment_viewer = self.task.find_viewer_by_name("segments")
        map_viewer = self.task.find_viewer_by_name("map")
        tile_viewer = self.task.find_viewer_by_name("tile")

        log.debug("task arguments: %s" % self.task_arguments)
        viewer_names = [a.strip() for a in self.task_arguments.split(",")]

        first = True
        layer = 0
        for name in viewer_names:
            viewer_type = self.task.find_viewer_by_name(name)
            viewer = viewer_type.create(panel, center_base, center_base.machine)
            if first:
                viewer.pane_info.CenterPane()
                self.focused_viewer = viewer  # Initial focus is center pane
                first = False
            else:
                layer += 1
                viewer.pane_info.Right().Layer(layer)
            self.viewers.append(viewer)
            self.mgr.AddPane(viewer.control, viewer.pane_info)

        # import stuff for extra renderers
        from ..arch import antic_renderers
        from ..arch.machine import disasm
        from ..arch import fonts

        layer = 0

        # viewer = char_viewer.create(panel, center_base)
        # viewer.pane_info.Right().Layer(layer)
        # self.viewers.append(viewer)
        # self.mgr.AddPane(viewer.control, viewer.pane_info)

        # machine2 = center_base.machine.clone_machine()
        # machine2.set_font(font_renderer=antic_renderers.Mode5())
        # viewer = char_viewer.create(panel, center_base, machine2)
        # viewer.pane_info.Right().Layer(layer)
        # self.viewers.append(viewer)
        # self.mgr.AddPane(viewer.control, viewer.pane_info)

        # machine2 = center_base.machine.clone_machine()
        # machine2.set_font(font=fonts.A2MouseTextFont, font_renderer=antic_renderers.Apple2TextMode())
        # viewer = char_viewer.create(panel, center_base, machine2)
        # viewer.pane_info.Right().Layer(layer)
        # self.viewers.append(viewer)
        # self.mgr.AddPane(viewer.control, viewer.pane_info)

        # layer += 1
        # viewer = bitmap_viewer.create(panel, center_base)
        # viewer.pane_info.Right().Layer(layer)
        # self.viewers.append(viewer)
        # self.mgr.AddPane(viewer.control, viewer.pane_info)

        # machine2 = center_base.machine.clone_machine()
        # machine2.set_bitmap_renderer(antic_renderers.ModeE())
        # viewer = bitmap_viewer.create(panel, center_base, machine2)
        # viewer.pane_info.Right().Layer(layer)
        # self.viewers.append(viewer)
        # self.mgr.AddPane(viewer.control, viewer.pane_info)

        # layer += 1
        # viewer = disassembly_viewer.create(panel, center_base)
        # viewer.pane_info.Right().Layer(layer)
        # self.viewers.append(viewer)
        # self.mgr.AddPane(viewer.control, viewer.pane_info)

        # layer += 1
        # viewer = tile_viewer.create(panel, center_base, center_base.machine)
        # viewer.pane_info.Right().Layer(layer)
        # self.viewers.append(viewer)
        # self.mgr.AddPane(viewer.control, viewer.pane_info)

        # layer += 1
        # viewer = segment_viewer.create(panel, center_base)
        # viewer.pane_info.Right().Layer(layer)
        # self.viewers.append(viewer)
        # self.mgr.AddPane(viewer.control, viewer.pane_info)

        self.sidebar = self.window.get_dock_pane('byte_edit.sidebar')
        self.update_pane_names()
        self.mgr.Update()

        return panel

    #### wx event handlers

    def force_focus(self, viewer):
        self.mgr.ActivatePane(viewer.control)
        self.update_pane_names()

    def on_pane_active(self, evt):
        # NOTE: evt.pane in this case is not an AuiPaneInfo object, it's the
        # AuiPaneInfo.window object
        if evt.pane is None:
            log.debug("skipping on_pane_active with no AuiPaneInfo object")
            return
        v = evt.pane.segment_viewer
        log.debug("on_pane_active: activated viewer %s %s" % (v, v.window_title))
        if v != self.focused_viewer:
            self.focused_viewer = evt.pane.segment_viewer
            self.focused_viewer_changed_event = self.focused_viewer

    def on_pane_close(self, evt):
        v = evt.pane.window.segment_viewer
        log.debug("on_pane_close: closed viewer %s %s" % (v, v.window_title))
        self.viewers.remove(v)

    def index_clicked(self, index, bit, from_control, refresh_from=True):
        log.debug("index_clicked: %s from %s at %d, %s" % (refresh_from, from_control, index, bit))
        self.cursor_index = index
        self.check_document_change()
        if refresh_from:
            from_control = None
        self.focused_viewer.linked_base.update_cursor = (from_control, index, bit)
        self.sidebar.refresh_active()
        self.can_copy = len(self.selected_ranges) > 1 or (bool(self.selected_ranges) and (self.selected_ranges[0][0] != self.selected_ranges[0][1]))
        self.can_copy_baseline = self.can_copy and self.baseline_present
