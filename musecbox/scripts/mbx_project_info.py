#  musecbox/bin/mb-project-info.py
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
Displays information about a saved MusecBox project.
"""
import logging, argparse, sys, json
from musecbox import PROJECT_OPTION_KEYS, LOG_FORMAT

def main():
	p = argparse.ArgumentParser()
	p.add_argument('Filename', type=str, nargs='+',
		help='MuseScore score to use for port setup, or saved port setup')
	p.add_argument("--show-plugins", "-p", action="store_true")
	p.add_argument("--show-options", "-s", action="store_true")
	p.add_argument("--verbose", "-v", action="store_true",
		help="Show more detailed debug information")
	p.epilog = __doc__
	options = p.parse_args()
	log_level = logging.DEBUG if options.verbose else logging.ERROR
	logging.basicConfig(level = log_level, format = LOG_FORMAT)

	try:
		with open(options.Filename[0], 'r') as fh:
			project_definition = json.load(fh)
	except FileNotFoundError:
		p.exit(f'"{options.Filename[0]}" is not a file')
	except json.JSONDecodeError:
		p.exit(f'There was an error decoding "{options.Filename[0]}"')

	for pd in project_definition["ports"]:
		print(f' Port {pd["port"]:d}')
		for td in pd["tracks"]:
			print(f'   Channel {td["channel"]:2d}: {td["instrument_name"]} ({td["voice"]})')
			print(f'     {td["sfz"]}')
			if options.show_plugins:
				for saved_state in td["plugins"]:
					print(f'     Plugin: {saved_state["vars"]["moniker"]}')
	if options.show_plugins and project_definition["shared_plugins"]:
		print(' Shared Plugins:')
		for saved_state in project_definition["shared_plugins"]:
			print(f'   {saved_state["vars"]["moniker"]}')
	if options.show_options and project_definition['options']:
		print(' Options:')
		fmt = '   {0:%ds}: {1}' % max(len(key) for key in PROJECT_OPTION_KEYS)
		for key in PROJECT_OPTION_KEYS:
			if key in project_definition['options']:
				print(fmt.format(key, project_definition['options'][key]))

if __name__ == '__main__':
	sys.exit(main() or 0)


#  musecbox/bin/mb-project-info.py
