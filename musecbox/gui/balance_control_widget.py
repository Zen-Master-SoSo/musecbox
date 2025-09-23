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
from math import floor
from functools import partial
from operator import attrgetter, itemgetter
from uuid import uuid4

# PyQt5 imports
from PyQt5.QtCore import	Qt, pyqtSlot, QObject, QRect, QEvent
from PyQt5.QtCore import	QPoint
from PyQt5.QtGui import		QPainter, QColor, QPen, QBrush, QPalette, QFontMetrics
from PyQt5.QtWidgets import	QWidget, QMenu, QAction

from musecbox import		setting, set_setting, main_window, \
							KEY_BCWIDGET_LINES, KEY_BCWIDGET_LABELS, KEY_BCWIDGET_TRACKING

GRAB_PANNING		= 0		# What the user is grabbing.
GRAB_LEFT_BALANCE	= 1		# If "can_pan", but not "can_balance",
GRAB_RIGHT_BALANCE	= 2		# will always be "GRAB_PANNING".
GRAB_CENTER			= 3

MARGIN				= 4		# Maximum pixels outside of pan_group indicators area

GRAB_RANGE			= 5		# Number of pixels left/right of the mouse considered "over" a feature

TRACK_WIDTH			= 20	# Fake "thickness" of a PanGroup
TRACK_HALF_WIDTH	= 10	# Number of pixels added to each side of PanGroup to give it thickness
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
LABEL_TRIM			= 10		# Number of pixels to "trim" from label text bounding rect left/right.


class BalanceControlWidget(QWidget):

	def __init__(self, parent):
		super().__init__(parent)
		self.usable_bounds_pen = QPen(Qt.DashLine)
		self.usable_bounds_pen.setWidth(1)
		self.balance_brush = QBrush(Qt.SolidPattern)
		self.balance_pen = QPen()
		self.balance_pen.setWidth(1)
		self.panning_pen = QPen()
		self.panning_pen.setWidth(TRACK_WIDTH)
		self.label_pen = QPen()
		self.label_pen.setWidth(1)
		self.zero_line_pen = QPen(Qt.DashLine)
		self.zero_line_pen.setWidth(1)
		self.setAutoFillBackground(True)
		self.setMinimumHeight(TRACK_HEIGHT * 3 + MARGIN * 2)
		self.visible_bounds_rect = None
		self.nearest_element = None
		self.grabbed_feature = None
		self.hovered_group = None
		self.show_labels = setting(KEY_BCWIDGET_LABELS, bool, True)
		self.hover_tracking = setting(KEY_BCWIDGET_TRACKING, bool, True)
		self.lines = setting(KEY_BCWIDGET_LINES, int, 2)
		self.last_line = self.lines - 1
		self.setFixedHeight(self.lines * TRACK_HEIGHT + MARGIN * 2)
		self.setMouseTracking(True)
		self.setContextMenuPolicy(Qt.DefaultContextMenu)
		self.set_styles()

	def clear(self):
		PanGroups.clear()
		self.conditional_update()

	@pyqtSlot()
	def changeEvent(self, event):
		if event.type() == QEvent.StyleChange:
			self.set_styles()
		super().changeEvent(event)

	def set_styles(self):
		self.metrics = QFontMetrics(self.font())
		self.label_pen.setColor(self.palette().color(QPalette.WindowText))
		self.label_bgcolor= self.palette().color(QPalette.Window)
		self.label_bgcolor.setAlpha(LABEL_ALPHA)
		line_color = QColor('black')
		self.usable_bounds_pen.setColor(line_color)
		self.zero_line_pen.setColor(line_color)

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

		action = QAction("Show labels", self)
		action.setCheckable(True)
		action.setChecked(self.show_labels)
		action.triggered.connect(self.slot_show_labels)
		menu.addAction(action)

		action = QAction("Follow tracks as they are hovered", self)
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

	def resizeEvent(self, event):
		# Returns a new rectangle with dx1, dy1, dx2 and dy2 added respectively to the
		# existing coordinates of this rectangle.
		self.visible_bounds_rect = QRect(QPoint(0, 0), event.size()).adjusted(
			MARGIN, MARGIN, -MARGIN, -MARGIN)
		usable_bounds_rect = self.visible_bounds_rect.adjusted(
			TRACK_HALF_WIDTH, 0, -TRACK_HALF_WIDTH, 0)
		self.center_x = usable_bounds_rect.center().x()
		# f_scale is what you divide event x by in order to get a value in a range
		# from -1.0 to 1.0 (proportion)
		f_usable_width = float(usable_bounds_rect.width())
		self.f_scale = f_usable_width / 2
		self.f_grab_range = GRAB_RANGE / self.f_scale
		self.f_track_half_width = TRACK_HALF_WIDTH / self.f_scale

	def screen_x_to_float(self, x):
		return max(-1.0, min(1.0, float(x - self.center_x) / self.f_scale))

	def float_to_screen_x(self, float_x):
		return round(float_x * self.f_scale + self.center_x)

	def screen_y_to_line(self, y):
		return floor((y - MARGIN) / TRACK_HEIGHT)

	def line_to_screen_y(self, line):
		return line * TRACK_HEIGHT + MARGIN

	def paintEvent(self, _):
		self.painter = QPainter(self)
		self.painter.setPen(self.usable_bounds_pen)
		self.painter.drawRect(self.visible_bounds_rect)
		self.painter.setPen(self.zero_line_pen)
		x = self.float_to_screen_x(0.0)
		self.painter.drawLine(x, self.visible_bounds_rect.top(), x, self.visible_bounds_rect.bottom())
		for pan_group in PanGroups():
			hue = pan_group.color().hsvHue()
			if self.hover_tracking and self.hovered_group is pan_group:
				fill_color = QColor.fromHsv(hue, FILL_SATURATION_HL, FILL_LUMINANCE_HL, FILL_ALPHA_HL)
				line_color = QColor.fromHsv(hue, LINE_SATURATION_HL, LINE_LUMINANCE_HL)
			else:
				fill_color = QColor.fromHsv(hue, FILL_SATURATION, FILL_LUMINANCE, FILL_ALPHA)
				line_color = QColor.fromHsv(hue, LINE_SATURATION, LINE_LUMINANCE)
			self.panning_pen.setColor(line_color)
			if pan_group.can_balance:
				self.draw_balance(pan_group, fill_color, line_color)
			elif pan_group.can_pan:
				self.draw_pan(pan_group, line_color)
		if self.show_labels:
			self.painter.setPen(self.label_pen)
			for pan_group in PanGroups():
				if pan_group.can_balance:
					self.draw_label(pan_group, pan_group.balance_center)
				elif pan_group.can_pan:
					self.draw_label(pan_group, pan_group.panning)
		self.painter.end()

	def draw_balance(self, pan_group, fill_color, line_color):
		left_x = self.float_to_screen_x(pan_group.balance_left) - TRACK_HALF_WIDTH
		right_x = self.float_to_screen_x(pan_group.balance_right) + TRACK_HALF_WIDTH
		top_y = self.line_to_screen_y(pan_group.bcwidget_line)
		rect = QRect(left_x, top_y, right_x - left_x, TRACK_HEIGHT)
		self.balance_brush.setColor(fill_color)
		self.painter.fillRect(rect, self.balance_brush)
		self.balance_pen.setColor(line_color)
		self.painter.setPen(self.balance_pen)
		self.painter.drawRect(rect)

	def draw_pan(self, pan_group, line_color):
		self.panning_pen.setColor(line_color)
		self.painter.setPen(self.panning_pen)
		x = self.float_to_screen_x(pan_group.panning)
		y = self.line_to_screen_y(pan_group.bcwidget_line)
		self.painter.drawLine(x, y, x, y + TRACK_HEIGHT)

	def draw_label(self, pan_group, float_x):
		text = pan_group.brief_label()
		rect = self.metrics.boundingRect(text)
		rect.setWidth = self.metrics.horizontalAdvance(text)
		rect.moveCenter(QPoint(
			self.float_to_screen_x(float_x),
			self.line_to_screen_y(pan_group.bcwidget_line) + TRACK_HALF_HEIGHT
		))
		self.painter.fillRect(rect.adjusted(LABEL_TRIM, 0, -LABEL_TRIM, 0), self.label_bgcolor)
		self.painter.drawText(rect, Qt.AlignHCenter | Qt.AlignBottom, text)

	def mouseMoveEvent(self, event):
		x = event.x()
		float_x = self.screen_x_to_float(x)
		line = min(self.last_line, max(0, self.screen_y_to_line(event.y())))

		if self.grabbed_feature:
			self.grabbed_feature.drag(float_x, line, event.modifiers() & Qt.ControlModifier)

		else:
			# can_balance tracks may have a feature under the mouse if the
			# mouse x (float) is between max_balance_left and min_balance_right:
			max_balance_left = float_x + self.f_grab_range + self.f_track_half_width
			min_balance_right = float_x - self.f_grab_range - self.f_track_half_width

			# can_balance tracks have the left balance under the mouse if the
			# mouse x (float) is between max_balance_left and min_balance_left:
			min_balance_left = float_x - self.f_grab_range + self.f_track_half_width
			# can_balance tracks have the right balance under the mouse if the
			# mouse x (float) is between max_balance_right and min_balance_right:
			max_balance_right = float_x + self.f_grab_range - self.f_track_half_width

			min_pan = float_x - self.f_track_half_width
			max_pan = float_x + self.f_track_half_width

			near = []
			for pan_group in PanGroups():
				if line == pan_group.bcwidget_line:
					# Inside vertical limits
					if pan_group.can_balance:
						if pan_group.balance_left <= max_balance_left and \
							pan_group.balance_right >= min_balance_right:

							# Inside most outer limits; check if inside left grab handle:
							if pan_group.balance_left >= min_balance_left:
								near.append(GrabEvent(
									pan_group, GRAB_LEFT_BALANCE,						# group, feature
									pan_group.balance_left + self.f_track_half_width,	# offset_value
									float_x												# event_x
								))

							# Inside most outer limits; check if inside right grab handle:
							elif pan_group.balance_right <= max_balance_left:
								near.append(GrabEvent(
									pan_group, GRAB_RIGHT_BALANCE,						# group, feature
									pan_group.balance_right - self.f_track_half_width,	# offset_value
									float_x												# event_x
								))

							# Inside most outer limits:
							else:
								near.append(GrabEvent(
									pan_group, GRAB_CENTER,								# group, feature
									pan_group.balance_center,							# offset_value
									float_x												# event_x
								))

					elif min_pan <= pan_group.panning <= max_pan:
						near.append(GrabEvent(
							pan_group, GRAB_PANNING,							# group, feature
							pan_group.panning,									# offset_value
							float_x												# event_x
						))
			if len(near):
				near.sort(key=attrgetter('distance_x'))
				self.nearest_element = near[0]
				# Change hover_track
				if self.hover_tracking:
					if self.hovered_group is not None and not self.nearest_element.pan_group is self.hovered_group:
						self.hovered_group.set_selected(False)
					self.hovered_group = self.nearest_element.pan_group
					self.hovered_group.set_selected(True)
				# Set cursor
				if	self.nearest_element.feature in (GRAB_LEFT_BALANCE, GRAB_RIGHT_BALANCE):
					self.setCursor(Qt.SplitHCursor)
				elif self.nearest_element.feature == GRAB_PANNING:
					self.setCursor(Qt.PointingHandCursor)
				else:
					self.setCursor(Qt.OpenHandCursor)

			else:
				self.nearest_element = None
				if self.hovered_group is not None:
					self.hovered_group.set_selected(False)
				self.hovered_group = None
				self.unsetCursor()

		self.conditional_update()

	def mousePressEvent(self, event):
		if self.nearest_element is not None:
			self.grabbed_feature = self.nearest_element
			self.grabbed_feature.grabbed(self.screen_x_to_float(event.x()))
			if self.grabbed_feature.feature == GRAB_CENTER:
				self.setCursor(Qt.ClosedHandCursor)

	def mouseReleaseEvent(self, _):
		if self.grabbed_feature is not None and self.grabbed_feature.feature == GRAB_CENTER:
			self.setCursor(Qt.OpenHandCursor)
		self.grabbed_feature = None

	def leaveEvent(self, _):
		self.grabbed_feature = None
		if self.hovered_group is not None:
			self.hovered_group.set_selected(False)
			self.hovered_group = None
		self.conditional_update()

	@pyqtSlot()
	def slot_spread(self):
		"""
		Triggered by context menu.
		Spreads all channels' balance or panning across the left / right axis.
		"""
		groups_count = len(PanGroups())
		if groups_count < 2:
			return
		allotment = 2.0 / groups_count
		half_allotment = allotment / 2.0
		line = 0
		float_val = -1.0
		for pan_group in PanGroups():
			if pan_group.can_balance:
				pan_group.balance_left = float_val
				pan_group.balance_right = float_val + allotment
			elif pan_group.can_pan:
				pan_group.panning = float_val + half_allotment
			pan_group.bcwidget_line = line
			float_val += allotment
			line += 1
			if line == self.lines:
				line = 0
		self.update()

	@pyqtSlot(bool)
	def slot_show_labels(self, state):
		if state != self.show_labels:
			self.show_labels = state
			set_setting(KEY_BCWIDGET_LABELS, state)
			self.conditional_update()

	@pyqtSlot(int)
	def slot_set_lines(self, lines):
		self.lines = lines
		self.last_line = self.lines - 1
		for pan_group in PanGroups():
			pan_group.bcwidget_line = min(pan_group.bcwidget_line, self.last_line)
		set_setting(KEY_BCWIDGET_LINES, self.lines)
		self.setFixedHeight(self.lines * TRACK_HEIGHT + MARGIN * 2)

	@pyqtSlot(bool)
	def slot_hover_tracking(self, state):
		self.hover_tracking = state
		set_setting(KEY_BCWIDGET_TRACKING, state)

	@pyqtSlot(QObject)
	def slot_track_hover_in(self, track_widget):
		"""
		Triggered from TrackWidget when mouse hovers over it
		"""
		if self.hover_tracking:
			self.hovered_group = PanGroups.group(track_widget.pan_group_key)
			self.conditional_update()

	@pyqtSlot()
	def slot_track_hover_out(self):
		"""
		Triggered from TrackWidget when mouse leaves.
		"""
		self.hovered_group = None

	def conditional_update(self):
		if self.isVisible() and not main_window().project_loading:
			self.update()

# -----------------------------------------------------------------
# Support classes

class GrabEvent:
	"""
	Used to sort / determine the nearest feature to the mouse pointer, and when
	grabbed, keep pan_group of mouse movement and apply the changes to the appropriate
	target.
	"""

	def __init__ (self, pan_group, feature, offset_value, float_x):
		self.pan_group = pan_group
		self.feature = feature
		self.distance_x = abs(float_x - offset_value)

	def grabbed(self, float_x):
		# Remember initial values on mouse down:
		self.initial_x = float_x
		self.initial_balance_left = self.pan_group.balance_left
		self.initial_balance_right = self.pan_group.balance_right

	def drag(self, float_x, line, ctrl_button):
		shift_x = float_x - self.initial_x
		if self.feature == GRAB_CENTER:
			self.pan_group.balance_left = min(1.0, max(-1.0, self.initial_balance_left + shift_x))
			self.pan_group.balance_right = min(1.0, max(-1.0, self.initial_balance_right + shift_x))
		else:
			if self.feature == GRAB_LEFT_BALANCE:
				self.pan_group.balance_left = min(float_x, self.pan_group.balance_right)
			elif self.feature == GRAB_RIGHT_BALANCE:
				self.pan_group.balance_right = max(float_x, self.pan_group.balance_left)
			elif self.feature == GRAB_PANNING:
				self.pan_group.panning = float_x
		if not ctrl_button and self.feature in (GRAB_CENTER, GRAB_PANNING):
			self.pan_group.bcwidget_line = line


# -----------------------------------------------------------------
# Classes for locking balance/pan values for groups of tracks.

class PanGroups:

	_groups		= {}	# PanGroup.key : PanGroup

	@classmethod
	def __iter__(cls):
		yield from cls._groups.values()

	@classmethod
	def __len__(cls):
		return len(cls._groups)

	@classmethod
	def group(cls, key):
		return cls._groups[key] if key in cls._groups else None

	@classmethod
	def make_new_group(cls, track):
		key = str(uuid4())
		cls._groups[key] = PanGroup(key, track)

	@classmethod
	def join_group(cls, key, track):
		cls.orphan(track)
		if key in cls._groups:
			cls._groups[key].add_track(track)
		else:
			cls._groups[key] = PanGroup(key, track)

	@classmethod
	def orphan(cls, track):
		key = track.pan_group_key
		if key in cls._groups:
			cls._groups[key].remove_track(track)
			if len(cls._groups[key]) == 0:
				del cls._groups[key]

	@classmethod
	def candidate_groups(cls, track):
		"""
		Returns a list of PanGroups, sorted by how many tracks in each have an
		instrument name matching the given track's instrument name.
		"""
		groups = [ (group.match_track(track), group) \
			for key, group in cls._groups.items() \
			if key != track.pan_group_key ]
		groups.sort(key = itemgetter(0), reverse = True)
		return [ group[1] for group in groups ]	# Strip out the scores, return only PanGroups

	@classmethod
	def clear(cls):
		cls._groups = {}


class PanGroup:

	def __init__(self, key, track):
		self.key = key
		self._tracks = [track]
		self.can_balance = track.synth.can_balance
		self.can_pan = track.synth.can_pan
		track.pan_group_key = key

	def add_track(self, track):
		if track in self._tracks:
			raise RuntimeError("Plugin already in PanGroup")
		if self.can_balance != track.synth.can_balance or self.can_pan != track.synth.can_pan:
			raise RuntimeError("Track capabilities mismatch pan group")
		if self.can_pan:
			track.synth.panning = self._tracks[0].synth.panning
		if self.can_balance:
			track.synth.balance_left = self._tracks[0].synth.balance_left
			track.synth.balance_right = self._tracks[0].synth.balance_right
		track.bcwidget_line = self._tracks[0].bcwidget_line
		self._tracks.append(track)
		track.pan_group_key = self.key

	def remove_track(self, track):
		"""
		Removes a single track from a group.
		"""
		if track in self._tracks:
			track.pan_group_key = None
			del self._tracks[ self._tracks.index(track) ]

	def __len__(self):
		return len(self._tracks)

	def label(self):
		"""
		Descriptive label shows all group members
		"""
		if len(self._tracks) == 1:
			return str(self._tracks[0].voice_name)
		return ', '.join('{} ({})'.format(instrument_name,
			', '.join(
				track.voice_name.voice for track in self._tracks \
				if track.voice_name.instrument_name == instrument_name
			)) for instrument_name in set(
				track.voice_name.instrument_name for track in self._tracks
			))

	def brief_label(self):
		if len(self._tracks) == 1:
			return str(self._tracks[0].voice_name)
		return ', '.join('{} ({})'.format(instrument_name, len(
			[ track for track in self._tracks \
			if track.voice_name.instrument_name == instrument_name ]
		)) for instrument_name in set(
				track.voice_name.instrument_name for track in self._tracks
		))

	def match_track(self, track):
		"""
		Returns a score based on how well this group matches the given track.
		"""
		return len([ t for t in self._tracks
			if track.voice_name.instrument_name == t.voice_name.instrument_name ]) \
			/ len(self._tracks)

	def color(self):
		return self._tracks[0].color()

	def set_selected(self, state):
		for track in self._tracks:
			track.set_selected(state)

	@property
	def balance_left(self):
		return self._tracks[0].synth.balance_left

	@balance_left.setter
	def balance_left(self, value):
		for track in self._tracks:
			track.synth.balance_left = value
		main_window().set_dirty()

	@property
	def balance_right(self):
		return self._tracks[0].synth.balance_right

	@balance_right.setter
	def balance_right(self, value):
		for track in self._tracks:
			track.synth.balance_right = value
		main_window().set_dirty()

	@property
	def balance_center(self):
		return self._tracks[0].synth.balance_center

	@balance_center.setter
	def balance_center(self, value):
		for track in self._tracks:
			track.synth.balance_center = value

	@property
	def panning(self):
		return self._tracks[0].synth.panning

	@panning.setter
	def panning(self, value):
		for track in self._tracks:
			track.synth.panning = value
		main_window().set_dirty()

	@property
	def bcwidget_line(self):
		return self._tracks[0].bcwidget_line

	@bcwidget_line.setter
	def bcwidget_line(self, value):
		for track in self._tracks:
			track.bcwidget_line = value



#  end musecbox/gui/balance_control_widget.py
