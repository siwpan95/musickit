# After Midnight — The Mix Engineer Series (10 Mixers × 6 Tracks)

**Compiled & mixed with musickit stems**  

Six instrumental R&B/soul tracks assembled from the G:\musickit sample library. **The same six tracks, the same stems, the same arrangement** are mixed through 10 different mixing engineers' signature chains — from Craig Burbidge's vocal-forward warmth to Al Schmitt's natural transparency and Mike Dean's saturated psychedelia — so the styles can be A/B-compared directly. Each chain is a parameterization of the zero-dependency DSP toolkit in dsp.py (biquad EQ, feed-forward compression, tanh saturation, convolution plate/room reverb, M/S width, brickwall limiting).


## The 10 mixers at a glance

| # | Mixer | 中文 | Reference artists | Signature | Target LUFS |
|---|---|---|---|---|---|
| 1 | Craig Burbidge | 克雷格·伯比奇 | Barry White, Brian McKnight, Take 6, Vanessa Williams | warm console · vocal-forward · lush plate | -13.0 |
| 2 | Serban Ghenea | 塞尔班·吉尼亚 | Taylor Swift, Ariana Grande, The Weeknd, Bruno Mars | hyper-clean · bright air · loud but polite | -9.0 |
| 3 | Bob Clearmountain | 鲍勃·克利尔芒廷 | Bruce Springsteen, The Rolling Stones, INXS, Bryan Adams | big room · dynamic drums · classic rock | -14.0 |
| 4 | Manny Marroquin | 曼尼·马罗奎因 | Kendrick Lamar, Post Malone, Kanye West, Rihanna | deep 808 lows · hard kick · modern loudness | -10.0 |
| 5 | Dave Pensado | 戴夫·潘萨多 | Christina Aguilera, Kelly Rowland, Beyoncé, Justin Timberlake | big lows · crispy highs · exciting | -10.0 |
| 6 | Tchad Blake | 查德·布莱克 | Tom Waits, Peter Gabriel, Arctic Monkeys, The Black Keys | gritty · squashed · quirky mono width | -12.0 |
| 7 | Chris Lord-Alge | 克里斯·洛德-阿尔吉 | Green Day, Muse, My Chemical Romance, Avril Lavigne | loud · punchy · radio bright | -9.0 |
| 8 | Al Schmitt | 阿尔·施密特 | Frank Sinatra, Steely Dan, Diana Krall, Henry Mancini | natural · transparent · dynamic | -16.0 |
| 9 | Mike Dean | 迈克·迪恩 | Kanye West, Travis Scott, The Weeknd, Beyoncé | saturated · spacey · huge stereo | -10.0 |
| 10 | Spike Stent | 斯派克·斯坦特 | Björk, Depeche Mode, Muse, Massive Attack | dark · edgy · tense mids | -10.0 |

## Craig Burbidge (克雷格·伯比奇) — album/burbidge/

Late-80s/90s LA R&B, soul, gospel and pop (Barry White, Brian McKnight, Take 6, Vanessa Williams, David Tao 陶喆, 张惠妹, 王力宏, 五月天). Signature: vocal-forward, warm SSL/Neve console body, deep punchy bottom, lush plate on lead + gospel-style backgrounds, smooth opto-style lead compression, glue bus compression, wide polished stereo.

- Reference artists: Barry White, Brian McKnight, Take 6, Vanessa Williams, David Tao, 张惠妹, 王力宏, 五月天.

- Output folder: album/burbidge/ — open album/burbidge/index.html to listen.


| Stage | Signature | This implementation |
|---|---|---|
| Drums | Punchy, controlled, centered (SSL drum bus) | HPF 35 Hz · lowshelf +1.0 dB @ 120 Hz · peak +1.5 dB @ 4000 Hz · comp -20 dB 4:1 (5/120 ms, k3, +2 dB) · sat drive 1.2 mix 0.12 · room reverb 10% · -5 dB |
| Bass | Deep Barry-White bottom, tight 6:1 | HPF 30 Hz · lowshelf +2.0 dB @ 90 Hz · peak +2.0 dB @ 80 Hz · comp -24 dB 6:1 (3/200 ms, k2, +1 dB) · sat drive 1.5 mix 0.22 · -7 dB |
| Harmony/pad | Warm, slightly recessed harmony bed | HPF 40 Hz · lowshelf -1.0 dB @ 250 Hz · peak +1.0 dB @ 2500 Hz · comp -22 dB 2.5:1 (15/250 ms, k3, +1 dB) · med reverb 18% · M/S +0.30 · -11 dB |
| Lead (the 'voice') | THE vocal stand-in: front, intimate, lush plate | HPF 50 Hz · lowshelf +1.0 dB @ 200 Hz · peak +2.0 dB @ 3800 Hz · comp -16 dB 2:1 (20/300 ms, k4, +1.5 dB) · long reverb 30% · M/S +0.15 · pan +0.08 · -3 dB |
| Background | Wide gospel-style backgrounds behind the lead | HPF 80 Hz · LPF 9000 Hz · comp -24 dB 2:1 (20/300 ms, k3, +0 dB) · long reverb 35% · M/S +0.60 · -15 dB |
| Master bus | Warm glue, polished width, musical dynamics | HPF 30 Hz · lowshelf +0.5 dB @ 60 Hz · peak +1.5 dB @ 12000 Hz · comp -18 dB 2:1 (10/200 ms, k2, +1.5 dB) · sat drive 1.1 mix 0.08 · M/S +0.10 · target -13 LUFS · limiter rel 80 ms |

| # | Title | Tempo | Key | Duration | est. LUFS |
|---|---|---|---|---|---|
| 01 | Midnight Velvet | 88 BPM | B | 152.7 s | -27.0 |
| 02 | Slow Car | 90 BPM | D | 149.3 s | -21.3 |
| 03 | Neon Rain | 100 BPM | E | 144.0 s | -21.2 |
| 04 | Gravity | 105 BPM | A | 137.1 s | -19.3 |
| 05 | Sunset Boulevard | 110 BPM | A | 130.9 s | -19.3 |
| 06 | After Hours | 120 BPM | C | 128.0 s | -23.3 |

## Serban Ghenea (塞尔班·吉尼亚) — album/ghenea/

The most-played mixer in modern pop (Taylor Swift, Ariana Grande, The Weeknd, Bruno Mars, Dua Lipa). Signature: hyper-clean separation between elements, punchy-but-polite dynamics, crisp top-end air, loud without sounding crushed.

- Reference artists: Taylor Swift, Ariana Grande, The Weeknd, Bruno Mars, Dua Lipa.

- Output folder: album/ghenea/ — open album/ghenea/index.html to listen.


| Stage | Signature | This implementation |
|---|---|---|
| Drums | Punchy but polite, crisp attack | HPF 30 Hz · lowshelf +0.5 dB @ 100 Hz · peak +2.0 dB @ 2500 Hz · peak +1.5 dB @ 8000 Hz · comp -16 dB 3:1 (4/100 ms, k2, +1 dB) · sat drive 1.05 mix 0.02 · room reverb 6% · -5 dB |
| Bass | Tight, controlled, clean low end | HPF 35 Hz · lowshelf +1.5 dB @ 80 Hz · peak +1.0 dB @ 120 Hz · peak -1.0 dB @ 200 Hz · comp -20 dB 4:1 (4/150 ms, k2, +1 dB) · -8 dB |
| Harmony/pad | Tucked well behind the vocal lane | HPF 60 Hz · lowshelf -2.0 dB @ 200 Hz · peak +1.0 dB @ 3000 Hz · comp -24 dB 3:1 (10/200 ms, k2, +0.5 dB) · med reverb 12% · M/S +0.40 · -13 dB |
| Lead (the 'voice') | Hyper-clean, bright, sits perfectly on top | HPF 80 Hz · lowshelf -0.5 dB @ 150 Hz · peak +2.5 dB @ 3000 Hz · peak +2.0 dB @ 8000 Hz · comp -14 dB 2:1 (15/120 ms, k2, +2 dB) · med reverb 12% · M/S +0.10 · -3 dB |
| Background | Wide but out of the way | HPF 100 Hz · LPF 11000 Hz · comp -26 dB 2:1 (15/200 ms, k2, +0 dB) · med reverb 20% · M/S +0.50 · -16 dB |
| Master bus | Transparent glue, bright air, loud yet un-crushed | HPF 25 Hz · lowshelf +0.5 dB @ 50 Hz · peak +0.5 dB @ 2000 Hz · peak +2.0 dB @ 12000 Hz · comp -14 dB 1.5:1 (8/100 ms, k1, +1.5 dB) · sat drive 1.03 mix 0.02 · M/S +0.15 · target -9 LUFS · limiter rel 80 ms |

| # | Title | Tempo | Key | Duration | est. LUFS |
|---|---|---|---|---|---|
| 01 | Midnight Velvet | 88 BPM | B | 152.7 s | -24.3 |
| 02 | Slow Car | 90 BPM | D | 149.3 s | -21.7 |
| 03 | Neon Rain | 100 BPM | E | 144.0 s | -21.0 |
| 04 | Gravity | 105 BPM | A | 137.1 s | -19.7 |
| 05 | Sunset Boulevard | 110 BPM | A | 130.9 s | -18.7 |
| 06 | After Hours | 120 BPM | C | 128.0 s | -21.4 |

## Bob Clearmountain (鲍勃·克利尔芒廷) — album/clearmountain/

Classic rock royalty (Bruce Springsteen, The Rolling Stones, INXS, Bryan Adams, Roxy Music). Signature: big natural room ambience, dynamic punchy drums, the sound of a band playing in a great room rather than a polished product.

- Reference artists: Bruce Springsteen, The Rolling Stones, INXS, Bryan Adams, Roxy Music.

- Output folder: album/clearmountain/ — open album/clearmountain/index.html to listen.


| Stage | Signature | This implementation |
|---|---|---|
| Drums | Big, dynamic, roomy | HPF 30 Hz · lowshelf +2.0 dB @ 100 Hz · peak +1.0 dB @ 3000 Hz · comp -18 dB 3:1 (8/150 ms, k2, +1 dB) · sat drive 1.15 mix 0.1 · room reverb 35% · -4 dB |
| Bass | Round, natural, supportive | HPF 40 Hz · lowshelf +1.0 dB @ 90 Hz · peak +1.0 dB @ 160 Hz · comp -22 dB 3:1 (6/180 ms, k2, +0.5 dB) · sat drive 1.3 mix 0.15 · -8 dB |
| Harmony/pad | Open, airy, unhyped | HPF 50 Hz · lowshelf -1.0 dB @ 250 Hz · comp -24 dB 2:1 (20/300 ms, k2, +0 dB) · med reverb 15% · M/S +0.20 · -12 dB |
| Lead (the 'voice') | Natural, sits in the band rather than on it | HPF 70 Hz · lowshelf +0.5 dB @ 180 Hz · peak +1.5 dB @ 2500 Hz · comp -16 dB 2:1 (25/250 ms, k3, +1 dB) · room reverb 20% · M/S +0.10 · -4 dB |
| Background | Ambient width from the room | HPF 90 Hz · LPF 10000 Hz · comp -24 dB 2:1 (20/300 ms, k2, +0 dB) · med reverb 25% · M/S +0.40 · -15 dB |
| Master bus | Gentle glue, real dynamics, classic rock sheen | HPF 28 Hz · lowshelf +1.0 dB @ 60 Hz · peak +1.0 dB @ 10000 Hz · comp -16 dB 1.5:1 (15/250 ms, k2, +1 dB) · sat drive 1.08 mix 0.05 · M/S +0.05 · target -14 LUFS · limiter rel 80 ms |

| # | Title | Tempo | Key | Duration | est. LUFS |
|---|---|---|---|---|---|
| 01 | Midnight Velvet | 88 BPM | B | 152.7 s | -26.6 |
| 02 | Slow Car | 90 BPM | D | 149.3 s | -21.4 |
| 03 | Neon Rain | 100 BPM | E | 144.0 s | -22.3 |
| 04 | Gravity | 105 BPM | A | 137.1 s | -18.8 |
| 05 | Sunset Boulevard | 110 BPM | A | 130.9 s | -19.4 |
| 06 | After Hours | 120 BPM | C | 128.0 s | -20.5 |

## Manny Marroquin (曼尼·马罗奎因) — album/marroquin/

Modern hip-hop and R&B (Kendrick Lamar, Post Malone, Kanye West, Rihanna, Alicia Keys). Signature: massive deep lows, hard-hitting kick, clean intimate vocals, modern loudness that stays musical.

- Reference artists: Kendrick Lamar, Post Malone, Kanye West, Rihanna, Alicia Keys.

- Output folder: album/marroquin/ — open album/marroquin/index.html to listen.


| Stage | Signature | This implementation |
|---|---|---|
| Drums | Huge kick, modern punch | HPF 28 Hz · lowshelf +2.5 dB @ 90 Hz · peak +2.0 dB @ 5000 Hz · comp -18 dB 4:1 (3/90 ms, k2, +2 dB) · sat drive 1.25 mix 0.15 · room reverb 8% · -4 dB |
| Bass | 808-grade depth, bass-forward | HPF 25 Hz · lowshelf +3.0 dB @ 60 Hz · peak +1.5 dB @ 100 Hz · comp -22 dB 5:1 (2/120 ms, k2, +1 dB) · sat drive 1.6 mix 0.25 · -6 dB |
| Harmony/pad | Thin-walled so the lows stay clear | HPF 50 Hz · lowshelf -2.0 dB @ 200 Hz · peak +0.5 dB @ 2000 Hz · comp -24 dB 3:1 (12/220 ms, k2, +0.5 dB) · med reverb 15% · M/S +0.35 · -13 dB |
| Lead (the 'voice') | Clean, intimate, slightly wet | HPF 70 Hz · lowshelf +0.5 dB @ 160 Hz · peak +2.0 dB @ 3200 Hz · comp -15 dB 2.5:1 (18/180 ms, k3, +2 dB) · long reverb 22% · M/S +0.12 · -3 dB |
| Background | Deep, wide bed | HPF 100 Hz · LPF 9500 Hz · comp -26 dB 2:1 (18/250 ms, k2, +0 dB) · long reverb 30% · M/S +0.55 · -16 dB |
| Master bus | Massive lows, controlled loudness | HPF 25 Hz · lowshelf +1.5 dB @ 45 Hz · peak +1.0 dB @ 15000 Hz · comp -15 dB 2:1 (6/150 ms, k2, +2 dB) · sat drive 1.12 mix 0.1 · M/S +0.12 · target -10 LUFS · limiter rel 80 ms |

| # | Title | Tempo | Key | Duration | est. LUFS |
|---|---|---|---|---|---|
| 01 | Midnight Velvet | 88 BPM | B | 152.7 s | -26.4 |
| 02 | Slow Car | 90 BPM | D | 149.3 s | -21.1 |
| 03 | Neon Rain | 100 BPM | E | 144.0 s | -18.8 |
| 04 | Gravity | 105 BPM | A | 137.1 s | -18.7 |
| 05 | Sunset Boulevard | 110 BPM | A | 130.9 s | -20.1 |
| 06 | After Hours | 120 BPM | C | 128.0 s | -20.1 |

## Dave Pensado (戴夫·潘萨多) — album/pensado/

Hitmaker and educator ('Pensado's Place'); credits include Christina Aguilera, Kelly Rowland, Beyoncé. Signature: BIG bottom, crispy sparkling highs, a smiley curve that sounds exciting on any system.

- Reference artists: Christina Aguilera, Kelly Rowland, Beyoncé, Justin Timberlake.

- Output folder: album/pensado/ — open album/pensado/index.html to listen.


| Stage | Signature | This implementation |
|---|---|---|
| Drums | Big and snappy | HPF 30 Hz · lowshelf +2.0 dB @ 110 Hz · peak +2.5 dB @ 6000 Hz · comp -17 dB 3.5:1 (5/110 ms, k2, +1.5 dB) · sat drive 1.3 mix 0.15 · room reverb 10% · -5 dB |
| Bass | Sub-heavy, rumbling | HPF 28 Hz · lowshelf +3.0 dB @ 70 Hz · peak +1.5 dB @ 90 Hz · comp -22 dB 5:1 (3/140 ms, k2, +1 dB) · sat drive 1.5 mix 0.2 · -7 dB |
| Harmony/pad | Balanced, sparkly | HPF 55 Hz · lowshelf -1.5 dB @ 220 Hz · peak +1.5 dB @ 2800 Hz · comp -23 dB 2.5:1 (14/240 ms, k2, +0.5 dB) · med reverb 15% · M/S +0.35 · -12 dB |
| Lead (the 'voice') | Bright, crispy, exciting | HPF 75 Hz · lowshelf +0.5 dB @ 170 Hz · peak +2.5 dB @ 3500 Hz · peak +2.5 dB @ 8000 Hz · comp -15 dB 2:1 (18/150 ms, k3, +2 dB) · long reverb 25% · M/S +0.12 · -3 dB |
| Background | Wide and shimmery | HPF 100 Hz · LPF 10500 Hz · comp -25 dB 2:1 (18/260 ms, k2, +0 dB) · long reverb 30% · M/S +0.55 · -15 dB |
| Master bus | Big lows + crispy highs, exciting loudness | HPF 28 Hz · lowshelf +1.5 dB @ 55 Hz · peak +1.0 dB @ 3000 Hz · peak +2.0 dB @ 14000 Hz · comp -15 dB 1.8:1 (7/130 ms, k2, +2 dB) · sat drive 1.15 mix 0.1 · M/S +0.15 · target -10 LUFS · limiter rel 80 ms |

| # | Title | Tempo | Key | Duration | est. LUFS |
|---|---|---|---|---|---|
| 01 | Midnight Velvet | 88 BPM | B | 152.7 s | -29.0 |
| 02 | Slow Car | 90 BPM | D | 149.3 s | -21.3 |
| 03 | Neon Rain | 100 BPM | E | 144.0 s | -20.4 |
| 04 | Gravity | 105 BPM | A | 137.1 s | -19.5 |
| 05 | Sunset Boulevard | 110 BPM | A | 130.9 s | -20.4 |
| 06 | After Hours | 120 BPM | C | 128.0 s | -22.3 |

## Tchad Blake (查德·布莱克) — album/blake/

The anti-polish mix master — engineer for Tom Waits and Peter Gabriel, mixer for Arctic Monkeys, The Black Keys, Sheryl Crow. Signature: gritty saturation, squashed dynamics, quirky narrow/mono-ish width, lo-fi character with attitude.

- Reference artists: Tom Waits, Peter Gabriel, Arctic Monkeys, The Black Keys, Sheryl Crow.

- Output folder: album/blake/ — open album/blake/index.html to listen.


| Stage | Signature | This implementation |
|---|---|---|
| Drums | Squashed, gritty, explosive | HPF 40 Hz · lowshelf +1.0 dB @ 90 Hz · peak +2.0 dB @ 2000 Hz · comp -14 dB 5:1 (3/80 ms, k2, +1 dB) · sat drive 2 mix 0.5 · room reverb 15% · M/S -0.15 · -5 dB |
| Bass | Furry, driven, midrangey | HPF 35 Hz · lowshelf +2.0 dB @ 80 Hz · comp -18 dB 5:1 (2/100 ms, k2, +0.5 dB) · sat drive 2.2 mix 0.45 · -7 dB |
| Harmony/pad | Dark, murky texture | HPF 70 Hz · LPF 7000 Hz · comp -22 dB 3:1 (10/200 ms, k2, +0 dB) · sat drive 1.6 mix 0.3 · M/S -0.10 · -11 dB |
| Lead (the 'voice') | Lo-fi, gritty, in-your-face | HPF 90 Hz · peak +2.0 dB @ 1800 Hz · comp -12 dB 3:1 (12/140 ms, k3, +1 dB) · sat drive 2 mix 0.4 · room reverb 18% · M/S -0.10 · -3 dB |
| Background | Narrow, dark backdrop | HPF 110 Hz · LPF 6500 Hz · comp -24 dB 2.5:1 (15/220 ms, k2, +0 dB) · sat drive 1.5 mix 0.25 · M/S -0.05 · -15 dB |
| Master bus | Narrow-ish mono glue, pleasing grit, no polish | HPF 35 Hz · LPF 16000 Hz · lowshelf +1.0 dB @ 70 Hz · peak +1.5 dB @ 2500 Hz · comp -13 dB 2.5:1 (5/90 ms, k2, +1.5 dB) · sat drive 1.5 mix 0.25 · M/S -0.15 · target -12 LUFS · limiter rel 80 ms |

| # | Title | Tempo | Key | Duration | est. LUFS |
|---|---|---|---|---|---|
| 01 | Midnight Velvet | 88 BPM | B | 152.7 s | -25.2 |
| 02 | Slow Car | 90 BPM | D | 149.3 s | -16.9 |
| 03 | Neon Rain | 100 BPM | E | 144.0 s | -22.0 |
| 04 | Gravity | 105 BPM | A | 137.1 s | -18.7 |
| 05 | Sunset Boulevard | 110 BPM | A | 130.9 s | -17.9 |
| 06 | After Hours | 120 BPM | C | 128.0 s | -19.8 |

## Chris Lord-Alge (克里斯·洛德-阿尔吉) — album/lordalge/

Radio rock and pop (Green Day, Muse, My Chemical Romance, Avril Lavigne, Bon Jovi). Signature: loud, punchy, bright — every element maximized for radio impact without turning to mush.

- Reference artists: Green Day, Muse, My Chemical Romance, Avril Lavigne, Bon Jovi.

- Output folder: album/lordalge/ — open album/lordalge/index.html to listen.


| Stage | Signature | This implementation |
|---|---|---|
| Drums | Huge, hard-hitting | HPF 30 Hz · lowshelf +2.5 dB @ 110 Hz · peak +2.0 dB @ 3000 Hz · peak +1.5 dB @ 8000 Hz · comp -16 dB 4:1 (4/90 ms, k2, +2.5 dB) · sat drive 1.3 mix 0.18 · room reverb 20% · -4 dB |
| Bass | Firm, defined low end | HPF 32 Hz · lowshelf +2.0 dB @ 85 Hz · peak +1.0 dB @ 150 Hz · comp -20 dB 4:1 (4/130 ms, k2, +1 dB) · sat drive 1.4 mix 0.18 · -7 dB |
| Harmony/pad | Supportive, slightly compressed | HPF 55 Hz · lowshelf -1.5 dB @ 240 Hz · peak +1.0 dB @ 2600 Hz · comp -23 dB 2.5:1 (12/220 ms, k2, +0.5 dB) · med reverb 15% · M/S +0.30 · -12 dB |
| Lead (the 'voice') | Loud, bright, radio-forward | HPF 75 Hz · lowshelf +1.0 dB @ 170 Hz · peak +2.5 dB @ 3000 Hz · comp -14 dB 2.5:1 (15/130 ms, k3, +2 dB) · med reverb 18% · M/S +0.10 · -3 dB |
| Background | Wide, glossy | HPF 100 Hz · LPF 10000 Hz · comp -25 dB 2:1 (15/240 ms, k2, +0 dB) · med reverb 25% · M/S +0.50 · -15 dB |
| Master bus | Loud, punchy, bright — radio ready | HPF 28 Hz · lowshelf +1.5 dB @ 55 Hz · peak +1.0 dB @ 2500 Hz · peak +1.5 dB @ 12000 Hz · comp -14 dB 2:1 (6/120 ms, k2, +2.5 dB) · sat drive 1.15 mix 0.12 · M/S +0.12 · target -9 LUFS · limiter rel 80 ms |

| # | Title | Tempo | Key | Duration | est. LUFS |
|---|---|---|---|---|---|
| 01 | Midnight Velvet | 88 BPM | B | 152.7 s | -27.1 |
| 02 | Slow Car | 90 BPM | D | 149.3 s | -23.5 |
| 03 | Neon Rain | 100 BPM | E | 144.0 s | -20.8 |
| 04 | Gravity | 105 BPM | A | 137.1 s | -19.6 |
| 05 | Sunset Boulevard | 110 BPM | A | 130.9 s | -20.6 |
| 06 | After Hours | 120 BPM | C | 128.0 s | -21.7 |

## Al Schmitt (阿尔·施密特) — album/schmitt/

23-time Grammy winner, the conscience of natural sound (Frank Sinatra, Steely Dan, Diana Krall, Henry Mancini, Toto). Signature: the microphone does the work and the mixer stays out of the way — pure tone, real dynamics, no hype.

- Reference artists: Frank Sinatra, Steely Dan, Diana Krall, Henry Mancini, Toto.

- Output folder: album/schmitt/ — open album/schmitt/index.html to listen.


| Stage | Signature | This implementation |
|---|---|---|
| Drums | Natural, open, unhyped | HPF 30 Hz · lowshelf +0.5 dB @ 90 Hz · comp -20 dB 2:1 (10/200 ms, k2, +0.5 dB) · room reverb 25% · -6 dB |
| Bass | Round and acoustic-sounding | HPF 35 Hz · lowshelf +1.0 dB @ 80 Hz · comp -22 dB 2.5:1 (8/220 ms, k2, +0 dB) · -8 dB |
| Harmony/pad | Airy, transparent | HPF 45 Hz · lowshelf -1.0 dB @ 220 Hz · comp -26 dB 1.5:1 (25/400 ms, k2, +0 dB) · med reverb 10% · M/S +0.15 · -13 dB |
| Lead (the 'voice') | Pure tone, no hype | HPF 60 Hz · lowshelf +0.5 dB @ 180 Hz · peak +1.0 dB @ 2800 Hz · comp -18 dB 1.5:1 (30/350 ms, k2, +0.5 dB) · room reverb 15% · M/S +0.05 · -4 dB |
| Background | Gentle, natural depth | HPF 80 Hz · LPF 11000 Hz · comp -26 dB 1.5:1 (25/400 ms, k2, +0 dB) · med reverb 15% · M/S +0.25 · -16 dB |
| Master bus | Transparent, dynamic, audiophile headroom | HPF 30 Hz · lowshelf +0.5 dB @ 60 Hz · peak +0.5 dB @ 10000 Hz · comp -18 dB 1.5:1 (20/350 ms, k2, +0.5 dB) · M/S +0.05 · target -16 LUFS · limiter rel 80 ms |

| # | Title | Tempo | Key | Duration | est. LUFS |
|---|---|---|---|---|---|
| 01 | Midnight Velvet | 88 BPM | B | 152.7 s | -25.9 |
| 02 | Slow Car | 90 BPM | D | 149.3 s | -21.0 |
| 03 | Neon Rain | 100 BPM | E | 144.0 s | -21.9 |
| 04 | Gravity | 105 BPM | A | 137.1 s | -17.9 |
| 05 | Sunset Boulevard | 110 BPM | A | 130.9 s | -20.0 |
| 06 | After Hours | 120 BPM | C | 128.0 s | -19.4 |

## Mike Dean (迈克·迪恩) — album/mikedean/

Synth-driven psychedelia and modern hip-hop (Kanye West, Travis Scott, The Weeknd, Beyoncé). Signature: heavy saturation everywhere, enormous wide stereo, long spacey reverbs, a wall of sound with detail.

- Reference artists: Kanye West, Travis Scott, The Weeknd, Beyoncé.

- Output folder: album/mikedean/ — open album/mikedean/index.html to listen.


| Stage | Signature | This implementation |
|---|---|---|
| Drums | Saturated, smeared, huge | HPF 30 Hz · lowshelf +1.5 dB @ 100 Hz · peak +2.0 dB @ 2500 Hz · comp -16 dB 3.5:1 (5/110 ms, k2, +1.5 dB) · sat drive 1.8 mix 0.35 · room reverb 15% · -5 dB |
| Bass | Distorted depth, synth-heavy | HPF 28 Hz · lowshelf +2.5 dB @ 70 Hz · peak +1.0 dB @ 90 Hz · comp -20 dB 4:1 (3/140 ms, k2, +1 dB) · sat drive 1.8 mix 0.3 · -6 dB |
| Harmony/pad | Washed in space, wide | HPF 50 Hz · lowshelf -1.0 dB @ 200 Hz · peak +1.5 dB @ 3500 Hz · comp -22 dB 2.5:1 (15/240 ms, k2, +0.5 dB) · sat drive 1.4 mix 0.2 · long reverb 35% · M/S +0.50 · -11 dB |
| Lead (the 'voice') | Psychedelic, drenched in long verb | HPF 70 Hz · lowshelf +0.5 dB @ 160 Hz · peak +2.0 dB @ 3200 Hz · comp -14 dB 2.5:1 (18/160 ms, k3, +2 dB) · sat drive 1.5 mix 0.25 · long reverb 40% · M/S +0.25 · -3 dB |
| Background | Enormous ambient width | HPF 95 Hz · LPF 10000 Hz · comp -24 dB 2:1 (18/260 ms, k2, +0 dB) · long reverb 45% · M/S +0.70 · -15 dB |
| Master bus | Heavy saturation, huge stereo, spacey loudness | HPF 26 Hz · lowshelf +1.0 dB @ 50 Hz · peak +1.5 dB @ 2500 Hz · peak +2.0 dB @ 13000 Hz · comp -14 dB 2:1 (8/140 ms, k2, +2 dB) · sat drive 1.3 mix 0.2 · M/S +0.20 · target -10 LUFS · limiter rel 80 ms |

| # | Title | Tempo | Key | Duration | est. LUFS |
|---|---|---|---|---|---|
| 01 | Midnight Velvet | 88 BPM | B | 152.7 s | -24.9 |
| 02 | Slow Car | 90 BPM | D | 149.3 s | -20.3 |
| 03 | Neon Rain | 100 BPM | E | 144.0 s | -16.9 |
| 04 | Gravity | 105 BPM | A | 137.1 s | -16.7 |
| 05 | Sunset Boulevard | 110 BPM | A | 130.9 s | -19.2 |
| 06 | After Hours | 120 BPM | C | 128.0 s | -19.7 |

## Spike Stent (斯派克·斯坦特) — album/stent/

Alt/electronic edginess (Björk, Depeche Mode, Muse, Massive Attack, Madonna, No Doubt). Signature: dark overall tone with aggressive presence mids, tense and punchy, big alternative width.

- Reference artists: Björk, Depeche Mode, Muse, Massive Attack, Madonna, No Doubt.

- Output folder: album/stent/ — open album/stent/index.html to listen.


| Stage | Signature | This implementation |
|---|---|---|
| Drums | Aggressive, edgy, punchy | HPF 32 Hz · lowshelf +1.5 dB @ 100 Hz · peak +2.5 dB @ 1800 Hz · peak +2.0 dB @ 6000 Hz · comp -15 dB 4:1 (4/100 ms, k2, +2 dB) · sat drive 1.4 mix 0.2 · room reverb 12% · -5 dB |
| Bass | Dark with midrange bite | HPF 30 Hz · lowshelf +2.0 dB @ 80 Hz · peak +1.0 dB @ 250 Hz · comp -19 dB 4:1 (3/130 ms, k2, +1 dB) · sat drive 1.5 mix 0.22 · -7 dB |
| Harmony/pad | Tense, middy, textured | HPF 55 Hz · lowshelf -2.0 dB @ 250 Hz · peak +2.0 dB @ 3000 Hz · comp -22 dB 3:1 (10/200 ms, k2, +0.5 dB) · med reverb 18% · M/S +0.40 · -12 dB |
| Lead (the 'voice') | Edgy, forward, slightly dark | HPF 80 Hz · lowshelf +0.5 dB @ 200 Hz · peak +2.5 dB @ 2500 Hz · peak +2.0 dB @ 7000 Hz · comp -14 dB 2.5:1 (16/140 ms, k3, +2 dB) · long reverb 25% · M/S +0.15 · -3 dB |
| Background | Big alternative width | HPF 100 Hz · LPF 9000 Hz · comp -25 dB 2:1 (16/240 ms, k2, +0 dB) · long reverb 30% · M/S +0.60 · -15 dB |
| Master bus | Dark, aggressive, controlled loudness | HPF 28 Hz · lowshelf +1.0 dB @ 55 Hz · peak +1.5 dB @ 2000 Hz · peak +1.5 dB @ 9000 Hz · comp -14 dB 2:1 (6/120 ms, k2, +2 dB) · sat drive 1.18 mix 0.12 · M/S +0.15 · target -10 LUFS · limiter rel 80 ms |

| # | Title | Tempo | Key | Duration | est. LUFS |
|---|---|---|---|---|---|
| 01 | Midnight Velvet | 88 BPM | B | 152.7 s | -26.2 |
| 02 | Slow Car | 90 BPM | D | 149.3 s | -21.8 |
| 03 | Neon Rain | 100 BPM | E | 144.0 s | -16.8 |
| 04 | Gravity | 105 BPM | A | 137.1 s | -17.5 |
| 05 | Sunset Boulevard | 110 BPM | A | 130.9 s | -19.1 |
| 06 | After Hours | 120 BPM | C | 128.0 s | -18.7 |

## Stems used (shared by every style)

### 01. Midnight Velvet  (88 BPM / B)

- **Drums:** drum (3480).wav

- **Bass:** XAM Bladerunner Reese.wav

- **Harmony/pad:** EBH_Synth_Loop_16_Bm_126.wav

- **Lead (the 'voice'):** PPC_Synths_80_Yumm_Bmin_GH.wav

- **Background:** ESW Trap Flutes 26 - Gyspy 05 - 160 BPM B Min.wav

- **SFX/transitions:** SRHS_Impact_20.wav

### 02. Slow Car  (90 BPM / D)

- **Drums:** SRHS_110_Full_Drum_Loop_23.wav

- **Bass:** bass (375).wav

- **Harmony/pad:** GS_FS 2_Piano Loop_ 8_70bpm_Dmaj .wav

- **Lead (the 'voice'):** ESW I Had You 01 - Guitar Chords - 90 BPM D Minor.wav

- **Background:** Ghosthack Vocal Demo Kit 5 - STRINGS.wav

- **SFX/transitions:** SRHS_Impact_18.wav

### 03. Neon Rain  (100 BPM / E)

- **Drums:** drum (1898).wav

- **Bass:** bass (98).wav

- **Harmony/pad:** ESWX Kit 5 - Brass Stabs - 100 BPM E Maj.wav

- **Lead (the 'voice'):** ESWX Kit 5 - Dustry Mallets - 100 BPM E Maj.wav

- **Background:** ESW PL Thorny.wav

- **SFX/transitions:** SRHS_Impact_07.wav

### 04. Gravity  (105 BPM / A)

- **Drums:** drum (1168).wav

- **Bass:** bass (106).wav

- **Harmony/pad:** FPV_Try_Kit_Arp_Am_105BPM.wav

- **Lead (the 'voice'):** FPV_Try_Kit_Adlibs_Am_105BPM_Dry.wav

- **Background:** bww3_altoflute_portl_rep1_31-31_A3 - AB.wav

- **SFX/transitions:** XAM Riser 1.wav

### 05. Sunset Boulevard  (110 BPM / A)

- **Drums:** drum (1413).wav

- **Bass:** synth (70).wav

- **Harmony/pad:** FPV_Keep_Balance_Kit_Guitar_Ambience_Fm_105BPM.wav

- **Lead (the 'voice'):** FPV_Online_Kit_Ambience_Bm_105BPM.wav

- **Background:** 110bpm_vl1_meastrills_slow_103-103_A2 - AB.wav

- **SFX/transitions:** SRHS_Impact_13.wav

### 06. After Hours  (120 BPM / C)

- **Drums:** SRHS_Clap_04.wav

- **Bass:** XAM Clean Reese.wav

- **Harmony/pad:** FBHA_C_126_Piano_Loop_10.wav

- **Lead (the 'voice'):** Acoustic Guitar-110 bpm-Cmaj-25.wav

- **Background:** GS_FS 2_Flute Loop_ 7_100bpm_Cm.wav

- **SFX/transitions:** XAM Transition 5.wav


## Notes & honest limitations

- **Identical arrangement across styles** is deliberate: it isolates the mixing differences (balance, EQ, compression, space, width, loudness) from the arrangement differences.

- Instrumental by design: the musickit acapella set contains real famous-song vocals (copyright), so the album is instrumental and a **lead instrument** is mixed front-and-center in place of a vocal.

- Harmonic compatibility is best-effort: stems are selected by matching root key where the library exposes one; some layers may be modal neighbours rather than identical keys.

- Tempo matching uses a pitch-preserving phase-vocoder time-stretch (ratio kept within ±20% of each stem's native BPM) so loops lock to the track tempo.

- LUFS is a K-weighting RMS proxy for monitoring only, not a certified measurement.

- Each 'mixer' is an interpretation of that engineer's documented signature expressed with the same DSP primitives — a homage/study, not a claim of authentic hardware emulation.


*Generated with build_album.py + generate_album_docs.py (numpy/scipy/soundfile, zero external DSP deps).*
