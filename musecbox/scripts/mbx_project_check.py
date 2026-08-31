#  musecbox/scripts/mbx_project_check.py
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
#  pylint: disable = duplicate-code, too-many-nested-blocks
#
"""
Checks validity of a MusecBox project.
Checks that all .sfz files exist and are readable. Optionally checks each SFZ
to see whether all the samples needed exist and are readable.
This script will return a non-zero value if any given project has problems.
"""
import logging, argparse, sys, json
from os import access, R_OK
from pathlib import Path
from rich import print as rprint
from sfzen import SFZ
from musecbox import LOG_FORMAT

ERR_MISSING_PROJECT	= 0b000000001
ERR_PROJECT_ACCESS	= 0b000000010
ERR_PROJECT_DECODE	= 0b000000100
ERR_MISSING_SFZ		= 0b000001000
ERR_SFZ_ACCESS		= 0b000010000
ERR_SFZ_DECODE_ERR	= 0b000100000
ERR_MISSING_SAMPLE	= 0b001000000
ERR_SAMPLE_ACCESS	= 0b010000000
ERR_MISSING_PLUGIN	= 0b100000000


def main():
	p = argparse.ArgumentParser()
	p.add_argument('Filename', type = str, nargs = '+', help = 'MusecBox project to check')
	p.add_argument("--quiet", "-q", action = "store_true",
		help = "Do not print anything to the console - just return a value")
	p.add_argument("--verbose", "-v", action = "store_true",
		help = "Show more detailed debug information")
	p.epilog = __doc__
	options = p.parse_args()
	log_level = logging.DEBUG if options.verbose else logging.ERROR
	logging.basicConfig(level = log_level, format = LOG_FORMAT)


	retval = 0

	for filename in options.Filename:

		path = Path(filename)

		if not options.quiet:
			rprint(f'[bold black]{path}[/bold black]', end="")

		if not path.exists():
			retval |= ERR_MISSING_PROJECT
			if not options.quiet:
				rprint(r' [red]\[missing project][/red]')
			continue
		if not access(path, R_OK):
			retval |= ERR_PROJECT_ACCESS
			if not options.quiet:
				rprint(r' [red]\[project not readable][/red]')
			continue
		try:
			project_definition = json.loads(path.read_text(encoding = 'utf-8'))
		except json.JSONDecodeError as e:
			retval |= ERR_PROJECT_DECODE
			if not options.quiet:
				rprint(fr' [red]\[JSON decode error: {e}][/red]')
			continue
		if not options.quiet:
			print()

		for portdef in project_definition["ports"]:
			for trackdef in portdef["tracks"]:
				sfz_filename = trackdef["sfz"]
				sfz_path = path.parent.joinpath(sfz_filename)
				if not path.exists():
					retval |= ERR_MISSING_SFZ
					if not options.quiet:
						rprint(fr'[black]{sfz_filename}[/black] [red]\[missing SFZ][/red]')
					continue
				if not access(path, R_OK):
					retval |= ERR_SFZ_ACCESS
					if not options.quiet:
						rprint(fr'[black]{sfz_filename}[/black] [red]\[SFZ not readable][/red]')
					continue
				sfz = SFZ(sfz_path)
				if sfz.error:
					retval |= ERR_SFZ_DECODE_ERR
					if not options.quiet:
						rprint(fr'[black]{sfz_filename}[/black] [red]\[SFZ error: {sfz.error}][/red]')
				for sample in sfz.samples():
					if not sample.abspath.exists():
						retval |= ERR_MISSING_SAMPLE
						if not options.quiet:
							rprint(fr'[black]{sample.path}[/black] [red]\[missing sample][/red]')
						continue
					if not access(sample.abspath, R_OK):
						retval |= ERR_SAMPLE_ACCESS
						if not options.quiet:
							rprint(fr'[black]{sample.path}[/black] [red]\[sample not readable][/red]')

		if not options.quiet and len(options.Filename) > 1:
			print()

	return retval

if __name__ == '__main__':
	sys.exit(main() or 0)


#  musecbox/scripts/mbx_project_check.py
