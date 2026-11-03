# Caliversity video kit (vidkit)

One command turns a raw talking clip into an ad/reel with on-time pop-up captions,
motion-graphic scenes, flash+whoosh transitions, CTA button, music bed — in 9:16 AND 4:5 at once.
Typical run: ~2.5 min for a 25s video (both sizes).

## Setup (fresh session)
    git clone https://github.com/caliversityofficial-commits/caliversity-media && cd caliversity-media/vidkit
    pip install --break-system-packages faster-whisper pocketsphinx playwright   # usually already there
    # whisper model: a folder named `small` (CTranslate2) — pass --model /path/to/small

## 1. Exact word times (forced alignment)
    python3 align.py raw.mp4 words.json --model /path/to/small
Whisper for the words, pocketsphinx to snap each word to the real sound. Prints `word@time`.
Fix any misheard word in words.json by hand (keep the times).

## 2. Write spec.json (times = SOURCE seconds, copy them from words.json)
See the docstring at the top of render.py. Minimal:
    {"input":"raw.mp4","out":"myad","words":"words.json","highlight":["free"],"red":[],
     "transitions":[], "cta":{"at":20.1,"text":"TAP BELOW · MESSAGE ME"}, "formats":["916","45"]}
Scene types: `bignum` (big number + label + timeline bar + lines), `cards` (tilted photo cards,
THEN/NOW tags, frames grabbed from the video), `title` (kinetic words), `list` (checklist; "overlay":true
puts it on top of the video). Every word inside scenes pops in at its own time.

## 3. Render
    python3 render.py spec.json      ->  myad_916.mp4  myad_45.mp4  myad_debug.json

## Crop only (finished 9:16 -> Feed 4:5, ~20s)
    ./crop45.sh video.mp4 [y_offset]
