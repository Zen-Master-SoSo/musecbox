#!/bin/bash

#set -e		# Exit immediately if a command exits with a non-zero status.
#set +e		# Continue normally when a command exits with a non-zero status.
#set -x		# Print commands and their arguments as they are executed.
#set +x		# Stop printing commands and their arguments as they are executed.

TEMP=/tmp/zen_soso-musecbox.xml
MIME_XML=$HOME/.local/share/mime/packages/zen_soso-musecbox.xml
FILE_ICON=$HOME/.local/share/icons/hicolor/scalable/mimetypes/application-x-musecbox.svg
APP_ICON=$HOME/.local/share/icons/hicolor/scalable/apps/musecbox.svg
DESKTOP_FILE=$HOME/.local/share/applications/musecbox.desktop

usage() {
	MYNAME=$(basename ${0})
	echo "Usage: $MYNAME [Options]
Install MusecBox mime type and icons.

Options:
   -h    Show this help and exit
   -u    Uninstall

"
	exit 1
}


make_mime_type() {
	# mime-type definition:
	#dir=$(dirname $MIME_XML)
	#[ -d $dir ] || mkdir -p $dir
	echo "<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<mime-info xmlns=\"http://www.freedesktop.org/standards/shared-mime-info\">
  <mime-type type=\"application/x-musecbox\">
    <comment>MusecBox project</comment>
    <glob pattern=\"*.mbxp\"/>
    <generic-icon name=\"application-x-musecbox\"/>
  </mime-type>
</mime-info>
" > $TEMP
}


make_file_icon() {
	# File manager file icon:
	dir=$(dirname $FILE_ICON)
	[ -d $dir ] || mkdir -p $dir
	echo "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"no\"?>
<!-- Created with Inkscape (http://www.inkscape.org/) -->
<svg
   width=\"600\"
   height=\"600\"
   viewBox=\"0 0 600 600\"
   id=\"svg2\"
   version=\"1.1\"
   xmlns:xlink=\"http://www.w3.org/1999/xlink\"
   xmlns=\"http://www.w3.org/2000/svg\"
   xmlns:svg=\"http://www.w3.org/2000/svg\"
   xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\"
   xmlns:cc=\"http://creativecommons.org/ns#\"
   xmlns:dc=\"http://purl.org/dc/elements/1.1/\">
  <defs
     id=\"defs4\">
    <linearGradient
       id=\"linearGradient3772\">
      <stop
         style=\"stop-color:#c4c4c4;stop-opacity:1\"
         offset=\"0\"
         id=\"stop3768\" />
      <stop
         style=\"stop-color:#e7eaef;stop-opacity:1\"
         offset=\"1\"
         id=\"stop3770\" />
    </linearGradient>
    <linearGradient
       xlink:href=\"#linearGradient8964\"
       id=\"linearGradient8966\"
       x1=\"29.7466\"
       y1=\"514.23\"
       x2=\"570.254\"
       y2=\"514.23\"
       gradientUnits=\"userSpaceOnUse\" />
    <linearGradient
       id=\"linearGradient8964\">
      <stop
         style=\"stop-color:#bdced6;stop-opacity:1\"
         offset=\"0\"
         id=\"stop8960\" />
      <stop
         style=\"stop-color:#d1daf0;stop-opacity:0.996078\"
         offset=\"0.274734\"
         id=\"stop9810\" />
      <stop
         style=\"stop-color:#dce7f6;stop-opacity:0.996078\"
         offset=\"0.488656\"
         id=\"stop9744\" />
      <stop
         style=\"stop-color:#d0dae8;stop-opacity:0.996078\"
         offset=\"0.760405\"
         id=\"stop9876\" />
      <stop
         style=\"stop-color:#b8c1cd;stop-opacity:0.996078\"
         offset=\"1\"
         id=\"stop8962\" />
    </linearGradient>
    <linearGradient
       xlink:href=\"#linearGradient3772\"
       id=\"linearGradient3774\"
       x1=\"109.431\"
       y1=\"549.968\"
       x2=\"220.251\"
       y2=\"18.7833\"
       gradientUnits=\"userSpaceOnUse\" />
  </defs>
  <metadata
     id=\"metadata7\">
    <rdf:RDF>
      <cc:Work
         rdf:about=\"\">
        <dc:format>image/svg+xml</dc:format>
        <dc:type
           rdf:resource=\"http://purl.org/dc/dcmitype/StillImage\" />
      </cc:Work>
    </rdf:RDF>
  </metadata>
  <g
     id=\"layer1\"
     transform=\"translate(0,-452.36)\">
    <g
       id=\"g1078\"
       transform=\"translate(-262.858,485.714)\">
      <g
         id=\"g3430\"
         transform=\"translate(-2.64885,2.9805)\">
        <path
           id=\"rect864\"
           style=\"overflow:visible;fill:url(#linearGradient3774);fill-opacity:1;fill-rule:evenodd;stroke-width:0.6\"
           transform=\"translate(262.858,-33.354)\"
           d=\"M 75.2027,4.34041 409.518,4.34 530.095,124.917 V 589.699 H 75.2027 Z\" />
        <path
           id=\"path2357\"
           style=\"overflow:visible;fill:#ffffff;fill-opacity:1;fill-rule:evenodd;stroke-width:0.6\"
           d=\"m 97.2031,567.699 c 136.9639,0 273.9289,0 410.8929,0 0,-144.557 0,-289.114 0,-433.672 C 472.2,98.1315 436.304,62.2357 400.408,26.3398 c -101.068,0 -202.137,0 -303.2049,0 0,180.4532 0,360.9062 0,541.3592 z\"
           transform=\"translate(262.858,-33.354)\" />
      </g>
      <g
         id=\"g840\"
         transform=\"matrix(0.779849,0,0,0.780316,123.914,58.579)\"
         style=\"stroke-width:1.28192\">
        <path
           style=\"color:#000000;overflow:visible;fill:#b8b8b8;fill-rule:evenodd;stroke:#05114a;stroke-width:2.39559;stroke-opacity:1\"
           d=\"M 32.2383,394.467 300,330.303 567.762,394.467 296.538,473.441 Z\"
           id=\"path2703\"
           transform=\"matrix(0.802451,0,0,0.802895,322.342,31.604)\" />
        <path
           id=\"path4785\"
           style=\"color:#000000;overflow:visible;fill:#e1e2e8;fill-opacity:1;fill-rule:evenodd;stroke:#05114a;stroke-width:5.12766;stroke-miterlimit:4;stroke-dasharray:none;stroke-opacity:1\"
           d=\"m -175.078,13.3711 c -5.092,2.8669 -12.045,9.0681 -16.85,14.8069 -11.144,13.5456 -18.534,29.9876 -22.051,47.1283 -4.344,20.5015 -3.726,41.7267 -0.886,62.3867 1.194,8.6 2.799,17.141 4.814,25.586 -14.364,14.812 -28.27,30.216 -39.777,47.393 -11.496,17.457 -20.068,37.088 -23.327,57.818 -3.627,23.003 -0.357,47.22 10.163,68.072 0.184,0.495 0.979,1.271 -0.03,1.22 -36.248,8.691 -58.561,17.381 -94.809,26.071 -11.469,2.496 -20.797,8.093 -20.149,20.847 v 90.904 c -0.49,14.76 9.045,16.768 20.508,22.581 65.032,30.989 116.133,61.976 181.164,92.967 9.539,4.821 21.302,5.087 31.046,-0.03 67.8472,-31.18 121.9413,-62.356 189.7884,-93.536 14.2769,-6.025 19.7214,-9.474 19.5369,-21.563 V 384.474 C 64.0152,371.178 58.4871,367.347 44.8824,364.086 2.64897,353.962 -25.8302,343.837 -68.0635,333.713 c 4.5076,-12.257 5.7697,-25.592 4.2443,-38.531 -1.6421,-14.533 -7.0151,-28.734 -16.0058,-40.325 -10.4927,-13.798 -25.482,-24.344 -42.344,-28.659 -6.278,-1.613 -12.753,-2.417 -19.23,-2.536 l -4.686,-17.289 c 10.746,-12.86 20.36,-26.869 26.827,-42.395 8.287,-19.293 12.93,-40.374 11.874,-61.426 -0.682,-14.3489 -3.571,-28.6016 -8.594,-42.0618 -5.425,-14.2102 -13.563,-27.5171 -24.492,-38.163 -4.124,-3.964 -8.716,-7.564 -13.961,-9.917 -7.729,-2.75055 -15.555,-1.906 -20.647,0.9609 z\"
           transform=\"translate(719.829,-36.146)\" />
        <text
           id=\"text14254\"
           y=\"626.328\"
           x=\"-23.3769\"
           style=\"color:#000000;font-style:normal;font-variant:normal;font-weight:normal;font-stretch:normal;font-size:83.796px;line-height:100%;font-family:'Tensentype XingKaiF';-inkscape-font-specification:'Tensentype XingKaiF';text-align:start;writing-mode:lr-tb;text-anchor:start;clip-rule:nonzero;display:inline;overflow:visible;visibility:visible;isolation:auto;mix-blend-mode:normal;color-interpolation:sRGB;color-interpolation-filters:linearRGB;solid-color:#000000;solid-opacity:1;fill:#1329d1;fill-opacity:1;fill-rule:evenodd;stroke:#1329d1;stroke-width:1.16032;stroke-linecap:round;stroke-linejoin:miter;stroke-miterlimit:4;stroke-dasharray:none;stroke-dashoffset:0;stroke-opacity:1;color-rendering:auto;image-rendering:auto;shape-rendering:auto;text-rendering:auto;enable-background:accumulate\"
           xml:space=\"preserve\"
           transform=\"matrix(3.00261,-0.284997,0.284997,3.00261,359.721,-1605.78)\"><tspan
             style=\"fill:#1329d1;fill-opacity:1;stroke:#1329d1;stroke-width:1.16032;stroke-miterlimit:4;stroke-dasharray:none;stroke-opacity:1\"
             y=\"626.328\"
             x=\"-23.3769\"
             id=\"tspan14252\"></tspan></text>
        <path
           id=\"path2701\"
           style=\"color:#000000;overflow:visible;fill:url(#linearGradient8966);fill-opacity:1;fill-rule:evenodd;stroke:#05114a;stroke-width:6.38824;stroke-miterlimit:4;stroke-dasharray:none;stroke-opacity:1\"
           transform=\"matrix(0.802451,0,0,0.802895,322.342,31.604)\"
           d=\"M 296.538,473.441 554.057,394.467 V 508.218 L 295.143,633.409 Z M 46.8353,394.467 v 113.751 l 248.3077,125.191 1.395,-159.968 z\" />
      </g>
    </g>
  </g>
</svg>
" > $FILE_ICON
}


make_app_icon() {
	# Application icon:
	dir=$(dirname $APP_ICON)
	[ -d $dir ] || mkdir -p $dir
	echo "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"no\"?>
<!-- Created with Inkscape (http://www.inkscape.org/) -->
<svg
   width=\"600\"
   height=\"600\"
   viewBox=\"0 0 600 600\"
   id=\"svg2\"
   version=\"1.1\"
   xmlns:xlink=\"http://www.w3.org/1999/xlink\"
   xmlns=\"http://www.w3.org/2000/svg\"
   xmlns:svg=\"http://www.w3.org/2000/svg\"
   xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\"
   xmlns:cc=\"http://creativecommons.org/ns#\"
   xmlns:dc=\"http://purl.org/dc/elements/1.1/\">
  <defs
     id=\"defs4\">
    <linearGradient
       id=\"linearGradient10016\">
      <stop
         style=\"stop-color:#b8b8b8;stop-opacity:1;\"
         offset=\"0\"
         id=\"stop10012\" />
      <stop
         style=\"stop-color:#eeeeee;stop-opacity:1\"
         offset=\"1\"
         id=\"stop10014\" />
    </linearGradient>
    <linearGradient
       id=\"linearGradient8964\">
      <stop
         style=\"stop-color:#bdced6;stop-opacity:1\"
         offset=\"0\"
         id=\"stop8960\" />
      <stop
         style=\"stop-color:#d1e5f0;stop-opacity:0.996078\"
         offset=\"0.274734\"
         id=\"stop9810\" />
      <stop
         style=\"stop-color:#dcedf6;stop-opacity:0.996078\"
         offset=\"0.488656\"
         id=\"stop9744\" />
      <stop
         style=\"stop-color:#d0e0e8;stop-opacity:0.996078\"
         offset=\"0.760405\"
         id=\"stop9876\" />
      <stop
         style=\"stop-color:#b8c6cd;stop-opacity:0.996078\"
         offset=\"1\"
         id=\"stop8962\" />
    </linearGradient>
    <linearGradient
       xlink:href=\"#linearGradient8964\"
       id=\"linearGradient8966\"
       x1=\"29.7466\"
       y1=\"514.23\"
       x2=\"570.254\"
       y2=\"514.23\"
       gradientUnits=\"userSpaceOnUse\" />
    <radialGradient
       xlink:href=\"#linearGradient10016\"
       id=\"radialGradient10018\"
       cx=\"-157.061\"
       cy=\"302.792\"
       fx=\"-157.061\"
       fy=\"302.792\"
       r=\"236.882\"
       gradientTransform=\"matrix(1,0,0,1.24145,0,-73.1091)\"
       gradientUnits=\"userSpaceOnUse\" />
  </defs>
  <metadata
     id=\"metadata7\">
    <rdf:RDF>
      <cc:Work
         rdf:about=\"\">
        <dc:format>image/svg+xml</dc:format>
        <dc:type
           rdf:resource=\"http://purl.org/dc/dcmitype/StillImage\" />
      </cc:Work>
    </rdf:RDF>
  </metadata>
  <g
     id=\"layer1\"
     transform=\"translate(0,-452.36)\">
    <g
       id=\"g8383\"
       transform=\"translate(-2.94707,-2.79202)\">
      <path
         style=\"color:#000000;overflow:visible;fill:#b8b8b8;fill-rule:evenodd;stroke:#05114a;stroke-width:1.86876;stroke-opacity:1\"
         d=\"M 32.2383,394.467 300,330.303 567.762,394.467 296.538,473.441 Z\"
         id=\"path2703\"
         transform=\"matrix(0.802451,0,0,0.802895,62.5214,520.11)\" />
      <path
         id=\"path4785\"
         style=\"color:#000000;overflow:visible;fill:url(#radialGradient10018);fill-opacity:1;fill-rule:evenodd;stroke:#05114a;stroke-width:4;stroke-miterlimit:4;stroke-dasharray:none;stroke-opacity:1\"
         d=\"m -175.078,13.3711 c -5.092,2.8669 -12.045,9.0681 -16.85,14.8069 -11.144,13.5456 -18.534,29.9876 -22.051,47.1283 -4.344,20.5015 -3.726,41.7267 -0.886,62.3867 1.194,8.6 2.799,17.141 4.814,25.586 -14.364,14.812 -28.27,30.216 -39.777,47.393 -11.496,17.457 -20.068,37.088 -23.327,57.818 -3.627,23.003 -0.357,47.22 10.163,68.072 0.184,0.495 0.979,1.271 -0.03,1.22 -36.248,8.691 -58.561,17.381 -94.809,26.071 -11.469,2.496 -20.797,8.093 -20.149,20.847 v 90.904 c -0.49,14.76 9.045,16.768 20.508,22.581 65.032,30.989 116.133,61.976 181.164,92.967 9.539,4.821 21.302,5.087 31.046,-0.03 67.8472,-31.18 121.9413,-62.356 189.7884,-93.536 14.2769,-6.025 19.7214,-9.474 19.5369,-21.563 V 384.474 C 64.0152,371.178 58.4871,367.347 44.8824,364.086 2.64897,353.962 -25.8302,343.837 -68.0635,333.713 c 4.5076,-12.257 5.7697,-25.592 4.2443,-38.531 -1.6421,-14.533 -7.0151,-28.734 -16.0058,-40.325 -10.4927,-13.798 -25.482,-24.344 -42.344,-28.659 -6.278,-1.613 -12.753,-2.417 -19.23,-2.536 l -4.686,-17.289 c 10.746,-12.86 20.36,-26.869 26.827,-42.395 8.287,-19.293 12.93,-40.374 11.874,-61.426 -0.682,-14.3489 -3.571,-28.6016 -8.594,-42.0618 -5.425,-14.2102 -13.563,-27.5171 -24.492,-38.163 -4.124,-3.964 -8.716,-7.564 -13.961,-9.917 -7.729,-2.75055 -15.555,-1.906 -20.647,0.9609 z\"
         transform=\"translate(460.008,452.36)\" />
      <text
         id=\"text14254\"
         y=\"626.328\"
         x=\"-23.3769\"
         style=\"color:#000000;font-style:normal;font-variant:normal;font-weight:normal;font-stretch:normal;font-size:83.796px;line-height:100%;font-family:'Tensentype XingKaiF';-inkscape-font-specification:'Tensentype XingKaiF';text-align:start;writing-mode:lr-tb;text-anchor:start;clip-rule:nonzero;display:inline;overflow:visible;visibility:visible;isolation:auto;mix-blend-mode:normal;color-interpolation:sRGB;color-interpolation-filters:linearRGB;solid-color:#000000;solid-opacity:1;fill:#1329d1;fill-opacity:1;fill-rule:evenodd;stroke:#1329d1;stroke-width:0.905144;stroke-linecap:round;stroke-linejoin:miter;stroke-miterlimit:4;stroke-dasharray:none;stroke-dashoffset:0;stroke-opacity:1;color-rendering:auto;image-rendering:auto;shape-rendering:auto;text-rendering:auto;enable-background:accumulate\"
         xml:space=\"preserve\"
         transform=\"matrix(3.00261,-0.284997,0.284997,3.00261,99.8998,-1117.27)\"><tspan
           style=\"fill:#1329d1;fill-opacity:1;stroke:#1329d1;stroke-width:0.905144;stroke-miterlimit:4;stroke-dasharray:none;stroke-opacity:1\"
           y=\"626.328\"
           x=\"-23.3769\"
           id=\"tspan14252\"></tspan></text>
      <path
         id=\"path2701\"
         style=\"color:#000000;overflow:visible;fill:url(#linearGradient8966);fill-opacity:1;fill-rule:evenodd;stroke:#05114a;stroke-width:4.98335;stroke-miterlimit:4;stroke-dasharray:none;stroke-opacity:1\"
         transform=\"matrix(0.802451,0,0,0.802895,62.5214,520.11)\"
         d=\"M 296.538,473.441 554.057,394.467 V 508.218 L 295.143,633.409 Z M 46.8353,394.467 v 113.751 l 248.3077,125.191 1.395,-159.968 z\" />
    </g>
  </g>
</svg>
" > $APP_ICON
}


make_desktop_file() {
	# .desktop file (launcher)
	dir=$(dirname $DESKTOP_FILE)
	[ -d $dir ] || mkdir -p $dir
	echo "[Desktop Entry]
Version=1.0
Name=MusecBox
Comment=SFZ-oriented synthesizer utilizing liquidsfz, Carla, and JACK audio connection kit
Keywords=audio;sound;jackd,lv2,midi,sfz
Icon=musecbox
Exec=/usr/bin/python3 -m musecbox
Terminal=false
Type=Application
Categories=AudioVideo;Audio;
MimeType=application/x-musecbox;audio/x-sfz;application/x-musescore3;application/x-musescore3+xml;
" > $DESKTOP_FILE
}


install() {
	make_mime_type
	xdg-mime install $TEMP
	rm $TEMP
	make_file_icon
	make_app_icon
	update-icon-caches $HOME/.local/share/icons/*
	make_desktop_file
	xdg-mime default musecbox.desktop application/x-musecbox
	update-mime-database $HOME/.local/share/mime
	update-desktop-database $HOME/.local/share/applications
}


uninstall() {
	xdg-mime uninstall $MIME_XML
	rm -f $MIME_XML $FILE_ICON $APP_ICON $DESKTOP_FILE
	update-mime-database $HOME/.local/share/mime
	update-icon-caches $HOME/.local/share/icons/*
}


# Short format command args:
if [ "$1" == "-h" ] ; then usage ; fi

if [ "$1" == "-u" ]
then
	uninstall
else
	install
fi

