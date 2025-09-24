#  musecbox/dialogs/record_dialog.py
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
Provides a dialog which shows modal when recording.
"""
import logging
from os.path import join, dirname
from qt_extras import ShutUpQT
from simple_carla import Plugin

# PyQt5 imports
from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSlot, QTimer
from PyQt5.QtWidgets import QApplication, QDialog

from musecbox import set_application_style, carla, main_window, LOG_FORMAT
from musecbox.audio_recorder import AudioRecorder


CONNECT_DELAY	= 300
START_DELAY		= 500
STOP_DELAY		= 100
TIMER_MS		= 200
REWIND_TRIES	= 8
REWIND_WAIT		= 0.2


class RecordDialog(QDialog):

	def __init__(self, parent, filename):
		super().__init__(parent)
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'record_dialog.ui'), self)
		self.lbl_filename.setText(filename)
		self.timer = QTimer()
		self.timer.setInterval(TIMER_MS)
		self.timer.timeout.connect(self.slot_timer_timeout)
		self.recorder = AudioRecorder()
		self.recorder.sig_ready.connect(self.slot_recorder_ready)
		self.recorder.add_to_carla()
		self.started_playing = False

	@pyqtSlot(Plugin)
	def slot_recorder_ready(self, _):
		if mw := main_window():
			musecbox_clients = list(track_widget.last_plugin() \
				for track_widget in mw.iterate_track_widgets())
			musecbox_clients.extend(mw.iterate_shared_plugin_widgets())
			for client in set(
				source_client \
				for patchbay_client in carla().system_audio_in_clients() \
				for source_client in patchbay_client.audio_input_clients() \
				if source_client in musecbox_clients):
				client.connect_audio_outputs_to(self.recorder)
			QTimer.singleShot(CONNECT_DELAY, self.slot_ready)

	@pyqtSlot()
	def slot_ready(self):
		gcarla = carla()
		gcarla.transport_relocate(0)
		rewind_tries = 0
		while gcarla.get_current_transport_frame() != 0:
			rewind_tries += 1
			if rewind_tries > REWIND_TRIES:
				raise RuntimeError("Cannot rewind")
			sleep(REWIND_WAIT)
		self.recorder.record()
		QTimer.singleShot(START_DELAY, self.slot_start)

	@pyqtSlot()
	def slot_start(self):
		carla().transport_play()
		self.timer.start()

	@pyqtSlot()
	def slot_timer_timeout(self):
		info = carla().get_transport_info()
		if info['playing']:
			self.started_playing = True
			self.lbl_frame.setText(str(info['frame']))
		elif self.started_playing:
			self.timer.stop()
			self.lbl_frame.setText('-----')
			QTimer.singleShot(STOP_DELAY, self.slot_stop)

	@pyqtSlot()
	def slot_stop(self):
		carla().transport_pause()
		self.recorder.save_as(self.lbl_filename.text())
		self.recorder.remove_from_carla()
		self.accept()


class TestApp(QApplication):

	def __init__(self):
		super().__init__([])
		set_application_style()
		carla().sig_engine_started.connect(self.slot_engine_started, type = Qt.QueuedConnection)
		if not carla().engine_init():
			raise EngineInitFailure()

	@pyqtSlot(int, int, int, int, float, str)
	def slot_engine_started(*_):
		logging.debug('======= Engine started ======== ')
		dialog = RecordDialog(None, '/save/to/filename.wav')
		dialog.exec()
		carla().delete()


def main():
	logging.basicConfig(level = logging.DEBUG, format = LOG_FORMAT)
	TestApp().exec()


if __name__ == "__main__":
	main()


#  end musecbox/dialogs/record_dialog.py
