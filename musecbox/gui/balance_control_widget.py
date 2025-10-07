#  musecbox/gui/balance_control_widget.py
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
Provides an integrated balanced control widget, which you can use to
graphically locate instruments in the stereo space.
"""
import logging, time
from math import floor
from functools import partial
from operator import attrgetter, itemgetter
from uuid import uuid4
from qt_extras.autofit import autofit

# PyQt5 imports
from PyQt5.QtCore import	Qt, pyqtSlot, QObject, QRect, QEvent
from PyQt5.QtCore import	QPoint
from PyQt5.QtGui import		QPainter, QColor, QPen, QBrush, QPalette, QFontMetrics
from PyQt5.QtWidgets import	QWidget, QLabel, QMenu, QAction, QSizePolicy

from musecbox import		setting, set_setting, main_window, \
							KEY_BCWIDGET_LINES, KEY_BCWIDGET_TRACKING

GRAB_PANNING		= 0		# What the user is grabbing.
GRAB_LEFT_BALANCE	= 1		# If "can_pan", but not "can_balance",
GRAB_RIGHT_BALANCE	= 2		# will always be "GRAB_PANNING".
GRAB_CENTER			= 3

GRAB_RANGE			= 5		# Number of pixels left/right of the mouse considered "over" a feature

TRACK_WIDTH			= 20	# Fake "thickness" of a BCGroup
TRACK_HALF_WIDTH	= 10	# Number of pixels added to each side of BCGroup to give it thickness
TRACK_HEIGHT		= 18
TRACK_HALF_HEIGHT	= 9

FILL_SATURATION		= 180	# Saturation, luminance, alpha of pan group fill.
FILL_LUMINANCE		= 180
FILL_ALPHA			= 80

FILL_SATURATION_HL	= 200	# Saturation, luminance, alpha when highlighted (hovered over)
FILL_LUMINANCE_HL	= 200
FILL_ALPHA_HL		= 180

LINE_SATURATION		= 200
LINE_LUMINANCE		= 80
LINE_SATURATION_HL	= 240
LINE_LUMINANCE_HL	= 120

LABEL_ALPHA			= 90
LABEL_PADDING		= 4		# Number of pixels to add to label text bounding rect left/right.


class BalanceControlWidget(QWidget):

	def __init__(self, parent):
		super().__init__(parent)
		self._groups = {}
		self.lines_pen = QPen(Qt.DashLine)
		self.lines_pen.setWidth(1)
		self.setAttribute(Qt.WA_StyledBackground, True)
		self.setAutoFillBackground(True)
		self.bounds_rect = None
		self.nearest_feature = None
		self.grabbed_feature = None
		self.focused_group = None
		self.hover_tracking = setting(KEY_BCWIDGET_TRACKING, bool, True)
		self.lines = setting(KEY_BCWIDGET_LINES, int, 2)
		self.last_line = self.lines - 1
		self.setFixedHeight(self.lines * TRACK_HEIGHT)
		self.setMouseTracking(True)
		self.setContextMenuPolicy(Qt.DefaultContextMenu)
		self.set_styles()

	# -----------------------------------------------------------------
	# Styles

	@pyqtSlot()
	def changeEvent(self, event):
		if event.type() == QEvent.StyleChange:
			self.set_styles()
		super().changeEvent(event)

	def set_styles(self):
		self.metrics = QFontMetrics(self.font())
		self.lines_pen.setColor(self.palette().color(QPalette.WindowText))

	def contextMenuEvent(self, event):
		menu = QMenu()
		menu.addAction(main_window().action_show_balance)
		menu.addSeparator()	# ---------------------

		resize_menu = menu.addMenu('Set height ...')
		for lines in range(1, 7):
			action = QAction(f'{lines} lines', self)
			action.setCheckable(True)
			action.setChecked(self.lines == lines)
			action.triggered.connect(partial(self.slot_set_lines, lines))
			resize_menu.addAction(action)

		action = QAction("Highlight tracks as they are hovered", self)
		action.setCheckable(True)
		action.setChecked(self.hover_tracking)
		action.triggered.connect(self.slot_hover_tracking)
		menu.addAction(action)
		menu.addSeparator()	# ---------------------

		action = QAction("Spread out evenly", self)
		action.triggered.connect(self.slot_spread)
		action.setEnabled(bool(main_window().track_widget_count()))
		menu.addAction(action)

		menu.exec(event.globalPos())

	# -----------------------------------------------------------------
	# Screen / internal plugin value conversions

	def resizeEvent(self, event):
		self.bounds_rect = QRect(QPoint(0, 0), event.size()).adjusted(
			TRACK_HALF_WIDTH + 1, 1, -TRACK_HALF_WIDTH - 1, -1)
		self.center_x = self.bounds_rect.center().x()
		self.f_scale = float(self.bounds_rect.width() / 2)
		for group in self._groups.values():
			group.reposition()
		self.update()

	def screen_x_to_float(self, x):
		return max(-1.0, min(1.0, float(x - self.center_x) / self.f_scale))

	def float_to_screen_x(self, float_x):
		return round(float_x * self.f_scale + self.center_x)

	# -----------------------------------------------------------------
	# Events

	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setPen(self.lines_pen)
		x = self.float_to_screen_x(0.0)
		painter.drawLine(x, self.bounds_rect.top(), x, self.bounds_rect.bottom())
		painter.end()
		super().paintEvent(event)

	def mouseMoveEvent(self, event):
		x = event.x()
		float_x = self.screen_x_to_float(x)
		line = min(self.last_line, max(0, floor(event.y() / TRACK_HEIGHT)))

		if self.grabbed_feature:
			self.grabbed_feature.drag(float_x, line, event.modifiers() & Qt.ControlModifier)

		else:
										# Over a can_balance group if:
			max_left = x + GRAB_RANGE	# left <= max_left     and
			min_right = x - GRAB_RANGE	# right >= min_right

			min_left = x - GRAB_RANGE
			max_right = x + GRAB_RANGE

			near = []
			for group in self._groups.values():

				if line != group.bcwidget_line or group.left > max_left or group.right < min_right:
					continue

				if group.can_balance:

					# Inside most outer limits; check if inside left grab handle:
					if group.left >= min_left:
						near.append(GrabEvent(
							group, GRAB_LEFT_BALANCE,		# group, feature
							abs(group.left - x),			# distance
							float_x, line					# initial float_x, line
						))

					# Inside most outer limits; check if inside right grab handle:
					elif group.right <= max_left:
						near.append(GrabEvent(
							group, GRAB_RIGHT_BALANCE,		# group, feature
							abs(group.right - x),			# distance
							float_x, line					# initial float_x, line
						))

					# Inside most outer limits:
					else:
						near.append(GrabEvent(
							group, GRAB_CENTER,				# group, feature
							abs(group.center - x),			# distance
							float_x, line					# initial float_x, line
						))

				elif group.can_pan:
					near.append(GrabEvent(
						group, GRAB_PANNING,				# group, feature
						abs(group.center - x),				# distance
						float_x, line						# initial float_x, line
					))

			if near:
				near.sort(key = attrgetter('distance'))
				self.nearest_feature = near[0]
				hover_group = self.nearest_feature.group
				if self.nearest_feature.feature == GRAB_CENTER:
					self.setCursor(Qt.OpenHandCursor)
				elif self.nearest_feature.feature == GRAB_PANNING:
					self.setCursor(Qt.PointingHandCursor)
				else:
					self.setCursor(Qt.SplitHCursor)
			else:
				self.nearest_feature = None
				hover_group = None
				self.unsetCursor()

			self.change_focused_group(hover_group, self.hover_tracking)

		#self.update()

	def mousePressEvent(self, event):
		if self.nearest_feature is not None:
			self.grabbed_feature = self.nearest_feature
			self.grabbed_feature.grabbed()
			if self.grabbed_feature.feature == GRAB_CENTER:
				self.setCursor(Qt.ClosedHandCursor)

	def mouseReleaseEvent(self, _):
		if self.grabbed_feature is not None and self.grabbed_feature.feature == GRAB_CENTER:
			self.setCursor(Qt.OpenHandCursor)
		self.grabbed_feature = None

	def leaveEvent(self, _):
		self.grabbed_feature = None
		self.change_focused_group(None, self.hover_tracking)
		#self.update()

	# -----------------------------------------------------------------
	# Action slots

	@pyqtSlot()
	def slot_spread(self):
		"""
		Triggered by context menu.
		Spreads all channels' balance or panning across the left / right axis.
		"""
		groups_count = len(self._groups)
		if groups_count < 2:
			return
		allotment = 2.0 / groups_count
		half_allotment = allotment / 2.0
		line = 0
		float_val = -1.0
		for group in self._groups.values():
			if group.can_balance:
				group.balance_left = float_val
				group.balance_right = float_val + allotment
			elif group.can_pan:
				group.panning = float_val + half_allotment
			group.bcwidget_line = line
			group.reposition()
			float_val = min(1.0, float_val + allotment)
			line += 1
			if line == self.lines:
				line = 0
		self.update()

	@pyqtSlot(int)
	def slot_set_lines(self, lines):
		self.lines = lines
		self.last_line = self.lines - 1
		for group in self._groups.values():
			group.bcwidget_line = min(group.bcwidget_line, self.last_line)
		set_setting(KEY_BCWIDGET_LINES, self.lines)
		self.setFixedHeight(self.lines * TRACK_HEIGHT)

	@pyqtSlot(bool)
	def slot_hover_tracking(self, state):
		self.hover_tracking = state
		set_setting(KEY_BCWIDGET_TRACKING, state)
		if not state:
			for group in self._groups.values():
				group.set_bcwidget_focus(False, True)


	def hover_in(self, pan_group_key):
		"""
		Called from TrackWidget when mouse hovers over it
		"""
		if pan_group_key in self._groups:
			self.change_focused_group(self._groups[pan_group_key], False)

	def hover_out(self):
		"""
		Called from TrackWidget when mouse leaves.
		"""
		self.change_focused_group(None, False)

	def change_focused_group(self, group, hover_tracking):
		if not group is self.focused_group:
			if self.focused_group:
				self.focused_group.set_bcwidget_focus(False, hover_tracking)
			self.focused_group = group
			if self.focused_group:
				self.focused_group.set_bcwidget_focus(True, hover_tracking)

	def update(self):
		if self.isVisible() and not main_window().project_loading:
			super().update()

	# -----------------------------------------------------------------
	# BCGroup management

	def group(self, key):
		return self._groups[key] if key in self._groups else None

	def make_new_group(self, track):
		self._create_group(str(uuid4()), track)

	def join_group(self, key, track):
		self.orphan(track)
		if key in self._groups:
			self._groups[key].add_track(track)
		else:
			self._create_group(key, track)

	def _create_group(self, key, track):
		self._groups[key] = BCGroup(self, key, track)
		if self.isVisible():
			self._groups[key].reposition()
		self._groups[key].show()

	def orphan(self, track):
		key = track.pan_group_key
		if key in self._groups:
			self._groups[key].remove_track(track)
			if len(self._groups[key]) == 0:
				self._groups[key].deleteLater()
				del self._groups[key]

	def candidate_groups(self, track):
		"""
		Used by TrackWidget when locking an instrument to a different group.
		Returns a list of BCGroup, sorted by how many tracks in each have an
		matching instrument name.
		"""
		groups = [ (group.match_track(track), group) \
			for key, group in self._groups.items() \
			if key != track.pan_group_key ]
		groups.sort(key = itemgetter(0), reverse = True)
		return [ group[1] for group in groups ]	# Strip out the scores, return only BCGroup

	def clear(self):
		self._groups = {}
		self.update()

	# -----------------------------------------------------------------
	# Encode state for restoring from saved project

	def encode_saved_state(self):
		return { group.key:group.bcwidget_line for group in self._groups.values() }

	def project_load_complete(self):
		self.slot_set_lines(setting(KEY_BCWIDGET_LINES, int, 3))
		self.update()


class GrabEvent:
	"""
	Used to sort / determine the nearest feature to the mouse pointer, and when
	grabbed, remember the grabbed group and apply the changes to it.
	"""

	def __init__ (self, group, feature, distance, float_x, line):
		self.group = group
		self.feature = feature
		self.distance = distance
		self.initial_x = float_x
		self.initial_line = line

	def grabbed(self):
		self.initial_balance_left = self.group.balance_left
		self.initial_balance_right = self.group.balance_right
		self.initial_panning = self.group.panning

	def drag(self, float_x, line, ctrl_button):
		shift_x = float_x - self.initial_x
		if ctrl_button and self.initial_line != line:
			self.group.balance_left = self.initial_balance_left
			self.group.balance_right = self.initial_balance_right
			self.group.panning = self.initial_panning
		else:
			if self.feature == GRAB_CENTER:
				self.group.balance_left = min(1.0, max(-1.0,
					self.initial_balance_left + shift_x))
				self.group.balance_right = min(1.0, max(-1.0,
					self.initial_balance_right + shift_x))
			elif self.feature == GRAB_LEFT_BALANCE:
				self.group.balance_left = max(-1.0, min(
					self.initial_balance_left + shift_x, self.group.balance_right))
			elif self.feature == GRAB_RIGHT_BALANCE:
				self.group.balance_right = min(1.0, max(
					self.initial_balance_right + shift_x, self.group.balance_left))
			elif self.feature == GRAB_PANNING:
				self.group.panning = min(1.0, max(-1.0,
					self.initial_panning + shift_x))
		self.group.bcwidget_line = line
		self.group.reposition()


class BCGroup(QLabel):

	def __init__(self, parent, key, track):
		super().__init__(parent)
		self.setMouseTracking(True)
		autofit(self)
		self.setEnabled(False)
		self.key = key
		self.tracks = [track]
		self.port = track.port
		track.pan_group_key = key
		self.setObjectName(f'bcwidget_port_{self.port}')
		self.can_balance = track.synth.can_balance
		self.can_pan = track.synth.can_pan
		pdef = main_window().project_definition
		self.bcwidget_line = 0 if pdef is None \
			or 'bcwidget' not in pdef \
			or key not in pdef['bcwidget'] \
			else pdef['bcwidget'][key]
		self.left = None
		self.right = None
		self.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
		self.setText(self.brief_text())
		self.resize(TRACK_WIDTH, TRACK_HEIGHT)		# Will be changed for can_balance groups

	def add_track(self, track):
		if track in self.tracks:
			raise RuntimeError("Plugin already in BCGroup")
		if self.can_balance != track.synth.can_balance or self.can_pan != track.synth.can_pan:
			raise RuntimeError("Track capabilities mismatch pan group")
		if self.can_pan:
			track.synth.panning = self.tracks[0].synth.panning
		if self.can_balance:
			track.synth.balance_left = self.tracks[0].synth.balance_left
			track.synth.balance_right = self.tracks[0].synth.balance_right
		self.tracks.append(track)
		track.pan_group_key = self.key
		self.setText(self.brief_text())

	def remove_track(self, track):
		"""
		Removes a single track from a group.
		"""
		if track in self.tracks:
			track.pan_group_key = None
			del self.tracks[ self.tracks.index(track) ]
		self.setText(self.brief_text())

	def reposition(self):
		bcwidget = main_window().balance_control_widget
		top = self.bcwidget_line * TRACK_HEIGHT
		if self.can_balance:
			self.left = bcwidget.float_to_screen_x(self.balance_left) - TRACK_HALF_WIDTH
			self.right = bcwidget.float_to_screen_x(self.balance_right) + TRACK_HALF_WIDTH
			width = self.right - self.left
			self.resize(width, TRACK_HEIGHT)
		elif self.can_pan:
			self.left = bcwidget.float_to_screen_x(self.panning) - TRACK_HALF_WIDTH
			self.right = self.left + TRACK_WIDTH
		self.center = self.left + width // 2
		self.move(self.left, top)

	def __len__(self):
		return len(self.tracks)

	def long_text(self):
		"""
		Descriptive text enumerating all track's voice names.
		"""
		if len(self.tracks) == 1:
			return str(self.tracks[0].voice_name)
		return ', '.join('{} ({})'.format(instrument_name,
			', '.join(
				track.voice_name.voice for track in self.tracks \
				if track.voice_name.instrument_name == instrument_name
			)) for instrument_name in set(
				track.voice_name.instrument_name for track in self.tracks
			))

	def brief_text(self):
		"""
		Short text showing only instrument names / count
		"""
		if len(self.tracks) == 1:
			return str(self.tracks[0].voice_name)
		return ', '.join('{} ({})'.format(instrument_name, len(
			[ track for track in self.tracks \
			if track.voice_name.instrument_name == instrument_name ]
		)) for instrument_name in set(
				track.voice_name.instrument_name for track in self.tracks
		))

	def match_track(self, track):
		"""
		Returns a score based on how well this group matches the given track.
		"""
		return len([ t for t in self.tracks
			if track.voice_name.instrument_name == t.voice_name.instrument_name ]) \
			/ len(self.tracks)

	def set_bcwidget_focus(self, state, highlight_tracks):
		self.setEnabled(state)
		if highlight_tracks:
			for track in self.tracks:
				track.set_bcwidget_focus(state)

	@property
	def balance_left(self):
		return self.tracks[0].synth.balance_left

	@balance_left.setter
	def balance_left(self, value):
		for track in self.tracks:
			track.synth.balance_left = value
		main_window().set_dirty()

	@property
	def balance_right(self):
		return self.tracks[0].synth.balance_right

	@balance_right.setter
	def balance_right(self, value):
		for track in self.tracks:
			track.synth.balance_right = value
		main_window().set_dirty()

	@property
	def balance_center(self):
		return self.tracks[0].synth.balance_center

	@balance_center.setter
	def balance_center(self, value):
		for track in self.tracks:
			track.synth.balance_center = value

	@property
	def panning(self):
		return self.tracks[0].synth.panning

	@panning.setter
	def panning(self, value):
		for track in self.tracks:
			track.synth.panning = value
		main_window().set_dirty()


#  end musecbox/gui/balance_control_widget.py
