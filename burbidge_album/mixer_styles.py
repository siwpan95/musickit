#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共享「混音师风格」注册表与渲染链（mixer_styles）。

本模块同时服务两条管线：
  1. burbidge_album/build_album.py —— 固定风格专辑（同一组 stems × 10 位混音师）
  2. musickit/remix/main.py        —— 随机风格混音引擎（--mixer-style 可选接入）

只依赖 numpy/scipy（经同目录 dsp.py），供本机 Python 与专辑构建环境共用。
每个风格 dict 的 buses 键：drums/bass/pad/lead/bg（分轨总线）与 master（母带），
reverb 键定义 room/med/long 三组卷积 IR 参数。
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dsp

SR = dsp.SR


def reverb_send(bus, ir, amount):
    wet = dsp.convolve_rev(bus, ir)
    return (bus + wet*amount).astype(np.float32)


# ---------------- style registry ----------------
# Bus spec keys:
#   hpf/lpf: cutoff Hz | shelf: [(type, f0, dB)] | peak: [(f0, dB, Q)]
#   comp: (threshold dB, ratio, attack ms, release ms, knee dB, makeup dB)
#   sat: (drive, mix) | rev: ("room"|"med"|"long", amount) | widen: M/S amount
#   pan: -1..1 | gain: bus level in dB
def bus(hpf=0, lpf=0, shelf=(), peak=(), comp=None, sat=None, rev=None,
        widen=None, pan=None, gain=None):
    p = {"shelf": list(shelf), "peak": list(peak)}
    if hpf: p["hpf"] = hpf
    if lpf: p["lpf"] = lpf
    if comp: p["comp"] = comp
    if sat: p["sat"] = sat
    if rev: p["rev"] = rev
    if widen is not None: p["widen"] = widen
    if pan is not None: p["pan"] = pan
    if gain is not None: p["gain"] = gain
    return p

# master spec: like bus + target_lufs + limiter release
def mast(hpf=0, lpf=0, shelf=(), peak=(), comp=None, widen=None, sat=None,
         target_lufs=-13.0, lim_release=80.0):
    p = bus(hpf=hpf, lpf=lpf, shelf=shelf, peak=peak, comp=comp, widen=widen, sat=sat)
    p["target_lufs"] = target_lufs
    p["lim_release"] = lim_release
    return p

STYLES = [
 dict(
  slug="burbidge", folder="burbidge", name="Craig Burbidge", zh="克雷格·伯比奇",
  color="#d9a441", tagline="warm console · vocal-forward · lush plate",
  about="Late-80s/90s LA R&B, soul, gospel and pop (Barry White, Brian McKnight, Take 6, "
        "Vanessa Williams, David Tao 陶喆, 张惠妹, 王力宏, 五月天). Signature: vocal-forward, "
        "warm SSL/Neve console body, deep punchy bottom, lush plate on lead + gospel-style "
        "backgrounds, smooth opto-style lead compression, glue bus compression, wide polished stereo.",
  refs=["Barry White", "Brian McKnight", "Take 6", "Vanessa Williams", "David Tao", "张惠妹", "王力宏", "五月天"],
  sig=dict(
    drums="Punchy, controlled, centered (SSL drum bus)",
    bass="Deep Barry-White bottom, tight 6:1",
    pad="Warm, slightly recessed harmony bed",
    lead="THE vocal stand-in: front, intimate, lush plate",
    bg="Wide gospel-style backgrounds behind the lead",
    master="Warm glue, polished width, musical dynamics"),
  reverb=dict(room=(0.5, 1), med=(1.6, 0.018, 11), long=(2.2, 0.025, 22)),
  drums=bus(hpf=35, shelf=[("lowshelf",120,1.0)], peak=[(4000,1.5,1.0)],
            comp=(-20,4.0,5,120,3,2.0), sat=(1.2,0.12), rev=("room",0.10), gain=-5),
  bass=bus(hpf=30, shelf=[("lowshelf",90,2.0)], peak=[(80,2.0,1.2)],
           comp=(-24,6.0,3,200,2,1.0), sat=(1.5,0.22), gain=-7),
  pad=bus(hpf=40, shelf=[("lowshelf",250,-1.0)], peak=[(2500,1.0,1.0)],
          comp=(-22,2.5,15,250,3,1.0), rev=("med",0.18), widen=0.3, gain=-11),
  lead=bus(hpf=50, shelf=[("lowshelf",200,1.0)], peak=[(3800,2.0,1.0)],
           comp=(-16,2.0,20,300,4,1.5), rev=("long",0.30), widen=0.15, pan=0.08, gain=-3),
  bg=bus(hpf=80, lpf=9000, comp=(-24,2.0,20,300,3), rev=("long",0.35), widen=0.6, gain=-15),
  master=mast(hpf=30, shelf=[("lowshelf",60,0.5)], peak=[(12000,1.5,1.0)],
              comp=(-18,2.0,10,200,2,1.5), widen=0.10, sat=(1.1,0.08), target_lufs=-13.0),
 ),
 dict(
  slug="ghenea", folder="ghenea", name="Serban Ghenea", zh="塞尔班·吉尼亚",
  color="#7fd4ff", tagline="hyper-clean · bright air · loud but polite",
  about="The most-played mixer in modern pop (Taylor Swift, Ariana Grande, The Weeknd, "
        "Bruno Mars, Dua Lipa). Signature: hyper-clean separation between elements, "
        "punchy-but-polite dynamics, crisp top-end air, loud without sounding crushed.",
  refs=["Taylor Swift", "Ariana Grande", "The Weeknd", "Bruno Mars", "Dua Lipa"],
  sig=dict(
    drums="Punchy but polite, crisp attack",
    bass="Tight, controlled, clean low end",
    pad="Tucked well behind the vocal lane",
    lead="Hyper-clean, bright, sits perfectly on top",
    bg="Wide but out of the way",
    master="Transparent glue, bright air, loud yet un-crushed"),
  reverb=dict(room=(0.4, 31), med=(1.2, 0.010, 41), long=(1.8, 0.015, 51)),
  drums=bus(hpf=30, shelf=[("lowshelf",100,0.5)], peak=[(2500,2.0,1.0),(8000,1.5,1.0)],
            comp=(-16,3.0,4,100,2,1.0), sat=(1.05,0.02), rev=("room",0.06), gain=-5),
  bass=bus(hpf=35, shelf=[("lowshelf",80,1.5)], peak=[(120,1.0,1.0),(200,-1.0,1.0)],
           comp=(-20,4.0,4,150,2,1.0), gain=-8),
  pad=bus(hpf=60, shelf=[("lowshelf",200,-2.0)], peak=[(3000,1.0,1.0)],
          comp=(-24,3.0,10,200,2,0.5), rev=("med",0.12), widen=0.4, gain=-13),
  lead=bus(hpf=80, shelf=[("lowshelf",150,-0.5)], peak=[(3000,2.5,1.0),(8000,2.0,1.0)],
           comp=(-14,2.0,15,120,2,2.0), rev=("med",0.12), widen=0.10, gain=-3),
  bg=bus(hpf=100, lpf=11000, comp=(-26,2.0,15,200,2), rev=("med",0.20), widen=0.5, gain=-16),
  master=mast(hpf=25, shelf=[("lowshelf",50,0.5)], peak=[(2000,0.5,1.0),(12000,2.0,1.0)],
              comp=(-14,1.5,8,100,1,1.5), widen=0.15, sat=(1.03,0.02), target_lufs=-9.0),
 ),
 dict(
  slug="clearmountain", folder="clearmountain", name="Bob Clearmountain", zh="鲍勃·克利尔芒廷",
  color="#d98e5f", tagline="big room · dynamic drums · classic rock",
  about="Classic rock royalty (Bruce Springsteen, The Rolling Stones, INXS, Bryan Adams, "
        "Roxy Music). Signature: big natural room ambience, dynamic punchy drums, the sound "
        "of a band playing in a great room rather than a polished product.",
  refs=["Bruce Springsteen", "The Rolling Stones", "INXS", "Bryan Adams", "Roxy Music"],
  sig=dict(
    drums="Big, dynamic, roomy",
    bass="Round, natural, supportive",
    pad="Open, airy, unhyped",
    lead="Natural, sits in the band rather than on it",
    bg="Ambient width from the room",
    master="Gentle glue, real dynamics, classic rock sheen"),
  reverb=dict(room=(0.9, 61), med=(1.6, 0.020, 71), long=(2.0, 0.030, 81)),
  drums=bus(hpf=30, shelf=[("lowshelf",100,2.0)], peak=[(3000,1.0,1.0)],
            comp=(-18,3.0,8,150,2,1.0), sat=(1.15,0.10), rev=("room",0.35), gain=-4),
  bass=bus(hpf=40, shelf=[("lowshelf",90,1.0)], peak=[(160,1.0,1.0)],
           comp=(-22,3.0,6,180,2,0.5), sat=(1.3,0.15), gain=-8),
  pad=bus(hpf=50, shelf=[("lowshelf",250,-1.0)], comp=(-24,2.0,20,300,2),
          rev=("med",0.15), widen=0.2, gain=-12),
  lead=bus(hpf=70, shelf=[("lowshelf",180,0.5)], peak=[(2500,1.5,1.0)],
           comp=(-16,2.0,25,250,3,1.0), rev=("room",0.20), widen=0.1, gain=-4),
  bg=bus(hpf=90, lpf=10000, comp=(-24,2.0,20,300,2), rev=("med",0.25), widen=0.4, gain=-15),
  master=mast(hpf=28, shelf=[("lowshelf",60,1.0)], peak=[(10000,1.0,1.0)],
              comp=(-16,1.5,15,250,1.5,1.0), widen=0.05, sat=(1.08,0.05), target_lufs=-14.0),
 ),
 dict(
  slug="marroquin", folder="marroquin", name="Manny Marroquin", zh="曼尼·马罗奎因",
  color="#ff6a9c", tagline="deep 808 lows · hard kick · modern loudness",
  about="Modern hip-hop and R&B (Kendrick Lamar, Post Malone, Kanye West, Rihanna, "
        "Alicia Keys). Signature: massive deep lows, hard-hitting kick, clean intimate "
        "vocals, modern loudness that stays musical.",
  refs=["Kendrick Lamar", "Post Malone", "Kanye West", "Rihanna", "Alicia Keys"],
  sig=dict(
    drums="Huge kick, modern punch",
    bass="808-grade depth, bass-forward",
    pad="Thin-walled so the lows stay clear",
    lead="Clean, intimate, slightly wet",
    bg="Deep, wide bed",
    master="Massive lows, controlled loudness"),
  reverb=dict(room=(0.45, 91), med=(1.7, 0.015, 101), long=(2.4, 0.020, 111)),
  drums=bus(hpf=28, shelf=[("lowshelf",90,2.5)], peak=[(5000,2.0,1.0)],
            comp=(-18,4.0,3,90,2,2.0), sat=(1.25,0.15), rev=("room",0.08), gain=-4),
  bass=bus(hpf=25, shelf=[("lowshelf",60,3.0)], peak=[(100,1.5,1.2)],
           comp=(-22,5.0,2,120,2,1.0), sat=(1.6,0.25), gain=-6),
  pad=bus(hpf=50, shelf=[("lowshelf",200,-2.0)], peak=[(2000,0.5,1.0)],
          comp=(-24,3.0,12,220,2,0.5), rev=("med",0.15), widen=0.35, gain=-13),
  lead=bus(hpf=70, shelf=[("lowshelf",160,0.5)], peak=[(3200,2.0,1.0)],
           comp=(-15,2.5,18,180,3,2.0), rev=("long",0.22), widen=0.12, gain=-3),
  bg=bus(hpf=100, lpf=9500, comp=(-26,2.0,18,250,2), rev=("long",0.30), widen=0.55, gain=-16),
  master=mast(hpf=25, shelf=[("lowshelf",45,1.5)], peak=[(15000,1.0,1.0)],
              comp=(-15,2.0,6,150,1.5,2.0), widen=0.12, sat=(1.12,0.10), target_lufs=-10.0),
 ),
 dict(
  slug="pensado", folder="pensado", name="Dave Pensado", zh="戴夫·潘萨多",
  color="#ffc04d", tagline="big lows · crispy highs · exciting",
  about="Hitmaker and educator ('Pensado's Place'); credits include Christina Aguilera, "
        "Kelly Rowland, Beyoncé. Signature: BIG bottom, crispy sparkling highs, a smiley "
        "curve that sounds exciting on any system.",
  refs=["Christina Aguilera", "Kelly Rowland", "Beyoncé", "Justin Timberlake"],
  sig=dict(
    drums="Big and snappy",
    bass="Sub-heavy, rumbling",
    pad="Balanced, sparkly",
    lead="Bright, crispy, exciting",
    bg="Wide and shimmery",
    master="Big lows + crispy highs, exciting loudness"),
  reverb=dict(room=(0.5, 121), med=(1.7, 0.016, 131), long=(2.4, 0.022, 141)),
  drums=bus(hpf=30, shelf=[("lowshelf",110,2.0)], peak=[(6000,2.5,1.0)],
            comp=(-17,3.5,5,110,2,1.5), sat=(1.3,0.15), rev=("room",0.10), gain=-5),
  bass=bus(hpf=28, shelf=[("lowshelf",70,3.0)], peak=[(90,1.5,1.2)],
           comp=(-22,5.0,3,140,2,1.0), sat=(1.5,0.2), gain=-7),
  pad=bus(hpf=55, shelf=[("lowshelf",220,-1.5)], peak=[(2800,1.5,1.0)],
          comp=(-23,2.5,14,240,2,0.5), rev=("med",0.15), widen=0.35, gain=-12),
  lead=bus(hpf=75, shelf=[("lowshelf",170,0.5)], peak=[(3500,2.5,1.0),(8000,2.5,1.0)],
           comp=(-15,2.0,18,150,3,2.0), rev=("long",0.25), widen=0.12, gain=-3),
  bg=bus(hpf=100, lpf=10500, comp=(-25,2.0,18,260,2), rev=("long",0.30), widen=0.55, gain=-15),
  master=mast(hpf=28, shelf=[("lowshelf",55,1.5)], peak=[(3000,1.0,1.0),(14000,2.0,1.0)],
              comp=(-15,1.8,7,130,1.5,2.0), widen=0.15, sat=(1.15,0.10), target_lufs=-10.0),
 ),
 dict(
  slug="blake", folder="blake", name="Tchad Blake", zh="查德·布莱克",
  color="#9db36a", tagline="gritty · squashed · quirky mono width",
  about="The anti-polish mix master — engineer for Tom Waits and Peter Gabriel, mixer for "
        "Arctic Monkeys, The Black Keys, Sheryl Crow. Signature: gritty saturation, squashed "
        "dynamics, quirky narrow/mono-ish width, lo-fi character with attitude.",
  refs=["Tom Waits", "Peter Gabriel", "Arctic Monkeys", "The Black Keys", "Sheryl Crow"],
  sig=dict(
    drums="Squashed, gritty, explosive",
    bass="Furry, driven, midrangey",
    pad="Dark, murky texture",
    lead="Lo-fi, gritty, in-your-face",
    bg="Narrow, dark backdrop",
    master="Narrow-ish mono glue, pleasing grit, no polish"),
  reverb=dict(room=(0.35, 151), med=(1.0, 0.008, 161), long=(1.6, 0.012, 171)),
  drums=bus(hpf=40, shelf=[("lowshelf",90,1.0)], peak=[(2000,2.0,1.0)],
            comp=(-14,5.0,3,80,2,1.0), sat=(2.0,0.5), rev=("room",0.15), widen=-0.15, gain=-5),
  bass=bus(hpf=35, shelf=[("lowshelf",80,2.0)], comp=(-18,5.0,2,100,2,0.5),
           sat=(2.2,0.45), gain=-7),
  pad=bus(hpf=70, lpf=7000, comp=(-22,3.0,10,200,2), sat=(1.6,0.3), widen=-0.1, gain=-11),
  lead=bus(hpf=90, peak=[(1800,2.0,1.0)], comp=(-12,3.0,12,140,3,1.0),
           sat=(2.0,0.4), rev=("room",0.18), widen=-0.1, gain=-3),
  bg=bus(hpf=110, lpf=6500, comp=(-24,2.5,15,220,2), sat=(1.5,0.25), widen=-0.05, gain=-15),
  master=mast(hpf=35, lpf=16000, shelf=[("lowshelf",70,1.0)], peak=[(2500,1.5,1.0)],
              comp=(-13,2.5,5,90,2,1.5), widen=-0.15, sat=(1.5,0.25), target_lufs=-12.0),
 ),
 dict(
  slug="lordalge", folder="lordalge", name="Chris Lord-Alge", zh="克里斯·洛德-阿尔吉",
  color="#5f8dff", tagline="loud · punchy · radio bright",
  about="Radio rock and pop (Green Day, Muse, My Chemical Romance, Avril Lavigne, "
        "Bon Jovi). Signature: loud, punchy, bright — every element maximized for radio "
        "impact without turning to mush.",
  refs=["Green Day", "Muse", "My Chemical Romance", "Avril Lavigne", "Bon Jovi"],
  sig=dict(
    drums="Huge, hard-hitting",
    bass="Firm, defined low end",
    pad="Supportive, slightly compressed",
    lead="Loud, bright, radio-forward",
    bg="Wide, glossy",
    master="Loud, punchy, bright — radio ready"),
  reverb=dict(room=(0.6, 181), med=(1.5, 0.014, 191), long=(2.0, 0.020, 201)),
  drums=bus(hpf=30, shelf=[("lowshelf",110,2.5)], peak=[(3000,2.0,1.0),(8000,1.5,1.0)],
            comp=(-16,4.0,4,90,2,2.5), sat=(1.3,0.18), rev=("room",0.20), gain=-4),
  bass=bus(hpf=32, shelf=[("lowshelf",85,2.0)], peak=[(150,1.0,1.0)],
           comp=(-20,4.0,4,130,2,1.0), sat=(1.4,0.18), gain=-7),
  pad=bus(hpf=55, shelf=[("lowshelf",240,-1.5)], peak=[(2600,1.0,1.0)],
          comp=(-23,2.5,12,220,2,0.5), rev=("med",0.15), widen=0.3, gain=-12),
  lead=bus(hpf=75, shelf=[("lowshelf",170,1.0)], peak=[(3000,2.5,1.0)],
           comp=(-14,2.5,15,130,3,2.0), rev=("med",0.18), widen=0.1, gain=-3),
  bg=bus(hpf=100, lpf=10000, comp=(-25,2.0,15,240,2), rev=("med",0.25), widen=0.5, gain=-15),
  master=mast(hpf=28, shelf=[("lowshelf",55,1.5)], peak=[(2500,1.0,1.0),(12000,1.5,1.0)],
              comp=(-14,2.0,6,120,1.5,2.5), widen=0.12, sat=(1.15,0.12), target_lufs=-9.0),
 ),
 dict(
  slug="schmitt", folder="schmitt", name="Al Schmitt", zh="阿尔·施密特",
  color="#e0d2b0", tagline="natural · transparent · dynamic",
  about="23-time Grammy winner, the conscience of natural sound (Frank Sinatra, Steely Dan, "
        "Diana Krall, Henry Mancini, Toto). Signature: the microphone does the work and the "
        "mixer stays out of the way — pure tone, real dynamics, no hype.",
  refs=["Frank Sinatra", "Steely Dan", "Diana Krall", "Henry Mancini", "Toto"],
  sig=dict(
    drums="Natural, open, unhyped",
    bass="Round and acoustic-sounding",
    pad="Airy, transparent",
    lead="Pure tone, no hype",
    bg="Gentle, natural depth",
    master="Transparent, dynamic, audiophile headroom"),
  reverb=dict(room=(0.7, 211), med=(1.3, 0.015, 221), long=(1.8, 0.020, 231)),
  drums=bus(hpf=30, shelf=[("lowshelf",90,0.5)], comp=(-20,2.0,10,200,2,0.5),
            rev=("room",0.25), gain=-6),
  bass=bus(hpf=35, shelf=[("lowshelf",80,1.0)], comp=(-22,2.5,8,220,2,0.0), gain=-8),
  pad=bus(hpf=45, shelf=[("lowshelf",220,-1.0)], comp=(-26,1.5,25,400,2,0.0),
          rev=("med",0.10), widen=0.15, gain=-13),
  lead=bus(hpf=60, shelf=[("lowshelf",180,0.5)], peak=[(2800,1.0,1.0)],
           comp=(-18,1.5,30,350,2,0.5), rev=("room",0.15), widen=0.05, gain=-4),
  bg=bus(hpf=80, lpf=11000, comp=(-26,1.5,25,400,2), rev=("med",0.15), widen=0.25, gain=-16),
  master=mast(hpf=30, shelf=[("lowshelf",60,0.5)], peak=[(10000,0.5,1.0)],
              comp=(-18,1.5,20,350,1.5,0.5), widen=0.05, target_lufs=-16.0),
 ),
 dict(
  slug="mikedean", folder="mikedean", name="Mike Dean", zh="迈克·迪恩",
  color="#b06aff", tagline="saturated · spacey · huge stereo",
  about="Synth-driven psychedelia and modern hip-hop (Kanye West, Travis Scott, The Weeknd, "
        "Beyoncé). Signature: heavy saturation everywhere, enormous wide stereo, long spacey "
        "reverbs, a wall of sound with detail.",
  refs=["Kanye West", "Travis Scott", "The Weeknd", "Beyoncé"],
  sig=dict(
    drums="Saturated, smeared, huge",
    bass="Distorted depth, synth-heavy",
    pad="Washed in space, wide",
    lead="Psychedelic, drenched in long verb",
    bg="Enormous ambient width",
    master="Heavy saturation, huge stereo, spacey loudness"),
  reverb=dict(room=(0.5, 241), med=(2.0, 0.020, 251), long=(3.2, 0.030, 261)),
  drums=bus(hpf=30, shelf=[("lowshelf",100,1.5)], peak=[(2500,2.0,1.0)],
            comp=(-16,3.5,5,110,2,1.5), sat=(1.8,0.35), rev=("room",0.15), gain=-5),
  bass=bus(hpf=28, shelf=[("lowshelf",70,2.5)], peak=[(90,1.0,1.2)],
           comp=(-20,4.0,3,140,2,1.0), sat=(1.8,0.3), gain=-6),
  pad=bus(hpf=50, shelf=[("lowshelf",200,-1.0)], peak=[(3500,1.5,1.0)],
          comp=(-22,2.5,15,240,2,0.5), rev=("long",0.35), widen=0.5, sat=(1.4,0.2), gain=-11),
  lead=bus(hpf=70, shelf=[("lowshelf",160,0.5)], peak=[(3200,2.0,1.0)],
           comp=(-14,2.5,18,160,3,2.0), rev=("long",0.40), widen=0.25, sat=(1.5,0.25), gain=-3),
  bg=bus(hpf=95, lpf=10000, comp=(-24,2.0,18,260,2), rev=("long",0.45), widen=0.7, gain=-15),
  master=mast(hpf=26, shelf=[("lowshelf",50,1.0)], peak=[(2500,1.5,1.0),(13000,2.0,1.0)],
              comp=(-14,2.0,8,140,2,2.0), widen=0.2, sat=(1.3,0.2), target_lufs=-10.0),
 ),
 dict(
  slug="stent", folder="stent", name="Spike Stent", zh="斯派克·斯坦特",
  color="#4dd9c0", tagline="dark · edgy · tense mids",
  about="Alt/electronic edginess (Björk, Depeche Mode, Muse, Massive Attack, Madonna, "
        "No Doubt). Signature: dark overall tone with aggressive presence mids, tense and "
        "punchy, big alternative width.",
  refs=["Björk", "Depeche Mode", "Muse", "Massive Attack", "Madonna", "No Doubt"],
  sig=dict(
    drums="Aggressive, edgy, punchy",
    bass="Dark with midrange bite",
    pad="Tense, middy, textured",
    lead="Edgy, forward, slightly dark",
    bg="Big alternative width",
    master="Dark, aggressive, controlled loudness"),
  reverb=dict(room=(0.45, 271), med=(1.5, 0.012, 281), long=(2.1, 0.018, 291)),
  drums=bus(hpf=32, shelf=[("lowshelf",100,1.5)], peak=[(1800,2.5,1.0),(6000,2.0,1.0)],
            comp=(-15,4.0,4,100,2,2.0), sat=(1.4,0.2), rev=("room",0.12), gain=-5),
  bass=bus(hpf=30, shelf=[("lowshelf",80,2.0)], peak=[(250,1.0,1.0)],
           comp=(-19,4.0,3,130,2,1.0), sat=(1.5,0.22), gain=-7),
  pad=bus(hpf=55, shelf=[("lowshelf",250,-2.0)], peak=[(3000,2.0,1.0)],
          comp=(-22,3.0,10,200,2,0.5), rev=("med",0.18), widen=0.4, gain=-12),
  lead=bus(hpf=80, shelf=[("lowshelf",200,0.5)], peak=[(2500,2.5,1.0),(7000,2.0,1.0)],
           comp=(-14,2.5,16,140,3,2.0), rev=("long",0.25), widen=0.15, gain=-3),
  bg=bus(hpf=100, lpf=9000, comp=(-25,2.0,16,240,2), rev=("long",0.30), widen=0.6, gain=-15),
  master=mast(hpf=28, shelf=[("lowshelf",55,1.0)], peak=[(2000,1.5,1.0),(9000,1.5,1.0)],
              comp=(-14,2.0,6,120,1.5,2.0), widen=0.15, sat=(1.18,0.12), target_lufs=-10.0),
 ),

 dict(
  slug="wallace", folder="wallace", name="Andy Wallace", zh="安迪·华莱士",
  color="#ff6a3d", tagline="massive drums · dense but clear · arena loud",
  about="Rock and metal giant (Nirvana Nevermind, Rage Against The Machine, Linkin Park, "
        "Foo Fighters). Signature: massive punchy drums in a big room, dense layered mixes "
        "that stay clear, aggressive yet musical loudness.",
  refs=["Nirvana", "Rage Against The Machine", "Linkin Park", "Foo Fighters", "System of a Down"],
  sig=dict(
    drums="Massive, roomy, hard-hitting",
    bass="Firm foundation under the guitars",
    pad="Dense but carved out",
    lead="Loud, aggressive, always intelligible",
    bg="Thick layers behind the wall",
    master="Dense, clear, arena loudness"),
  reverb=dict(room=(0.8, 301), med=(1.5, 0.012, 311), long=(2.0, 0.018, 321)),
  drums=bus(hpf=28, shelf=[("lowshelf",90,2.5)], peak=[(3000,1.5,1.0),(7000,2.0,1.0)],
            comp=(-14,4.0,3,90,2,2.5), sat=(1.3,0.18), rev=("room",0.30), gain=-4),
  bass=bus(hpf=30, shelf=[("lowshelf",85,2.0)], peak=[(160,1.0,1.0)],
           comp=(-18,4.0,3,110,2,1.5), sat=(1.4,0.2), gain=-7),
  pad=bus(hpf=50, shelf=[("lowshelf",240,-1.5)], peak=[(2600,1.0,1.0)],
          comp=(-22,3.0,10,200,2,0.5), rev=("med",0.15), widen=0.25, gain=-12),
  lead=bus(hpf=75, shelf=[("lowshelf",170,1.0)], peak=[(2800,2.0,1.0)],
           comp=(-13,2.5,15,120,3,2.5), rev=("med",0.15), widen=0.08, gain=-3),
  bg=bus(hpf=95, lpf=9500, comp=(-24,2.0,15,240,2), rev=("med",0.22), widen=0.45, gain=-15),
  master=mast(hpf=28, shelf=[("lowshelf",55,1.5)], peak=[(2500,1.0,1.0),(11000,1.5,1.0)],
              comp=(-13,2.0,5,110,1.5,3.0), widen=0.10, sat=(1.18,0.12), target_lufs=-9.0),
 ),
 dict(
  slug="maserati", folder="maserati", name="Tony Maserati", zh="托尼·马塞拉蒂",
  color="#f5c518", tagline="glossy · huge vocals · radio smooth",
  about="Pop and R&B polish (Beyoncé, Alicia Keys, Mariah Carey, Usher, Jason Mraz). "
        "Signature: glossy radio-ready sheen, huge smooth vocals, wide polished stereo, "
        "effortless commercial balance.",
  refs=["Beyoncé", "Alicia Keys", "Mariah Carey", "Usher", "Jason Mraz"],
  sig=dict(
    drums="Tight, glossy, radio punch",
    bass="Smooth, solid, supportive",
    pad="Silky bed under the vocal",
    lead="HUGE vocal, front and glossy",
    bg="Wide sparkling dressing",
    master="Glossy, wide, radio smooth"),
  reverb=dict(room=(0.4, 331), med=(1.6, 0.014, 341), long=(2.2, 0.020, 351)),
  drums=bus(hpf=30, shelf=[("lowshelf",100,1.5)], peak=[(4000,2.0,1.0)],
            comp=(-16,3.5,5,110,2,2.0), sat=(1.2,0.1), rev=("room",0.08), gain=-5),
  bass=bus(hpf=32, shelf=[("lowshelf",80,2.0)], peak=[(100,1.0,1.0)],
           comp=(-21,4.0,4,150,2,1.0), sat=(1.4,0.18), gain=-7),
  pad=bus(hpf=55, shelf=[("lowshelf",220,-1.5)], peak=[(3000,1.5,1.0)],
          comp=(-23,2.5,12,220,2,0.5), rev=("med",0.16), widen=0.35, gain=-12),
  lead=bus(hpf=70, shelf=[("lowshelf",160,0.5)], peak=[(3200,2.5,1.0),(9000,1.5,1.0)],
           comp=(-14,2.5,18,150,3,2.5), rev=("long",0.25), widen=0.12, pan=0.05, gain=-3),
  bg=bus(hpf=95, lpf=10000, comp=(-25,2.0,16,240,2), rev=("long",0.28), widen=0.5, gain=-15),
  master=mast(hpf=26, shelf=[("lowshelf",55,1.0)], peak=[(2500,1.0,1.0),(12000,2.0,1.0)],
              comp=(-14,2.0,6,120,1.5,2.5), widen=0.12, sat=(1.1,0.08), target_lufs=-10.0),
 ),
 dict(
  slug="joshua", folder="joshua", name="Jaycen Joshua", zh="杰森·约书亚",
  color="#00e5a0", tagline="huge clean lows · wide 808 · bright loud",
  about="Modern hip-hop and R&B (Rihanna, Beyoncé, Busta Rhymes, Justin Timberlake). "
        "Signature: enormous but clean low end, wide stereo 808s, bright top, modern "
        "loudness that never turns to mush.",
  refs=["Rihanna", "Beyoncé", "Busta Rhymes", "Justin Timberlake"],
  sig=dict(
    drums="Hard-hitting, tight, modern",
    bass="Enormous clean 808 depth",
    pad="Carved to leave the lows open",
    lead="Bright, up-front, expensive",
    bg="Deep wide bed",
    master="Huge lows, bright, modern loud"),
  reverb=dict(room=(0.35, 361), med=(1.4, 0.010, 371), long=(2.0, 0.016, 381)),
  drums=bus(hpf=26, shelf=[("lowshelf",85,3.0)], peak=[(5000,2.5,1.0)],
            comp=(-16,4.0,3,85,2,2.5), sat=(1.25,0.15), rev=("room",0.06), gain=-4),
  bass=bus(hpf=22, shelf=[("lowshelf",55,4.0)], peak=[(90,2.0,1.2)],
           comp=(-20,5.0,2,100,2,1.5), sat=(1.5,0.25), gain=-5),
  pad=bus(hpf=50, shelf=[("lowshelf",200,-2.5)], peak=[(2200,1.0,1.0)],
          comp=(-24,3.0,10,200,2,0.5), rev=("med",0.14), widen=0.4, gain=-13),
  lead=bus(hpf=75, shelf=[("lowshelf",150,-0.5)], peak=[(3000,2.5,1.0),(9000,2.0,1.0)],
           comp=(-13,2.5,14,110,3,2.5), rev=("med",0.15), widen=0.12, gain=-3),
  bg=bus(hpf=95, lpf=9500, comp=(-26,2.0,14,220,2), rev=("long",0.26), widen=0.55, gain=-16),
  master=mast(hpf=22, shelf=[("lowshelf",40,2.0)], peak=[(2500,0.5,1.0),(14000,2.5,1.0)],
              comp=(-13,2.0,5,100,1.5,3.0), widen=0.14, sat=(1.12,0.10), target_lufs=-9.0),
 ),
 dict(
  slug="ali", folder="ali", name="MixedByAli", zh="阿里",
  color="#8fa3c7", tagline="dark · deep · atmospheric soul",
  about="TDE in-house engineer (Kendrick Lamar, SZA, Schoolboy Q, Baby Keem). Signature: "
        "dark deep atmospheres, organic human feel, huge but controlled low end, mixes that "
        "breathe rather than blast.",
  refs=["Kendrick Lamar", "SZA", "Schoolboy Q", "Baby Keem", "Mac Miller"],
  sig=dict(
    drums="Deep, organic, in the pocket",
    bass="Dark, huge, controlled",
    pad="Atmospheric smoke",
    lead="Human, close, honest",
    bg="Deep ambient shadows",
    master="Dark, deep, breathing dynamics"),
  reverb=dict(room=(0.5, 391), med=(1.7, 0.016, 401), long=(2.6, 0.024, 411)),
  drums=bus(hpf=30, shelf=[("lowshelf",100,1.0)], peak=[(2500,1.5,1.0)],
            comp=(-16,3.0,6,110,2,1.5), sat=(1.3,0.2), rev=("room",0.12), gain=-5),
  bass=bus(hpf=28, shelf=[("lowshelf",70,2.5)], peak=[(100,1.0,1.2)],
           comp=(-20,4.0,4,130,2,1.0), sat=(1.5,0.25), gain=-6),
  pad=bus(hpf=55, shelf=[("lowshelf",240,-1.5)], peak=[(2000,0.5,1.0)],
          comp=(-23,2.5,14,230,2), rev=("long",0.22), widen=0.45, sat=(1.2,0.15), gain=-12),
  lead=bus(hpf=80, shelf=[("lowshelf",180,0.5)], peak=[(2600,2.0,1.0)],
           comp=(-14,2.0,18,160,3,1.5), rev=("long",0.30), widen=0.10, gain=-3),
  bg=bus(hpf=90, lpf=8000, comp=(-25,2.0,18,250,2), rev=("long",0.35), widen=0.5, gain=-16),
  master=mast(hpf=30, shelf=[("lowshelf",60,1.5)], peak=[(1800,1.0,1.0),(8000,1.0,1.0)],
              comp=(-15,2.0,8,150,2,2.0), widen=0.12, sat=(1.2,0.15), target_lufs=-11.0),
 ),
 dict(
  slug="elmhirst", folder="elmhirst", name="Tom Elmhirst", zh="汤姆·埃尔姆赫斯特",
  color="#e85d75", tagline="pristine · huge clean vocals · deep control",
  about="Modern pop and soul mastery (Adele, David Bowie Blackstar, Amy Winehouse, Lorde, "
        "Dua Lipa). Signature: pristine clarity, enormous clean vocals, deep controlled low "
        "end, mixes that sound effortless and expensive.",
  refs=["Adele", "David Bowie", "Amy Winehouse", "Lorde", "Dua Lipa"],
  sig=dict(
    drums="Tight, clean, tasteful",
    bass="Deep, controlled, clean",
    pad="Polished harmonic support",
    lead="Enormous clean vocal, intimate",
    bg="Wide, elegant, unobtrusive",
    master="Pristine, deep, effortless polish"),
  reverb=dict(room=(0.4, 421), med=(1.5, 0.012, 431), long=(2.1, 0.018, 441)),
  drums=bus(hpf=28, shelf=[("lowshelf",95,2.0)], peak=[(3500,2.0,1.0)],
            comp=(-15,3.5,4,95,2,2.0), sat=(1.15,0.08), rev=("room",0.07), gain=-5),
  bass=bus(hpf=30, shelf=[("lowshelf",75,2.5)], peak=[(110,1.5,1.0)],
           comp=(-20,4.0,3,130,2,1.0), sat=(1.3,0.15), gain=-7),
  pad=bus(hpf=55, shelf=[("lowshelf",220,-2.0)], peak=[(2800,1.0,1.0)],
          comp=(-24,3.0,12,210,2,0.5), rev=("med",0.15), widen=0.35, gain=-13),
  lead=bus(hpf=70, shelf=[("lowshelf",150,0.5)], peak=[(3000,2.5,1.0),(8500,1.5,1.0)],
           comp=(-13,2.0,20,140,3,2.5), rev=("long",0.22), widen=0.08, pan=0.04, gain=-3),
  bg=bus(hpf=95, lpf=10500, comp=(-25,2.0,16,230,2), rev=("long",0.26), widen=0.5, gain=-16),
  master=mast(hpf=26, shelf=[("lowshelf",50,1.0)], peak=[(2000,0.5,1.0),(12000,1.5,1.0)],
              comp=(-14,1.8,7,110,1.5,2.5), widen=0.12, sat=(1.08,0.06), target_lufs=-10.0),
 ),
 dict(
  slug="scheps", folder="scheps", name="Andrew Scheps", zh="安德鲁·谢普斯",
  color="#ff4d4d", tagline="punchy · natural · loud but breathing",
  about="Rock and beyond (Red Hot Chili Peppers, Green Day, Metallica, Adele 21, "
        "Biffy Clyro). Signature: punchy natural drums, forward guitars, loud mixes that "
        "keep dynamics and never sound squashed.",
  refs=["Red Hot Chili Peppers", "Green Day", "Metallica", "Adele", "Biffy Clyro"],
  sig=dict(
    drums="Punchy, natural, present",
    bass="Supportive, defined",
    pad="Open and unhyped",
    lead="Forward, energetic, clear",
    bg="Natural depth",
    master="Loud but breathing, honest punch"),
  reverb=dict(room=(0.6, 451), med=(1.4, 0.012, 461), long=(1.9, 0.018, 471)),
  drums=bus(hpf=30, shelf=[("lowshelf",95,2.0)], peak=[(2800,1.5,1.0)],
            comp=(-16,3.0,6,120,2,1.5), sat=(1.2,0.12), rev=("room",0.15), gain=-5),
  bass=bus(hpf=35, shelf=[("lowshelf",85,1.5)], peak=[(140,1.0,1.0)],
           comp=(-21,3.5,5,160,2,0.5), sat=(1.3,0.15), gain=-8),
  pad=bus(hpf=50, shelf=[("lowshelf",240,-1.0)], peak=[(2500,0.5,1.0)],
          comp=(-24,2.5,14,240,2,0.5), rev=("med",0.12), widen=0.25, gain=-12),
  lead=bus(hpf=70, shelf=[("lowshelf",170,1.0)], peak=[(3000,2.0,1.0)],
           comp=(-14,2.5,18,160,3,2.0), rev=("med",0.12), widen=0.08, gain=-3),
  bg=bus(hpf=90, lpf=10000, comp=(-24,2.0,18,260,2), rev=("med",0.20), widen=0.4, gain=-15),
  master=mast(hpf=28, shelf=[("lowshelf",55,1.0)], peak=[(2500,1.0,1.0),(10000,1.0,1.0)],
              comp=(-15,1.8,8,130,1.5,2.0), widen=0.08, sat=(1.1,0.08), target_lufs=-11.0),
 ),
 dict(
  slug="moulder", folder="moulder", name="Alan Moulder", zh="艾伦·莫尔德",
  color="#7c4dff", tagline="wall of sound · dense reverb · layered",
  about="Shoegaze and alternative legend (My Bloody Valentine, Smashing Pumpkins, "
        "Nine Inch Nails, The Killers, Arctic Monkeys). Signature: immense walls of layered "
        "guitars, dense lush reverb, huge stereo wash with detail.",
  refs=["My Bloody Valentine", "Smashing Pumpkins", "Nine Inch Nails", "The Killers", "Arctic Monkeys"],
  sig=dict(
    drums="Big, buried in the wash yet punchy",
    bass="Thick, rumbling under the wall",
    pad="Drenched in long space",
    lead="Soaring through the haze",
    bg="Infinite reverb clouds",
    master="Wall of sound, huge and dense"),
  reverb=dict(room=(0.7, 481), med=(2.0, 0.020, 491), long=(3.4, 0.030, 501)),
  drums=bus(hpf=30, shelf=[("lowshelf",100,1.5)], peak=[(2500,2.0,1.0)],
            comp=(-15,3.5,5,100,2,2.0), sat=(1.4,0.2), rev=("room",0.25), gain=-4),
  bass=bus(hpf=32, shelf=[("lowshelf",80,2.0)], peak=[(200,1.0,1.0)],
           comp=(-20,4.0,4,140,2,1.0), sat=(1.4,0.2), gain=-7),
  pad=bus(hpf=50, shelf=[("lowshelf",220,-1.0)], peak=[(3200,1.5,1.0)],
          comp=(-22,2.5,15,240,2), rev=("long",0.40), widen=0.6, sat=(1.3,0.2), gain=-10),
  lead=bus(hpf=75, shelf=[("lowshelf",160,0.5)], peak=[(2800,2.0,1.0)],
           comp=(-14,2.5,18,150,3,2.0), rev=("long",0.45), widen=0.2, sat=(1.4,0.25), gain=-3),
  bg=bus(hpf=90, lpf=9000, comp=(-24,2.0,18,260,2), rev=("long",0.50), widen=0.7, gain=-14),
  master=mast(hpf=28, shelf=[("lowshelf",55,1.0)], peak=[(2000,1.5,1.0),(9000,1.5,1.0)],
              comp=(-14,2.0,7,130,2,2.0), widen=0.2, sat=(1.25,0.15), target_lufs=-10.0),
 ),

 dict(
  slug="guzauski", folder="guzauski", name="Mick Guzauski", zh="米克·古佐斯基",
  color="#67c6dd", tagline="clean · musical · effortless polish",
  about="Polished R&B, disco and pop (Daft Punk Random Access Memories, Pharrell, "
        "Jamiroquai, Michael Jackson mixes). Signature: clean balanced sound, musical "
        "EQ choices, effortless polish where nothing fights for attention.",
  refs=["Daft Punk", "Pharrell Williams", "Jamiroquai", "Michael Jackson"],
  sig=dict(
    drums="Tight, clean, danceable",
    bass="Round, musical, groovy",
    pad="Balanced harmonic sheen",
    lead="Clear, smooth, musical",
    bg="Elegant supporting depth",
    master="Clean, balanced, effortless"),
  reverb=dict(room=(0.45, 511), med=(1.5, 0.014, 521), long=(2.0, 0.020, 531)),
  drums=bus(hpf=32, shelf=[("lowshelf",100,1.5)], peak=[(4000,1.5,1.0)],
            comp=(-17,3.0,6,120,2,1.5), sat=(1.15,0.08), rev=("room",0.10), gain=-5),
  bass=bus(hpf=33, shelf=[("lowshelf",85,2.0)], peak=[(110,1.0,1.0)],
           comp=(-22,3.5,5,170,2,1.0), sat=(1.3,0.15), gain=-7),
  pad=bus(hpf=50, shelf=[("lowshelf",230,-1.0)], peak=[(2600,1.0,1.0)],
          comp=(-23,2.5,15,240,2,0.5), rev=("med",0.14), widen=0.3, gain=-12),
  lead=bus(hpf=70, shelf=[("lowshelf",170,0.5)], peak=[(3200,2.0,1.0)],
           comp=(-15,2.0,20,180,3,2.0), rev=("long",0.20), widen=0.1, gain=-3),
  bg=bus(hpf=90, lpf=10000, comp=(-25,2.0,18,250,2), rev=("long",0.24), widen=0.45, gain=-15),
  master=mast(hpf=28, shelf=[("lowshelf",55,0.5)], peak=[(2500,0.5,1.0),(11000,1.0,1.0)],
              comp=(-16,1.8,10,160,1.5,1.5), widen=0.10, sat=(1.08,0.06), target_lufs=-12.0),
 ),
 dict(
  slug="albini", folder="albini", name="Steve Albini", zh="史蒂夫·阿尔比尼",
  color="#b8b8b8", tagline="raw · room-honest · zero hype",
  about="The anti-production conscience (Nirvana In Utero, Pixies Surfer Rosa, Shellac, "
        "PJ Harvey). Signature: the band in the room as it actually sounds — natural "
        "dynamics, honest midrange, roomy drums, zero hype.",
  refs=["Nirvana", "Pixies", "Shellac", "PJ Harvey", "The Breeders"],
  sig=dict(
    drums="Room-honest, dynamic, present",
    bass="Growly, natural, unpolished",
    pad="Sparse, unadorned",
    lead="Direct, human, no hype",
    bg="Natural ambience only",
    master="Transparent, dynamic, raw truth"),
  reverb=dict(room=(1.0, 541), med=(1.3, 0.015, 551), long=(1.8, 0.020, 561)),
  drums=bus(hpf=30, shelf=[("lowshelf",90,1.0)], peak=[(2000,1.0,1.0)],
            comp=(-18,2.5,8,160,2,0.5), sat=(1.15,0.15), rev=("room",0.35), gain=-5),
  bass=bus(hpf=40, shelf=[("lowshelf",80,1.0)], peak=[(300,1.0,1.0)],
           comp=(-22,2.5,6,200,2,0.0), sat=(1.3,0.2), gain=-7),
  pad=bus(hpf=60, shelf=[("lowshelf",250,-1.0)], comp=(-26,1.5,25,380,2,0.0),
          rev=("room",0.15), widen=0.15, gain=-12),
  lead=bus(hpf=65, shelf=[("lowshelf",180,0.5)], peak=[(2500,1.5,1.0)],
           comp=(-16,2.0,25,280,3,0.5), rev=("room",0.25), widen=0.05, gain=-4),
  bg=bus(hpf=85, lpf=11000, comp=(-26,1.5,25,380,2), rev=("room",0.20), widen=0.3, gain=-15),
  master=mast(hpf=30, shelf=[("lowshelf",60,0.5)], peak=[(3000,1.0,1.0)],
              comp=(-18,1.5,18,320,1.5,0.5), widen=0.05, sat=(1.1,0.08), target_lufs=-15.0),
 ),
 dict(
  slug="everett", folder="everett", name="Shawn Everett", zh="肖恩·埃弗里特",
  color="#ff7ab8", tagline="colorful · quirky · wide experiments",
  about="Experimental pop colorist (Alabama Shakes Sound & Color, Kacey Musgraves Golden "
        "Hour, The War on Drugs, Brittany Howard). Signature: colorful creative textures, "
        "quirky panning and distortion, wide adventurous stereo.",
  refs=["Alabama Shakes", "Kacey Musgraves", "The War on Drugs", "Brittany Howard"],
  sig=dict(
    drums="Characterful, colored, alive",
    bass="Round with creative character",
    pad="Playful, colored, wide",
    lead="Quirky, bright, adventurous",
    bg="Wide psychedelic dressing",
    master="Colorful, wide, experimental gloss"),
  reverb=dict(room=(0.5, 571), med=(1.6, 0.014, 581), long=(2.4, 0.022, 591)),
  drums=bus(hpf=32, shelf=[("lowshelf",100,1.5)], peak=[(3500,2.0,1.0),(8000,1.5,1.0)],
            comp=(-16,3.0,5,110,2,1.5), sat=(1.35,0.25), rev=("room",0.20), gain=-5),
  bass=bus(hpf=35, shelf=[("lowshelf",85,1.5)], peak=[(150,1.0,1.0)],
           comp=(-21,3.5,5,160,2,0.5), sat=(1.4,0.2), gain=-7),
  pad=bus(hpf=55, shelf=[("lowshelf",230,-1.0)], peak=[(3000,1.5,1.0)],
          comp=(-23,2.5,14,230,2,0.5), rev=("long",0.25), widen=0.55, sat=(1.25,0.15), gain=-12),
  lead=bus(hpf=75, shelf=[("lowshelf",170,0.5)], peak=[(3000,2.5,1.0)],
           comp=(-14,2.0,16,150,3,2.0), rev=("long",0.28), widen=0.18, pan=0.1, gain=-3),
  bg=bus(hpf=95, lpf=10500, comp=(-25,2.0,16,240,2), rev=("long",0.30), widen=0.65, gain=-15),
  master=mast(hpf=28, shelf=[("lowshelf",55,1.0)], peak=[(2500,1.5,1.0),(11000,2.0,1.0)],
              comp=(-14,1.8,7,130,1.5,2.0), widen=0.18, sat=(1.2,0.12), target_lufs=-11.0),
 ),
 dict(
  slug="elevado", folder="elevado", name="Russell Elevado", zh="拉塞尔·埃莱瓦多",
  color="#c9804d", tagline="warm analog · tape soul · live feel",
  about="Analog soul revivalist (D'Angelo Voodoo, Erykah Badu Mama's Gun, Common Like "
        "Water for Chocolate). Signature: warm tape saturation, raw live-band feel, deep "
        "organic bass, mixes that breathe like a room of musicians.",
  refs=["D'Angelo", "Erykah Badu", "Common", "The Roots", "Alicia Keys"],
  sig=dict(
    drums="Loose, live, breathing",
    bass="Deep, warm, organic",
    pad="Analog haze, warm",
    lead="Raw, soulful, close",
    bg="Tape-warm ambience",
    master="Warm analog glue, live dynamics"),
  reverb=dict(room=(0.6, 601), med=(1.5, 0.016, 611), long=(2.0, 0.024, 621)),
  drums=bus(hpf=28, shelf=[("lowshelf",90,1.5)], peak=[(2200,1.0,1.0)],
            comp=(-18,2.5,7,150,2,1.0), sat=(1.5,0.3), rev=("room",0.20), gain=-5),
  bass=bus(hpf=30, shelf=[("lowshelf",75,2.5)], peak=[(90,1.0,1.2)],
           comp=(-21,3.5,4,150,2,0.5), sat=(1.6,0.3), gain=-6),
  pad=bus(hpf=50, shelf=[("lowshelf",240,-1.0)], peak=[(2400,0.5,1.0)],
          comp=(-24,2.0,18,260,2,0.5), rev=("long",0.20), widen=0.25, sat=(1.2,0.2), gain=-12),
  lead=bus(hpf=65, shelf=[("lowshelf",180,1.0)], peak=[(2800,1.5,1.0)],
           comp=(-15,2.0,22,200,3,1.5), rev=("long",0.22), widen=0.08, gain=-3),
  bg=bus(hpf=85, lpf=9500, comp=(-25,2.0,20,280,2), rev=("long",0.25), widen=0.4, gain=-15),
  master=mast(hpf=30, shelf=[("lowshelf",55,1.5)], peak=[(2500,0.5,1.0),(10000,1.0,1.0)],
              comp=(-17,1.8,12,200,1.5,1.5), widen=0.08, sat=(1.3,0.15), target_lufs=-13.0),
 ),
 dict(
  slug="shebib", folder="shebib", name="Noah '40' Shebib", zh="诺阿·40·谢比布",
  color="#4d6b7c", tagline="dark · sparse · underwater mood",
  about="Drake's sonic architect (OVO). Signature: dark sparse arrangements, underwater "
        "low end, moody minimalism, space and silence as instruments.",
  refs=["Drake", "PARTYNEXTDOOR", "The Weeknd", "OVO Sound"],
  sig=dict(
    drums="Sparse, dark, muffled punch",
    bass="Underwater, filtered, deep",
    pad="Murky atmosphere, minimal",
    lead="Close, moody, half-lit",
    bg="Dark filtered shadows",
    master="Dark, sparse, moody depth"),
  reverb=dict(room=(0.4, 631), med=(1.8, 0.018, 641), long=(2.8, 0.028, 651)),
  drums=bus(hpf=35, lpf=12000, shelf=[("lowshelf",110,0.5)], peak=[(2500,1.5,1.0)],
            comp=(-16,3.0,6,110,2,1.0), sat=(1.25,0.2), rev=("room",0.06), gain=-6),
  bass=bus(hpf=25, lpf=5000, shelf=[("lowshelf",60,3.5)],
           comp=(-20,4.0,3,120,2,1.0), sat=(1.5,0.3), gain=-6),
  pad=bus(hpf=60, lpf=7500, shelf=[("lowshelf",230,-1.5)], comp=(-24,2.5,16,240,2,0.5),
          rev=("long",0.30), widen=0.5, sat=(1.2,0.15), gain=-12),
  lead=bus(hpf=85, lpf=11000, shelf=[("lowshelf",190,0.5)], peak=[(2600,1.5,1.0)],
           comp=(-14,2.0,18,150,3,1.5), rev=("long",0.35), widen=0.06, gain=-3),
  bg=bus(hpf=100, lpf=6500, comp=(-26,2.0,20,280,2), rev=("long",0.40), widen=0.55, gain=-16),
  master=mast(hpf=32, lpf=15000, shelf=[("lowshelf",55,2.0)], peak=[(2500,0.5,1.0)],
              comp=(-16,2.0,10,170,2,1.5), widen=0.15, sat=(1.25,0.18), target_lufs=-11.0),
 ),
 dict(
  slug="power", folder="power", name="Bob Power", zh="鲍勃·鲍尔",
  color="#a5755a", tagline="warm · organic · deep NYC soul",
  about="NYC hip-hop and soul pioneer (A Tribe Called Quest, The Roots, Erykah Badu, "
        "D'Angelo, De La Soul). Signature: warm organic textures, deep round bass, honest "
        "midrange, grooves that feel hand-made.",
  refs=["A Tribe Called Quest", "The Roots", "Erykah Badu", "D'Angelo", "De La Soul"],
  sig=dict(
    drums="Warm, organic, in the groove",
    bass="Deep, round, soulful",
    pad="Warm harmonic quilt",
    lead="Honest, close, warm",
    bg="Earthy ambience",
    master="Warm glue, organic groove"),
  reverb=dict(room=(0.55, 661), med=(1.5, 0.015, 671), long=(2.1, 0.022, 681)),
  drums=bus(hpf=30, shelf=[("lowshelf",95,1.5)], peak=[(2600,1.0,1.0)],
            comp=(-17,3.0,6,120,2,1.0), sat=(1.4,0.25), rev=("room",0.12), gain=-5),
  bass=bus(hpf=30, shelf=[("lowshelf",80,2.5)], peak=[(95,1.5,1.2)],
           comp=(-21,4.0,4,140,2,0.5), sat=(1.5,0.28), gain=-6),
  pad=bus(hpf=50, shelf=[("lowshelf",240,-1.0)], peak=[(2200,0.5,1.0)],
          comp=(-24,2.0,18,260,2,0.5), rev=("med",0.15), widen=0.25, sat=(1.2,0.18), gain=-12),
  lead=bus(hpf=65, shelf=[("lowshelf",180,1.0)], peak=[(2700,1.5,1.0)],
           comp=(-15,2.0,22,200,3,1.5), rev=("med",0.15), widen=0.08, gain=-3),
  bg=bus(hpf=85, lpf=9500, comp=(-25,2.0,20,280,2), rev=("med",0.20), widen=0.4, gain=-15),
  master=mast(hpf=30, shelf=[("lowshelf",55,1.5)], peak=[(2000,0.5,1.0),(10000,1.0,1.0)],
              comp=(-16,1.8,10,190,1.5,1.5), widen=0.08, sat=(1.25,0.14), target_lufs=-12.0),
 ),
 dict(
  slug="zhoutianche", folder="zhoutianche", name="Tianche Zhou", zh="周天澈",
  color="#8fc1a9", tagline="清晰 · 精致 · 人声为核心",
  about="华语流行混音与母带代表（Studio21A 创始人，合作鹿晗、张艺兴、林俊杰、刘若英等）。"
        "Signature: 清晰干净的层次，精致的高频质感，人声永远处于最核心最舒服的位置，"
        "兼顾响度与耐听度。",
  refs=["鹿晗", "张艺兴", "林俊杰", "刘若英", "华语流行"],
  sig=dict(
    drums="干净、克制、有弹性",
    bass="清晰扎实的低频支撑",
    pad="细腻的铺底，不抢人声",
    lead="人声永远是主角，透亮",
    bg="精致的氛围层次",
    master="清晰、精致、耐听的响度"),
  reverb=dict(room=(0.42, 691), med=(1.5, 0.013, 701), long=(2.1, 0.019, 711)),
  drums=bus(hpf=30, shelf=[("lowshelf",100,1.0)], peak=[(3800,1.5,1.0)],
            comp=(-17,3.0,6,120,2,1.5), sat=(1.15,0.08), rev=("room",0.08), gain=-5),
  bass=bus(hpf=33, shelf=[("lowshelf",85,1.5)], peak=[(120,1.0,1.0)],
           comp=(-22,3.5,5,160,2,1.0), sat=(1.25,0.12), gain=-7),
  pad=bus(hpf=52, shelf=[("lowshelf",230,-1.5)], peak=[(2800,1.0,1.0)],
          comp=(-23,2.5,14,230,2,0.5), rev=("med",0.15), widen=0.3, gain=-12),
  lead=bus(hpf=70, shelf=[("lowshelf",165,0.5)], peak=[(3000,2.5,1.0),(8000,1.5,1.0)],
           comp=(-14,2.0,18,150,3,2.5), rev=("long",0.22), widen=0.08, pan=0.03, gain=-3),
  bg=bus(hpf=92, lpf=10200, comp=(-25,2.0,16,240,2), rev=("long",0.25), widen=0.45, gain=-15),
  master=mast(hpf=27, shelf=[("lowshelf",52,0.5)], peak=[(2500,0.5,1.0),(11500,1.5,1.0)],
              comp=(-15,1.8,8,130,1.5,2.0), widen=0.10, sat=(1.08,0.05), target_lufs=-11.0),
 ),
]
for st in STYLES:
    st["target_lufs"] = st["master"]["target_lufs"]

# ---------------- generic chain renderers ----------------
def bus_chain(x, p, irs, apply_level=True):
    if p.get("hpf"): x = dsp.hpf(x, SR, p["hpf"])
    if p.get("lpf"): x = dsp.lpf(x, SR, p["lpf"])
    for t, f, g in p.get("shelf", ()): x = dsp.shelf(x, SR, t, f, g)
    for f, g, q in p.get("peak", ()): x = dsp.peak(x, SR, f, g, q)
    if p.get("comp"): x, _ = dsp.compressor(x, SR, *p["comp"])
    if p.get("sat"): x = dsp.saturate(x, p["sat"][0], p["sat"][1])
    if p.get("rev"): x = reverb_send(x, irs[p["rev"][0]], p["rev"][1])
    if p.get("widen"): x = dsp.mid_side_widen(x, p["widen"])
    if p.get("pan"): x = dsp.pan(x, p["pan"])
    if apply_level and p.get("gain"): x = x * 10**(p["gain"]/20.0)
    return x

def master_chain(x, p, ceiling_db=-1.0):
    if p.get("hpf"): x = dsp.hpf(x, SR, p["hpf"])
    if p.get("lpf"): x = dsp.lpf(x, SR, p["lpf"])
    for t, f, g in p.get("shelf", ()): x = dsp.shelf(x, SR, t, f, g)
    for f, g, q in p.get("peak", ()): x = dsp.peak(x, SR, f, g, q)
    if p.get("comp"): x, _ = dsp.compressor(x, SR, *p["comp"])
    if p.get("widen"): x = dsp.mid_side_widen(x, p["widen"])
    if p.get("sat"): x = dsp.saturate(x, p["sat"][0], p["sat"][1])
    target = p.get("target_lufs", -13.0)
    l = dsp.estimate_lufs(x, SR)
    gain = min(10**((target - l)/20.0), 10**(12/20))
    x = x * gain
    x, _ = dsp.limiter(x, SR, ceiling_db, release_ms=p.get("lim_release", 80.0), lookahead_ms=4.0)
    x = dsp.normalize_peak(x, ceiling_db)
    return x, dsp.estimate_lufs(x, SR)

def style_irs(r):
    return {
        "room": dsp.room_ir(SR, decay=r["room"][0], seed=r["room"][1]),
        "med": dsp.plate_ir(SR, decay=r["med"][0], pre_delay=r["med"][1], seed=r["med"][2]),
        "long": dsp.plate_ir(SR, decay=r["long"][0], pre_delay=r["long"][1], seed=r["long"][2]),
    }

# ---------------- manifest helpers ----------------
def fmt_bus(p):
    bits = []
    if p.get("hpf"): bits.append(f"HPF {p['hpf']} Hz")
    if p.get("lpf"): bits.append(f"LPF {p['lpf']} Hz")
    for t, f, g in p.get("shelf", ()): bits.append(f"{t} {g:+.1f} dB @ {f} Hz")
    for f, g, q in p.get("peak", ()): bits.append(f"peak {g:+.1f} dB @ {f} Hz")
    if p.get("comp"):
        c = list(p["comp"])
        thr, ratio, atk, rel = c[0], c[1], c[2], c[3]
        knee = c[4] if len(c) > 4 else 3.0
        mk = c[5] if len(c) > 5 else 0.0
        bits.append(f"comp {thr} dB {ratio:g}:1 ({atk:.0f}/{rel:.0f} ms, k{knee:.0f}, +{mk:g} dB)")
    if p.get("sat"): bits.append(f"sat drive {p['sat'][0]:g} mix {p['sat'][1]:g}")
    if p.get("rev"): bits.append(f"{p['rev'][0]} reverb {int(p['rev'][1]*100)}%")
    if p.get("widen"): bits.append(f"M/S {p['widen']:+.2f}")
    if p.get("pan"): bits.append(f"pan {p['pan']:+.2f}")
    if p.get("gain"): bits.append(f"{p['gain']:+g} dB")
    return " · ".join(bits)

def fmt_master(p):
    bits = [fmt_bus(p)]
    bits.append(f"target {p.get('target_lufs', -13.0):g} LUFS · limiter rel {p.get('lim_release', 80):g} ms")
    return " · ".join(bits)



STYLE_BY_SLUG = {st["slug"]: st for st in STYLES}
SLUGS = [st["slug"] for st in STYLES]


def resolve_style(name, rng=None):
    """按 slug 或 'random' 解析一个混音师风格；'random' 需要 rng（random.Random 或 random 模块）。"""
    if name in ("random", "*", "auto"):
        import random
        chooser = rng if rng is not None else random
        return STYLE_BY_SLUG[chooser.choice(SLUGS)]
    if name not in STYLE_BY_SLUG:
        raise KeyError(f"未知混音师风格 '{name}'，可用：{', '.join(SLUGS)} / random")
    return STYLE_BY_SLUG[name]
