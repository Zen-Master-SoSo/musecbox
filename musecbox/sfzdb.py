#  musecbox/sfzdb.py
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
Provides a database of sfz files with which instruments may be grouped and matched to.
"""
import logging, re
from os import mkdir, remove
from os.path import join, dirname, basename, splitext, isfile
from time import time
from functools import cached_property
from sqlite3 import connect
from appdirs import user_config_dir
from mscore import CHANNEL_NAMES, DEFAULT_VOICE, VoiceName
from mscore.fuzzy import FuzzyVoice, FuzzyVoiceCandidate

SPLIT_WORDS_REGEX		= '[^\w]'
ACCEPT_WORD_REGEX		= '[a-zA-Z][a-zA-Z]+'


def single_spaced(s):
	return re.sub('\s+', ' ', s).strip()


class SFZDatabase:

	instance = None		# Enforce singleton
	conn = None

	def __new__(cls):
		if cls.instance is None:
			cls.instance = super().__new__(cls)
		return cls.instance

	@classmethod
	def db_file(cls):
		"""
		Returns the (default) path to the sqlite3 database in the user's config dir.
		"""
		try:
			mkdir(join(user_config_dir(), 'ZenSoSo'))
		except FileExistsError:
			pass
		return join(user_config_dir(), 'ZenSoSo', 'musecbox-sfzs.db')

	def __init__(self):
		if self.conn is None:
			self.conn = connect(self.db_file())
			self.conn.execute('PRAGMA foreign_keys = ON')
			if len(self.conn.execute('SELECT name FROM sqlite_master WHERE type="table"').fetchall()) == 0:
				self._init_schema()
			else:
				self.clean()

	def _init_schema(self):
		logging.debug('Initializing schema')
		self.conn.execute("""
			CREATE TABLE sfzs(
				path TEXT,
				PRIMARY KEY(path)
			)""")
		self.conn.execute("""
			CREATE TABLE instrument_mappings(
				path TEXT,
				instrument_name TEXT,
				voice TEXT,
				date INTEGER,
				PRIMARY KEY(path, instrument_name, voice),
				FOREIGN KEY(path) REFERENCES sfzs(path) ON DELETE CASCADE
			)""")
		self.conn.execute("""
			CREATE INDEX map_date
			ON instrument_mappings (
				date
			)""")
		self.conn.execute("""
			CREATE TABLE group_members(
				path TEXT,
				group_name TEXT,
				PRIMARY KEY(path, group_name),
				FOREIGN KEY(path) REFERENCES sfzs(path) ON DELETE CASCADE
			)""")

	def dump(self):
		"""
		Dump the entire sql necessary to recreate.
		"""
		for line in self.conn.iterdump():
			print(line)

	def reset(self):
		"""
		Deletes and recreates the database.
		"""
		self.conn.close()
		remove(self.db_file())
		self.conn = connect(self.db_file())
		self._init_schema()

	def clean(self):
		"""
		Deletes all SFZs that do not exist on the file system
		"""
		cursor = self.conn.execute("""
			SELECT path
			FROM sfzs
		""")
		paths = [ tup[0] for tup in cursor.fetchall() if not isfile(tup[0]) ]
		self.remove_sfzs(paths)

	def insert_sfz(self, path):
		"""
		Inserts the given path.
		"""
		self.conn.execute('INSERT OR IGNORE INTO sfzs VALUES (?)', (path, ))
		self.conn.commit()

	def insert_sfzs(self, paths):
		"""
		Inserts multiple SFZs, ignoring if already in DB
		"""
		data = [ (path,) for path in paths ]
		self.conn.executemany('INSERT OR IGNORE INTO sfzs(path) VALUES(?)', data)
		self.conn.commit()

	def remove_sfz(self, path):
		"""
		Remove the given SFZ identified by "path".
		"""
		self.conn.execute("""
			DELETE FROM sfzs
			WHERE path = ?
		""", (path, ))
		self.conn.commit()

	def remove_sfzs(self, paths):
		"""
		Remove all the given SFZ identified by (list) "paths".
		"""
		self.conn.execute("""
			DROP TABLE IF EXISTS selections
		""")
		self.conn.execute("""
			CREATE TEMPORARY TABLE selections (
				path TEXT,
				PRIMARY KEY(path)
			)
		""")
		data = [ (path,) for path in paths]
		self.conn.executemany('INSERT INTO selections(path) VALUES(?)', data)
		self.conn.execute("""
			DELETE FROM sfzs
			WHERE ROWID IN (
				SELECT sfzs.ROWID FROM sfzs JOIN selections USING(path)
			)
		""")
		self.conn.commit()

	def paths(self, group_name):
		"""
		Returns list of paths
		If group_name is None, returns all
		"""
		if group_name is None:
			cursor = self.conn.execute("""
				SELECT path
				FROM sfzs
				ORDER BY path
			""")
		else:
			cursor = self.conn.execute("""
				SELECT path
				FROM sfzs
				JOIN group_members USING(path)
				WHERE group_name=?
				ORDER BY path
			""", (group_name, ))
		return [ result[0] for result in cursor.fetchall() ]

	def assign_group(self, group_name: str, paths: list):
		"""
		(Adds and) assigns "group_name" to every SFZ in (list) "paths"
		SFZs need not have been added to the database, as they will be added.
		"""
		self.insert_sfzs(paths)
		self.conn.executemany('INSERT OR IGNORE INTO group_members(group_name, path) VALUES(?,?)',
			[ (group_name, path) for path in paths ])
		self.conn.commit()

	def remove_group(self, group_name: str):
		"""
		Deletes the group identified by "group_name"; does NOT delete the SFZ reco
		"""
		self.conn.execute('DELETE FROM group_members WHERE group_name=?', (group_name,))
		self.conn.commit()

	def group_names(self):
		"""
		Returns list of (str) group_name
		"""
		cursor = self.conn.execute('SELECT DISTINCT(group_name) FROM group_members')
		return [ result[0] for result in cursor.fetchall() ]

	def map_instrument(self, voice_name: VoiceName, path: str):
		"""
		Associates the given "voice_name" to the SFZ found at "path".
		"""
		self.insert_sfz(path)
		self.conn.execute("""
			INSERT OR REPLACE INTO instrument_mappings
			VALUES (?, ?, ?, ?)
		""", (path, voice_name.instrument_name, voice_name.voice or DEFAULT_VOICE, time()))
		self.conn.commit()

	def mappings(self, voice_name: VoiceName, group_name: str = None):
		"""
		Returns list of (str) SFZ path associated with the given "voice_name".
		"""
		wheres = ['instrument_name = ?']
		parms = [voice_name.instrument_name]
		tables = ['instrument_mappings', 'sfzs USING(path)']
		if not voice_name.voice is None:
			wheres.append('voice = ?')
			parms.append(voice_name.voice)
		if not group_name is None:
			wheres.append('group_name = ?')
			parms.append(group_name)
			tables.append('group_members USING(path)')
		sql = 'SELECT path FROM ' + \
			' JOIN '.join(tables) + \
			' WHERE ' + ' AND '.join(wheres) + \
			' ORDER BY date DESC'
		return [ tup[0] for tup in self.conn.execute(sql, tuple(parms)).fetchall() ]

	def path_mappings(self, path):
		"""
		Returns list of VoiceName associated with the SFZ found at the given "path".
		"""
		sql = """
			SELECT instrument_name, voice
			FROM instrument_mappings
			WHERE path = ?
			ORDER BY date DESC
		"""
		return [ VoiceName(r[0], r[1]) \
			for r in self.conn.execute(sql, (path,)).fetchall() ]

	def mapped_instrument_names(self):
		"""
		Returns a list of (str) instruments which have been mapped to SFZs
		"""
		sql = """
			SELECT DISTINCT(instrument_name) AS name
			FROM instrument_mappings
			ORDER BY name
		"""
		return [ tup[0] for tup in self.conn.execute(sql).fetchall() ]

	def mapped_voices(self):
		"""
		Returns a list of ALL (str) voices which have been mapped to any SFZ.
		"""
		sql = """
			SELECT DISTINCT(voice) AS name
			FROM instrument_mappings
			ORDER BY name
		"""
		return [ tup[0] for tup in self.conn.execute(sql).fetchall() ]

	def all_voices(self):
		"""
		Returns a sorted list of all mscore channel names + all mapped voices
		"""
		voices = [DEFAULT_VOICE]
		voices.extend(sorted(list(
			(set(self.mapped_voices()) | set(CHANNEL_NAMES)) - set([DEFAULT_VOICE])
		)))
		return voices

	def forget_mapping(self, voice_name: VoiceName, path: str):
		"""
		Deletes the association between the given "voice_name" and the SFZ found at the
		given "path".
		"""
		if voice_name.voice is None:
			self.conn.execute("""
				DELETE FROM instrument_mappings
				WHERE instrument_name=? AND path=?
			""", (voice_name.instrument_name, path))
		else:
			self.conn.execute("""
				DELETE FROM instrument_mappings
				WHERE instrument_name=? AND voice=? AND path=?
			""", (voice_name.instrument_name, voice_name.voice, path))
		self.conn.commit()

	def sfzs(self, group_name: str = None) -> list:
		"""
		Returns list of SFZRecord.
		"""
		if group_name is None:
			cursor = self.conn.execute("""
				SELECT path
				FROM sfzs
				ORDER BY path
			""")
		else:
			cursor = self.conn.execute("""
				SELECT path
				FROM sfzs
				JOIN group_members USING(path)
				WHERE group_name=?
				ORDER BY path
			""", (group_name, ))
		return [ SFZRecord(r[0]) for r in cursor.fetchall() ]

	def sfzs_by_paths(self, paths):
		"""
		Returns list of SFZRecord objects.
		"""
		self.insert_sfzs(paths)
		return [ SFZRecord(path) for path in paths ]

	def best_match(self, ref: VoiceName, group_name: str = None):
		mapped, unmapped = self.ranked_sfzs(ref, self.sfzs(group_name), group_name)
		return mapped[0] if mapped else unmapped[0]

	def ranked_sfzs(self, ref, sfzs, group_name = None):
		"""
		Returns two lists of SFZRecord objects.
		The first list is of SFZs which have been mapped to the given VoiceName,
		the second list is scored and sorted by mscore.fuzzy
		"""
		assert isinstance(ref, VoiceName)
		assert isinstance(sfzs, list)
		if sfzs:
			assert isinstance(sfzs[0], SFZRecord)
		previously_mapped = self.mappings(ref, group_name)
		unmapped, mapped = [], []
		for sfz in sfzs:
			(unmapped, mapped)[sfz.path in previously_mapped].append(sfz)
		mapped.sort(key = lambda rec: previously_mapped.index(rec.path))
		candidates = [ FuzzyVoiceCandidate(sfz.voice_name, index) for index, sfz in enumerate(unmapped) ]
		results = FuzzyVoice(ref).score_candidates(candidates)
		return mapped, [ unmapped[result.candidate.index] for result in results ]


class SFZRecord:

	def __init__(self, path):
		self.path = path
		self.title = splitext(basename(self.path))[0]

	@cached_property
	def voice_name(self):
		"""
		Returns a VoiceName tuple interpreted from the file title
		"""
		instrument_name = re.sub('\W', ' ', self.title)
		for voice in SFZDatabase().all_voices():
			if re.search(voice, instrument_name, flags = re.I):
				instrument_name = re.sub(voice, '', instrument_name, flags = re.I)
				return VoiceName(single_spaced(instrument_name), voice)
		return VoiceName(single_spaced(instrument_name), None)

	def mappings(self):
		"""
		Returns a list VoiceName mapped to this SFZ
		"""
		return SFZDatabase().path_mappings(self.path)

	def __repr__(self):
		return f'"{self.title}"'

	@cached_property
	def dirname(self):
		return basename(dirname(self.path))

	def encode_saved_state(self):
		return self.path



#  end musecbox/sfzdb.py
