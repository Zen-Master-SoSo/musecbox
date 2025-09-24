#  musecbox/gui/track_widget.py
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
Provides vertical and horizontal track widgets.
"""
import logging, os
from os.path import join, dirname, relpath, abspath, exists
from math import floor
from functools import partial
from itertools import chain
import qt_extras.autofit
from qt_extras import SigBlock, ShutUpQT, DevilBox
from qt_extras.list_button import QtListButton
from qt_extras.list_layout import HListLayout, VListLayout
from simple_carla import Plugin, PatchbayPort
try:
	from simple_carla.plugin_dialog import CarlaPluginDialog
except ModuleNotFoundError:
	pass

# PyQt5 imports
from PyQt5 import uic
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QObject, QVariant, QTimer, QPoint
from PyQt5.QtWidgets import QApplication, QPushButton, QFrame, QAction, QMenu, \
							QHBoxLayout, QGraphicsColorizeEffect

# musecbox imports
from musecbox import (
	carla,
	main_window,
	recent_plugins,
	setting,
	xdg_open,
	plugin_display_name,
	APP_PATH,
	TEXT_NO_CONN,
	TEXT_MULTI_CONN,
	KEY_COPY_SFZS,
	KEY_SHOW_CHANNELS,
	KEY_SHOW_INDICATORS,
	KEY_SHOW_TRACK_VOLUME,
	KEY_SHOW_PLUGIN_VOLUME,
	KEY_AUTO_CONNECT,
	SFZ_FILE_TYPE
)
from musecbox.liquidsfz import LiquidSFZ
from musecbox.gui.plugin_widgets import	TrackPluginWidget, \
										VerticalTrackPluginWidget, HorizontalTrackPluginWidget, \
										ActivityIndicator, SmallSlider
from musecbox.gui.balance_control_widget import PanGroups

SPINNER_DEBOUNCE = 250


class TrackWidget(QFrame):

	sig_ready			= pyqtSignal(int, int)
	sig_hover_over		= pyqtSignal(QObject)		# Used by balance control widget
	sig_hover_out		= pyqtSignal()				# Used by balance control widget
	sig_channel_set		= pyqtSignal(int, int, int)	# Triggered when channel is set
	sig_cleared			= pyqtSignal(int, int)

	pb_indicator_height	= 22

	def __init__(self, parent, port, slot, voice_name, sfz_filename, *,
		saved_state = None, moniker = None):
		super().__init__(parent)
		self.port = port
		self.slot = slot
		self.voice_name = voice_name
		self.moniker = moniker or str(voice_name)
		self.setVisible(False)
		if saved_state is None:
			synth_def = None
			self.channel = 0
			self.pan_group_key = None
			self.destination_client_names = []
		else:
			synth_def = saved_state["synth"]
			self.channel = saved_state["channel"] or 0
			self.pan_group_key = saved_state['pan_group_key']
			self.destination_client_names = saved_state["destination_client_names"]

		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), self.ui), self)

		self.b_name.autoFit()
		self.b_name.setText(self.moniker)
		self.b_name.clicked.connect(self.slot_select_sfz_click)

		# Setup indicators
		lo_indicators = QHBoxLayout()
		# QLayout::setContentsMargins(left, top, right, bottom)
		lo_indicators.setContentsMargins(0,0,0,0)
		self.led_midi = ActivityIndicator(self, 'led_midi')
		lo_indicators.addWidget(self.led_midi)
		self.frm_activity.setLayout(lo_indicators)

		# Setup custom volume indicator
		self.pb_volume = SmallSlider(self)
		self.pb_volume.valueChanged.connect(self.slot_volume_change)
		self.pb_volume.setFixedHeight(self.pb_indicator_height)
		self.layout().replaceWidget(self.pb_volume_placeholder, self.pb_volume)
		self.pb_volume_placeholder.setVisible(False)
		self.pb_volume_placeholder.deleteLater()
		del self.pb_volume_placeholder

		# Setup mute/solo buttons
		self.b_mute.setIcon(QIcon(join(APP_PATH, 'res', 'mute.svg')))
		self.b_solo.setIcon(QIcon(join(APP_PATH, 'res', 'solo.svg')))

		# Setup track plugins layout
		self.plugin_layout = VListLayout(end_space=10) \
			if isinstance(self, HorizontalTrackWidget) else \
			HListLayout(end_space=10)
		self.plugin_layout.setContentsMargins(0,0,0,0)
		self.plugin_layout.setSpacing(0)
		self.frm_plugins.setLayout(self.plugin_layout)

		# Setup liquid_sfz
		self.synth = TrackSynth(self.port, self.slot, sfz_filename, saved_state = synth_def)
		for src, tgt in [
			(self.synth.sig_midi_active, self.slot_midi_active),
			(self.synth.sig_sfz_loaded, self.slot_sfz_loaded),
			(self.synth.sig_ready, self.slot_plugin_ready),
			(self.synth.sig_removed, self.slot_plugin_removed),
			(self.synth.sig_parameter_changed, main_window().slot_parameter_changed),
			(self.synth.sig_connection_change, self.slot_plugin_connection_change)
		]: src.connect(tgt, type = Qt.QueuedConnection)

		# Setup output select button:
		self.b_output = QtListButton(self, self.track_targets)
		self.b_output.autoFit()
		self.b_output.setText(TEXT_NO_CONN)
		self.b_output.sig_item_selected.connect(self.slot_output_client_selected)
		self.layout().replaceWidget(self.b_output_placeholder, self.b_output)
		self.b_output_placeholder.setVisible(False)
		self.b_output_placeholder.deleteLater()
		del self.b_output_placeholder

		# Setup this TrackWidget's actions:
		action = QAction('Copy SFZ ...', self)
		action.triggered.connect(self.slot_copy_sfz)
		self.addAction(action)
		action = QAction('Open SFZ in editor', self)
		action.triggered.connect(self.slot_open_sfz_externally)
		self.addAction(action)
		action = QAction('Copy SFZ path to clipboard', self)
		action.triggered.connect(self.slot_copy_sfz_path)
		self.addAction(action)
		action = QAction('Reload SFZ', self)
		action.triggered.connect(self.synth.reload)
		self.addAction(action)
		action = QAction(self)
		action.setSeparator(True)
		self.addAction(action)
		action = QAction('Lock balance to ...', self)
		action.triggered.connect(self.slot_lock_pan)
		self.addAction(action)
		action = QAction('Unlock balance (isolate)', self)
		action.triggered.connect(self.slot_unlock_pan)
		action.setEnabled(not self.is_pan_group_orphan())
		self.addAction(action)
		action = QAction('Center balance', self)
		action.triggered.connect(self.slot_center_track)
		self.addAction(action)
		action = QAction('Spread balance full stereo', self)
		action.triggered.connect(self.go_full_stereo)
		action.setEnabled(self.can_balance)
		self.addAction(action)

		# Setup track plugins context menu
		self.frm_plugins.setContextMenuPolicy(Qt.CustomContextMenu)
		self.frm_plugins.customContextMenuRequested.connect(self.slot_plugins_context_menu)

		# Variable used only by the unified BalanceControlWidget:
		self.bcwidget_line = 0 if saved_state is None else saved_state["bcwidget_line"]
		self.sig_hover_over.connect(main_window().balance_control_widget.slot_track_hover_in)
		self.sig_hover_out.connect(main_window().balance_control_widget.slot_track_hover_out)

		self.show_channels(setting(KEY_SHOW_CHANNELS, bool, True))
		self.show_indicators(setting(KEY_SHOW_INDICATORS, bool, True))
		self.show_track_volume(setting(KEY_SHOW_TRACK_VOLUME, bool, True))

	# -----------------------------------------------------------------
	# Handlers for internal signals:

	@pyqtSlot()
	def slot_copy_sfz(self):
		"""
		Copy this TrackWidget's SFZ to a new location.
		This function overrides the project preference.
		"""
		from musecbox.dialogs.copy_sfz_dialog import CopySFZDialog
		old_path = self.synth.sfz_filename
		dlg = CopySFZDialog(self, old_path)
		if dlg.exec():
			self.setCursor(Qt.WaitCursor)
			target_path = realpath(dlg.target_path)
			# Determine if target file is beneath project dir; If so, the Synth will be
			# given a relative filename (so that it can be moved with the project). If not,
			# we need to pass an absolute path.
			if project_dir := main_window().project_dir():
				new_path = relpath(target_path, project_dir)
				if new_path.startswith(os.pardir):
					new_path = target_path
			else:
				new_path = target_path
			try:
				sfz_copy = SFZ(old_path)
				if dlg.clean_sfzs:
					liquid_clean(sfz_copy)
				sfz_copy.save_as(target_path, dlg.samples_mode)
			except Exception as err:
				self.unsetCursor()
				QMessageBox.warning(self, "SFZ Copy failed",
					f"""<p>There was an error when copying {self.synth.sfz_filename} to
					{dlg.target_path}:</p><p><b>{err}</b></p>""")
			else:
				self.synth.load_sfz(new_path)
				self.unsetCursor()
				logging.debug('Copied SFZ %s to %s', old_path, new_path)

	@pyqtSlot()
	def slot_copy_sfz_path(self):
		"""
		Copies this TrackWidget's SFZ path to the clipboard.
		"""
		QApplication.instance().clipboard().setText(self.synth.sfz_filename)

	@pyqtSlot()
	def slot_open_sfz_externally(self):
		"""
		Opens this TrackWidget's SFZ in the system -defined external editor.
		"""
		xdg_open(self.synth.sfz_filename)

	@pyqtSlot()
	def slot_lock_pan(self):
		"""
		Called from context menu.
		Lock this track's pan / balance to another track.
		"""
		groups = PanGroups.candidate_groups(self)
		labels = [ group.label() for group in groups ]
		selection, okay = QInputDialog().getItem(self,
			f'{self.moniker}: Lock pan to ...',
			'Track / group', labels, 0, False)
		if okay:
			idx = labels.index(selection)
			PanGroups.join_group(groups[idx].key, self)
			main_window().set_dirty()

	@pyqtSlot()
	def slot_unlock_pan(self):
		"""
		Called from context menu.
		Allows the selected track's control its own pan / balance.
		"""
		PanGroups.orphan(self)
		PanGroups.make_new_group(self)
		main_window().set_dirty()

	@pyqtSlot()
	def slot_center_track(self):
		"""
		Called from context menu.
		Center this track's balance.
		"""
		self.balance_left = 0.0
		self.balance_right = 0.0
		main_window().balance_control_widget.update()

	@pyqtSlot(str, QVariant)
	def slot_output_client_selected(self, _, client):
		last_plugin = self.last_plugin()
		last_plugin.disconnect_outputs()
		if client is not None:
			last_plugin.connect_audio_outputs_to(client)
		main_window().set_dirty()

	@pyqtSlot()
	def slot_add_plugin_dialog(self):
		"""
		Shows the plugin dialog and adds from the returned dict
		"""
		plugin_def = CarlaPluginDialog(main_window()).exec_dialog()
		if plugin_def is not None:
			self.runtime_add_plugin(plugin_def)

	@pyqtSlot()
	def slot_remove_all_plugins(self):
		if len(self.plugin_layout):
			out_clients = self.last_plugin().output_clients()
			for plugin in reversed(self.plugin_layout):
				self.remove_plugin(plugin, False)
			if out_clients:
				for next_client in out_clients:
					self.synth.connect_outputs_to(next_client)

	@pyqtSlot(QPoint)
	def slot_plugins_context_menu(self, position):
		menu = QMenu()
		clicked_plugin_widget = self.frm_plugins.childAt(position)
		if clicked_plugin_widget is not None:
			while not isinstance(clicked_plugin_widget, TrackPluginWidget) \
				and clicked_plugin_widget.parent() is not None:
				clicked_plugin_widget = clicked_plugin_widget.parent()
			if isinstance(clicked_plugin_widget, TrackPluginWidget):
				if clicked_plugin_widget.has_custom_ui:
					action = QAction('Prefer generic interface', self)
					action.setCheckable(True)
					action.setChecked(clicked_plugin_widget.prefer_generic_dialog)
					action.triggered.connect(clicked_plugin_widget.slot_prefer_generic)
					menu.addAction(action)
					if not clicked_plugin_widget.prefer_generic_dialog:
						action = QAction('Open generic interface', self)
						action.triggered.connect(clicked_plugin_widget.slot_show_generic_dialog)
						menu.addAction(action)
					menu.addSeparator()	# ---------------------
				action = QAction(f'Show "{clicked_plugin_widget.original_plugin_name}" info', self)
				action.triggered.connect(clicked_plugin_widget.slot_show_info_dialog)
				menu.addAction(action)
				action = QAction(f'Rename "{clicked_plugin_widget.moniker}"', self)
				action.triggered.connect(clicked_plugin_widget.slot_rename)
				menu.addAction(action)
				menu.addSeparator()	# ---------------------
				action = QAction(f'Remove {clicked_plugin_widget.moniker}', self)
				action.triggered.connect(partial(self.slot_remove_plugin, clicked_plugin_widget))
				menu.addAction(action)
		action = QAction('Add plugin', self)
		action.triggered.connect(self.slot_add_plugin_dialog)
		menu.addAction(action)
		if len(self.plugin_layout) > 0:
			action = QAction('Remove all plugins', self)
			action.triggered.connect(self.slot_remove_all_plugins)
			menu.addAction(action)
		if len(recent_plugins()) > 0:
			menu.addSeparator()	# ---------------------
			for plugin_def in recent_plugins():
				action = QAction(f'Add {plugin_display_name(plugin_def)}', self)
				action.triggered.connect(partial(self.runtime_add_plugin, plugin_def))
				menu.addAction(action)
		menu.exec(self.frm_plugins.mapToGlobal(position))

	@pyqtSlot()
	def slot_select_sfz_click(self):
		from musecbox.dialogs.sfz_file_dialog import SFZFileDialog
		sfz_dialog = SFZFileDialog(self.voice_name)
		if sfz_dialog.exec():
			self.synth.load_sfz(sfz_dialog.sfz_filename)
			main_window().set_dirty()

	@pyqtSlot(str)
	def slot_sfz_loaded(self, sfz_filename):
		self.setToolTip(sfz_filename)

	@pyqtSlot(Plugin)
	def slot_plugin_ready(self, plugin):
		if plugin is self.synth:
			if self.pan_group_key is None:
				PanGroups.make_new_group(self)
			else:
				PanGroups.join_group(self.pan_group_key, self)
			if not main_window().project_loading:
				self.pb_volume.setValue(100)
				if setting(KEY_AUTO_CONNECT, bool):
					for client in carla().system_audio_in_clients():
						self.synth.connect_audio_outputs_to(client)
						self.b_output.setText(client.moniker)
						break
			self.setVisible(True)
			self.sig_ready.emit(self.port, self.slot)
		elif not main_window().project_loading:
			idx = self.plugin_layout.index(plugin)
			previous_client = self.plugin_layout[idx - 1] if idx else self.synth
			next_clients = previous_client.output_clients()
			previous_client.disconnect_outputs()
			previous_client.connect_outputs_to(plugin)
			for next_client in next_clients:
				plugin.connect_outputs_to(next_client)
			main_window().set_dirty()

	@pyqtSlot(PatchbayPort, PatchbayPort, bool)
	def slot_plugin_connection_change(self, my_port, other_port, state):
		if my_port.is_output and my_port.client is self.last_plugin():
			is_project_port = other_port.client_name() in self.destination_client_names
			# If connecting, and is not a project port, that's a change.
			# If disconnecting, and IS a project port, it's not a change
			if state != is_project_port:
				main_window().set_dirty()
			self.update_output_connection_ui()

	@pyqtSlot(bool)
	def slot_midi_active(self, state):
		self.led_midi.light(state)

	@pyqtSlot(int)
	def slot_volume_change(self, value):
		"""
		Triggered by the volume slider in the GUI.
		"""
		self.synth.volume = float(value / 100)
		main_window().set_dirty()

	# -----------------------------------------------------------------
	# Create / load / save functions

	def add_to_carla(self):
		self.synth.add_to_carla()

	def encode_saved_state(self):
		return {
			"port"						: self.port,
			"slot"						: self.slot,
			"channel"					: self.channel,
			"moniker"					: self.moniker,
			"instrument_name"			: self.voice_name.instrument_name,
			"voice"						: self.voice_name.voice,
			"pan_group_key"				: self.pan_group_key,
			"bcwidget_line"				: self.bcwidget_line,
			"sfz"						: self.synth.relative_path,
			"synth"						: self.synth.encode_saved_state(),
			"plugins"					: [ plugin.encode_saved_state() \
											for plugin in self.plugin_layout ],
			"destination_client_names"	: [ client.client_name \
											for client in self.last_plugin().output_clients() ]
		}

	def project_load_complete(self):
		"""
		Called after loading saved project or importing track setup.
		"""
		prev_plugin = self.synth
		for plugin in self.plugin_layout:
			prev_plugin.connect_outputs_to(plugin)
			prev_plugin = plugin
		for client_name in self.destination_client_names:
			try:
				client = carla().named_client(client_name)
				prev_plugin.connect_outputs_to(client)
			except IndexError:
				logging.debug('Named client "%s" not found', client_name)
		self.display_channel_selection()
		self.pb_volume.setValue(
			100 if self.synth.volume is None \
			else round(100 * self.synth.volume))

	def remove_self(self):
		for plugin in reversed(self.plugin_layout):
			self.remove_plugin(plugin, False)
		main_window().unwatch(self.synth.sfz_filename)
		self.synth.remove_from_carla()

	def is_missing_sfz(self):
		return not exists(self.synth.sfz_filename)

	# -----------------------------------------------------------------
	# Plugin manipulation:

	def runtime_add_plugin(self, plugin_def):
		"""
		Called only from slot_add_plugin_dialog and slot_plugins_context_menu.
		Creates plugin and adds it to Carla.
		"""
		try:
			plugin = self.create_plugin_widget(self, plugin_def)
		except Exception as e:
			logging.error(e)
			DevilBox(e)
		else:
			recent_plugins().bump(plugin_def)
			self.append_plugin(plugin)
			plugin.add_to_carla()
			main_window().set_dirty()

	def restore_plugin(self, saved_state):
		"""
		Called from ProjectLoadDialog.
		Creates plugin but does not add it to Carla.
		"""
		plugin = self.create_plugin_widget(self,
			saved_state['plugin_def'], saved_state = saved_state)
		self.append_plugin(plugin)
		return plugin

	def append_plugin(self, plugin):
		"""
		Called from "runtime_add_plugin" and "restore_plugin" functions.
		You should not normally call this function from outside this class.
		"""
		for src, tgt in [
			(plugin.sig_removed, self.slot_plugin_removed),
			(plugin.sig_parameter_changed, main_window().slot_parameter_changed),
			(plugin.sig_ready, self.slot_plugin_ready),
			(plugin.sig_connection_change, self.slot_plugin_connection_change)
		]: src.connect(tgt, type = Qt.QueuedConnection)
		plugin.show_plugin_volume(setting(KEY_SHOW_PLUGIN_VOLUME, bool, True))
		self.plugin_layout.append(plugin)

	def remove_plugin(self, plugin, reconnect):
		if reconnect:
			idx = self.plugin_layout.index(plugin)
			prev_plugin = self.plugin_layout[idx - 1] if idx else self.synth
			for client in plugin.output_clients():
				prev_plugin.connect_audio_outputs_to(client)
		plugin.remove_from_carla()

	@pyqtSlot(Plugin)
	def slot_remove_plugin(self, plugin):
		"""
		Called from context menu
		"""
		self.remove_plugin(plugin, True)

	@pyqtSlot(Plugin)
	def slot_plugin_removed(self, plugin):
		"""
		Triggered by sig_removed originating from any plugin added to this TrackWidget.
		"""
		if plugin is self.synth:
			self.synth = None
		else:
			self.plugin_layout.remove(plugin)
			plugin.deleteLater()
		if self.synth is None and len(self.plugin_layout) == 0:
			PanGroups.orphan(self)
			self.sig_cleared.emit(self.port, self.slot)
		main_window().set_dirty()

	# -----------------------------------------------------------------
	# IO ports / connections funcs:

	def midi_input_port(self):
		return self.synth.midi_input_port()

	def last_plugin(self):
		return self.plugin_layout[-1] if len(self.plugin_layout) else self.synth

	@staticmethod
	def track_targets():
		"""
		Returns a list of audio in clients which track widgets can connect to.
		Used as the source for (QtListButton) "self.b_output".

		Each list item is a tuple of (moniker, client)
		"""
		return [ (client.moniker, client) for client in chain(
					main_window().iterate_shared_plugin_widgets(),
					carla().system_audio_in_clients() ) ]

	# -----------------------------------------------------------------
	# Misc funcs

	def plugin_count(self):
		return len(self.plugin_layout)

	def slot_number_changed(self, slot):
		"""
		Called from PortWidget when moving / removing a track.
		"""
		self.slot = slot
		self.synth.slot = slot
		for plugin_widget in self.plugin_layout:
			plugin_widget.slot = slot

	# -----------------------------------------------------------------
	# Volume / balance / panning funcs:

	def mute(self):
		self.synth.mute()

	def unmute(self):
		self.synth.unmute()

	@property
	def can_balance(self):
		return self.synth.can_balance

	@property
	def can_pan(self):
		return self.synth.can_pan

	@pyqtSlot()
	def go_full_stereo(self):
		self.synth.balance_left = -1.0
		self.synth.balance_right = 1.0
		main_window().set_dirty()
		main_window().balance_control_widget.update()

	def is_pan_group_orphan(self):
		group = PanGroups.group(self.pan_group_key)
		return group is None or len(group) < 2

	def color(self):
		return main_window().port_widget(self.port).color()

	def enterEvent(self, _):
		self.sig_hover_over.emit(self)

	def leaveEvent(self, _):
		self.sig_hover_out.emit()

	def set_selected(self, state):
		self.setGraphicsEffect(QGraphicsColorizeEffect() if state else None)

	def show_indicators(self, state):
		self.frm_activity.setVisible(state)

	def show_track_volume(self, state):
		self.pb_volume.setVisible(state)

	def show_plugin_volume(self, state):
		for plugin_widget in self.plugin_layout:
			plugin_widget.show_plugin_volume(state)

	def update_output_connection_ui(self):
		clients = [ client for client in self.last_plugin().output_clients() ]
		if len(clients) == 0:
			self.b_output.setText(TEXT_NO_CONN)
		elif len(clients) == 1:
			self.b_output.setText(clients[0].moniker)
		else:
			self.b_output.setText(TEXT_MULTI_CONN % len(clients))

	def __str__(self):
		return f'<Track "{self.moniker}" port {self.port}, slot {self.slot}>'


class HorizontalTrackWidget(TrackWidget):
	"""
	Track widget used when "horizontal" orientation is selected.
	"""

	ui					= 'horizontal_track_widget.ui'
	fixed_width			= 116
	pb_indicator_height	= 20

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.setFixedWidth(self.fixed_width)
		self.frm_channels.setFixedHeight(84)
		self.channel_buttons = []
		channel_grid = self.frm_channels.layout()
		channel_grid.setContentsMargins(0,0,0,0)
		channel_grid.setSpacing(1)
		for chan in range(16):
			channel = chan + 1
			button = QPushButton(self)
			button.setText(str(channel))
			button.setCheckable(True)
			button.toggled.connect(partial(self.slot_channel_click, channel))
			channel_grid.addWidget(button, floor(chan / 4), chan % 4)
			self.channel_buttons.append(button)
			setattr(self, f'b_chan_{channel:d}', button)
		self.frm_channels.setVisible(setting(KEY_SHOW_CHANNELS, bool, True))

	# -----------------------------------------------------------------
	# Channel button / selection funcs:

	@pyqtSlot(bool)
	def slot_channel_click(self, button_channel, checked):
		if checked:
			with SigBlock(* self.channel_buttons):
				for chan in range(16):
					channel = chan + 1
					if channel != button_channel and self.channel_buttons[chan].isChecked():
						self.channel_buttons[chan].setChecked(False)
			self.channel = button_channel
		else:
			self.channel = 0
		self.sig_channel_set.emit(self.port, self.slot, self.channel)

	def display_channel_selection(self):
		button = self.channel_buttons[self.channel - 1]
		with SigBlock(button):
			button.setChecked(True)

	def show_channels(self, state):
		self.frm_channels.setVisible(state)

	def create_plugin_widget(self, parent, plugin_def, *, saved_state = None):
		return HorizontalTrackPluginWidget(
			parent, self.port, self.slot, len(self.plugin_layout),
			plugin_def, saved_state = saved_state)


class VerticalTrackWidget(TrackWidget):
	"""
	Track widget used when "vertical" orientation is selected.
	"""

	ui				= 'vertical_track_widget.ui'
	fixed_height	= 28
	minimum_width	= 300

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.setFixedHeight(self.fixed_height)
		self.setMinimumWidth(self.minimum_width)
		self.spin_debounce = QTimer(self)
		self.spin_debounce.setSingleShot(True)
		self.spin_debounce.timeout.connect(self.debounce_timer_timeout)
		self.spn_channel.valueChanged.connect(self.slot_spinner_changed)

	@pyqtSlot(int)
	def slot_spinner_changed(self, _):
		self.spin_debounce.start(SPINNER_DEBOUNCE)

	@pyqtSlot()
	def debounce_timer_timeout(self):
		self.channel = self.spn_channel.value()
		self.sig_channel_set.emit(self.port, self.slot, self.channel)

	def display_channel_selection(self):
		with SigBlock(self.spn_channel):
			self.spn_channel.setValue(self.channel)

	def show_channels(self, state):
		self.spn_channel.setVisible(state)

	def create_plugin_widget(self, parent, plugin_def, *, saved_state):
		return VerticalTrackPluginWidget(
			parent, self.port, self.slot, len(self.plugin_layout),
			plugin_def, saved_state = saved_state)


class TrackSynth(LiquidSFZ):
	"""
	Synth used by track widgets.
	"""

	sig_sfz_loaded = pyqtSignal(str)

	def __init__(self, port, slot, sfz_filename, *, saved_state = None):
		self.port = port
		self.slot = slot
		if not exists(sfz_filename):
			sfz_filename = abspath(join(main_window().project_dir(), sfz_filename))
		super().__init__(sfz_filename, saved_state = saved_state)

	def track_widget(self):
		return main_window().port_widget(self.port).track_widget(self.slot)

	def finalize_init(self):
		super().finalize_init()
		main_window().watch(self.sfz_filename)

	def load_sfz(self, sfz_filename):
		oldpath = self.sfz_filename
		if not exists(sfz_filename):
			sfz_filename = abspath(join(main_window().project_dir(), sfz_filename))
		super().load_sfz(sfz_filename)
		if oldpath != self.sfz_filename:
			main_window().unwatch(oldpath)
			main_window().watch(self.sfz_filename)

	def auto_load_complete(self):
		super().auto_load_complete()
		self.sig_sfz_loaded.emit(self.sfz_filename)

	@property
	def relative_path(self):
		return relpath(self.sfz_filename, main_window().project_dir())


#  end musecbox/gui/track_widget.py
