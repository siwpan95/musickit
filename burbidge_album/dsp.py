#!/usr/bin/env python3
# dsp.py - Zero-dependency (numpy/scipy/soundfile) DSP primitives for a Craig Burbidge-style mix.
# All functions operate on float32 stereo arrays of shape [n, 2] unless noted.
import numpy as np
import soundfile as sf
from scipy.signal import sosfilt
from scipy.ndimage import uniform_filter1d

SR = 44100

def load_audio(path, sr=SR, max_seconds=None):
    data, fs = sf.read(path, always_2d=True)
    if data.dtype != np.float32:
        data = data.astype(np.float32)
    # to mono? keep channels but force stereo
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    elif data.shape[1] > 2:
        data = data[:, :2]
    if fs != sr:
        # resample
        from scipy.signal import resample
        n_new = int(round(len(data) * sr / fs))
        data = resample(data, n_new, axis=0).astype(np.float32)
    if max_seconds:
        cap = int(sr * max_seconds)
        if len(data) > cap:
            data = data[:cap]
    # normalize if extremely hot
    peak = np.max(np.abs(data))
    if peak > 1.0:
        data = data / peak
    return data

# ---------------- EQ (RBJ biquad) ----------------
def _rbj(type_, f0, Q, dbgain, sr):
    w0 = 2*np.pi*f0/sr
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw/(2*Q)
    if type_ in ("lowpass","highpass"):
        if type_ == "highpass":
            b0 = (1+cw)/2
            b1 = -(1+cw)
            b2 = (1+cw)/2
        else:
            b0 = (1-cw)/2
            b1 = (1-cw)
            b2 = (1-cw)/2
        a0, a1, a2 = 1+alpha, -2*cw, 1-alpha
    elif type_ == "peak":
        A = 10**(dbgain/40)
        b0, b2 = 1+alpha*A, 1-alpha*A
        a0, a2 = 1+alpha/A, 1-alpha/A
        b1 = a1 = -2*cw
    elif type_ in ("highshelf","lowshelf"):
        A = 10**(dbgain/40)
        if type_ == "highshelf":
            b0 = A*((A+1)+(A-1)*cw+2*np.sqrt(A)*alpha)
            b1 = -2*A*((A-1)+(A+1)*cw)
            b2 = A*((A+1)+(A-1)*cw-2*np.sqrt(A)*alpha)
            a0 = (A+1)-(A-1)*cw+2*np.sqrt(A)*alpha
            a1 = 2*((A-1)-(A+1)*cw)
            a2 = (A+1)-(A-1)*cw-2*np.sqrt(A)*alpha
        else:
            b0 = A*((A+1)-(A-1)*cw+2*np.sqrt(A)*alpha)
            b1 = 2*A*((A-1)-(A+1)*cw)
            b2 = A*((A+1)-(A-1)*cw-2*np.sqrt(A)*alpha)
            a0 = (A+1)+(A-1)*cw+2*np.sqrt(A)*alpha
            a1 = -2*((A-1)+(A+1)*cw)
            a2 = (A+1)+(A-1)*cw-2*np.sqrt(A)*alpha
    else:
        raise ValueError(type_)
    return np.array([[b0/a0, b1/a0, b2/a0, 1.0, a1/a0, a2/a0]], dtype=np.float32)

def eq(x, sr, type_, f0, Q=0.707, dbgain=0.0):
    sos = _rbj(type_, f0, Q, dbgain, sr)
    return sosfilt(sos, x, axis=0).astype(np.float32)

def hpf(x, sr, f0=30.0, Q=0.707):
    return eq(x, sr, "highpass", f0, Q)

def lpf(x, sr, f0, Q=0.707):
    return eq(x, sr, "lowpass", f0, Q)

def peak(x, sr, f0, db, Q=1.0):
    return eq(x, sr, "peak", f0, Q, db)

def shelf(x, sr, type_, f0, db, Q=0.707):
    return eq(x, sr, type_, f0, Q, db)

# ---------------- Dynamics (vectorized via lfilter) ----------------
from scipy.signal import lfilter

def _rms_env(x, sr, tau_ms):
    power = np.mean(x.astype(np.float64)**2, axis=1)
    a = np.exp(-1.0/(sr*(tau_ms/1000.0)))
    sm = lfilter([1-a], [1, -a], power)
    return np.sqrt(np.maximum(sm, 1e-12))

def _peak_env(x, sr, tau_ms):
    p = np.max(np.abs(x).astype(np.float64), axis=1)
    a = np.exp(-1.0/(sr*(tau_ms/1000.0)))
    return lfilter([1-a], [1, -a], p)

def compressor(x, sr, threshold_db=-18.0, ratio=4.0, attack_ms=10.0, release_ms=150.0,
               knee_db=3.0, makeup_db=0.0):
    # RMS detector: fast-ish attack, musical release
    env = _rms_env(x, sr, max(attack_ms, 5.0))
    thr = 10**(threshold_db/20.0)
    over_db = 20*np.log10(env/(thr+1e-9))
    gr = np.where(over_db <= -knee_db/2, 0.0,
           np.where(over_db >= knee_db/2, over_db*(1-1/ratio),
                    ((over_db+knee_db/2)**2)/(2*knee_db)*(1-1/ratio)))
    # smooth the gain reduction a touch with release
    ra = np.exp(-1.0/(sr*(max(release_ms,20.0)/1000.0)))
    gr = lfilter([1-ra], [1, -ra], gr)
    gain = 10**(-gr/20.0)
    y = x * gain[:, None].astype(np.float32)
    if makeup_db:
        y = y * 10**(makeup_db/20.0)
    return y.astype(np.float32), gr.astype(np.float32)

def saturate(x, drive=1.5, mix=0.3):
    # gentle tape-ish saturation (asymmetric-ish via tanh)
    sat = np.tanh(x*drive)
    return (x*(1-mix) + sat*mix).astype(np.float32)

# ---------------- Time stretch (phase vocoder, pitch-preserving) ----------------
def time_stretch(x, ratio, sr=SR, frame=2048, ana_hop=None):
    """Stretch time by `ratio` (out_len = len/ratio). Pitch preserved."""
    if abs(ratio-1.0) < 1e-3:
        return x.astype(np.float32)
    if ana_hop is None:
        ana_hop = frame//4
    syn_hop = max(1, int(round(ana_hop*ratio)))
    win = np.hanning(frame)
    n_frames = (x.shape[0]-frame)//ana_hop + 1
    out_len = (n_frames-1)*syn_hop + frame
    y = np.zeros((out_len, x.shape[1]), dtype=np.float64)
    wsum = np.zeros(out_len)
    prev_ana = [None]*x.shape[1]
    prev_syn = [None]*x.shape[1]
    for fi in range(n_frames):
        start = fi*ana_hop
        for ch in range(x.shape[1]):
            seg = x[start:start+frame, ch]*win
            S = np.fft.rfft(seg)
            mag = np.abs(S)
            ph = np.angle(S)
            if prev_ana[ch] is None:
                prev_ana[ch] = ph
                prev_syn[ch] = ph
            omega = 2*np.pi*ana_hop*np.arange(len(ph))/frame
            dphi = ph - prev_ana[ch] - omega
            dphi = dphi - 2*np.pi*np.round(dphi/(2*np.pi))
            syn_ph = prev_syn[ch] + omega*ratio + dphi
            prev_ana[ch] = ph
            prev_syn[ch] = syn_ph
            Y = mag*np.exp(1j*syn_ph)
            seg_out = np.fft.irfft(Y)*win
            s2 = fi*syn_hop
            if s2 >= out_len:
                break
            end = min(s2+frame, out_len)
            y[s2:end, ch] += seg_out[:end-s2]
            wsum[s2:end] += win[:end-s2]
    wsum[wsum < 1e-6] = 1.0
    y = y/wsum[:, None]
    return y[:int(x.shape[0]/ratio), :].astype(np.float32)

# ---------------- Reverb ----------------
def plate_ir(sr=SR, decay=2.2, pre_delay=0.02, er=10, seed=0):
    rng = np.random.default_rng(seed)
    total = int((decay+pre_delay)*sr)
    pd = int(pre_delay*sr)
    def tail():
        t = np.arange(total)/sr
        env = np.exp(-t/ (decay/4.6))
        n = rng.standard_normal(total)
        # add a little density / diffusion
        n = uniform_filter1d(n, size=int(0.03*sr))
        ir = n*env
        ir[pd:] += env[pd:]*0.0
        # early reflections
        for i in range(er):
            pos = int((pre_delay + 0.008*i + rng.random()*0.02)*sr)
            if pos < total:
                ir[pos] += (0.6**(i+1))*rng.standard_normal()
        ir /= np.max(np.abs(ir))
        return ir.astype(np.float32)
    L = tail(); R = tail()
    return np.stack([L, R], axis=1)

def room_ir(sr=SR, decay=0.5, seed=1):
    rng = np.random.default_rng(seed)
    total = int((decay+0.02)*sr)
    t = np.arange(total)/sr
    env = np.exp(-t/(decay/4.6))
    L = uniform_filter1d(rng.standard_normal(total), size=int(0.01*sr))*env
    R = uniform_filter1d(rng.standard_normal(total), size=int(0.01*sr))*env
    L/=np.max(np.abs(L)); R/=np.max(np.abs(R))
    return np.stack([L, R], axis=1).astype(np.float32)

def convolve_rev(x, ir):
    from scipy.signal import fftconvolve
    out = np.zeros((x.shape[0]+len(ir), x.shape[1]), dtype=np.float32)
    for ch in range(x.shape[1]):
        c = fftconvolve(x[:, ch], ir[:, ch])[:x.shape[0]]
        out[:len(c), ch] = c.astype(np.float32)
    return out[:x.shape[0]].astype(np.float32)

# ---------------- Stereo width ----------------
def mid_side_widen(x, amount=0.3):
    mid = (x[:,0]+x[:,1])/2
    side = (x[:,0]-x[:,1])/2 * (1+amount)
    L = mid+side; R = mid-side
    return np.stack([L,R], axis=1).astype(np.float32)

def pan(x, pos=-0.3):
    # pos -1..1 (L..R) simple constant-power
    pos = np.clip(pos, -1, 1)
    Lg = np.cos((pos+1)/2*np.pi/2)
    Rg = np.cos((1-pos)/2*np.pi/2)
    L = x[:,0]*Lg + x[:,1]*(1-Rg)
    R = x[:,1]*Rg + x[:,0]*(1-Lg)
    return np.stack([L,R], axis=1).astype(np.float32)

# ---------------- Limiter / normalize ----------------
def limiter(x, sr, ceiling_db=-1.0, release_ms=60.0, lookahead_ms=3.0, margin_db=0.5):
    ceil = 10**((ceiling_db - margin_db)/20.0)
    env = _peak_env(x, sr, 1.0)  # fast detector
    desired = np.minimum(1.0, ceil/(env+1e-9))
    ra = np.exp(-1.0/(sr*(release_ms/1000.0)))
    desired = lfilter([1-ra], [1, -ra], desired)
    la = int(lookahead_ms/1000.0*sr)
    if la > 0:
        desired = np.concatenate([desired[la:], np.ones(la)])
    y = x * desired[:, None].astype(np.float32)
    return y.astype(np.float32), desired.astype(np.float32)

def normalize_peak(x, target_db=-1.0):
    peak = np.max(np.abs(x))
    if peak < 1e-6:
        return x
    g = 10**(target_db/20.0)/peak
    return (x*g).astype(np.float32)

def estimate_lufs(x, sr=SR):
    # simplified K-weighted loudness (RMS-based proxy)
    # high-shelf +4dB @ ~1.5k, highpass ~38Hz (ITU), then mean square
    y = shelf(x.copy(), sr, "highshelf", 1500, 4.0, Q=0.707)
    y = hpf(y, sr, 38.0, Q=0.5)
    rms = np.sqrt(np.mean(y**2))
    return -0.691 + 10*np.log10(rms**2 + 1e-12)
