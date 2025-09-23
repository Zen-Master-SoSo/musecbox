#  musecbox/liquidsfz.py
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
Provides synth plugin used by TrackWidget and SFZPreviewer
"""
from simple_carla.qt import QtPlugin
from PyQt5.QtCore import pyqtSignal
from musecbox import carla


class LiquidSFZ(QtPlugin):
	"""
	Base class of TrackSynth and SFZPreviewer.
	Pre-defined plugin.
	Autoloads the SFZ file.
	"""

	sig_midi_active = pyqtSignal(bool)

	def __init__(self, sfz_filename, *, saved_state = None):
		self.sfz_filename = sfz_filename
		super().__init__({
			'build'		: 2,
			'type'		: 4,
			'filename'	: 'liquidsfz.lv2',
			'name'		: 'liquidsfz',
			'label'		: 'http://spectmorph.org/plugins/liquidsfz',
			'uniqueId'	: None
		}, saved_state)

	def finalize_init(self):
		self.reload()

	def load_sfz(self, sfz_filename):
		self.sfz_filename = sfz_filename
		self.reload()

	def reload(self):
		carla().autoload(self, self.sfz_filename, self.auto_load_complete)

	def auto_load_complete(self):
		self.check_ports_ready()

	def midi_active(self, state):
		self.sig_midi_active.emit(state)

	def midi_input_port(self):
		return self.midi_ins()[0]


#  end musecbox/liquidsfz.py
