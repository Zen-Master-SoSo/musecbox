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
import logging
from os import unlink
from tempfile import mkstemp
from PyQt5.QtCore import Qt, pyqtSignal
from simple_carla.qt import QtPlugin
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
		}, saved_state = saved_state)

	def finalize_init(self):
		self.sig_ready.connect(self.reload, type = Qt.QueuedConnection)

	def load_sfz(self, sfz_filename):
		self.sfz_filename = sfz_filename
		self.reload()

	def reload(self):
		logging.debug('Loading "%s"', self.sfz_filename)
		_, tempfile = mkstemp(prefix = 'liquidsfz-', suffix = '.state')
		with open(tempfile, 'w') as fob:
			fob.write(self.state_xml())
		carla().load_plugin_state(self.plugin_id, tempfile)
		unlink(tempfile)

	def state_xml(self):
		active = 'Yes' if self._active else 'No'
		control_channel = self._control_channel or 1
		out_level = self.parameter('Output Level').value
		return f"""<?xml version='1.0' encoding='UTF-8'?>
<!DOCTYPE CARLA-PRESET>
<CARLA-PRESET VERSION='2.0'>
  <Info>
   <Type>LV2</Type>
   <Name>liquidsfz 1</Name>
   <URI>http://spectmorph.org/plugins/liquidsfz</URI>
  </Info>

  <Data>
   <Active>{active}</Active>
   <ControlChannel>{control_channel}</ControlChannel>
   <Options>0x{self.optionsEnabled:x}</Options>

   <Parameter>
    <Index>0</Index>
    <Name>Output Level</Name>
    <Symbol>level</Symbol>
    <Value>{out_level}</Value>
   </Parameter>

   <CustomData>
    <Type>http://lv2plug.in/ns/ext/atom#Path</Type>
    <Key>http://spectmorph.org/plugins/liquidsfz#sfzfile</Key>
    <Value>{self.sfz_filename}</Value>
   </CustomData>

   <CustomData>
    <Type>http://lv2plug.in/ns/ext/atom#Int</Type>
    <Key>http://spectmorph.org/plugins/liquidsfz#program</Key>
    <Value>AAAAAA==</Value>
   </CustomData>
  </Data>
</CARLA-PRESET>
"""

	def midi_active(self, state):
		self.sig_midi_active.emit(bool(state))

	def midi_input_port(self):
		return self.midi_ins()[0]


#  end musecbox/liquidsfz.py
