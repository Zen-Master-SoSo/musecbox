#  musecbox/score_fixer.py
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
Modifies the channel assignments in a MuseScore3 score to match a MusecBox project.
"""
import logging
from collections import namedtuple
from operator import attrgetter
from datetime import datetime
from shutil import copy2 as copy
from os.path import splitext
from mscore import Score, VoiceName
from mscore.fuzzy import FuzzyVoice, FuzzyVoiceCandidate

TrackTuple = namedtuple('TrackTuple', ['port', 'slot', 'channel', 'voice_name'])
VoicePairing = namedtuple('VoicePairing', ['track', 'channel'])


class ScoreFixer:

	def __init__(self, project_definition, mscore_filename):
		self.project_definition = project_definition
		self.score = Score(mscore_filename)

	def fix(self, *, ignore_extraneous = False, make_backup = False, fuzzy = False):
		pairs = self.pairs(fuzzy = fuzzy)
		extraneous = [ pair for pair in pairs if pair.track is None ]
		if not ignore_extraneous and extraneous:
			raise ExtraneousChannelsError(extraneous)
		if make_backup:
			copy(self.score.filename, self.backup_name())
		for pair in pairs:
			if not pair.track is None and not pair.channel is None:
				pair.channel.midi_port = pair.track.port
				pair.channel.midi_channel = pair.track.channel
		self.score.save()

	def backup_name(self):
		"""
		Returns path to backup file to create in the same directory as the
		mscore filename.
		"""
		path, ext = splitext(self.score.filename)
		date_str = datetime.now().strftime('%Y-%m-%d-%H-%M')
		return f'{path}-backup-{date_str}{ext}'

	def project_tracks(self):
		"""
		Returns a list of TrackTuple
		"""
		return sorted([
			TrackTuple(track['port'], track['slot'], track['channel'],
				VoiceName(track['instrument_name'], track['voice'])) \
			for port in self.project_definition['ports'] \
			for track in port['tracks'] ],
			key = attrgetter('port', 'channel'))

	def score_channels(self):
		"""
		Returns a list of Channel
		"""
		return sorted(self.score.channels(), key = attrgetter('midi_port', 'midi_channel'))

	def pairs(self, *, fuzzy = False):
		"""
		Returns list of VoicePairing tuples.

		When there is no channel matching a track, the "channel" property of the
		VoicePairing will be empty. These are missing channels.

		When there is no track matching a channel, the "track" property of the
		VoicePairing will be empty. These are extraneous channels and are more serious.
		"""
		tracks = self.project_tracks()
		channels = self.score_channels()
		if fuzzy:
			return self._pair_fuzzy(tracks, channels)
		return self._pair_exact(tracks, channels)

	def _pair_exact(self, tracks, channels):
		pairs = []
		for channel in channels:
			paired = False
			for track in tracks:
				if channel.voice_name == track.voice_name:
					pair = VoicePairing(track, channel)
					pairs.append(pair)
					paired = True
					break
			if not paired:
				pairs.append(VoicePairing(None, channel))
		assigned_tracks = [ pair.track for pair in pairs ]
		for track in tracks:
			if not track in assigned_tracks:
				pairs.append(VoicePairing(track, None))
		return pairs

	def _pair_fuzzy(self, tracks, channels):
		pairs = []
		candidate_tracks = [ FuzzyVoiceCandidate(track.voice_name, index) \
			for index, track in enumerate(tracks) ]
		for channel in channels:
			best = FuzzyVoice(channel.voice_name).best_match(candidate_tracks)
			if best.score >= 0.5:
				pairs.append(VoicePairing(tracks[best.candidate.index], channel))
			else:
				pairs.append(VoicePairing(None, channel))
		assigned_tracks = [ pair.track for pair in pairs ]
		for track in tracks:
			if not track in assigned_tracks:
				pairs.append(VoicePairing(track, None))
		return pairs


class ExtraneousChannelsError(Exception):

	def __init__(self, extraneous):
		self.message = 'the MuseScore score has extra channels'
		self.extraneous = extraneous


#  end musecbox/score_fixer.py
