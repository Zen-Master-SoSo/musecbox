#  musecbox/gui/main_window.py
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
Provides the main application window.
"""
import logging, json
from os import mkdir, linesep
from os.path import join, dirname, basename, splitext, realpath, exists
from functools import partial
from itertools import chain
from collections import namedtuple
from signal import signal, SIGINT, SIGTERM
from socket import socket, AF_UNIX, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR
from qt_extras import SigBlock, ShutUpQT, DevilBox
from qt_extras.list_layout import HListLayout, VListLayout
from sfzen import SFZ
from sfzen.cleaners.liquidsfz import clean as liquid_clean
from mscore import VoiceName
from simple_carla import	Plugin, Parameter, \
							ENGINE_TRANSPORT_MODE_DISABLED as TRANSPORT_DISABLED
try:
	from simple_carla.plugin_dialog import CarlaPluginDialog
except ModuleNotFoundError:
	pass

# PyQt5 imports
from PyQt5 import uic
from PyQt5.QtCore import	Qt, pyqtSignal, pyqtSlot, QDir, QThread, QPoint, QTimer, QEvent, QVariant, \
							pyqtProperty, QPropertyAnimation, QAbstractAnimation, QFileSystemWatcher
from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QMessageBox, QFileDialog, QInputDialog, \
							QMenu, QLabel, QAction, QActionGroup, QStyle, QSizePolicy, QVBoxLayout
from PyQt5.QtGui import		QPainter, QColor, QBrush, QPalette, QIcon

# musecbox imports
from musecbox import 		carla, set_main_window, EngineInitFailure, \
							recent_files, recent_plugins, \
							setting, set_setting, sync_settings, \
							styles, set_application_style, xdg_open, plugin_display_name, \
							APPLICATION_NAME, APP_PATH, SOCKET_PATH, CARRIAGE_RETURN, \
							SUPPORTED_FILE_TYPES, MUSESCORE_FILE_TYPES, RENDER_FILE_TYPE, \
							PROJECT_OPTION_KEYS, DEFAULT_STYLE, KEY_STYLE, \
							KEY_RECENT_PROJECT_DIR, KEY_RECENT_SCORE_DIR, \
							KEY_SHOW_CHANNELS, KEY_SHOW_PORT_INPUTS, KEY_SHOW_INDICATORS, \
							KEY_SHOW_TRACK_VOLUME, KEY_SHOW_PLUGIN_VOLUME, KEY_SHOW_BALANCE, \
							KEY_SHOW_SHARED_PLUGINS, KEY_SHOW_TOOLBAR, KEY_SHOW_STATUSBAR, \
							KEY_AUTO_CONNECT, KEY_AUTO_START, KEY_WATCH_FILES, KEY_VERTICAL_LAYOUT, \
							KEY_BCWIDGET_LINES, KEY_COPY_SFZS, KEY_SAMPLES_MODE, KEY_CLEAN_SFZS, \
							LAYOUT_COMPLETE_DELAY
from musecbox.gui.port_widget import PortWidget, HorizontalPortWidget, VerticalPortWidget
from musecbox.gui.track_widget import TrackWidget
from musecbox.gui.plugin_widgets import SharedPluginWidget
from musecbox.gui.balance_control_widget import BalanceControlWidget

INDICATOR_TIMER_MS		= 310
LOAD_TIMER_MS			= 530
XRUN_TIMER_MS			= 670
DELAY_AFTER_CLEAR		= 500
DELAY_AFTER_LOAD		= 100
DELAY_BEFORE_RENDER		= 250


class MainWindow(QMainWindow):

	# -----------------------------------------------------------------
	# Window init functions

	def __init__(self, options):
		super().__init__()
		set_main_window(self)
		self.startup_options = options

		self.project_filename = None
		self.project_definition = None
		self.source_score = None
		self.dirty = False
		self.project_loading = False
		self.is_clearing = False
		self.is_closing = False
		self.function_after_cleared = None
		self.single_sfz_filename = None
		self.file_system_watcher = None
		self.wav_filename = None
		self.transport_mode = TRANSPORT_DISABLED
		self.port_assignments = {}	# {midi_port:self.port_layout index}

		if options.Filename and exists(options.Filename):
			ext = splitext(options.Filename)[-1]
			if ext == '.mbxp':
				try:
					with open(options.Filename, 'r') as fh:
						self.project_definition = json.load(fh)
				except json.JSONDecodeError as e:
					logging.error(e)
				else:
					self.project_filename = realpath(options.Filename)

		if self.startup_options.vertical_layout:
			set_setting(KEY_VERTICAL_LAYOUT, True)
		elif self.startup_options.horizontal_layout:
			set_setting(KEY_VERTICAL_LAYOUT, False)

		set_application_style()
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'main_window.ui'), self)
		self.setWindowIcon(QIcon(join(APP_PATH, 'res', 'musecbox-icon.png')))

		self._setup_window_elements()
		self._show_hide_window_elements()
		self._connect_actions()
		self._setup_timers()
		self._setup_socket_listener()
		self._connect_host_callbacks()
		signal(SIGINT, self.system_signal)
		signal(SIGTERM, self.system_signal)

		self.restore_geometry()
		if not carla().engine_init():
			raise EngineInitFailure()
		QTimer.singleShot(LAYOUT_COMPLETE_DELAY, self.update_ui)

	def _connect_host_callbacks(self):
		gcarla = carla()
		gcarla.set_open_file_callback(self.carla_open_file_dialog)
		gcarla.set_save_file_callback(self.carla_save_file_dialog)
		for src, tgt in [
			(gcarla.sig_engine_started, self.slot_engine_started),
			(gcarla.sig_engine_stopped, self.slot_engine_stopped),
			(gcarla.sig_last_plugin_removed, self.slot_last_plugin_removed),
			(gcarla.sig_process_mode_changed, self.slot_process_mode_changed),
			(gcarla.sig_transport_mode_changed, self.slot_transport_mode_changed),
			(gcarla.sig_buffer_size_changed, self.slot_buffer_size_changed),
			(gcarla.sig_sample_rate_changed, self.slot_sample_rate_changed),
			(gcarla.sig_cancelable_action, self.slot_cancelable_action),
			(gcarla.sig_info, self.slot_carla_info),
			(gcarla.sig_error, self.slot_carla_error),
			(gcarla.sig_application_error, self.slot_application_error),
			(gcarla.sig_quit, self.slot_carla_quit)
		]: src.connect(tgt, type = Qt.QueuedConnection)

	def _setup_window_elements(self):
		self.frm_ports.setContextMenuPolicy(Qt.CustomContextMenu)
		self.frm_ports.customContextMenuRequested.connect(self.slot_ports_context_menu)

		if setting(KEY_VERTICAL_LAYOUT, bool):
			self.action_vertical_layout.setChecked(True)
			self.port_layout = VListLayout(end_space=10)
			self.scrl_ports.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
		else:
			self.action_vertical_layout.setChecked(False)
			self.port_layout = HListLayout(end_space=10)
			self.scrl_ports.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

		self.port_layout.setContentsMargins(0,0,0,0)
		self.port_layout.setSpacing(0)
		self.frm_ports.setLayout(self.port_layout)

		self.shared_plugin_layout = HListLayout(end_space=10)
		self.shared_plugin_layout.setContentsMargins(0,0,0,0)
		self.shared_plugin_layout.setSpacing(0)
		self.frm_shared_plugins.setLayout(self.shared_plugin_layout)
		self.scr_shared_plugins.setFixedHeight(SharedPluginWidget.fixed_height + 16)
		self.scr_shared_plugins.setContextMenuPolicy(Qt.CustomContextMenu)
		self.scr_shared_plugins.customContextMenuRequested.connect(self.slot_shared_plugins_context_menu)

		self.balance_control_widget = BalanceControlWidget(self)
		lo = self.frm_balance.layout()
		lo.setContentsMargins(0,0,0,0)
		lo.setSpacing(0)
		lo.addWidget(self.balance_control_widget)

		self.load_indicator = LoadIndicator(self)
		self.frm_statusbar.layout().replaceWidget(self.pb_dsp_load_placeholder, self.load_indicator)
		self.pb_dsp_load_placeholder.setVisible(False)
		self.pb_dsp_load_placeholder.deleteLater()
		del self.pb_dsp_load_placeholder

	def _show_hide_window_elements(self):
		show_toolbar = setting(KEY_SHOW_TOOLBAR, bool, True)
		show_port_inputs = setting(KEY_SHOW_PORT_INPUTS, bool, True)
		show_channels = setting(KEY_SHOW_CHANNELS, bool, True)
		show_indicators = setting(KEY_SHOW_INDICATORS, bool, True)
		show_balance_control = setting(KEY_SHOW_BALANCE, bool, True)
		show_shared_plugins = setting(KEY_SHOW_SHARED_PLUGINS, bool, True)
		show_statusbar = setting(KEY_SHOW_STATUSBAR, bool, True)
		show_track_volume = setting(KEY_SHOW_TRACK_VOLUME, bool, True)
		show_plugin_volume = setting(KEY_SHOW_PLUGIN_VOLUME, bool, True)

		self.toolbar.setVisible(show_toolbar)
		self.frm_balance.setVisible(show_balance_control)
		self.scr_shared_plugins.setVisible(show_shared_plugins)
		self.frm_statusbar.setVisible(show_statusbar)

		self.action_show_toolbar.setChecked(show_toolbar)
		self.action_show_port_inputs.setChecked(show_port_inputs)
		self.action_show_channels.setChecked(show_channels)
		self.action_show_indicators.setChecked(show_indicators)
		self.action_show_balance.setChecked(show_balance_control)
		self.action_show_shared_plugins.setChecked(show_shared_plugins)
		self.action_show_statusbar.setChecked(show_statusbar)
		self.action_show_track_volume.setChecked(show_track_volume)
		self.action_show_plugin_volume.setChecked(show_plugin_volume)

		self.action_show_toolbar.toggled.connect(self.slot_show_toolbar)
		self.action_show_port_inputs.toggled.connect(self.slot_show_port_inputs)
		self.action_show_channels.toggled.connect(self.slot_show_channels)
		self.action_show_indicators.toggled.connect(self.slot_show_indicators)
		self.action_show_balance.toggled.connect(self.slot_show_balance_control)
		self.action_show_shared_plugins.toggled.connect(self.slot_show_shared_plugins)
		self.action_show_statusbar.toggled.connect(self.slot_show_statusbar)
		self.action_show_track_volume.toggled.connect(self.slot_show_track_volume)
		self.action_show_plugin_volume.toggled.connect(self.slot_show_plugin_volume)

		self.action_vertical_layout.toggled.connect(self.slot_vertical_layout)

	def _connect_actions(self):
		# Menu actions
		self.action_new.triggered.connect(self.slot_new)
		self.action_open.triggered.connect(self.slot_open_file)
		self.action_save.triggered.connect(self.slot_save_project)
		self.action_save_as.triggered.connect(self.slot_save_project_as)
		self.action_revert.triggered.connect(self.slot_revert)
		self.action_close.triggered.connect(self.slot_close)
		self.action_watch_files.toggled.connect(self.slot_watch_files)
		self.action_copy_sfzs.triggered.connect(self.slot_copy_sfzs)
		self.action_copy_sfz_paths.triggered.connect(self.slot_copy_sfz_paths)
		self.action_auto_start.toggled.connect(self.slot_set_autostart)
		self.action_open_project_folder.triggered.connect(self.slot_open_project_folder)
		self.action_apply_to_score.triggered.connect(self.slot_apply_to_score)
		self.action_add_port.triggered.connect(self.slot_add_port)
		self.action_add_track.triggered.connect(self.slot_add_track)
		self.action_connect_all_tracks.triggered.connect(self.slot_connect_all_tracks)
		self.action_auto_connect_tracks.triggered.connect(self.slot_auto_connect_tracks)
		self.action_collapse_all_ports.triggered.connect(self.slot_collapse_all_ports)
		self.action_expand_all_ports.triggered.connect(self.slot_expand_all_ports)
		self.action_rollup_all_plugins.triggered.connect(self.slot_rollup_all_plugins)
		self.action_unroll_all_plugins.triggered.connect(self.slot_unroll_all_plugins)
		self.action_reload_style.triggered.connect(self.slot_reload_style)
		self.action_add_shared_plugin.triggered.connect(self.slot_add_shared_plugin)
		self.action_clear_shared_plugins.triggered.connect(self.slot_clear_shared_plugins)
		self.action_mute_all_tracks.triggered.connect(self.slot_mute_all_tracks)
		self.action_unmute_all_tracks.triggered.connect(self.slot_unmute_all_tracks)
		self.action_clear_track_plugins.triggered.connect(self.slot_clear_track_plugins)
		self.action_show_connections.triggered.connect(self.slot_show_connections)
		self.action_show_project_info.triggered.connect(self.slot_show_project_info)
		self.action_show_score_info.triggered.connect(self.slot_show_score_info)
		self.action_show_sfzdb.triggered.connect(self.slot_show_sfzdb)

		self.action_record.triggered.connect(self.slot_record)
		self.action_transport_start.triggered.connect(self.slot_transport_start)
		self.action_transport_stop.triggered.connect(self.slot_transport_stop)
		self.action_transport_rewind.triggered.connect(self.slot_transport_rewind)

		# Pushbutton events
		self.b_xruns.clicked.connect(self.slot_clear_xruns)
		current_style = setting(KEY_STYLE, str, DEFAULT_STYLE)
		actions = QActionGroup(self)
		actions.setExclusive(True)
		for style_name in styles():
			action = QAction(style_name, self)
			action.triggered.connect(partial(self.select_style, style_name))
			action.setCheckable(True)
			action.setChecked(style_name == current_style)
			actions.addAction(action)
			self.menu_style.addAction(action)
		self.menu_open_recent.aboutToShow.connect(self.slot_recent_menu_show)
		self.menu_view.aboutToShow.connect(self.slot_view_menu_show)

	def _setup_timers(self):
		self._update_indicator_timer = QTimer()
		self._update_indicator_timer.setInterval(INDICATOR_TIMER_MS)
		self._update_indicator_timer.timeout.connect(self.slot_indicator_timer_timeout)
		self._update_load_timer = QTimer()
		self._update_load_timer.setInterval(LOAD_TIMER_MS)
		self._update_load_timer.timeout.connect(self.slot_load_timer_timeout)
		self._update_xrun_timer = QTimer()
		self._update_xrun_timer.setInterval(XRUN_TIMER_MS)
		self._update_xrun_timer.timeout.connect(self.slot_xrun_timer_timeout)

	def _setup_socket_listener(self):
		self.socket_listener_thread = QThread()
		self.socket_listener = SocketListener()
		self.socket_listener.sig_message.connect(self.slot_socket_message)
		self.socket_listener.moveToThread(self.socket_listener_thread)
		self.socket_listener.start()

	# -----------------------------------------------------------------
	# Carla file open/save filename helpers
	# (see Carla.set_open_file_callback)

	def carla_open_file_dialog(self, caption, filter):
		filename, ok = QFileDialog.getOpenFileName(self, caption, "", filter)
		return filename if ok else None

	def carla_save_file_dialog(self, caption, filter, dirs_only):
		filename, ok = QFileDialog.getSaveFileName(self, caption, "", filter,
			QFileDialog.ShowDirsOnly if dirs_only else 0)
		return filename if ok else None

	# -----------------------------------------------------------------
	# GUI update functions:

	def set_dirty(self):
		if not self.project_loading and not self.is_clearing:
			self.dirty = True
			self.update_ui()

	def clear_dirty(self):
		self.dirty = False
		self.update_ui()

	def update_ui(self):
		has_tracks = self.track_widget_count() > 0
		has_track_plugins = self.track_plugin_count() > 0
		has_shared_plugins = len(self.shared_plugin_layout) > 0
		has_project = not self.project_filename is None
		has_score = bool(self.source_score)
		self.action_save.setEnabled(self.dirty)
		self.action_save_as.setEnabled(has_project)
		self.action_revert.setEnabled(has_project)
		self.action_close.setEnabled(has_project)
		self.action_auto_start.setEnabled(has_project)
		self.action_open_project_folder.setEnabled(has_project)
		self.action_apply_to_score.setEnabled(has_project)
		self.action_watch_files.setEnabled(has_tracks)
		self.action_show_project_info.setEnabled(has_project)
		self.action_show_score_info.setEnabled(has_score)
		self.action_copy_sfzs.setEnabled(has_project)
		self.action_copy_sfz_paths.setEnabled(has_tracks)
		self.action_clear_shared_plugins.setEnabled(has_shared_plugins)
		self.action_mute_all_tracks.setEnabled(has_tracks)
		self.action_unmute_all_tracks.setEnabled(has_tracks)
		self.action_connect_all_tracks.setEnabled(has_tracks)
		self.action_clear_track_plugins.setEnabled(has_track_plugins)
		self.action_show_connections.setEnabled(has_tracks)
		self.action_auto_connect_tracks.setChecked(setting(KEY_AUTO_CONNECT, bool))
		if has_project:
			if self.dirty:
				self.setWindowTitle(f'* {self.project_filename} {APPLICATION_NAME}')
			else:
				self.setWindowTitle(f'{self.project_filename} {APPLICATION_NAME}')
		else:
			self.setWindowTitle(f'{APPLICATION_NAME}')

	def update_buffer_size(self, size):
		self.lbl_buffer_size.setText(str(size))

	def update_sample_rate(self, rate):
		self.lbl_sample_rate.setText(f'{rate:.0f}')

	def start_timers(self):
		if self.action_show_indicators.isChecked():
			self._update_indicator_timer.start()
		self._update_xrun_timer.start()
		self._update_load_timer.start()

	def stop_timers(self):
		self._update_indicator_timer.stop()
		self._update_xrun_timer.stop()
		self._update_load_timer.stop()

	@pyqtSlot()
	def slot_indicator_timer_timeout(self):
		for plugin in chain(
			self.iterate_track_plugin_widgets(),
			self.iterate_shared_plugin_widgets()
		):
			plugin.update_indicators()

	@pyqtSlot()
	def slot_xrun_timer_timeout(self):
		info = carla().get_runtime_engine_info()
		self.b_xruns.setText(f'{info["xruns"]} Xrun' \
			if info['xruns'] == 1 else f'{info["xruns"]} Xruns')

	@pyqtSlot()
	def slot_load_timer_timeout(self):
		info = carla().get_runtime_engine_info()
		self.load_indicator.set_value(int(info['load']))

	# -----------------------------------------------------------------
	# Application start functions, including from another instance.

	@pyqtSlot(QVariant)
	def slot_socket_message(self, message):
		self.raise_()
		if message != '???':
			try:
				self.open_file(message)
			except Exception as e:
				DevilBox(e)

	def open_file(self, filename):
		ext = splitext(filename)[-1]
		if ext in ('.mscz', '.mscx'):
			self.when_clear(partial(self.import_score, filename))
		elif ext == '.mbxp':
			self.when_clear(partial(self.load_project, filename))
		elif ext == '.mbxt':
			self.when_clear(partial(self.import_track_setup, filename))
		elif ext == '.sfz':
			self.when_clear(partial(self.load_single_sfz, filename))
		else:
			DevilBox('Unknown file format: ' + filename)

	# -----------------------------------------------------------------
	# Project save / load functions:

	def okay_to_clear(self):
		if not self.dirty:
			return True
		dlg = QMessageBox(
			QMessageBox.Warning,
			"Save changes?",
			"There are changes to the current setup.\nDo you want to save changes?",
			QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
			self
		)
		ret = dlg.exec()
		if ret == QMessageBox.Cancel:
			return False
		if ret == QMessageBox.Save:
			self.slot_save_project()
		return True

	def is_clear(self):
		return	len(self.port_layout) == 0 and \
				len(self.shared_plugin_layout) == 0 and \
				carla().is_clear()

	def when_clear(self, func):
		if self.is_clear():
			self.clear_internal_state()
			func()
		elif self.okay_to_clear():
			logging.debug('CLEARING')
			self.function_after_cleared = func
			self.is_clearing = True
			carla().remove_all_plugins()	# See: slot_last_plugin_removed

	def clear_internal_state(self):
		self.project_filename = None
		self.source_score = None
		self.wav_filename = None
		self.port_layout.clear()
		self.shared_plugin_layout.clear()
		self.balance_control_widget.clear()
		self.resync_port_list()
		self.clear_dirty()

	def new_project(self):
		self.clear_internal_state()

	def load_project(self, filename):
		from musecbox.dialogs.project_load_dialog import ProjectLoadDialog
		project_realpath = realpath(filename)
		logging.debug('Load project "%s"', project_realpath)
		if exists(project_realpath):
			try:
				with open(project_realpath, 'r') as fh:
					self.project_definition = json.load(fh)
			except json.JSONDecodeError as e:
				DevilBox(
					f'<p>There was a problem decoding "{filename}"</p>' + \
					f'<p>{e}</p>')
				self.setWindowTitle(APPLICATION_NAME)
			else:
				self.enter_loading_state()
				set_application_style()
				self.project_filename = project_realpath
				self.source_score = self.project_definition['source_score']
				self.balance_control_widget.slot_set_lines(setting(KEY_BCWIDGET_LINES, int, 3))
				if 'exported_wav_file' in self.project_definition:
					self.wav_filename = self.project_definition['exported_wav_file']
				if ProjectLoadDialog(self, self.project_definition).exec():
					recent_files().bump(self.project_filename)
					set_setting(KEY_RECENT_PROJECT_DIR, self.project_dir())
					if bool(setting(KEY_AUTO_START)):
						set_setting(KEY_AUTO_START, self.project_filename)
					self.project_load_complete()
		else:
			recent_files().remove(filename)
			DevilBox(f"Project not found: {filename}")

	def enter_loading_state(self):
		self.balance_control_widget.setEnabled(False)
		self.stop_timers()
		self.project_loading = True

	def project_load_complete(self):
		"""
		Called after loading saved project or importing track setup.
		"""
		for widget in self.port_layout:
			widget.project_load_complete()
		for widget in self.iterate_track_widgets():
			widget.project_load_complete()
		for widget in self.iterate_shared_plugin_widgets():
			widget.project_load_complete()
		QTimer.singleShot(DELAY_AFTER_LOAD, self.leave_loading_state)

	def leave_loading_state(self):
		self.clear_dirty()
		self.balance_control_widget.setEnabled(True)
		self.balance_control_widget.update()
		self.start_timers()
		self.action_watch_files.setChecked(setting(KEY_WATCH_FILES, bool))
		self.project_loading = False
		tracks_missing_sfzs = [ track for track in self.iterate_track_widgets() \
			if track.is_missing_sfz() ]
		if tracks_missing_sfzs:
			from musecbox.dialogs.missing_sfzs_dialog import MissingSFZsDialog
			MissingSFZsDialog(self, tracks_missing_sfzs).show()

	def load_recent(self, filename):
		"""
		Called when a file is selected from the recent file menu.
		This function differs from "load_project" in that it checks for okay to clear.
		"""
		self.when_clear(partial(self.load_project, filename))

	def import_score(self, filename):
		from musecbox.dialogs.score_import_dialog import ScoreImportDialog
		import_dialog = ScoreImportDialog(self, filename)
		if import_dialog.exec():
			self.source_score = import_dialog.encoded_score()
			set_setting(KEY_RECENT_SCORE_DIR, dirname(realpath(filename)))
			self.load_from_track_setup(import_dialog.track_setup())

	def import_track_setup(self, filename):
		try:
			with open(filename, 'r') as fh:
				setup = json.load(fh)
			self.load_from_track_setup(setup)
		except json.JSONDecodeError:
			DevilBox('There was a problem decoding "{0}"'.format(filename))

	def load_from_track_setup(self, setup):
		from musecbox.dialogs.score_load_dialog import ScoreLoadDialog
		self.enter_loading_state()
		if ScoreLoadDialog(self, setup).exec():
			self.project_load_complete()
			self.slot_save_project_as()

	def load_single_sfz(self, filename):
		self.enter_loading_state()
		self.single_sfz_filename = filename
		self.add_port(1, on_ready_slot = self.single_port_ready)

	@pyqtSlot(int)
	def single_port_ready(self, port_number):
		track_widget = self.port_widget(port_number).add_track(
			VoiceName(basename(self.single_sfz_filename), None),
			self.single_sfz_filename
		)
		track_widget.sig_ready.connect(self.single_track_ready, type = Qt.QueuedConnection)
		track_widget.add_to_carla()

	@pyqtSlot(int, int)
	def single_track_ready(self, port_number, slot):
		self.port_widget(port_number).route_channel_to_slot(1, slot)
		self.project_load_complete()

	def save_project(self):
		try:
			with open(self.project_filename, 'w') as fh:
				json.dump(self.encode_saved_state(), fh, indent="\t")
		except Exception as e:
			DevilBox(e)
		else:
			self.clear_dirty()

	def encode_saved_state(self):
		return {
			"source_score"		: self.source_score,	# dict created by ScoreImportDialog.encoded_score()
			"exported_wav_file"	: self.wav_filename,
			"options"			: { key:setting(key) for key in PROJECT_OPTION_KEYS },
			"ports"				: [ port.encode_saved_state() for port in self.port_layout ],
			"shared_plugins"	: [ plugin.encode_saved_state() for plugin in self.shared_plugin_layout ]
		}

	def copy_sfzs(self):
		self.setCursor(Qt.WaitCursor)
		samples_mode = setting(KEY_SAMPLES_MODE, bool)
		clean_sfzs = setting(KEY_CLEAN_SFZS, bool)
		title, _ = splitext(basename(self.project_filename))
		sfz_dir = join(self.project_dir(), title)

		CopyOp = namedtuple('CopyOp', ['track_widget', 'current', 'new_abs', 'new_relative'])
		copy_ops = [
			CopyOp(
				track_widget,
				track_widget.synth.sfz_filename,
				join(sfz_dir, basename(track_widget.synth.sfz_filename)),
				join(title, basename(track_widget.synth.sfz_filename))
			) for track_widget in self.iterate_track_widgets()
		]

		try:
			if not exists(sfz_dir):
				mkdir(sfz_dir)
			for op in copy_ops:
				sfz_copy = SFZ(op.current)
				if clean_sfzs:
					liquid_clean(sfz_copy)
				sfz_copy.save_as(op.new_abs, samples_mode)
				op.track_widget.synth.load_sfz(op.new_relative)
		except Exception as err:
			self.unsetCursor()
			QMessageBox.warning(self, "SFZ Copy failed",
				f"""<p>There was an error when copying {op.current} to {op.new_relative}:</p>
				<p><b>{err}</b></p>
				<p>None of the SFZs in your project will be copied to the new
				location - the original SFZ files will be used instead.</p>
				<p>You can try to fix the problem, and then choose "Save as ..."
				from the file menu in order to try again.</p>
				""")
			self.setCursor(Qt.WaitCursor)
			for op in copy_ops:
				try:
					op.track_widget.synth.load_sfz(op.current)
				except Exception as e:
					DevilBox(e)
		else:
			self.set_dirty()
		self.unsetCursor()

	def sfzs_used(self):
		"""
		Returns a list of (str) SFZ paths.
		"""
		return [ track_widget.synth.sfz_filename \
			for track_widget in self.iterate_track_widgets() ]

	def project_dir(self):
		return dirname(self.project_filename) if self.project_filename else None

	def option(self, key):
		if self.project_definition and key in self.project_definition['options']:
			return self.project_definition['options'][key]
		return None

	def set_option(self, key, value):
		if self.project_definition and key in PROJECT_OPTION_KEYS:
			self.project_definition['options'][key] = value
			self.set_dirty()
			return True
		return False

	# -----------------------------------------------------------------
	# Operational funcs:

	def track_widget_count(self):
		"""
		Used by balance_control_widget.spread()
		"""
		return sum( len(port_widget.track_layout) for port_widget in self.port_layout )

	def track_plugin_count(self):
		"""
		Used by self.update_ui()
		"""
		return sum( track_widget.plugin_count() for track_widget in self.iterate_track_widgets() )

	def port_widget(self, port, *, on_ready_slot = None):
		"""
		Returns existing PortWidget, if exists, else creates one.

		"port" is the public -facing port number

		The optional "on_ready_slot" is a function to be connected to the sig_ready
		signal of the port_widget's channel splitter. This allows for adding a port and
		then immediately adding a track to the port as soon as it is ready.
		"""
		if port in self.port_assignments:
			return self.port_layout[self.port_assignments[port]]
		return self.add_port(port, on_ready_slot = on_ready_slot)

	def resync_port_list(self):
		self.port_assignments = {
			port_widget.port:index \
			for index, port_widget, in enumerate(self.port_layout)
		}

	def add_port(self, port, *, saved_state = None, on_ready_slot = None):
		"""
		Adds a port to the project.
		Returns PortWidget.

		When called from the ProjectLoadDialog, a saved_state is passed for
		restoring saved state.

		The "on_ready_slot" is a function to be connected to the sig_ready signal of
		the port_widget's channel splitter. This allows for adding a port and then
		immediately adding a track to the port as soon as it is ready.
		"""
		port_widget = VerticalPortWidget(self, port, saved_state = saved_state) \
			if self.action_vertical_layout.isChecked() else \
			HorizontalPortWidget(self, port, saved_state = saved_state)
		inserted = False
		for midi_port, layout_index in self.port_assignments.items():
			if midi_port > port_widget.port:
				self.port_layout.insert(layout_index, port_widget)
				inserted = True
				break
		if not inserted:
			self.port_layout.append(port_widget)
		self.resync_port_list()
		self.set_dirty()
		if on_ready_slot:
			port_widget.sig_ready.connect(on_ready_slot)
		port_widget.sig_ready.connect(self.slot_port_ready)
		port_widget.sig_cleared.connect(self.slot_port_cleared)
		port_widget.add_to_carla()
		return port_widget

	def remove_port(self, port_widget):
		port_widget.remove_self()

	def add_shared_plugin_widget(self, plugin_def):
		recent_plugins().bump(plugin_def)
		try:
			plugin_widget = SharedPluginWidget(self, plugin_def)
		except Exception as e:
			DevilBox(str(e))
		else:
			self._append_shared_plugin(plugin_widget)
			plugin_widget.add_to_carla()
			self.set_dirty()

	def remove_shared_plugin(self, plugin):
		plugin.remove_from_carla()
		self.set_dirty()

	def restore_shared_plugin(self, saved_state):
		plugin_widget = SharedPluginWidget(self, saved_state["plugin_def"], saved_state = saved_state)
		self._append_shared_plugin(plugin_widget)
		return plugin_widget

	def _append_shared_plugin(self, plugin_widget):
		for src, tgt in [
			(plugin_widget.sig_removed, self.slot_plugin_removed),
			(plugin_widget.sig_parameter_changed, self.slot_parameter_changed)
		]: src.connect(tgt, type = Qt.QueuedConnection)
		self.shared_plugin_layout.append(plugin_widget)

	def track_widget(self, port, slot):
		return self.port_widget(port).track_widget(slot)

	def iterate_track_widgets(self):
		for port_widget in self.port_layout:
			yield from port_widget.iterate_track_widgets()

	def iterate_track_plugin_widgets(self):
		"""
		Generator function which yields only the plugin widgets of the track widgets.
		"""
		for port_widget in self.port_layout:
			yield from port_widget.iterate_track_plugin_widgets()

	def iterate_shared_plugin_widgets(self):
		"""
		Generator function which yields only the "shared" plugin widgets at the bottom
		of the main window.
		"""
		yield from self.shared_plugin_layout

	def watch(self, path):
		if self.file_system_watcher:
			logging.debug('Watch: %s', path)
			self.file_system_watcher.addPath(path)

	def unwatch(self, path):
		if self.file_system_watcher:
			logging.debug('Unwatch: %s', path)
			self.file_system_watcher.removePath(path)

	def select_style(self, style):
		set_setting(KEY_STYLE, style)
		set_application_style()

	# -----------------------------------------------------------------
	# QMainWindow overloads - system calls

	def closeEvent(self, event):
		if self.is_closing or self.is_clear():
			self.save_geometry()
			sync_settings()
			event.accept()
		else:
			if self.okay_to_clear():
				self.is_closing = True
				self.is_clearing = True
				carla().remove_all_plugins()
			event.ignore()

	def system_signal(self, *_):
		self.close()

	# -----------------------------------------------------------------
	# Slots which catch signals from gui widgets

	@pyqtSlot(int)
	def slot_port_ready(self, port):
		port_widget = self.port_layout[self.port_assignments[port]]

	@pyqtSlot(int)
	def slot_port_cleared(self, port):
		logging.debug('Port %s cleared', port)
		port_widget = self.port_layout[self.port_assignments[port]]
		if port_widget.is_removing:
			self.port_layout.remove(port_widget)
			self.resync_port_list()
			port_widget.deleteLater()
			self.set_dirty()

	# -----------------------------------------------------------------
	# Slots which catch signals originating from this window

	@pyqtSlot(bool)
	def slot_watch_files(self, state):
		set_setting(KEY_WATCH_FILES, state)
		if state:
			logging.debug('Initializing QFileSystemWatcher')
			self.file_system_watcher = QFileSystemWatcher(self)
			self.file_system_watcher.fileChanged.connect(self.slot_watched_file_changed)
			for track_widget in self.iterate_track_widgets():
				self.watch(track_widget.synth.sfz_filename)
		else:
			logging.debug('Deleting QFileSystemWatcher')
			self.file_system_watcher = None

	@pyqtSlot(str)
	def slot_watched_file_changed(self, sfz_filename):
		logging.debug('Watched file changed: %s', sfz_filename)
		path_exists = False
		for track_widget in self.iterate_track_widgets():
			if track_widget.synth.sfz_filename == sfz_filename:
				track_widget.synth.load_sfz(sfz_filename)
				path_exists = True
				break
		if not path_exists:
			self.unwatch(sfz_filename)

	@pyqtSlot(bool)
	def slot_show_toolbar(self, state):
		self.toolbar.setVisible(state)
		set_setting(KEY_SHOW_TOOLBAR, state)

	@pyqtSlot(bool)
	def slot_show_port_inputs(self, state):
		for port_widget in self.port_layout:
			port_widget.show_input(state)
		set_setting(KEY_SHOW_PORT_INPUTS, state)

	@pyqtSlot(bool)
	def slot_show_channels(self, state):
		for track_widget in self.iterate_track_widgets():
			track_widget.show_channels(state)
		set_setting(KEY_SHOW_CHANNELS, state)

	@pyqtSlot(bool)
	def slot_show_track_volume(self, state):
		for track_widget in self.iterate_track_widgets():
			track_widget.show_track_volume(state)
		set_setting(KEY_SHOW_TRACK_VOLUME, state)

	@pyqtSlot(bool)
	def slot_show_plugin_volume(self, state):
		for track_widget in self.iterate_track_widgets():
			track_widget.show_plugin_volume(state)
		set_setting(KEY_SHOW_PLUGIN_VOLUME, state)

	@pyqtSlot(bool)
	def slot_show_indicators(self, state):
		for track_widget in self.iterate_track_widgets():
			track_widget.show_indicators(state)
		for plugin_widget in self.iterate_shared_plugin_widgets():
			plugin_widget.show_indicators(state)
		set_setting(KEY_SHOW_INDICATORS, state)
		if state:
			self._update_indicator_timer.start()
		else:
			self._update_indicator_timer.stop()

	@pyqtSlot(bool)
	def slot_show_balance_control(self, state):
		self.frm_balance.setVisible(state)
		set_setting(KEY_SHOW_BALANCE, state)

	@pyqtSlot(bool)
	def slot_show_shared_plugins(self, state):
		self.scr_shared_plugins.setVisible(state)
		set_setting(KEY_SHOW_SHARED_PLUGINS, state)

	@pyqtSlot(bool)
	def slot_show_statusbar(self, state):
		self.frm_statusbar.setVisible(state)
		set_setting(KEY_SHOW_STATUSBAR, state)

	@pyqtSlot(bool)
	def slot_vertical_layout(self, state):
		set_setting(KEY_VERTICAL_LAYOUT, state)
		QMessageBox.information(self, 'Layout orientation changed',
			'You must restart MusecBox in order to see changes')

	@pyqtSlot(bool)
	def slot_set_autostart(self, state):
		set_setting(KEY_AUTO_START, self.project_filename if state else False)

	@pyqtSlot()
	def slot_connect_all_tracks(self):
		clients = TrackWidget.track_targets()
		selection, okay = QInputDialog().getItem(self,
			'Connect all tracks', 'Audio client',
			[tup[0] for tup in clients],
			0, False)
		if okay:
			for tup in clients:
				if tup[0] == selection:
					for track_widget in self.iterate_track_widgets():
						track_widget.slot_output_client_selected(*tup)
					break
			self.set_dirty()

	@pyqtSlot(bool)
	def slot_auto_connect_tracks(self, state):
		set_setting(KEY_AUTO_CONNECT, state)

	@pyqtSlot()
	def slot_collapse_all_ports(self):
		for port_widget in self.port_layout:
			port_widget.implement_collapse(True)

	@pyqtSlot()
	def slot_expand_all_ports(self):
		for port_widget in self.port_layout:
			port_widget.implement_collapse(False)

	@pyqtSlot()
	def slot_rollup_all_plugins(self):
		for plugin_widget in self.iterate_track_plugin_widgets():
			plugin_widget.rollup()

	@pyqtSlot()
	def slot_unroll_all_plugins(self):
		for plugin_widget in self.iterate_track_plugin_widgets():
			plugin_widget.unroll()

	@pyqtSlot()
	def slot_reload_style(self):
		set_application_style()

	@pyqtSlot()
	def slot_mute_all_tracks(self):
		for track_widget in self.iterate_track_widgets():
			track_widget.mute()

	@pyqtSlot()
	def slot_unmute_all_tracks(self):
		for track_widget in self.iterate_track_widgets():
			track_widget.unmute()

	@pyqtSlot(QPoint)
	def slot_shared_plugins_context_menu(self, position):
		menu = QMenu()
		clicked_plugin_widget = self.scr_shared_plugins.viewport().childAt(position)
		if clicked_plugin_widget is not None:
			while not isinstance(clicked_plugin_widget, Plugin) and clicked_plugin_widget.parent() is not None:
				clicked_plugin_widget = clicked_plugin_widget.parent()
			if isinstance(clicked_plugin_widget, Plugin):
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
				action = QAction('Spread balance full stereo', self)
				action.triggered.connect(clicked_plugin_widget.go_full_stereo)
				action.setEnabled(clicked_plugin_widget.can_balance)
				menu.addAction(action)
				action = QAction('Center stereo panning', self)
				action.triggered.connect(clicked_plugin_widget.center_panning)
				action.setEnabled(clicked_plugin_widget.can_pan)
				menu.addAction(action)
				menu.addSeparator()	# ---------------------
				action = QAction(f'Show "{clicked_plugin_widget.original_plugin_name}" info', self)
				action.triggered.connect(clicked_plugin_widget.slot_show_info_dialog)
				menu.addAction(action)
				action = QAction(f'Rename "{clicked_plugin_widget.moniker}"', self)
				action.triggered.connect(clicked_plugin_widget.slot_rename)
				menu.addAction(action)
				menu.addSeparator()	# ---------------------
				action = QAction(f'Remove "{clicked_plugin_widget.moniker}"', self)
				action.triggered.connect(partial(self.remove_shared_plugin, clicked_plugin_widget))
				menu.addAction(action)
		menu.addAction(self.action_add_shared_plugin)
		if len(self.shared_plugin_layout) > 0:
			menu.addAction(self.action_clear_shared_plugins)
		if len(recent_plugins()) > 0:
			menu.addSeparator()	# ---------------------
			for plugin_def in recent_plugins():
				action = QAction(f'Add {plugin_display_name(plugin_def)}', self)
				action.triggered.connect(partial(self.add_shared_plugin_widget, plugin_def))
				menu.addAction(action)
		menu.addSeparator()	# ---------------------
		menu.addAction(self.action_show_shared_plugins)
		menu.exec(self.scr_shared_plugins.mapToGlobal(position))

	@pyqtSlot()
	def slot_clear_shared_plugins(self):
		for plugin in reversed(self.shared_plugin_layout):
			plugin.remove_from_carla()

	@pyqtSlot()
	def slot_clear_track_plugins(self):
		for track_widget in self.iterate_track_widgets():
			track_widget.slot_remove_all_plugins()

	@pyqtSlot()
	def slot_show_connections(self):
		from musecbox.dialogs.connection_dialog import ConnectionsDialog
		ConnectionsDialog(self).show()

	@pyqtSlot()
	def slot_add_shared_plugin(self):
		plugin_def = CarlaPluginDialog(self).exec_dialog()
		if plugin_def is not None:
			self.add_shared_plugin_widget(plugin_def)

	@pyqtSlot()
	def slot_add_port(self):
		"""
		Triggered by action_add_port.
		"""
		existing_ports = list(self.port_assignments.keys())
		port, ok = QInputDialog.getInt(self, 'Add port', 'Enter the port number you wish to add',
			value = max(existing_ports) + 1 if len(existing_ports) else 1
		)
		if ok:
			if port in existing_ports:
				DevilBox("Port %d already exists" % port)
			else:
				self.port_widget(port)

	@pyqtSlot()
	def slot_add_track(self):
		"""
		Triggered by action_add_track
		"""
		from musecbox.dialogs.track_creation_dialog import TrackCreationDialog
		dialog = TrackCreationDialog(self)
		if dialog.exec():
			voice_name = VoiceName(dialog.cmb_instrument.currentText(), dialog.cmb_voice.currentText())
			self.port_widget(dialog.spn_port.value()).add_track(
				voice_name, dialog.sfz_filename).add_to_carla()

	@pyqtSlot()
	def slot_show_sfzdb(self):
		from musecbox.dialogs.sfzdb_dialog import SFZMaintDialog
		dlg = SFZMaintDialog()
		dlg.exec()

	@pyqtSlot()
	def slot_show_project_info(self):
		from musecbox.dialogs.project_info_dialog import ProjectInfoDialog
		ProjectInfoDialog(self).exec()

	@pyqtSlot()
	def slot_open_project_folder(self):
		xdg_open(self.project_dir())

	@pyqtSlot()
	def slot_show_score_info(self):
		from musecbox.dialogs.score_info_dialog import ScoreInfoDialog
		ScoreInfoDialog(self, self.source_score).exec()

	@pyqtSlot()
	def slot_apply_to_score(self):
		"""
		Choose one or more MuseScore3 files and apply current project settings.
		Display dialog if incongruent.
		"""
		from musecbox.dialogs.score_apply_dialog import ApplyScoreDialog
		filenames, _ = QFileDialog.getOpenFileNames(self,
			"Apply to a MuseScore3 score",
			self.source_score['filename'] if self.source_score \
				else setting(KEY_RECENT_SCORE_DIR, str, QDir.homePath()),
			MUSESCORE_FILE_TYPES
		)
		self.project_definition = self.encode_saved_state()
		for filename in filenames:
			ApplyScoreDialog(self, self.project_definition, filename).exec()
			set_setting(KEY_RECENT_SCORE_DIR, dirname(realpath(filename)))

	@pyqtSlot()
	def slot_recent_menu_show(self):
		self.menu_open_recent.clear()
		actions = []
		for filename in recent_files():
			action = QAction(filename, self)
			action.triggered.connect(partial(self.load_recent, filename))
			actions.append(action)
		self.menu_open_recent.addActions(actions)

	@pyqtSlot()
	def slot_view_menu_show(self):
		has_ports = len(self.port_layout) > 0
		has_tracks = self.track_widget_count() > 0
		self.action_collapse_all_ports.setEnabled(
			has_ports and \
			not all(port.is_collapsed() for port in self.port_layout))
		self.action_expand_all_ports.setEnabled(
			has_ports and \
			any(port.is_collapsed() for port in self.port_layout))
		self.action_rollup_all_plugins.setEnabled(
			has_tracks and \
			not all(plugin.is_rolled_up() for plugin in self.iterate_track_plugin_widgets()))
		self.action_unroll_all_plugins.setEnabled(
			has_tracks and \
			any(plugin.is_rolled_up() for plugin in self.iterate_track_plugin_widgets()))

	@pyqtSlot()
	def slot_new(self):
		self.when_clear(self.new_project)

	@pyqtSlot()
	def slot_open_file(self):
		if self.okay_to_clear():
			filename, _ = QFileDialog.getOpenFileName(self,
				"Open saved MuseCBox project",
				setting(KEY_RECENT_PROJECT_DIR, str, QDir.homePath()),
				SUPPORTED_FILE_TYPES
			)
			if filename != '':
				self.open_file(filename)

	@pyqtSlot()
	def slot_save_project(self):
		if self.project_filename is None:
			self.slot_save_project_as()
		else:
			self.save_project()

	@pyqtSlot()
	def slot_save_project_as(self):
		from musecbox.dialogs.project_save_dialog import ProjectSaveDialog
		filename = self.project_filename if self.project_filename \
			else self.source_score['filename'] if self.source_score \
			else None
		dlg = ProjectSaveDialog(self, filename)
		if dlg.exec():
			set_setting(KEY_COPY_SFZS, dlg.copy_sfzs)
			set_setting(KEY_CLEAN_SFZS, dlg.clean_sfzs)
			set_setting(KEY_SAMPLES_MODE, dlg.samples_mode)
			if self.project_filename != dlg.target_path:
				self.project_filename = dlg.target_path
				if dlg.copy_sfzs:
					self.copy_sfzs()
			self.save_project()

	@pyqtSlot()
	def slot_copy_sfzs(self):
		"""
		Copy SFZs to project folder
		"""
		from musecbox.dialogs.copy_sfzs_dialog import CopySFZsDialog
		dlg = CopySFZsDialog(self)
		if dlg.exec():
			set_setting(KEY_COPY_SFZS, dlg.copy_sfzs)
			set_setting(KEY_CLEAN_SFZS, dlg.clean_sfzs)
			set_setting(KEY_SAMPLES_MODE, dlg.samples_mode)
			self.copy_sfzs()

	@pyqtSlot()
	def slot_copy_sfz_paths(self):
		"""
		Copy SFZ paths to clipboard
		"""
		from musecbox.dialogs.copy_sfz_paths_dialog import CopySFZPathsDialog
		dlg = CopySFZPathsDialog(self, linesep.join(self.sfzs_used()))
		dlg.exec()

	@pyqtSlot()
	def slot_revert(self):
		self.when_clear(partial(self.load_project, self.project_filename))

	@pyqtSlot()
	def slot_close(self):
		self.when_clear(self.new_project)

	# -----------------------------------------------------------------
	# Slots for GUI widgets

	@pyqtSlot(QPoint)
	def slot_ports_context_menu(self, position):
		menu = QMenu()
		clicked_port_widget = self.frm_ports.childAt(position)
		if clicked_port_widget is None:
			menu.addAction(self.action_add_track)
		else:
			while not isinstance(clicked_port_widget, PortWidget) \
				and clicked_port_widget.parent() is not None:
				clicked_port_widget = clicked_port_widget.parent()
			if isinstance(clicked_port_widget, PortWidget):
				action = QAction('Add a new track', self)
				action.triggered.connect(clicked_port_widget.slot_add_track_dialog)
				action.setEnabled(len(clicked_port_widget.track_layout) < 16)
				menu.addAction(action)
				action = QAction('Remove all tracks', self)
				action.triggered.connect(clicked_port_widget.slot_remove_all_tracks)
				action.setEnabled(len(clicked_port_widget.track_layout) > 0)
				menu.addAction(action)
				action = QAction(f'Remove port {clicked_port_widget.port}', self)
				action.triggered.connect(clicked_port_widget.remove_self)
				menu.addAction(action)
				menu.addSeparator()	# ---------------------
			else:
				menu.addAction(self.action_add_track)
		menu.addAction(self.action_add_port)
		# Update expand / collapse ports:
		self.slot_view_menu_show()
		menu.addAction(self.action_collapse_all_ports)
		menu.addAction(self.action_expand_all_ports)
		if len(self.port_layout) > 0:
			action = QAction('Remove all ports', self)
			action.triggered.connect(self.slot_remove_all_ports)
			menu.addAction(action)
		menu.exec(self.frm_ports.mapToGlobal(position))

	@pyqtSlot()
	def slot_remove_all_ports(self):
		for port_widget in reversed(self.port_layout):
			port_widget.slot_remove_all_tracks()

	# -----------------------------------------------------------------
	# Transport -related slots

	@pyqtSlot()
	def slot_record(self):
		from musecbox.dialogs.record_dialog import RecordDialog
		if self.wav_filename:
			saveto = self.wav_filename
		elif self.source_score:
			title, _ = splitext(basename(self.source_score['filename']))
			saveto = join(self.project_dir(), title + '.wav')
		else:
			path, _ = splitext(self.project_filename)
			saveto = path + '.wav'
		self.wav_filename, _ = QFileDialog.getSaveFileName(
			self, "Save audio to ...", saveto, RENDER_FILE_TYPE)
		if self.wav_filename:
			logging.debug('Saving to %s', self.wav_filename)
			RecordDialog(self, saveto).exec()

	@pyqtSlot()
	def slot_transport_start(self):
		carla().transport_play()

	@pyqtSlot()
	def slot_transport_stop(self):
		carla().transport_pause()

	@pyqtSlot()
	def slot_transport_rewind(self):
		carla().transport_relocate(0)

	@pyqtSlot(bool)
	def slot_clear_xruns(self):
		carla().clear_engine_xruns()

	@pyqtSlot()
	def slot_cancel_action_click(self):
		carla().cancel_engine_action()

	# -----------------------------------------------------------------
	# Slots which catch signals from CarlaQt

	@pyqtSlot(Plugin)
	def slot_plugin_removed(self, plugin):
		self.shared_plugin_layout.remove(plugin)
		plugin.deleteLater()

	@pyqtSlot(Plugin, Parameter, float)
	def slot_parameter_changed(self, *_):
		self.set_dirty()

	@pyqtSlot()
	def slot_last_plugin_removed(self):
		"""
		Note: carla does not issue ENGINE_CALLBACK_PLUGIN_REMOVED when the last plugin
		is removed - only "last plugin removed". Hence, we need to have the last plugin
		emit it's "sig_removed" signal.
		"""
		logging.debug('Got sig_last_plugin_removed')
		for plugin in chain(
			self.iterate_track_plugin_widgets(),
			self.iterate_shared_plugin_widgets()
		): plugin.sig_removed.emit(plugin)
		self.clear_internal_state()	# May be unneccessary
		if self.is_clearing:
			if self.is_closing:
				self.close()
			else:
				self.is_clearing = False
				if self.function_after_cleared is not None:
					QTimer.singleShot(DELAY_AFTER_CLEAR, self.function_after_cleared)
					self.function_after_cleared = None

	@pyqtSlot(int, int, int, int, float, str)
	def slot_engine_started(self, _a, _b, transport_mode, buffer_size, sample_rate, _c):
		logging.debug('======= Engine started ======== ')
		self.update_buffer_size(buffer_size)
		self.update_sample_rate(sample_rate)
		self.b_xruns.setText('0 Xruns')
		self.transport_mode = transport_mode
		self.update_ui()
		self.start_timers()
		if self.startup_options.Filename:
			self.open_file(self.startup_options.Filename)
		else:
			autostart = setting(KEY_AUTO_START)
			if bool(autostart):
				self.open_file(autostart)
				self.action_auto_start.setChecked(True)

	@pyqtSlot()
	def slot_engine_stopped(self):
		logging.debug('======= Engine stopped ========')
		self.stop_timers()

	@pyqtSlot(int)
	def slot_process_mode_changed(self, mode):
		pass

	@pyqtSlot(int, str)
	def slot_transport_mode_changed(self, transport_mode, _):
		self.transport_mode = transport_mode
		self.update_ui()

	@pyqtSlot(int)
	def slot_buffer_size_changed(self, size):
		self.update_buffer_size(size)

	@pyqtSlot(float)
	def slot_sample_rate_changed(self, rate):
		self.update_sample_rate(int(rate))

	@pyqtSlot(int, bool, str)
	def slot_cancelable_action(self, _, started, action):
		if self._cancel_action_dialog is not None:
			self._cancel_action_dialog.close()
		if started:
			self._cancel_action_dialog = QMessageBox(self)
			self._cancel_action_dialog.setIcon(QMessageBox.Information)
			self._cancel_action_dialog.setWindowTitle(self.tr("Action in progress"))
			self._cancel_action_dialog.setText(action)
			self._cancel_action_dialog.setInformativeText(self.tr("An action is in progress, please wait..."))
			self._cancel_action_dialog.setStandardButtons(QMessageBox.Cancel)
			self._cancel_action_dialog.setDefaultButton(QMessageBox.Cancel)
			self._cancel_action_dialog.buttonClicked.connect(self.slot_cancel_action_click)
			self._cancel_action_dialog.show()
		else:
			self._cancel_action_dialog = None

	@pyqtSlot(str)
	def slot_carla_info(self, info):
		QMessageBox.information(self, "Information", info)

	@pyqtSlot(str)
	def slot_carla_error(self, error):
		DevilBox("Error:" + error)

	@pyqtSlot(str, str, str, int)
	def slot_application_error(self, err_type, err_message, err_file, err_line):
		DevilBox('{0} "{1}" in {2}, line {3}'.format(err_type, err_message, err_file, err_line))

	@pyqtSlot()
	def slot_carla_quit(self):
		self._project_is_loading = False
		self.stop_timers()


class SocketListener(QThread):

	sig_message = pyqtSignal(QVariant)

	def __init__(self):
		super().__init__()
		if exists(SOCKET_PATH):
			raise Exception("SOCKET_PATH already exists!")
		self.socket = socket(AF_UNIX, SOCK_DGRAM)
		self.socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
		self.socket.bind(SOCKET_PATH)

	def run(self):
		read_buffer = bytearray()
		while True:
			data = self.socket.recv(1024)
			if not data:
				break
			read_buffer += data
			while CARRIAGE_RETURN in read_buffer:
				idx = read_buffer.index(CARRIAGE_RETURN)
				self.sig_message.emit(read_buffer[:idx].decode())
				read_buffer = read_buffer[idx + 1:]


# -----------------------------------------------------------------
# LoadIndicator for statusbar

class LoadIndicator(QWidget):

	def __init__(self, parent):
		super().__init__(parent)
		self.__value = 0
		self.label = QLabel(self)
		self.label.setAlignment(Qt.AlignHCenter | Qt.AlignBaseline)
		self.label.setText("%d%%" % self.__value)
		self.bar = LoadIndicatorBar(self)
		lo = QVBoxLayout()
		lo.setSpacing(2)
		lo.setContentsMargins(0,0,0,0)
		lo.addWidget(self.label)
		lo.addWidget(self.bar)
		self.setLayout(lo)
		self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
		self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
		self.bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

	def setEnabled(self, state):
		super().setEnabled(state)
		if not state:
			self.bar.anim.stop()

	def set_value(self, value):
		self.label.setText("%d%%" % value)
		self.bar.set_value(value)


class LoadIndicatorBar(QWidget):

	anim_duration	= 900
	fixed_height	= 2

	def __init__(self, parent):
		super().__init__(parent)
		self.bg_brush = QBrush(Qt.SolidPattern)
		self.fill_brush = QBrush(QColor("#B31B00"), Qt.SolidPattern)
		self.setFixedHeight(self.fixed_height)
		self.__value = 0
		self.__display_value = 0.0
		self.__scaling = None
		self.anim = QPropertyAnimation(self, b"_display_value")
		self.anim.setDuration(self.anim_duration)
		QTimer.singleShot(LAYOUT_COMPLETE_DELAY, self.set_bg_color)

	def changeEvent(self, event):
		if event.type() == QEvent.StyleChange:
			self.set_bg_color()
		super().changeEvent(event)

	def set_bg_color(self):
		self.bg_brush.setColor(self.palette().color(QPalette.Window))

	def set_value(self, value):
		if value == self.__value:
			return
		self.__value = value
		# QAbstractAnimation.Stopped
		# QAbstractAnimation.Paused
		# QAbstractAnimation.Running
		self.anim.setEndValue(float(value))
		if self.anim.state() == QAbstractAnimation.Stopped:
			self.anim.start()

	@pyqtProperty(float)
	def _display_value(self):
		return self.__display_value

	@_display_value.setter
	def _display_value(self, value):
		self.__display_value = value
		self.update()

	def resizeEvent(self, event):
		self.__scaling = event.size().width() / 100

	def paintEvent(self, _):
		painter = QPainter(self)
		x = int(self.__display_value * self.__scaling)
		painter.fillRect(0, 0, x, self.fixed_height, self.fill_brush)
		painter.fillRect(x, 0, self.width() - x, self.fixed_height, self.bg_brush)
		painter.end()


#  end musecbox/gui/main_window.py
