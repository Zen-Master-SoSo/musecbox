#  musecbox/__init__.py
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
"MusecBox" is A GUI application designed to be an SFZ -based synth replacement
for MuseScore3.

MusecBox utilizes the Carla plugin host application as its back-end. The
front-end is writted entirely in python, using PyQt.

Some features include.:

* Multiple MIDI port inputs with up to 16 tracks per port.
* The ability to create a project by importing a MuseScore3 file.
* A command line script which allows you to change the MuseScore3 MIDI port
assignments to match your project.
* The ability to add any plugin available to Carla to individual tracks.
* The ability to add shared plugins and route the output of individual tracks
to the shared plugins.
* A graphical balance control widget which allows you to visually set the
location of each instrument within the stereo plane.
* Super quick project load times.

"""
import sys, logging, argparse, glob
from os.path import join, dirname, basename, realpath, splitext
from os import linesep
try:
	from os import startfile
except ImportError:
	pass
from platform import system
from subprocess import Popen
from tempfile import gettempdir as tempdir
from traceback import print_tb

# PyQt5 imports
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtWidgets import QApplication, QWidget, QSplitter, QErrorMessage
from PyQt5.QtGui import QFont

from recent_items_list import RecentItemsList
from simple_carla import (
	PLUGIN_NONE,
	PLUGIN_INTERNAL,
	PLUGIN_LADSPA,
	PLUGIN_DSSI,
	PLUGIN_LV2,
	PLUGIN_VST2,
	PLUGIN_VST3,
	PLUGIN_AU,
	PLUGIN_DLS,
	PLUGIN_GIG,
	PLUGIN_SF2,
	PLUGIN_SFZ,
	PLUGIN_JACK,
	PLUGIN_JSFX,
	PLUGIN_CLAP
)
from simple_carla.qt import CarlaQt
from qt_extras import DevilBox
from log_soso import StreamToLogger

__version__ = "0.0.3"

APPLICATION_NAME		= 'MusecBox'
APP_PATH				= dirname(realpath(__file__))
SOCKET_PATH				= join(tempdir(), 'musecbox.socket')
CARRIAGE_RETURN			= linesep.encode()
DEFAULT_STYLE			= 'system'
LAYOUT_COMPLETE_DELAY	= 50
LOG_FORMAT				= "[%(filename)24s:%(lineno)4d] %(levelname)-8s %(message)s"

# -------------------------------------------------------------------
# Plugin type lookup dict (see str

PLUGIN_TYPE_STRINGS = {
	PLUGIN_INTERNAL: 'Internal',
	PLUGIN_LADSPA: 'LADSPA',
	PLUGIN_DSSI: 'DSSI',
	PLUGIN_LV2: 'LV2',
	PLUGIN_VST2: 'VST2',
	PLUGIN_VST3: 'VST3',
	PLUGIN_AU: 'AU',
	PLUGIN_DLS: 'DLS file',
	PLUGIN_GIG: 'GIG file',
	PLUGIN_SF2: 'SF2 (SoundFont)',
	PLUGIN_SFZ: 'SFZ (Carla)',
	PLUGIN_JACK: 'JACK app',
	PLUGIN_JSFX: 'JSFX',
	PLUGIN_CLAP: 'CLAP'
}

# -----------------------------------------------------------
# Filetype strings

PROJECT_FILE_TYPE		= "MusecBox project (*.mbxp)"
MUSESCORE_FILE_TYPES	= "MuseScore score (*.mscz *.mscx)"
TRACK_DEF_FILE_TYPE		= "Tab -separated values (*.tsv)"
RENDER_FILE_TYPE		= "Wav files (*.wav)"
SFZ_FILE_TYPE			= "SFZ instrument definition (*.sfz)"
SUPPORTED_FILE_TYPES	= "All supported files (*.mbxp *.mbxt *.mscz *.mscx *.sfz);;" + \
						  "MusecBox project (*.mbxp);;" + \
						  "MusecBox track definition (*.mbxt);;" + \
						  "MuseScore score (*.mscz *.mscx);;" + \
						  "SFZ instruments (*.sfz)"

# -----------------------------------------------------------
# Settings keys

KEY_VERTICAL_LAYOUT		= 'MainWindow/VerticalLayout'
KEY_STYLE				= 'Style'
KEY_COPY_SFZS			= 'Saving/SFZCopyToProject'
KEY_SAMPLES_MODE		= 'Saving/SFZSamplesMode'
KEY_CLEAN_SFZS			= 'Saving/SFZClean'
KEY_RECENT_FILES		= 'RecentFiles'
KEY_RECENT_PLUGINS		= 'RecentPlugins'
KEY_RECENT_PROJECT_DIR	= 'Dirs/RecentProject'
KEY_RECENT_SCORE_DIR	= 'Dirs/RecentScore'
KEY_RECENT_EXPORT_DIR	= 'Dirs/RecentExport'
KEY_SFZ_DIR				= 'Dirs/SFZFiles'
KEY_SCORES_DIR			= 'Dirs/Scores'
KEY_SHOW_CHANNELS		= 'TrackWidget/ShowChannels'
KEY_SHOW_INDICATORS		= 'TrackWidget/ShowIndicators'
KEY_SHOW_TOOLBAR		= 'MainWindow/ShowToolbar'
KEY_SHOW_PORT_INPUTS	= 'MainWindow/ShowPortInputs'
KEY_SHOW_BALANCE		= 'MainWindow/ShowBalanceControl'
KEY_SHOW_SHARED_PLUGINS	= 'MainWindow/ShowSharedPlugins'
KEY_SHOW_STATUSBAR		= 'MainWindow/ShowStatusbar'
KEY_SHOW_TRACK_VOLUME	= 'MainWindow/ShowTrackVolume'
KEY_SHOW_PLUGIN_VOLUME	= 'MainWindow/ShowPluginVolume'
KEY_AUTO_CONNECT		= 'MainWindow/AutoConnectTracks'
KEY_AUTO_START			= 'MainWindow/AutoStartProject'
KEY_WATCH_FILES			= 'MainWindow/WatchFiles'
KEY_BCWIDGET_LINES		= 'MainWindow/BalanceControlWidgetLines'
KEY_BCWIDGET_LABELS		= 'BalanceControlWidget/ShowLabels'
KEY_BCWIDGET_TRACKING	= 'BalanceControlWidget/HoverTracking'
KEY_PREVIEW_FILES		= 'SFZFileDialog/PreviewFiles'
KEY_PREVIEWER_MIDI_SRC	= 'SFZPreviewer/MIDISource'
KEY_PREVIEWER_AUDIO_TGT	= 'SFZPreviewer/AudioTarget'

# -----------------------------------------------------------
# Keys which are saved on a per-project basis:

PROJECT_OPTION_KEYS = [
	KEY_VERTICAL_LAYOUT,
	KEY_STYLE,
	KEY_COPY_SFZS,
	KEY_SAMPLES_MODE,
	KEY_CLEAN_SFZS,
	KEY_RECENT_PLUGINS,
	KEY_RECENT_PROJECT_DIR,
	KEY_RECENT_SCORE_DIR,
	KEY_RECENT_EXPORT_DIR,
	KEY_SFZ_DIR,
	KEY_SCORES_DIR,
	KEY_SHOW_CHANNELS,
	KEY_SHOW_INDICATORS,
	KEY_SHOW_TOOLBAR,
	KEY_SHOW_PORT_INPUTS,
	KEY_SHOW_BALANCE,
	KEY_SHOW_SHARED_PLUGINS,
	KEY_SHOW_STATUSBAR,
	KEY_SHOW_TRACK_VOLUME,
	KEY_SHOW_PLUGIN_VOLUME,
	KEY_BCWIDGET_LINES,
	KEY_WATCH_FILES,
	KEY_PREVIEW_FILES,
	KEY_PREVIEWER_MIDI_SRC,
	KEY_PREVIEWER_AUDIO_TGT
]

# -----------------------------------------------------------
# Global texts

TEXT_NO_CONN			= '- none -'
TEXT_MULTI_CONN			= '* %d *'
TEXT_CONNECTED_TO		= 'Connected to "%s"'
TEXT_NO_GROUP			= '(All sfzs)'
TEXT_NEW_GROUP			= 'New group ...'

T_SAMPLEMODE_ABSPATH	= 'Point to the original samples - absolute path'
T_SAMPLEMODE_RELPATH	= 'Point to the original samples - relative path'
T_SAMPLEMODE_COPY		= 'Copy samples to a "<project name>-samples" folder'
T_SAMPLEMODE_SYMLINK	= 'Create symlinks in a "<project name>-samples" folder'
T_SAMPLEMODE_HARDLINK	= 'Hardlink the originals in a "<project name>-samples" folder'

T_COPY_TO_LOCAL			= 'Copy SFZs to a local project folder'
T_CLEAN_SFZ				= 'Remove opcodes not recognized by LiquidSFZ'

# -------------------------------------------------------------------
# Global objects

__CARLA = None
__MAIN_WINDOW = None
__SFZ_PREVIEWER = None
__RECENT_PLUGINS = None
__RECENT_FILES = None
__SETTINGS = None
__STYLES = None

def carla():
	global __CARLA
	if __CARLA is None:
		__CARLA = CarlaQt(APPLICATION_NAME)
	return __CARLA

def set_main_window(window):
	global __MAIN_WINDOW
	__MAIN_WINDOW = window

def main_window():
	return __MAIN_WINDOW

def previewer():
	from musecbox.sfz_previewer import SFZPreviewer
	global __SFZ_PREVIEWER
	if __SFZ_PREVIEWER is None:
		__SFZ_PREVIEWER = SFZPreviewer()
		__SFZ_PREVIEWER.add_to_carla()
	return __SFZ_PREVIEWER

def recent_plugins():
	global __RECENT_PLUGINS
	def sync(items):
		set_setting(KEY_RECENT_PLUGINS, items)
	if __RECENT_PLUGINS is None:
		__RECENT_PLUGINS = RecentItemsList(setting(KEY_RECENT_PLUGINS, list, []))
		__RECENT_PLUGINS.on_change(sync)
	return __RECENT_PLUGINS

def recent_files():
	global __RECENT_FILES
	def sync(items):
		set_setting(KEY_RECENT_FILES, items)
	if __RECENT_FILES is None:
		__RECENT_FILES = RecentItemsList(setting(KEY_RECENT_FILES, list, []))
		__RECENT_FILES.on_change(sync)
	return __RECENT_FILES

def __settings():
	global __SETTINGS
	if __SETTINGS is None:
		__SETTINGS = QSettings('ZenSoSo', 'musecbox')
	return __SETTINGS

def sync_settings():
	__settings().sync()

def setting(key, type_ = None, default = None):
	mw = main_window()
	value = mw.option(key) if mw else None
	if value is None:
		value = __settings().value(key, default)
	if value is None and not type_ is None:
		return type_()	# Defaults to "False" for bool, "0" for int, etc.
	return type_(value) if type_ else value

def set_setting(key, value):
	# TODO(?): Save per-project window geometry
	# MainWindow project_definition takes the setting if possible:
	mw = main_window()
	if mw and main_window().set_option(key, value):
		return
	__settings().setValue(key, value)

def styles():
	global __STYLES
	if __STYLES is None:
		__STYLES = {
			splitext(basename(path))[0] : path \
			for path in glob.glob(join(APP_PATH, 'styles', '*.css'))
		}
	return __STYLES

def set_application_style():
	style = setting(KEY_STYLE, str, DEFAULT_STYLE)
	with open(styles()[style], 'r', encoding = 'utf-8') as cssfile:
		QApplication.instance().setStyleSheet(cssfile.read())

def plugin_display_name(plugin_def):
	"""
	Returns a string consisting of the plugin name and type (LADSPA, VST, etc.)
	"""
	str_type = PLUGIN_TYPE_STRINGS[plugin_def["type"]] \
		if plugin_def["type"] in PLUGIN_TYPE_STRINGS \
		else 'None'
	return f'"{plugin_def["name"]}" ({str_type})'

# -------------------------------------------------------------------
# Cross-platform open any file / folder with system associated tool

def xdg_open(filename):
	if system() == "Windows":
		startfile(filename)
	elif system() == "Darwin":
		Popen(["open", filename])
	else:
		Popen(["xdg-open", filename])

# -------------------------------------------------------------------
# Add extra methods to the QWidget class:

def _restore_geometry(widget):
	"""
	Restores geometry from musecbox settings using automatically generated key.
	"""
	if not hasattr(widget, 'restoreGeometry'):
		return
	geometry = setting(_geometry_key(widget))
	if not geometry is None:
		widget.restoreGeometry(geometry)
	for splitter in widget.findChildren(QSplitter):
		geometry = setting(_splitter_geometry_key(widget, splitter))
		if not geometry is None:
			splitter.restoreState(geometry)

def _save_geometry(widget):
	"""
	Saves geometry to musecbox settings using automatically generated key.
	"""
	if not hasattr(widget, 'saveGeometry'):
		return
	set_setting(_geometry_key(widget), widget.saveGeometry())
	for splitter in widget.findChildren(QSplitter):
		set_setting(_splitter_geometry_key(widget, splitter), splitter.saveState())

def _geometry_key(widget):
	"""
	Automatic QSettings key generated from class name.
	"""
	return f'{type(widget).__name__}/geometry'

def _splitter_geometry_key(widget, splitter):
	"""
	Automatic QSettings key generated from class name.
	"""
	return f'{type(widget).__name__}/{splitter.objectName()}/geometry'

QWidget.restore_geometry = _restore_geometry
QWidget.save_geometry = _save_geometry

# -------------------------------------------------------------------
# Extra GUI funcs:

def bold(widget):
	"""
	Set the "bold" attribute of the widget font.
	"""
	font = widget.font()
	font.setWeight(QFont.Bold)
	widget.setFont(font)

def unbold(widget):
	"""
	Clear the "bold" attribute of the widget font.
	"""
	font = widget.font()
	font.setWeight(QFont.Normal)
	widget.setFont(font)

# -------------------------------------------------------------------
# Custom exceptions:

class EngineInitFailure(RuntimeError):
	"""
	Raised if carla fails to initialize.
	"""
	def __init__(self):
		audio_error = carla().get_last_error()
		if audio_error:
			super().__init__(f'Could not start carla; possible reasons:\n{audio_error}')
		else:
			super().__init__('Could not start carla')

# -------------------------------------------------------------------
# Exception hook

def exceptions_hook(exception_type, value, traceback):
	if not QApplication.instance() is None:
		msg = QErrorMessage.qtHandler()
		msg.setWindowModality(Qt.ApplicationModal)
		msg.showMessage(
			f'{exception_type.__name__}: "{value}"',
			exception_type.__name__)
	logging.error('Exception "%s": %s', exception_type.__name__, value)
	with StreamToLogger() as log:
		print_tb(traceback, file = log)

sys.excepthook = exceptions_hook

#  end musecbox/__init__.py
