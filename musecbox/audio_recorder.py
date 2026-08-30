#  musecbox/audio_recorder.py
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
Provides AudioRecorder class
"""
import logging	 # pylint: disable = unused-import
from pathlib import Path
from shutil import move
from simple_carla.qt import QtPlugin
from PyQt5.QtCore import QDir


class AudioRecorder(QtPlugin):

	plugin_def = {
		"name"		: 'StereoRecord',
		"build"		: 2,
		"type"		: 4,
		"filename"	: 'sc_record.lv2',
		"label"		: 'https://github.com/brummer10/screcord#stereo_record',
		"uniqueId"	: 0
	}

	def __init__(self):
		super().__init__()
		self.directory_path = Path(QDir.homePath()) / 'lv2record'
		self.startup_files = None

	def record(self):
		self.parameter('FORM').value = 0.0
		self.parameter('REC').value = 1.0
		self.startup_files = set(self.directory_path.iterdir()) \
			if self.directory_path.exists() else []

	def save_as(self, filename):
		self.parameter('REC').value = 0.0
		new_paths = set(self.directory_path.iterdir()) - self.startup_files
		if len(new_paths) == 0:
			raise RuntimeError('Nothing saved by lv2record')
		if len(new_paths) > 1:
			raise RuntimeWarning('Multiple files saved by lv2record')
		move(new_paths.pop(), filename)


#  end musecbox/audio_recorder.py
