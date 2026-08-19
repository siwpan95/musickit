#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共享「混音师风格」注册表与渲染链（mixer_styles）。

本模块同时服务两条管线：
  1. burbidge_album/build_album.py —— 固定风格专辑（同一组 stems × 10 位混音师）
  2. musickit/remix/main.py        —— 随机风格混音引擎（--mixer-style 可选接入）

只依赖 numpy/scipy（经同目录 dsp.py），供 F:/Python314 与专辑构建环境共用。
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
