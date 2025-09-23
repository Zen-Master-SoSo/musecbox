#  musecbox/gui/port_widget.py
#
#  Copyright 2025 Leon Dionne <ldionne@dridesign.sh.cn>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
"""
Provides both horizontal and vertical port widgets.
"""
import logging
from os.path import join, dirname
from functools import partial
import qt_extras.autofit
from qt_extras import ShutUpQT, SigBlock
from qt_extras.list_button import QtListButton
from qt_extras.list_layout import HListLayout, GListLayout, VERTICAL_FLOW
from simple_carla import Plugin, PatchbayPort
from simple_carla.qt import QtPlugin
from mscore import VoiceName

# PyQt5 imports
from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QVariant, QPoint
from PyQt5.QtGui import QPalette, QIcon, QMouseEvent
from PyQt5.QtWidgets import QSizePolicy, QFrame, QAction, QMenu, QInputDialog

from musecbox import (
	carla,
	main_window,
	setting,
	APP_PATH,
	TEXT_NO_CONN,
	TEXT_MULTI_CONN,
	KEY_AUTO_CONNECT,
	KEY_SHOW_PORT_INPUTS
)
from musecbox.gui.track_widget import TrackWidget, HorizontalTrackWidget, VerticalTrackWidget
from musecbox.gui.balance_control_widget import PanGroups
from musecbox.dialogs.track_creation_dialog import TrackCreationDialog


class PortWidget(QFrame):

	sig_ready	= pyqtSignal(int)
	sig_cleared	= pyqtSignal(int)

	def __init__(self, parent, port, *, saved_state = None):
		super().__init__(parent)
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), self.ui), self)
		self.port = port
		self.source_port_names = [] if saved_state is None \
			else saved_state["source_port_names"] if "source_port_names" in saved_state \
			else []
		self.setObjectName(f'port{port}')	# allow for styling per port number using style sheets

		# Save "collapse_state" until layout is finalized:
		self.collapse_state = False if saved_state is None \
			else "collapsed" in saved_state and saved_state["collapsed"]

		# Create channel splitter
		self.channel_splitter = MIDISplitter(saved_state = None \
			if saved_state is None else saved_state["splitter"])
		for src, tgt in [
			(self.channel_splitter.sig_ready, self.slot_splitter_ready),
			(self.channel_splitter.sig_connection_change, self.slot_splitter_connection_change)
		]: src.connect(tgt, type = Qt.QueuedConnection)
		self.channel_ports = None

		self.is_removing = False

		# Setup plugin menu
		self.frm_tracks.setContextMenuPolicy(Qt.CustomContextMenu)
		self.frm_tracks.customContextMenuRequested.connect(self.slot_tracks_context_menu)

		# Setup input_select_widget
		self.input_select_widget = QtListButton(self, self.port_sources)
		self.input_select_widget.sig_item_selected.connect(self.slot_input_selected)
		self.layout.replaceWidget(self.input_select_placeholder, self.input_select_widget)
		self.input_select_placeholder.setVisible(False)
		self.input_select_placeholder.deleteLater()
		del self.input_select_placeholder

		# Show/hide self.input_select_widget:
		self.show_input(setting(KEY_SHOW_PORT_INPUTS, bool, True))

		self.lbl_port.mouseDoubleClickEvent = self.slot_port_lbl_dblclk

	def add_to_carla(self):
		self.channel_splitter.add_to_carla()

	def encode_saved_state(self):
		return {
			"port"				: self.port,
			"splitter"			: self.channel_splitter.encode_saved_state(),
			"source_port_names"	: [ patchbay_port.jack_name() for patchbay_port in self.input_connections() ],
			"tracks"			: [ track.encode_saved_state() for track in self.track_layout ],
			"collapsed"			: self.is_collapsed()
		}

	@pyqtSlot(Plugin)
	def slot_splitter_ready(self, _):
		"""
		Triggered by MIDISplitter sig_ready.
		"""
		self.channel_ports = self.channel_splitter.midi_outs()
		if not main_window().project_loading and setting(KEY_AUTO_CONNECT, bool):
			for patchbay_port in carla().system_midi_out_ports():
				patchbay_port.connect_to(self.midi_input_port())
				break
		self.sig_ready.emit(self.port)

	@pyqtSlot(PatchbayPort, PatchbayPort, bool)
	def slot_splitter_connection_change(self, self_port, *_):
		"""
		Triggered by MIDISplitter sig_connection_change.
		Update UI, but don't do anything else
		"""
		if self_port.is_input:
			self.update_input_connection_ui()

	@pyqtSlot(PatchbayPort)
	def slot_patchbay_port_added(self, patchbay_port):
		"""
		Triggered by CarlaQt when a new Jack client port is added.
		Reconnects if project was previously saved with it connected.
		"""
		if patchbay_port.jack_name() in self.source_port_names:
			patchbay_port.connect_to(self.midi_input_port())
			self.update_input_connection_ui()

	@staticmethod
	def port_sources():
		"""
		Returns a list of MIDI out port which ports widgets can connect to.

		Used as the source for (QtListButton) "self.input_select_widget".

		Each list item is a tuple of (moniker, PatchbayPort)
		"""
		return [ (patchbay_port.jack_name(), patchbay_port) \
			for patchbay_port in carla().system_midi_out_ports() ]

	@pyqtSlot(str, QVariant)
	def slot_input_selected(self, _, patchbay_port):
		"""
		Called in response to input_select_widget.sig_item_selected.

		Connects the selected patchbay_port to this PortWidget's channel_splitter MIDI
		input port.
		"""
		self.midi_input_port().disconnect_all()
		patchbay_port.connect_to(self.midi_input_port())
		if not patchbay_port.client_name() in self.source_port_names:
			main_window().set_dirty()
		self.source_port_names = [ patchbay_port.client_name() ]

	def all_sources_connected(self):
		"""
		Returns True if all source ports defined in the project are connected to this
		PortWidget's input port.
		"""
		return set(self.source_port_names) == \
			set(port.jack_name() for port in self.input_connections()) \
			if self.midi_input_port() else False

	def midi_input_port(self):
		"""
		Returns the first midi input of this PortWidget's channel splitter plugin.
		Returns PatchbayPort.
		"""
		return self.channel_splitter.midi_input_port

	def input_connections(self):
		"""
		Returns a list of PatchbayPort connected to this Port's channel splitter.
		"""
		return [ patchbay_port \
			for patchbay_port in self.midi_input_port().connected_ports() ]

	def add_track(self, voice_name, sfz_filename, *, moniker = None):
		"""
		Adds a track as a gui element, but does not add to Carla.
		"""
		main_window().set_dirty()
		return self.construct_track(len(self.track_layout), voice_name, sfz_filename, moniker = moniker)

	def restore_track(self, saved_state):
		"""
		Adds a track as a gui element, but does not add to Carla.
		"""
		return self.construct_track(
			saved_state["slot"],
			VoiceName(saved_state["instrument_name"], saved_state["voice"]),
			saved_state["sfz"],
			moniker = saved_state["moniker"],
			saved_state = saved_state
		)

	def construct_track(self, slot, voice_name, sfz_filename, **kwargs):
		"""
		Constructs a track in a specific slot. Does not add it to Carla.

		You should not call this function directly. Instead, call "add_track", which
		will assign the new track to the next available slot.

		This function is also called from "restore_track" when loading a project.
		"""
		track_widget = self._construct_track(slot, voice_name, sfz_filename, **kwargs)
		track_widget.sig_channel_set.connect(self.slot_channel_set)
		track_widget.sig_cleared.connect(self.slot_track_cleared)
		self.track_layout.append(track_widget)
		return track_widget

	def project_load_complete(self):
		"""
		Called after loading a saved project.
		"""
		carla().sig_patchbay_port_added.connect(
			self.slot_patchbay_port_added, type = Qt.QueuedConnection)
		for track in self.track_layout:
			if track.channel > 0:
				self.channel_ports[track.channel - 1].connect_to(track.midi_input_port())
		for source_port_name in self.source_port_names:
			client_name, port_name = source_port_name.split(':', 1)
			try:
				client = carla().named_client(client_name)
			except IndexError:
				logging.debug('Previously connected client "%s" not found', client_name)
			else:
				try:
					patchbay_port = client.named_port(port_name)
				except IndexError:
					logging.debug('Previously connected port "%s" not found', source_port_name)
				else:
					logging.debug(f'Connecting %s to port %s', source_port_name, self.port)
					patchbay_port.connect_to(self.channel_splitter.midi_input_port)
		self.update_input_connection_ui()

	def route_channel_to_slot(self, channel, slot):
		"""
		Called from ScoreLoadDialog, connects this PortWidget's channel splitter
		output for the given channel to the TrackWidget in the given slot.
		"""
		self.channel_ports[channel - 1].connect_to(self.track_widget(slot).midi_input_port())
		self.track_layout[slot].channel = channel
		self.track_layout[slot].display_channel_selection()

	def remove_self(self):
		self.is_removing = True
		if len(self.track_layout):
			for track_widget in self.track_layout:
				track_widget.remove_self()
		else:
			self.sig_cleared.emit(self.port)

	def track_widget(self, slot):
		return self.track_layout[slot]

	def iterate_track_widgets(self):
		yield from self.track_layout

	def iterate_track_plugin_widgets(self):
		for track_widget in self.track_layout:
			yield from track_widget.plugin_layout

	def show_input(self, state):
		self.input_select_widget.setVisible(state)

	def is_collapsed(self):
		return not self.frm_tracks.isVisible()

	@pyqtSlot(TrackWidget)
	def slot_remove_track(self, track_widget):
		track_widget.remove_self()

	@pyqtSlot(int, int, int)
	def slot_channel_set(self, _, slot, channel):
		"""
		Called when track_widget.sig_channel_set is triggered.
		"""
		self.track_widget(slot).midi_input_port().disconnect_all()
		if channel > 0:
			self.channel_ports[channel - 1].connect_to(self.track_widget(slot).midi_input_port())
		else:
			self.track_widget(slot).midi_input_port().disconnect_all()
		main_window().set_dirty()

	@pyqtSlot(int, int)
	def slot_track_cleared(self, _, slot):
		"""
		Called when track_widget.sig_cleared triggered, in response to
		track_widget.remove_self(). Removes the track widget from the GUI.
		When all track widgets are gone, emits sig_cleared.
		"""
		try:
			track_widget = self.track_layout[slot]
		except IndexError:
			return
		self.track_layout.remove(track_widget)
		if main_window().balance_control_widget.hovered_group is track_widget:
			main_window().balance_control_widget.hovered_group = None
		main_window().balance_control_widget.update()
		track_widget.deleteLater()
		if len(self.track_layout):
			if not main_window().is_clearing:
				for index, track_widget in enumerate(self.track_layout):
					track_widget.slot_number_changed(index)
		else:
			self.sig_cleared.emit(self.port)

	@pyqtSlot(QPoint)
	def slot_tracks_context_menu(self, position):
		menu = QMenu()
		clicked_track_widget = self.frm_tracks.childAt(position)
		if clicked_track_widget is not None:
			while not isinstance(clicked_track_widget, TrackWidget) \
				and clicked_track_widget.parent() is not None:
				clicked_track_widget = clicked_track_widget.parent()
			if isinstance(clicked_track_widget, TrackWidget):
				menu.addActions(clicked_track_widget.actions())
				menu.addSeparator()	# ---------------------
				if isinstance(self, HorizontalPortWidget):
					action = QAction('Move track to previous slot', self)
					action.triggered.connect(partial(self.slot_move_track_previous, clicked_track_widget))
					action.setEnabled(clicked_track_widget.slot > 0)
					menu.addAction(action)
					action = QAction('Move track to next slot', self)
					action.triggered.connect(partial(self.slot_move_track_next, clicked_track_widget))
					action.setEnabled(clicked_track_widget.slot < len(self.track_layout) - 1)
					menu.addAction(action)
				action = QAction(f'Remove track "{clicked_track_widget.moniker}"', self)
				action.triggered.connect(partial(self.slot_remove_track, clicked_track_widget))
				menu.addAction(action)
				menu.addSeparator()	# ---------------------
		action = QAction('Add a new track', self)
		action.triggered.connect(self.slot_add_track_dialog)
		action.setEnabled(len(self.track_layout) < 16)
		menu.addAction(action)
		action = QAction('Remove all tracks', self)
		action.triggered.connect(self.slot_remove_all_tracks)
		action.setEnabled(len(self.track_layout) > 0)
		menu.addAction(action)
		menu.exec(self.frm_tracks.mapToGlobal(position))

	@pyqtSlot()
	def slot_add_track_dialog(self):
		"""
		Shows the track dialog and adds from the returned dict
		"""
		dialog = TrackCreationDialog(self)
		dialog.spn_port.setValue(self.port)
		dialog.spn_port.setEnabled(False)
		if dialog.exec():
			voice_name = VoiceName(dialog.cmb_instrument.currentText(), dialog.cmb_voice.currentText())
			self.add_track(voice_name, dialog.sfz_filename).add_to_carla()

	@pyqtSlot()
	def slot_remove_all_tracks(self):
		for track_widget in reversed(self.track_layout):
			track_widget.remove_self()

	@pyqtSlot(QMouseEvent)
	def slot_port_lbl_dblclk(self, _):
		self.implement_collapse(not self.is_collapsed())

	def color(self):
		return self.lbl_port.palette().color(QPalette.Background)


class HorizontalPortWidget(PortWidget):
	"""
	Widget which lays out tracks in a horizonal list layout.
	"""

	ui				= 'horizontal_port_widget.ui'

	def __init__(self, parent, port, *, saved_state = None):
		super().__init__(parent, port, saved_state = saved_state)
		self.lbl_port.setText(f'Port {self.port}')
		self.input_select_widget.autoFit()
		self.icon_collapse = QIcon(join(APP_PATH, 'res', 'collapse.svg'))
		self.icon_expand = QIcon(join(APP_PATH, 'res', 'expand.svg'))
		self.b_collapse.setIcon(self.icon_collapse)
		self.b_collapse.clicked.connect(self.slot_collapse_click)
		# Setup track_layout
		self.track_layout = HListLayout(end_space=10)
		self.track_layout.setContentsMargins(0,0,0,0)
		self.track_layout.setSpacing(0)
		self.frm_tracks.setLayout(self.track_layout)
		# bottom spacer used when collapsing:
		self.spc_bottom = QFrame()
		self.spc_bottom.setVisible(False)
		self.spc_bottom.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
		self.spc_bottom.setFrameShadow(self.frm_tracks.frameShadow())
		self.spc_bottom.setFrameShape(self.frm_tracks.frameShape())
		self.spc_bottom.setFrameStyle(self.frm_tracks.frameStyle())
		self.layout.addWidget(self.spc_bottom)
		# expand / collapse based on saved state:
		self.setMinimumWidth(86)
		self.implement_collapse(self.collapse_state)

	def _construct_track(self, slot, voice_name, sfz_filename, **kwargs):
		return HorizontalTrackWidget(self, self.port, slot, voice_name, sfz_filename, **kwargs)

	@pyqtSlot(TrackWidget)
	def slot_move_track_previous(self, track_widget):
		self.track_layout.move_up(track_widget)
		for index, track_widget in enumerate(self.track_layout):
			track_widget.slot_number_changed(index)
		main_window().set_dirty()

	@pyqtSlot(TrackWidget)
	def slot_move_track_next(self, track_widget):
		self.track_layout.move_down(track_widget)
		for slot, _ in enumerate(self.track_layout):
			self.track_layout[slot].slot_number_changed(slot)
		main_window().set_dirty()

	@pyqtSlot(bool)
	def slot_collapse_click(self, checked):
		if self.is_collapsed() != checked:
			self.implement_collapse(checked)

	def implement_collapse(self, checked):
		self.frm_tracks.setVisible(not checked)
		self.spc_bottom.setVisible(checked)
		self.b_collapse.setIcon(self.icon_expand if checked else self.icon_collapse)
		with SigBlock(self.b_collapse):
			self.b_collapse.setChecked(checked)
		main_window().set_dirty()

	def update_input_connection_ui(self):
		ports = self.input_connections()
		self.input_select_widget.setText(TEXT_MULTI_CONN % len(ports) if len(ports) > 1 \
			else ports[0].jack_name() if len(ports) \
			else TEXT_NO_CONN)
		self.input_select_widget.setToolTip("\n".join([ patchbay_port.jack_name() for patchbay_port in ports ]) \
			if len(ports) else TEXT_NO_CONN)


class VerticalPortWidget(PortWidget):
	"""
	Widget which lays out tracks in a grid.
	"""

	ui				= 'vertical_port_widget.ui'
	minimum_height	= 48

	def __init__(self, parent, port, *, saved_state = None):
		super().__init__(parent, port, saved_state = saved_state)
		self.lbl_port.setText(str(self.port))
		self.input_select_widget.setFixedHeight(22)
		self.input_select_widget.setFixedWidth(22)
		self.track_layout = GListLayout(8, VERTICAL_FLOW)
		self.track_layout.setContentsMargins(0,0,0,0)
		self.track_layout.setSpacing(0)
		self.track_layout.sig_len_changed.connect(self.slot_layout_len_changed)
		self.frm_tracks.setLayout(self.track_layout)
		# expand / collapse based on saved state:
		self.implement_collapse(self.collapse_state)

	def _construct_track(self, slot, voice_name, sfz_filename, **kwargs):
		return VerticalTrackWidget(self, self.port, slot, voice_name, sfz_filename, **kwargs)

	@pyqtSlot()
	def slot_layout_len_changed(self):
		"""
		Triggered by track_layout.sig_len_changed
		Sets the height of this VerticalPortWidget
		"""
		if self.frm_tracks.isVisible():
			self.setFixedHeight(self._expanded_height())

	def implement_collapse(self, checked):
		self.frm_tracks.setVisible(not checked)
		self.setFixedHeight(self.minimum_height if checked else self._expanded_height())
		main_window().set_dirty()

	def _expanded_height(self):
		return max(
			self.minimum_height,
			VerticalTrackWidget.fixed_height * min(len(self.track_layout), 8)
		)

	def update_input_connection_ui(self):
		ports = self.input_connections()
		text = "\n".join([ patchbay_port.jack_name() for patchbay_port in ports ]) \
			if len(ports) else TEXT_NO_CONN
		self.lbl_port.setToolTip(text)
		self.input_select_widget.setToolTip(text)
		self.input_select_widget.setText('➲' if len(ports) else '-')

# -------------------------------------------------------------------
# MIDISplitter

class MIDISplitter(QtPlugin):

	def __init__(self, *, saved_state = None):
		super().__init__({
			'type'		: 4,
			'build'		: 2,
			'filename'	: 'carla.lv2',
			'name'		: 'MIDI Split',
			'label'		: 'http://kxstudio.sf.net/carla/plugins/midisplit',
			'uniqueId'	: None
		}, saved_state = saved_state)
		self.midi_input_port = None

	def ready(self):
		self.midi_input_port = self.midi_ins()[0]
		super().ready()


#  end musecbox/gui/port_widget.py
