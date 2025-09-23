#  musecbox/sfz_previewer.py
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
Provides a synth used for previewing SFZ files in SFZFileDialog.
"""
import logging
from os.path import join
from PyQt5.QtCore import Qt, pyqtSlot
from musecbox import	carla, setting, set_setting, APP_PATH, \
						KEY_PREVIEW_FILES, KEY_PREVIEWER_MIDI_SRC, KEY_PREVIEWER_AUDIO_TGT
from musecbox.liquidsfz import LiquidSFZ


class SFZPreviewer(LiquidSFZ):
	"""
	A Synth which automatically attaches to the first physical MIDI input port, and
	the first physical audio output ports, which is used for generating a preview
	of SFZ files when selecting.
	"""

	def __init__(self):
		super().__init__(join(APP_PATH, 'res', 'empty.sfz'))
		self._midi_src = None
		self._audio_tgt = None
		self.sig_ready.connect(self.slot_auto_connect, type = Qt.QueuedConnection)

	@pyqtSlot()
	def slot_auto_connect(self):
		self.active = setting(KEY_PREVIEW_FILES, bool)
		# self._midi_src is a PatchbayPort
		if midi_src_name := setting(KEY_PREVIEWER_MIDI_SRC):
			_, port_name = midi_src_name.split(':', 1)
			try:
				client = carla().system_client_by_name(midi_src_name)
				self.midi_src = client.named_port(port_name)
			except IndexError:
				pass
		if self.midi_src is None:
			for client in carla().system_midi_out_clients():
				self.midi_src = client.midi_outs()[0]
				break
		# self._audio_tgt is a SystemPatchbayClient
		if audio_tgt_name := setting(KEY_PREVIEWER_AUDIO_TGT):
			self.audio_tgt = carla().system_client_by_name(audio_tgt_name)
		if self.audio_tgt is None:
			for self.audio_tgt in carla().system_audio_in_clients():
				break

	@pyqtSlot()
	def deactivate(self):
		"""
		Tell the previewer to stop producing sounds.
		"""
		self.active = False

	@staticmethod
	def midi_sources():
		"""
		Returns a list of MIDI out port which the previewer can connect to.
		"""
		return [ (patchbay_port.jack_name(), patchbay_port) \
			for patchbay_port in carla().system_midi_out_ports() ]

	@staticmethod
	def audio_targets():
		"""
		Returns a list of audio in clients which the previewer can connect to.
		"""
		return [ (client.moniker, client) \
			for client in carla().system_audio_in_clients() ]

	@property
	def midi_src(self):
		return self._midi_src

	@midi_src.setter
	def midi_src(self, midi_src):
		"""
		Connects the selected port to MIDI input port.
		"""
		self.disconnect_midi_inputs()
		midi_src.connect_to(self.midi_input_port())
		set_setting(KEY_PREVIEWER_MIDI_SRC, midi_src.jack_name())
		self._midi_src = midi_src

	@property
	def audio_tgt(self):
		return self._audio_tgt

	@audio_tgt.setter
	def audio_tgt(self, audio_tgt):
		"""
		Connects the selected client to previewer MIDI input port.
		"""
		self.disconnect_audio_outputs()
		self.connect_audio_outputs_to(audio_tgt)
		set_setting(KEY_PREVIEWER_AUDIO_TGT, audio_tgt.client_name)
		self._audio_tgt = audio_tgt


#  end musecbox/sfz_previewer.py
