#  musecbox/scripts/mb_apply.py
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
Applies the port/channel assignments in a MusecBox project to a MuseScore3 score.
"""
import logging, argparse, sys, json
from musecbox import LOG_FORMAT
from musecbox.score_fixer import ScoreFixer


def main():
	p = argparse.ArgumentParser()
	p.add_argument('Project', type=str, nargs=1,
		help='MusecBox project to use for port setup')
	p.add_argument('Score', type=str, nargs='+',
		help='MuseScore score to apply port setup to')
	p.add_argument("--dry-run", "-n", action="store_true",
		help="Do not make changes - just show what would be changed.")
	p.add_argument("--verbose", "-v", action="store_true",
		help="Show more detailed debug information")
	p.epilog = """
	Applies the port/channel assignments in a MusecBox project to a MuseScore3 score.
	"""
	options = p.parse_args()
	log_level = logging.DEBUG if options.verbose else logging.ERROR
	logging.basicConfig(level = log_level, format = LOG_FORMAT)

	try:
		with open(options.Project[0], 'r') as fh:
			project_def = json.load(fh)
	except FileNotFoundError:
		p.exit(f'"{options.Project[0]}" is not a file')
	except json.JSONDecodeError:
		p.exit(f'There was an error decoding "{options.Project[0]}"')

	for filename in options.Score:
		print(filename)
		fixer = ScoreFixer(project_def, filename)
		try:
			fixer.fix()
		except Exception as e:
			print(e)


if __name__ == '__main__':
	sys.exit(main() or 0)


#  end musecbox/scripts/mb_apply.py
