#  musecbox/scripts/mbx_project_info.py
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
from os import access, R_OK
from os.path import dirname, abspath, join, exists
from rich import print as rprint
from musecbox import PROJECT_OPTION_KEYS, LOG_FORMAT

def print_sfz(sfz_path):
	print(sfz_path, end='')
	if exists(sfz_path):
		if access(sfz_path, R_OK):
			print()
		else:
			rprint(' [red]\[not readable\][/red]')
	else:
		rprint(' [red]\[missing][/red]')

def main():
	p = argparse.ArgumentParser()
	p.add_argument('Filename', type = str, nargs = '+', help = 'MusecBox project to display')
	p.add_argument("--show-sfzs", "-s", action = "store_true")
	p.add_argument("--show-channels", "-c", action = "store_true")
	p.add_argument("--show-plugins", "-p", action = "store_true")
	p.add_argument("--show-options", "-o", action = "store_true")
	p.add_argument("--abspath", "-a", action = "store_true",
		help = "Show abspath of SFZ files")
	p.add_argument("--verbose", "-v", action = "store_true",
		help = "Show more detailed debug information")
	p.epilog = __doc__
	options = p.parse_args()
	log_level = logging.DEBUG if options.verbose else logging.ERROR
	logging.basicConfig(level = log_level, format = LOG_FORMAT)

	for filename in options.Filename:
		try:
			with open(filename, 'r') as fh:
				project_definition = json.load(fh)

		except FileNotFoundError:
			rprint(f'{filename} [red]\[not a file][/red]')

		except json.JSONDecodeError as e:
			rprint(f'{filename} [red]\[JSON decode error: {e}][/red]')

		else:

			if len(options.Filename) > 1:
				rprint(f'[bold black]{filename}[/bold black]')

			show_channels = options.show_channels or \
				options.show_sfzs or \
				options.show_plugins and any(trackdef["plugins"] \
					for portdef in project_definition["ports"] \
					for trackdef in portdef["tracks"])
			show_shared_plugins = options.show_plugins and bool(project_definition["shared_plugins"])
			show_options = options.show_options and bool(project_definition['options'])
			show_section_heads = sum([show_channels, show_shared_plugins, show_options]) > 1

			if show_channels:

				if show_section_heads:
					rprint(' [bold green]-- Channels --[/bold green]')

				for portdef in project_definition["ports"]:
					for trackdef in portdef["tracks"]:
						sfz_path = join(dirname(filename), trackdef["sfz"])
						if options.show_channels or options.show_plugins and trackdef["plugins"]:
							print(f' Port {portdef["port"]}', end='\t')
							print(f'Channel {trackdef["channel"]}', end='\t')
							print(f'{trackdef["instrument_name"]} ({trackdef["voice"]})', end='\t')
						print_sfz(abspath(sfz_path) if options.abspath else sfz_path)
						if options.show_plugins:
							for saved_state in trackdef["plugins"]:
								print(f'     Plugin {saved_state["vars"]["moniker"]}', end='\t')
								print(saved_state["plugin_def"]["label"])
				if show_section_heads:
					print()

			if options.show_plugins and project_definition["shared_plugins"]:
				if show_section_heads:
					rprint(' [bold blue]-- Shared Plugins --[/bold blue]')
				for saved_state in project_definition["shared_plugins"]:
					print(f' {saved_state["vars"]["moniker"]}\t{saved_state["plugin_def"]["label"]}')
				if show_section_heads:
					print()

			if options.show_options and project_definition['options']:
				if show_section_heads:
					rprint(' [bold dark_orange]-- Options --[/bold dark_orange]')
				fmt = ' {0:%ds}: {1}' % max(len(key) for key in PROJECT_OPTION_KEYS)
				for key in PROJECT_OPTION_KEYS:
					if key in project_definition['options']:
						print(fmt.format(key, project_definition['options'][key]))

			if len(options.Filename) > 1:
				print()

if __name__ == '__main__':
	sys.exit(main() or 0)


#  musecbox/scripts/mbx_project_info.py
