#  musecbox/dialogs/score_load_dialog.py
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
Class used for loading track setup contructed from MuseScore3 file.
"""
from os.path import join, dirname
from mscore import VoiceName
from qt_extras import ShutUpQT, DevilBox

# PyQt5 imports
from PyQt5 import			uic
from PyQt5.QtCore import	pyqtSlot, QTimer
from PyQt5.QtWidgets import QDialog

from musecbox import LAYOUT_COMPLETE_DELAY

STEP_DELAY = 50
WATCHDOG_TIMEOUT = 2500


class ScoreLoadDialog(QDialog):
	"""
	Executes importing of a MuseScore score, displaying a progress bar.
	"""

	def __init__(self, parent, track_setup):
		"""
		"track_setup" is a list of dicts produced by the ScoreImportDialog.
		"""
		super().__init__(parent)
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'project_load_dialog.ui'), self)
		self.restore_geometry()
		self.finished.connect(self.save_geometry)
		self.rejected.connect(self.slot_rejected)
		self.watchdog_timer = QTimer(self)
		self.watchdog_timer.setInterval(WATCHDOG_TIMEOUT)
		self.watchdog_timer.setSingleShot(True)
		self.watchdog_timer.timeout.connect(self.slot_watchdog_timeout)
		self.track_setup = track_setup
		self.pb_progress.setMaximum(len(self.track_setup))
		self.current_track_index = 0
		self.continue_loading = True
		QTimer.singleShot(LAYOUT_COMPLETE_DELAY, self.start_next_step)

	@pyqtSlot()
	def slot_rejected(self):
		self.continue_loading = False

	def start_next_step(self):
		if self.current_track_index < len(self.track_setup):
			if self.continue_loading:
				setup = self.track_setup[self.current_track_index]
				moniker = f"{setup['part']} ({setup['voice']})"
				self.lbl_step.setText(f'Setting up {moniker} ...')
				self.pb_progress.setValue(self.current_track_index)
				port_widget = self.parent().port_widget(
					setup['midi_port'], on_ready_slot = self.slot_port_ready)
				if port_widget.channel_splitter.is_ready:
					self.slot_port_ready(setup['midi_port'])
				else:
					self.watchdog_timer.start()
			else:
				self.reject()
		else:
			self.accept()

	@pyqtSlot(int)
	def slot_port_ready(self, _):
		self.watchdog_timer.stop()
		setup = self.track_setup[self.current_track_index]
		moniker = f"{setup['part']} ({setup['voice']})"
		port_widget = self.parent().port_widget(setup['midi_port'])
		track_widget = port_widget.add_track(
			VoiceName(setup['instrument'], setup['voice']),
			setup['sfz']
		)
		track_widget.sig_ready.connect(self.slot_track_ready)
		try:
			track_widget.add_to_carla()
		except Exception as e:
			DevilBox(e)

	@pyqtSlot(int, int)
	def slot_track_ready(self, port, slot):
		self.watchdog_timer.stop()
		setup = self.track_setup[self.current_track_index]
		self.parent().port_widget(port).route_channel_to_slot(setup['midi_channel'], slot)
		self.current_track_index += 1
		QTimer.singleShot(STEP_DELAY, self.start_next_step)

	@pyqtSlot()
	def slot_watchdog_timeout(self):
		self.lbl_step.setText('The current step is taking a long time to complete. Please be patient.')


#  end musecbox/dialogs/score_import_dialog.py
