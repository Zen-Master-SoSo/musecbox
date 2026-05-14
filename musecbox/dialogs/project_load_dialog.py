#  musecbox/dialogs/project_load_dialog.py
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
 rovides a dialog which loads a project and displays its progress.
"""
import logging
from os.path import join, dirname
from time import time
from functools import partial
from simple_carla.qt import Plugin
from qt_extras import ShutUpQT, DevilBox
from collections import namedtuple

# PyQt5 imports
from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSlot, QTimer
from PyQt5.QtWidgets import QApplication, QDialog

from musecbox import LAYOUT_COMPLETE_DELAY

PLUGIN_READY_DELAY = 20
PROGRESS_LABEL_PERIOD = 333
Step = namedtuple('Step', ['label', 'func'])


class ProjectLoadDialog(QDialog):

	def __init__(self, parent, project_definition):
		super().__init__(parent)
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'project_load_dialog.ui'), self)
		self.restore_geometry()
		self.finished.connect(self.save_geometry)
		self.rejected.connect(self.slot_rejected)

		# self.tracks_missing_sfzs is a list of track_widget which have missing SFZs:
		self.tracks_missing_sfzs = []

		# self.steps is a list which contains tuples of type Step:
		# 	label:	A label to display on this progress dialog,
		# 	func:	The function to call to acomplish the step,
		self.steps = []
		for port_definition in project_definition["ports"]:
			self.steps.append(Step(
				f'Setup port #{port_definition["port"]}',
				partial(self.restore_port, port_definition)
			))
			for track_definition in port_definition["tracks"]:
				self.steps.append(Step(
					f'Setup track "{track_definition["moniker"]}"',
					partial(self.restore_track, track_definition)
				))
				for saved_state in track_definition["plugins"]:
					self.steps.append(Step(
						f'Restore track plugin {saved_state["vars"]["moniker"]}',
						partial(self.restore_track_plugin,
							track_definition["port"], track_definition["slot"],
							saved_state)
					))
		for saved_state in project_definition["shared_plugins"]:
			self.steps.append(Step(
				f'Restore shared plugin {saved_state["vars"]["moniker"]}',
				partial(self.restore_shared_plugin, saved_state)
			))
		self.pb_progress.setMaximum(len(self.steps) + 1)
		self.label_update_timer = QTimer(self)
		self.label_update_timer.timeout.connect(self.slot_update_label)
		self.label_update_timer.setInterval(PROGRESS_LABEL_PERIOD)
		self.label_update_timer.start()
		self.continue_loading = True
		self.start_time = time()
		self.current_step_index = -1
		QTimer.singleShot(LAYOUT_COMPLETE_DELAY, self.start_next_step)

	def start_next_step(self):
		if self.continue_loading:
			self.current_step_index += 1
			self.pb_progress.setValue(self.current_step_index)
			if self.current_step_index < len(self.steps):
				self.steps[self.current_step_index].func()
			else:
				self.label_update_timer.stop()
				logging.debug('Finished project load in %.3f seconds', time() - self.start_time)
				self.accept()
		else:
			self.label_update_timer.stop()
			self.reject()

	def restore_port(self, port_definition):
		self.parent().add_port(port_definition['port'],
			saved_state = port_definition, on_ready_slot = self.slot_port_ready)

	def restore_track(self, track_definition):
		port_widget = self.parent().port_widget(track_definition["port"])
		track_widget = port_widget.restore_track(track_definition)
		track_widget.sig_ready.connect(self.slot_track_ready)
		try:
			track_widget.add_to_carla()
		except Exception as e:
			DevilBox(e)

	def restore_track_plugin(self, port, slot, saved_state):
		plugin = self.parent().track_widget(port, slot).restore_plugin(saved_state)
		plugin.sig_ready.connect(self.slot_plugin_ready, type = Qt.QueuedConnection)
		try:
			plugin.add_to_carla()
		except Exception as e:
			DevilBox(f'Failed to add plugin "{saved_state["plugin_def"]["name"]}"')
			QTimer.singleShot(PLUGIN_READY_DELAY, self.start_next_step)

	def restore_shared_plugin(self, saved_state):
		plugin = self.parent().restore_shared_plugin(saved_state)
		plugin.sig_ready.connect(self.slot_plugin_ready, type = Qt.QueuedConnection)
		try:
			plugin.add_to_carla()
		except Exception as e:
			DevilBox(f'Failed to add plugin "{saved_state["plugin_def"]["name"]}"')
			QTimer.singleShot(PLUGIN_READY_DELAY, self.start_next_step)

	@pyqtSlot(int)
	def slot_port_ready(self, _):
		QApplication.instance().processEvents()
		QTimer.singleShot(PLUGIN_READY_DELAY, self.start_next_step)

	@pyqtSlot(int, int)
	def slot_track_ready(self, *_):
		QApplication.instance().processEvents()
		QTimer.singleShot(PLUGIN_READY_DELAY, self.start_next_step)

	@pyqtSlot(Plugin)
	def slot_plugin_ready(self, _):
		QApplication.instance().processEvents()
		QTimer.singleShot(PLUGIN_READY_DELAY, self.start_next_step)

	@pyqtSlot()
	def slot_update_label(self):
		self.lbl_step.setText(self.steps[self.current_step_index].label)

	@pyqtSlot()
	def slot_rejected(self):
		self.continue_loading = False


#  end musecbox/dialogs/project_load_dialog.py
