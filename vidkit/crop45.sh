#!/bin/bash
# crop45.sh IN.mp4 [Y_OFFSET] -> IN_4x5.mp4   (1080x1350 Feed crop of a finished 9:16 video, ~20s)
# Y_OFFSET = top of the crop window in the 1920-tall frame. 190 keeps heads; raise it if burned-in captions sit low.
in="$1"; y="${2:-190}"; out="${in%.*}_4x5.mp4"
ffmpeg -v error -y -i "$in" -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,crop=1080:1350:0:$y" -c:v libx264 -preset veryfast -b:v 3.5M -maxrate 4.5M -bufsize 8M -c:a copy -movflags +faststart "$out" && echo "$out"
