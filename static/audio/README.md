# Menu / battle music

The dashboard crossfades two looping tracks, locked to the 3D scene's scroll:

| File                   | Plays during            | Vibe                                   |
|------------------------|-------------------------|----------------------------------------|
| `menu.mp3`             | Sniper Rifle in view    | the choral Halo menu theme             |
| `battle.mp3`           | Warthog → Crew          | the intense Halo 2 battle riff         |

Drop real `.mp3` files at exactly those two paths and they take over automatically —
no code change. Until then, throwaway **placeholder tones** are generated locally so the
crossfade is audible while developing.

`*.mp3` here is git-ignored on purpose: the real Halo 2 tracks are Microsoft/Bungie's
and must not be committed. Regenerate the placeholders any time with:

```sh
ffmpeg -y -f lavfi -i "aevalsrc='0.22*sin(2*PI*110*t)+0.16*sin(2*PI*164.81*t)+0.10*sin(2*PI*220*t)':d=8:s=44100:c=mono" -codec:a libmp3lame -q:a 6 static/audio/menu.mp3
ffmpeg -y -f lavfi -i "aevalsrc='(0.20*sin(2*PI*146.83*t)+0.15*sin(2*PI*220*t)+0.12*sin(2*PI*293.66*t))*(0.72+0.28*sin(2*PI*5.5*t))':d=8:s=44100:c=mono" -codec:a libmp3lame -q:a 6 static/audio/battle.mp3
```
