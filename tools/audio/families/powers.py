"""Class power sounds: the Cleric's heal, the Warrior's doubled damage, the Paladin's shield,
and the dull "no effect" when the enemy is immune to a power.

Five candidates per event, each a different character (an acoustic or real one, a soft or
wooden one, a magical one, an 8-bit one, and one more of its own). Tonal parts are tuned to
D: D major pentatonic (D E F# A B) for the bright powers, D dorian (with F natural) for the
glum "immune" sounds. A phone speaker plays little below about 200 Hz, so every low thump
also carries harmonics between 150 and 600 Hz: the weight comes through on the phone too.

Private helpers here (the shared toolkit is not edited):
  _modes / _reson / _excite   modal synthesis (struck metal, wood, glass)
  _svf                        a filter whose cutoff can move every sample (sweeps, brass)
  _ks                         a plucked string tuned exactly (Karplus-Strong)
  _mallet / _ping / _bubble   a felt mallet bar, a small bell or glass, a liquid bubble
  _brass / _choir             a horn and an "ah" choir (formant filtered)
  _taiko / _blade / _knock    a big drum, a sword's ring, a knuckle on wood
  _pulse / _tri4 / _lfsr      the 8-bit voices, stepped at 60 frames a second
  _glue / _finish             tame a hit's first peak; cut to length with a natural fade
"""
from __future__ import annotations

import math
from typing import List, Sequence, Tuple

import numpy as np
from scipy import signal

import synth as A
from catalog import Candidate

SR = A.SR
TAU = 2 * math.pi


def N(name: str) -> float:
    return A.note_hz(name)


# ============================================================================= basics
def _n(d: float) -> int:
    return A.n_of(d)


def _t(d: float) -> np.ndarray:
    return A.seconds(d)


def _buf(d: float) -> np.ndarray:
    return np.zeros(_n(d))


def _fit(x: np.ndarray, d: float) -> np.ndarray:
    n = _n(d)
    return x[:n].copy() if len(x) >= n else np.concatenate([x, np.zeros(n - len(x))])


def _norm(x: np.ndarray) -> np.ndarray:
    p = float(np.max(np.abs(x))) if len(x) else 0.0
    return x / p if p > 0 else x


def _sat(x: np.ndarray, drive: float) -> np.ndarray:
    """Soft saturation that keeps the peak level: adds the harmonics that let a low thump
    read on a small speaker."""
    p = float(np.max(np.abs(x))) or 1.0
    return np.tanh(drive * x / p) / math.tanh(drive) * p


def _bn(d: float, lo: float, hi: float, seed: int, color: str = "white", order: int = 2) -> np.ndarray:
    """Band-limited noise, peak-normalised."""
    return _norm(A.bandpass(A.noise(d, color, seed), lo, hi, order))


def _burst(d: float, lo: float, hi: float, t60: float, seed: int) -> np.ndarray:
    """A short noise burst (a contact, a knuckle, a stick)."""
    return _bn(d, lo, hi, seed) * A.decay(d, t60, 0.0002)


def _hold(f0: float, f1: float, drop: float, d: float) -> np.ndarray:
    g = A.glide(f0, f1, min(drop, d))
    return np.concatenate([g, np.full(max(0, _n(d) - len(g)), f1)])[:_n(d)]


def _thump(f0: float, f1: float, drop: float, t60: float, d: float, drive: float = 0.0) -> np.ndarray:
    """A low body thump whose pitch falls from f0 to f1, optionally saturated."""
    y = A.sine(_hold(f0, f1, drop, d), d) * A.decay(d, t60, 0.0006)
    return _sat(y, drive) if drive else y


def _finish(x: np.ndarray, total: float, fade: float, hp: float = 40.0, lp: float = 0.0) -> np.ndarray:
    """Cut to ``total`` seconds and fade the last ``fade`` seconds with a half cosine; a
    high-pass removes rumble no one hears, a low-pass (if given) keeps the top gentle."""
    y = _fit(x, total)
    y = A.highpass(y, hp, 2)
    if lp:
        y = A.lowpass(y, lp, 4)
    nf = _n(fade)
    y[-nf:] *= 0.5 * (1 + np.cos(np.linspace(0, math.pi, nf)))
    return y


def _verb(x: np.ndarray, room: float, wet: float, damping: float = 0.5, tail: float = 0.0) -> np.ndarray:
    return A.reverb(x, room, wet, damping, 1.0, tail)


def _loudness(x: np.ndarray) -> float:
    """The build's loudness measure (gated RMS of 50 ms blocks after a 100 Hz high-pass)."""
    y = A.highpass(x, 100, 1)
    blk = _n(0.05)
    k = len(y) // blk
    if k < 1:
        return 10 * math.log10(np.mean(y ** 2) + 1e-20)
    p = np.mean(y[:k * blk].reshape(k, blk) ** 2, axis=1)
    keep = p[p > np.max(p) * 10 ** (-4.5)]
    return 10 * math.log10(np.mean(keep) + 1e-20)


def _glue(x: np.ndarray, crest_db: float = 15.0, release: float = 0.02) -> np.ndarray:
    """Hold a hit's first peaks to ``crest_db`` above its loudness with a fast limiter, so
    the master's slower limiter does not turn the whole ring down after the hit."""
    y = _norm(x)
    for _ in range(4):
        ceil = _loudness(y) + crest_db
        if 20 * math.log10(np.max(np.abs(y))) <= ceil + 0.2:
            break
        y = A.limit(y, ceil, lookahead=0.0015, release=release)
    return y


def _swell(d: float, attack: float, hold: float, release: float) -> np.ndarray:
    """A smooth rise (1 - e^-t/attack), held, then an exponential fall reaching -60 dB
    ``release`` seconds after ``hold``."""
    t = _t(d)
    up = 1 - np.exp(-t / max(attack, 1e-4))
    down = np.where(t < hold, 1.0, np.exp(-6.9078 * (t - hold) / max(release, 1e-4)))
    return up * down


# ============================================================================= resonators
def _modes(f0: float, ratios: Sequence[float], gains: Sequence[float], t60s: Sequence[float], d: float,
           beat: float = 0.0, attack: float = 0.0004, fmax: float = 7600.0) -> np.ndarray:
    """Struck-object modes: decaying sines at f0 x ratio. ``beat`` splits each mode into a
    slightly detuned pair (the slow shimmer of real metal and glass)."""
    t = _t(d)
    y = np.zeros(len(t))
    for k, (r, g, T) in enumerate(zip(ratios, gains, t60s)):
        f = f0 * r
        if f > fmax or g == 0:
            continue
        e = np.exp(-6.9078 * t / T)
        if beat:
            s = 0.5 * (np.sin(TAU * f * (1 - beat) * t) + np.sin(TAU * f * (1 + beat) * t + 0.7 * k))
        else:
            s = np.sin(TAU * f * t)
        y += g * s * e
    na = _n(attack)
    if na:
        y[:na] *= np.linspace(0, 1, na)
    return y


def _reson(x: np.ndarray, f: float, t60: float) -> np.ndarray:
    """A two-pole resonator ringing at f for t60 seconds."""
    w = TAU * f / SR
    r = 0.001 ** (1.0 / (t60 * SR))
    return signal.lfilter([math.sin(w)], [1.0, -2 * r * math.cos(w), r * r], x)


def _excite(burst: np.ndarray, modes: Sequence[Tuple[float, float, float]], d: float) -> np.ndarray:
    """Drive a bank of (freq, gain, t60) resonators with a short burst."""
    ex = _fit(burst, d)
    return sum(g * _reson(ex, f, T) for f, g, T in modes)


def _bp2(x: np.ndarray, fc, q: float = 1.0) -> np.ndarray:
    """Two moving band-passes in a row: a focused band with steep sides (no hiss above)."""
    return _svf(_svf(x, fc, q, "bp"), fc, q, "bp")


def _svf(x: np.ndarray, fc, q: float = 0.707, mode: str = "bp") -> np.ndarray:
    """A state-variable filter (trapezoidal) whose cutoff ``fc`` may change every sample.
    'bp' has unit gain at the centre; 'lp' and 'hp' as named."""
    n = len(x)
    fcv = np.broadcast_to(np.asarray(fc, dtype=float), (n,))
    g = np.tan(math.pi * np.clip(fcv, 20.0, 0.45 * SR) / SR)
    k = 1.0 / q
    a1 = 1.0 / (1.0 + g * (g + k))
    a2 = g * a1
    a3 = g * a2
    xs, A1, A2, A3 = x.tolist(), a1.tolist(), a2.tolist(), a3.tolist()
    ic1 = ic2 = 0.0
    lp = [0.0] * n
    bp = [0.0] * n
    for i in range(n):
        v3 = xs[i] - ic2
        v1 = A1[i] * ic1 + A2[i] * v3
        v2 = ic2 + A2[i] * ic1 + A3[i] * v3
        ic1 = 2 * v1 - ic1
        ic2 = 2 * v2 - ic2
        bp[i] = v1
        lp[i] = v2
    if mode == "lp":
        return np.array(lp)
    if mode == "bp":
        return k * np.array(bp)
    return x - k * np.array(bp) - np.array(lp)


# ============================================================================= voices
def _ks(freq: float, d: float, bright: float = 0.5, t60: float = 1.5, seed: int = 0) -> np.ndarray:
    """A plucked string (Karplus-Strong) tuned exactly: the loop is the integer delay plus
    the averaging filter's half sample plus a linear-interpolated fraction."""
    n = _n(d)
    P = SR / freq
    L = int(math.floor(P - 0.5))
    frac = P - 0.5 - L
    c0, c1, c2 = 0.5 * (1 - frac), 0.5, 0.5 * frac
    g = 10 ** (-3.0 * (P / SR) / max(t60, 0.05))
    rng = np.random.default_rng(seed)
    burst = rng.uniform(-1, 1, L + 2)
    burst = A.lowpass(burst, 400 + 7000 * bright, 1)
    burst -= burst.mean()
    out = np.zeros(max(n, L + 3))
    out[:L + 2] = burst
    i = L + 2
    while i < n:
        k = min(L, n - i)
        out[i:i + k] = g * (c0 * out[i - L:i - L + k] + c1 * out[i - L - 1:i - L - 1 + k]
                            + c2 * out[i - L - 2:i - L - 2 + k])
        i += k
    y = out[:n]
    na = _n(0.0008)
    y[:na] *= np.linspace(0, 1, na)
    return y


def _mallet(f: float, d: float, t60: float = 1.0, hard: float = 0.3) -> np.ndarray:
    """A felt mallet on a tuned wooden bar (marimba): a round fundamental, the bar's
    quieter 3.93x partial, and the soft knock of the felt."""
    t = _t(d)
    y = np.sin(TAU * f * t) * np.exp(-6.9078 * t / t60)
    if f * 3.93 < 7000:
        y += 0.12 * hard * 3 * np.sin(TAU * f * 3.93 * t) * np.exp(-6.9078 * t / (t60 * 0.25))
    knock = A.lowpass(A.noise(0.02, "white", int(f)), 900, 2) * A.decay(0.02, 0.012, 0.0005)
    y[:len(knock)] += 0.25 * hard * _norm(knock)
    na = _n(0.0015)
    y[:na] *= np.linspace(0, 1, na)
    return y


def _ping(f: float, t60: float, partial: float = 2.76, pgain: float = 0.2, d: float = 0.0,
          attack: float = 0.0008) -> np.ndarray:
    """A small bell or glass ping: a fundamental and one inharmonic partial. The short
    rounded attack (a soft mallet) keeps it from clicking."""
    d = d or min(t60 * 1.1, 2.5)
    t = _t(d)
    y = np.sin(TAU * f * t) * np.exp(-6.9078 * t / t60)
    if pgain and f * partial < 7600:
        y += pgain * np.sin(TAU * f * partial * t) * np.exp(-6.9078 * t / (t60 * 0.4))
    na = _n(attack)
    y[:na] *= 0.5 - 0.5 * np.cos(np.linspace(0, math.pi, na))
    return y


def _bubble(f0: float, xi: float = 0.15, damp: float = 0.6, d: float = 0.0) -> np.ndarray:
    """A bubble in a liquid (Minnaert resonance): a sine whose pitch rises as the bubble
    nears the surface, damped by the liquid (van den Doel's model). A 1.5 ms rounded
    onset (the bubble forming) keeps it from clicking."""
    dm = (0.043 * f0 + 0.0014 * f0 ** 1.5) * damp
    d = d or min(1.2, 7.0 / dm)
    t = _t(d)
    f = f0 * (1 + xi * dm * t)
    y = np.sin(TAU * np.cumsum(f) / SR) * np.exp(-dm * t)
    na = _n(0.0015)
    y[:na] *= 0.5 - 0.5 * np.cos(np.linspace(0, math.pi, na))
    return y


def _line(notes: Sequence[Tuple[float, float]], d: float, glide: float = 0.006) -> np.ndarray:
    """Per-sample pitch for a legato line: (start time, Hz) changes joined by short glides."""
    n = _n(d)
    f = np.empty(n)
    for i, (t0, hz) in enumerate(notes):
        a = _n(t0)
        b = _n(notes[i + 1][0]) if i + 1 < len(notes) else n
        f[a:b] = hz
    lf = np.log(f)
    a = math.exp(-1.0 / (glide * SR))
    lf = signal.lfilter([1 - a], [1, -a], lf, zi=[a * lf[0]])[0]
    return np.exp(lf)


def _brass(f: np.ndarray, amp: np.ndarray, seed: int, bright: float = 2000.0,
           onsets: Sequence[float] = (0.0,)) -> np.ndarray:
    """A horn: a sawtooth whose brightness follows its loudness (as a real horn's does),
    a brassy flare at each tongued onset, a bell resonance and a little breath."""
    d = len(f) / SR
    t = _t(d)
    saw = A.osc("saw", f, d, phase=math.pi)
    flare = sum(np.where(t >= o, np.exp(-np.clip(t - o, 0, None) / 0.05), 0.0) for o in onsets)
    fc = 200 + bright * np.clip(amp, 0, None) ** 1.5 + 1400 * flare
    y = _svf(saw, fc, 0.8, "lp")
    y = A.peak_eq(y, 520, 4.0, 1.1)
    y = A.peak_eq(y, 1300, 2.0, 1.4)
    y = y + 0.025 * _bn(d, 600, 2600, seed)
    return y * amp


# the vowel "ah" of an alto voice: (centre Hz, boost dB, Q)
_AH = [(800, 16.0, 4.5), (1150, 13.0, 5.5), (2800, 9.0, 8.0), (3500, 5.0, 8.0)]


def _choir(notes: Sequence[float], d: float, seed: int, voices: int = 3, vib: float = 5.2,
           depth: float = 0.004) -> np.ndarray:
    """An "ah" choir: for each note a few singers (slightly detuned saws with their own
    vibrato), the voice's source rolled off like vocal folds (-12 dB an octave), then
    shaped by the vowel's formant peaks, with a touch of breath."""
    rng = np.random.default_rng(seed)
    t = _t(d)
    src = np.zeros(len(t))
    for f in notes:
        for v in range(voices):
            det = 1 + rng.uniform(-0.005, 0.005)
            rate = vib * rng.uniform(0.85, 1.15)
            ve = np.clip((t - 0.1) / 0.3, 0, 1)
            fv = f * det * (1 + depth * ve * np.sin(TAU * rate * t + rng.uniform(0, TAU)))
            src += A.osc("saw", fv, d, phase=rng.uniform(0, TAU))
    src /= max(1, len(notes) * voices)
    y = A.lowpass(src, 450, 1) + 0.01 * A.noise(d, "pink", seed + 1)
    for fc, gdb, q in _AH:
        y = A.peak_eq(y, fc, gdb, q)
    return A.lowpass(y, 4500, 2)


def _taiko(f0: float, d: float, seed: int, t60: float = 0.8, drive: float = 1.8) -> np.ndarray:
    """A big drum: a membrane's inharmonic modes, the pitch dropping as the skin relaxes,
    and the stick's hit on the skin."""
    t = _t(d)
    bend = 1 + 0.2 * np.exp(-t / 0.03)
    ratios = [1.0, 1.594, 2.136, 2.296, 2.653, 2.918, 3.156, 3.501]
    gains = [1.0, 0.6, 0.45, 0.35, 0.28, 0.2, 0.15, 0.1]
    y = np.zeros(len(t))
    for k, (r, g) in enumerate(zip(ratios, gains)):
        ph = TAU * np.cumsum(f0 * r * bend) / SR
        y += g * np.sin(ph) * np.exp(-6.9078 * t / (t60 / (1 + 0.8 * k)))
    y[:_n(0.0006)] *= np.linspace(0, 1, _n(0.0006))
    y = _sat(y, drive)
    skin = _fit(_burst(0.05, 250, 1800, 0.03, seed), d)
    return y + 0.35 * skin


def _blade(f0: float, d: float, seed: int, power: float = 1.0) -> np.ndarray:
    """A sword blow on a blade: the steel bar's modes ringing (a slowly beating pair each),
    the edge's bright contact, the low push of the blow and a little grit."""
    y = _modes(f0, [1.0, 2.756, 5.404, 8.933], [1.0, 0.5, 0.25, 0.1],
               [0.8 * power, 0.5 * power, 0.28, 0.15], d, beat=0.0016)
    hit = _burst(0.018, 1800, 6500, 0.007, seed)
    y[:len(hit)] += 0.9 * hit
    y += 0.8 * power * _thump(180, 95, 0.03, 0.12, d, drive=2.2)
    grit = _burst(0.03, 300, 1600, 0.02, seed + 1)
    y[:len(grit)] += 0.4 * grit
    return y


def _knock(f: float, d: float, seed: int, damp: float = 1.0) -> np.ndarray:
    """A knuckle on a heavy wooden board: a short soft burst driving the board's damped
    modes, with the low thud of the board's mass."""
    rng = np.random.default_rng(seed)
    nb = _n(0.004)
    burst = A.lowpass(rng.uniform(-1, 1, nb), 2200, 1) * np.hanning(nb)
    modes = [(f, 1.0, 0.09 * damp), (f * 2.31, 0.35, 0.05 * damp), (f * 0.62, 0.45, 0.07 * damp),
             (f * 3.7, 0.12, 0.03 * damp)]
    y = _excite(burst, modes, d)
    y = _norm(y)
    y += 0.5 * _thump(130, 100, 0.02, 0.06, d, 1.5)
    y[:_n(0.0004)] *= np.linspace(0, 1, _n(0.0004))
    return y


# ============================================================================= 8-bit voices
FPS = 60.0


def _frames(values: Sequence[float], d: float) -> np.ndarray:
    """Per-frame (1/60 s) values held as steps for ``d`` seconds (the last value holds)."""
    v = np.asarray(values, dtype=float)
    per = SR / FPS
    idx = np.minimum((np.arange(_n(d)) / per).astype(int), len(v) - 1)
    return v[idx]


def _smooth(x: np.ndarray, ms: float = 1.5) -> np.ndarray:
    """Round the corners of a stepped envelope just enough that the steps do not click."""
    a = math.exp(-1.0 / (SR * ms / 1000.0))
    return signal.lfilter([1 - a], [1, -a], x)


def _vol(levels: Sequence[float], d: float, tail: float = 0.06) -> np.ndarray:
    """A 4-bit (0..15) per-frame volume envelope; after its last frame the sound fades out
    over ``tail`` seconds instead of stopping dead."""
    e = _frames(levels, d) / 15.0
    end = min(len(e), int(round(len(levels) * SR / FPS)))
    if tail and end < len(e):
        e[end:] = e[end - 1] * np.exp(-np.arange(len(e) - end) / SR * 6.9078 / tail)
    return _smooth(e, 2.0)


def _blep(t: np.ndarray, dt: np.ndarray) -> np.ndarray:
    out = np.zeros_like(t)
    a = t < dt
    x = t[a] / dt[a]
    out[a] = x + x - x * x - 1
    b = t > 1 - dt
    x = (t[b] - 1) / dt[b]
    out[b] = x * x + x + x + 1
    return out


def _pulse(freq: np.ndarray, duty: float = 0.5) -> np.ndarray:
    """A band-limited pulse wave of any duty (12.5, 25 or 50 %, the NES's three), no DC."""
    f = np.asarray(freq, dtype=float)
    t = (np.cumsum(f) / SR) % 1.0
    dt = np.clip(f / SR, 1e-9, 0.5)
    s1 = 2 * t - 1 - _blep(t, dt)
    t2 = (t - duty) % 1.0
    s2 = 2 * t2 - 1 - _blep(t2, dt)
    return s2 - s1


def _tri4(freq: np.ndarray) -> np.ndarray:
    """The NES triangle: a triangle stepped to 16 levels (its soft buzz)."""
    f = np.asarray(freq, dtype=float)
    t = (np.cumsum(f) / SR) % 1.0
    tri = 2 * np.abs(2 * t - 1) - 1
    return np.round((tri + 1) * 7.5) / 7.5 - 1


def _lfsr(rate: np.ndarray, short: bool = False, seed: int = 1) -> np.ndarray:
    """The NES noise channel: a 15-bit shift register clocked ``rate`` times a second
    ('short' mode gives a metallic, pitched noise)."""
    r = np.asarray(rate, dtype=float)
    clock = np.floor(np.cumsum(r) / SR).astype(np.int64)
    m = int(clock[-1]) + 1
    reg = ((0x4A5B + 977 * seed) & 0x7FFF) or 1
    tap = 6 if short else 1
    bits = np.empty(m)
    for i in range(m):
        bits[i] = reg & 1
        fb = (reg ^ (reg >> tap)) & 1
        reg = (reg >> 1) | (fb << 14)
    return 1.0 - 2.0 * bits[clock]


def _seq(steps: Sequence[Tuple[str, int, object]]) -> Tuple[List[float], List[float]]:
    """(note or None for a rest, frames, level or list of per-frame levels) -> per-frame
    pitches and volumes."""
    fr: List[float] = []
    lv: List[float] = []
    last = 440.0
    for nm, k, lev in steps:
        f = N(nm) if nm else last
        last = f
        if isinstance(lev, (list, tuple)):
            ls = list(lev) + [lev[-1]] * max(0, k - len(lev))
        else:
            ls = [float(lev)] * k
        if not nm:
            ls = [0.0] * k
        fr += [f] * k
        lv += ls[:k]
    return fr, lv


def _chip(x: np.ndarray, top: float = 5800.0) -> np.ndarray:
    """The console's output stage: a steep low-pass (the pulse waves' upper harmonics
    would fizz above 8 kHz) and a DC block."""
    return A.highpass(A.lowpass(x, top, 6), 60, 1)


# ============================================================================= heal (Cleric)
def _heal_harp() -> np.ndarray:
    """A harp's rising arpeggio of D major from D3 to D6, the strings left to ring."""
    d = 1.55
    x = _buf(d + 1.0)
    seq = ["D3", "A3", "D4", "F#4", "A4", "D5", "F#5", "A5", "D6"]
    for k, nm in enumerate(seq):
        s = _ks(N(nm), 2.0, bright=0.28 + 0.025 * k, t60=1.7 - 0.1 * k, seed=11 + k)
        x = A.mix_at(x, s, 0.05 * k, 0.6 + 0.05 * k)
    x = A.peak_eq(x, 240, 3.0, 1.0)      # the harp's soundboard
    x = A.peak_eq(x, 120, -6.0, 0.8)
    x = _verb(x, 0.55, 0.2, 0.6)
    return _finish(x, d, 0.5, lp=6500)


def _heal_glow() -> np.ndarray:
    """A felt mallet blooms on D, then warm voices enter one after another, each a step
    higher, while the sound slowly opens and a faint light shimmers above."""
    d = 1.45
    t = _t(d)
    x = _buf(d + 0.8)
    x = A.mix_at(x, _mallet(N("D3"), d, 1.3, 0.2), 0.0, 0.3)
    x = A.mix_at(x, _mallet(N("D4"), d, 1.1, 0.25), 0.0, 0.5)
    pad = np.zeros(len(t))
    entries = [("D3", 0.0, 1.0), ("A3", 0.07, 0.9), ("D4", 0.14, 0.8), ("F#4", 0.21, 0.7),
               ("A4", 0.28, 0.6), ("D5", 0.35, 0.45)]
    for k, (nm, at, g) in enumerate(entries):
        dv = d - at
        tv = _t(dv)
        v = A.osc("saw", N(nm) * 0.996, dv, phase=1.3 * k) + A.osc("saw", N(nm) * 1.004, dv, phase=2.9 * k + 1)
        env = (1 - np.exp(-tv / 0.09)) * np.where(tv + at < 0.6, 1.0, np.exp(-6.9078 * (tv + at - 0.6) / 1.0))
        pad = A.mix_at(pad, v * env, at, g)
    pad = _fit(pad, d)
    open_ = np.where(t < 0.6, 350 * (2000 / 350) ** (t / 0.6), 2000 * (800 / 2000) ** ((t - 0.6) / (d - 0.6)))
    pad = _svf(pad / 8.0, open_, 0.8, "lp")
    x = A.mix_at(x, pad, 0.0, 1.0)
    shimmer = np.zeros(len(t))
    for f, ph in ((N("A5"), 0.0), (N("D6"), 1.7)):
        shimmer += np.sin(TAU * f * t) * (1 + 0.35 * np.sin(TAU * 5.5 * t + ph))
    shimmer *= np.clip((t - 0.25) / 0.3, 0, 1) ** 2 * np.exp(-np.clip(t - 0.6, 0, None) * 3.5)
    x = A.mix_at(x, shimmer, 0.0, 0.03)
    x = _verb(x, 0.6, 0.22, 0.6)
    return _finish(x, d, 0.45, lp=6000)


def _heal_holy() -> np.ndarray:
    """A choir sings out a D major chord as a run of glass chimes climbs into the light."""
    d = 1.58
    t = _t(d)
    x = _buf(d + 1.2)
    run = ["A5", "B5", "D6", "E6", "F#6", "A6", "B6", "D7"]
    for k, nm in enumerate(run):
        last = k == len(run) - 1
        p = _ping(N(nm), 1.3 if last else 0.7, 2.76, 0.12)
        x = A.mix_at(x, p, 0.052 * k, (0.5 + 0.03 * k) * (1.2 if last else 1.0))
    ch = _choir([N("D4"), N("A4"), N("D5"), N("F#5")], d, 701)
    ch *= _swell(d, 0.07, 0.75, 0.9)
    x = A.mix_at(x, _norm(ch), 0.0, 0.55)
    x = _verb(x, 0.75, 0.3, 0.5)
    return _finish(x, d, 0.5, lp=7000)


def _heal_bubbles() -> np.ndarray:
    """A potion bubbles up: a warm bloop, then bubbles climbing in pitch to the surface,
    and a small clink of the glass."""
    d = 1.5
    t = _t(d)
    x = _buf(d + 0.8)
    rng = np.random.default_rng(801)
    x = A.mix_at(x, _bubble(N("D4"), 0.1, 0.45), 0.0, 0.8)
    x = A.mix_at(x, _bubble(N("A4"), 0.12, 0.5), 0.045, 0.55)
    scale = [N(n) for n in ("D5", "E5", "F#5", "A5", "B5", "D6", "E6", "F#6", "A6")]
    count = 15
    for k in range(count):
        u = k / (count - 1)
        at = 0.08 + 0.78 * u ** 0.85 + rng.uniform(-0.012, 0.012)
        pos = u * (len(scale) - 1) + rng.uniform(-1.2, 1.2)
        f = scale[int(np.clip(round(pos), 0, len(scale) - 1))] * rng.uniform(0.985, 1.0)
        g = rng.uniform(0.35, 0.65) * (1.0 - 0.3 * u)
        x = A.mix_at(x, _bubble(f, rng.uniform(0.1, 0.2), rng.uniform(0.45, 0.65)), at, g)
    warm = (np.sin(TAU * N("D4") * t) + 0.6 * np.sin(TAU * N("A4") * t)) * _swell(d, 0.25, 0.6, 0.9)
    x = A.mix_at(x, warm, 0.0, 0.08)
    x = A.mix_at(x, _ping(N("D6"), 0.9, 2.32, 0.1), 0.9, 0.22)
    x = A.mix_at(x, _ping(N("A6"), 0.7, 2.32, 0.08), 0.96, 0.14)
    x = _verb(x, 0.3, 0.16, 0.6)
    return _finish(x, d, 0.4, lp=7000)


def _heal_pixel() -> np.ndarray:
    """An 8-bit cure: quick rising arpeggios that climb a step at a time, with an echo,
    landing on a high D that wavers and fades."""
    d = 1.4
    groups = [("D5", "F#5", "A5", "D6"), ("E5", "A5", "B5", "E6"), ("F#5", "A5", "D6", "F#6"),
              ("A5", "D6", "F#6", "A6")]
    steps = []
    for gi, grp in enumerate(groups):
        for nm in grp:
            steps.append((nm, 2, 9 + gi))
    hold = [12, 12, 11, 11, 10, 10, 9, 9, 8, 8, 7, 7, 6, 6, 5, 5, 4, 4, 3, 3, 2, 2, 1, 1]
    steps.append(("D6", len(hold), hold))
    fr, lv = _seq(steps)
    f = _frames(fr, d)
    nf = int(len(fr))
    vib = np.where(np.arange(len(f)) / SR * FPS > 32,
                   1 + 0.012 * np.sign(np.sin(TAU * 7.5 * _t(d))), 1.0)
    lead = _pulse(f * vib, 0.25) * _vol(lv, d, 0.08)
    echo_lv = [0.0] * 4 + [v * 0.45 for v in lv]
    echo_f = _frames([fr[0]] * 4 + fr, d)
    echo = _pulse(echo_f, 0.5) * _vol(echo_lv, d, 0.08)
    bass_steps = [("D3", 8, 10), ("E3", 8, 10), ("F#3", 8, 10), ("A3", 8, 10), ("D4", 14, 10)]
    bfr, blv = _seq(bass_steps)
    bass = _tri4(_frames(bfr, d)) * _vol(blv, d, 0.12)
    x = 0.5 * lead + 0.35 * echo + 0.55 * bass
    del nf
    return _finish(_chip(x), d, 0.15)


# ============================================================================= double (Warrior)
def _double_twin() -> np.ndarray:
    """Two sword blows in quick succession: a ringing strike, the swish of the second
    swing, and a harder strike a fourth higher."""
    d = 1.1
    x = _buf(d + 0.8)
    x = A.mix_at(x, _blade(N("A4"), 0.9, 201, 0.8), 0.0, 0.6)
    sw_d = 0.13
    ts = _t(sw_d)
    sw = _bp2(A.noise(sw_d, "pink", 205), A.glide(600, 2200, sw_d), 1.6)
    sw = A.lowpass(sw, 4500, 2) * (ts / sw_d) ** 2 * np.minimum(1.0, (sw_d - ts) / 0.01)
    x = A.mix_at(x, _norm(sw), 0.05, 0.2)
    x = A.mix_at(x, _blade(N("D5"), 1.0, 211, 1.2), 0.18, 1.0)
    x = _verb(x, 0.35, 0.14)
    x = _glue(x, 16)
    return _finish(x, d, 0.35, lp=7500)


def _double_surge() -> np.ndarray:
    """Power gathers in a quick rising surge and bursts in a bright doubled flash: two
    hits an octave apart, sparkling as they ring."""
    d = 1.15
    rise = 0.36
    x = _buf(d + 1.0)
    t = _t(rise)
    f = A.glide(N("D3"), N("D4"), rise)
    saw = A.osc("saw", f * 0.994, rise) + A.osc("saw", f * 1.006, rise, 1.1)
    r = _svf(saw, 250 * (2800 / 250) ** (t / rise), 1.6, "lp")
    trate = 8 + 18 * (t / rise)
    trem = 1 - 0.3 * (0.5 + 0.5 * np.sin(TAU * np.cumsum(trate) / SR))
    nz = _bp2(A.noise(rise, "pink", 301), 500 * (3000 / 500) ** (t / rise), 1.4)
    amp = (0.35 + 0.65 * (t / rise) ** 1.5) * np.minimum(1.0, (rise - t) / 0.012)
    riser = A.lowpass(0.55 * _norm(r) + 0.15 * _norm(nz), 5000, 2) * amp * trem
    x = A.mix_at(x, riser, 0.0, 0.8)
    x = A.mix_at(x, _thump(180, 120, 0.03, 0.1, 0.3, 1.5), 0.0, 0.25)
    hits = ((rise, ("D4", "A4", "D5"), 0.8), (rise + 0.1, ("D5", "A5", "D6"), 1.0))
    for k, (at, notes, g) in enumerate(hits):
        x = A.mix_at(x, _thump(220, 110, 0.04, 0.22, 0.7, 2.2), at, 0.4 * g)
        for nm in notes:
            x = A.mix_at(x, A.bell(N(nm), 0.9, ratio=2.0, index=1.5, t60=0.75), at, 0.22 * g)
        x = A.mix_at(x, _burst(0.02, 1500, 5500, 0.008, 310 + k), at, 0.3 * g)
    sp = _sparkle(0.6, 9, 0.0, 0.5, 333)
    x = A.mix_at(x, sp, rise + 0.12, 0.1)
    x = _verb(x, 0.5, 0.2)
    x = _glue(x, 15)
    return _finish(x, d, 0.35, lp=7000)


SPARK = [N(n) for n in ("D7", "E7", "F#7", "A7")]


def _sparkle(d: float, count: int, t0: float, t1: float, seed: int, notes: Sequence[float] = SPARK,
             t60: Tuple[float, float] = (0.08, 0.22)) -> np.ndarray:
    """A cloud of tiny high pings on D pentatonic notes (magic dust), fading as it falls."""
    rng = np.random.default_rng(seed)
    y = _buf(d + 0.3)
    times = np.sort(t0 + (t1 - t0) * rng.random(count))
    for tt in times:
        f = float(rng.choice(notes)) * (1 + rng.uniform(-0.002, 0.002))
        amp = rng.uniform(0.4, 1.0) * (1 - 0.6 * (tt - t0) / max(1e-6, t1 - t0))
        y = A.mix_at(y, _ping(f, rng.uniform(*t60), pgain=0.0), tt, amp)
    return _fit(y, d)


def _double_drums() -> np.ndarray:
    """Two war drums: a strong boom, a grace flam, and a bigger, deeper BOOM."""
    d = 1.15
    x = _buf(d + 1.0)
    x = A.mix_at(x, _taiko(N("A2"), 0.9, 401, 0.6, 2.2), 0.0, 0.65)
    x = A.mix_at(x, _stick(0.06, 403), 0.0, 0.3)
    x = A.mix_at(x, _taiko(N("D3"), 0.3, 405, 0.2, 1.6), 0.19, 0.25)
    x = A.mix_at(x, _taiko(N("D2"), 1.1, 402, 0.85, 2.6), 0.22, 1.0)
    x = A.mix_at(x, _stick(0.06, 404), 0.22, 0.35)
    x = _verb(x, 0.6, 0.18, 0.4)
    x = _glue(x, 15)
    return _finish(x, d, 0.4, lp=7000)


def _stick(d: float, seed: int) -> np.ndarray:
    """A wooden drumstick catching the rim: a hard tick on a small wooden resonance."""
    rng = np.random.default_rng(seed)
    nb = _n(0.0015)
    burst = rng.uniform(-1, 1, nb) * np.hanning(nb)
    return _norm(_excite(burst, [(980, 1.0, 0.03), (1720, 0.5, 0.02), (2900, 0.25, 0.012)], d))


def _double_horn() -> np.ndarray:
    """A war horn calls twice as strong: a short A, then a long swelling D, doubled at
    the octave below by a second horn."""
    d = 1.15
    t = _t(d)
    x = _buf(d + 0.9)
    on2 = 0.17
    for k, (mult, g, sd) in enumerate(((1.0, 1.0, 501), (0.5, 0.6, 502))):
        f = _line([(0.0, N("A3") * mult), (on2, N("D4") * mult)], d, 0.008)
        scoop = 1 - 0.018 * (np.exp(-t / 0.025) + np.where(t >= on2, np.exp(-np.clip(t - on2, 0, None) / 0.025), 0))
        vib = 1 + 0.004 * np.clip((t - 0.5) / 0.2, 0, 1) * np.sin(TAU * 5.2 * t + k)
        a1 = np.where(t < on2 - 0.02, 0.75 * (1 - np.exp(-t / 0.008)), 0.0)
        a1 *= np.where(t < on2 - 0.04, 1.0, np.clip((on2 - 0.02 - t) / 0.02, 0, 1))
        t2 = np.clip(t - on2, 0, None)
        a2 = np.where(t >= on2, (1 - np.exp(-t2 / 0.012)) * (0.8 + 0.25 * np.clip(t2 / 0.3, 0, 1)), 0.0)
        a2 *= np.where(t < 0.78, 1.0, np.exp(-(t - 0.78) / 0.09))
        amp = a1 + a2
        y = _brass(f * scoop * vib, amp, sd, 2200 if k == 0 else 1300, (0.0, on2))
        x = A.mix_at(x, y, 0.0, g)
    x = _verb(x, 0.65, 0.22, 0.5)
    return _finish(x, d, 0.3, lp=6500)


def _double_pixel() -> np.ndarray:
    """An 8-bit power-up: rising arpeggios climbing two octaves, then a doubled ding-ding."""
    d = 1.0
    groups = [("D4", "A4", "D5"), ("E4", "B4", "E5"), ("F#4", "D5", "F#5"), ("A4", "E5", "A5"),
              ("D5", "A5", "D6")]
    steps = []
    for gi, grp in enumerate(groups):
        for j, nm in enumerate(grp):
            steps.append((nm, 2, 13 if j == 0 else 10))
    steps.append((None, 2, 0))
    steps.append(("A5", 2, 13))
    steps.append(("D6", 5, [14, 12, 10, 9, 8]))
    steps.append((None, 2, 0))
    steps.append(("A5", 2, 13))
    steps.append(("D6", 14, [15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2]))
    fr, lv = _seq(steps)
    lead = _pulse(_frames(fr, d), 0.5) * _vol(lv, d, 0.07)
    bfr, blv = _seq([("D3", 6, 10), ("E3", 6, 10), ("F#3", 6, 10), ("A3", 6, 10), ("D4", 6, 10),
                     (None, 2, 0), ("D3", 9, 10), (None, 2, 0), ("D3", 14, 10)])
    bass = _tri4(_frames(bfr, d)) * _vol(blv, d, 0.08)
    x = 0.5 * lead + 0.6 * bass
    return _finish(_chip(x), d, 0.12)


# ============================================================================= shield (Paladin)
def _shield_bash() -> np.ndarray:
    """A blow lands on a round wooden shield: the planks thud, the iron boss clanks and
    the rim rattles."""
    d = 0.95
    x = _buf(d + 0.8)
    rng = np.random.default_rng(551)
    nb = _n(0.005)
    burst = A.lowpass(rng.uniform(-1, 1, nb), 2500, 1) * np.hanning(nb)
    wood = _excite(burst, [(158, 1.0, 0.14), (236, 0.9, 0.12), (351, 0.75, 0.1), (497, 0.5, 0.08),
                           (668, 0.38, 0.06), (873, 0.25, 0.05)], d)
    x = A.mix_at(x, _norm(wood), 0.0, 0.9)
    x = A.mix_at(x, _thump(130, 80, 0.03, 0.13, d, 1.8), 0.0, 0.75)
    x = A.mix_at(x, _burst(0.012, 700, 4500, 0.005, 552), 0.0, 0.5)
    boss = _modes(N("A5"), [1.0, 1.48, 2.13, 2.71, 3.36], [1.0, 0.7, 0.5, 0.3, 0.2],
                  [0.35, 0.28, 0.2, 0.15, 0.1], d, beat=0.002)
    x = A.mix_at(x, boss, 0.0, 0.28)
    x = A.mix_at(x, boss, 0.032, 0.09)
    x = A.mix_at(x, boss, 0.058, 0.05)
    x = _verb(x, 0.3, 0.12)
    x = _glue(x, 15)
    return _finish(x, d, 0.3, lp=7000)


def _shield_steel() -> np.ndarray:
    """A steel shield takes a firm blow and rings out on D, its tones slowly beating."""
    d = 1.2
    x = _buf(d + 0.6)
    ratios = [1.0, 1.59, 2.14, 3.0, 3.42, 4.2, 5.03, 6.1]
    gains = [1.0, 0.45, 0.5, 0.65, 0.3, 0.22, 0.15, 0.1]
    t60s = [1.3, 0.9, 0.85, 1.0, 0.6, 0.45, 0.35, 0.28]
    ring = _modes(N("D4"), ratios, gains, t60s, d + 0.3, beat=0.0025)
    x = A.mix_at(x, ring, 0.0, 1.0)
    x = A.mix_at(x, _burst(0.008, 2000, 7000, 0.003, 601), 0.0, 0.6)
    x = A.mix_at(x, _thump(200, 120, 0.02, 0.08, 0.4, 1.5), 0.0, 0.5)
    x = _verb(x, 0.4, 0.15)
    x = _glue(x, 16)
    return _finish(x, d, 0.4, lp=7500)


def _shield_hum() -> np.ndarray:
    """A magic ward hums into place: a soft whump, then a low chord that glows, phases
    and settles."""
    d = 1.2
    t = _t(d)
    x = _buf(d + 0.8)
    x = A.mix_at(x, _thump(240, 147, 0.04, 0.18, 0.4, 1.4), 0.0, 0.6)
    x = A.mix_at(x, _burst(0.08, 400, 2000, 0.06, 651), 0.0, 0.18)
    hum = np.zeros(len(t))
    for k, (nm, g) in enumerate((("D3", 1.0), ("A3", 0.8), ("D4", 0.6), ("F#4", 0.25))):
        for j, det in enumerate((-0.003, 0.0, 0.003)):
            hum += g * A.osc("saw", N(nm) * (1 + det), d, phase=0.9 * k + 2.3 * j)
    fc = np.where(t < 0.15, 450 * (1500 / 450) ** (t / 0.15), 1500 * (600 / 1500) ** ((t - 0.15) / (d - 0.15)))
    hum = _svf(hum / 10.0, fc, 1.1, "lp")
    hum *= _swell(d, 0.045, 0.55, 0.9)
    x = A.mix_at(x, hum, 0.0, 1.0)
    glow = np.zeros(len(t))
    for f, ph in ((N("F#5"), 0.0), (N("A5"), 2.0)):
        glow += np.sin(TAU * f * t) * (1 + 0.5 * np.sin(TAU * 6.0 * t + ph))
    glow *= np.clip(t / 0.15, 0, 1) * np.exp(-6.9078 * t / 1.0)
    x = A.mix_at(x, glow, 0.0, 0.05)
    x = A.chorus(x, 0.7, 0.35, 0.4)
    x = _verb(x, 0.55, 0.2)
    return _finish(x, d, 0.4, lp=6000)


def _shield_crystal() -> np.ndarray:
    """A crystal dome closes over you: a struck glass rings on A and D, and its singing
    tone shimmers on."""
    d = 1.2
    t = _t(d)
    x = _buf(d + 0.9)
    glass = [1.0, 2.32, 4.25, 6.63]
    x = A.mix_at(x, _modes(N("A5"), glass, [1.0, 0.35, 0.15, 0.06], [1.1, 0.5, 0.25, 0.15], d,
                           beat=0.0012), 0.0, 0.6)
    x = A.mix_at(x, _modes(N("D6"), glass, [1.0, 0.3, 0.12, 0.05], [1.0, 0.45, 0.2, 0.12], d,
                           beat=0.0015), 0.004, 0.4)
    x = A.mix_at(x, _burst(0.006, 2500, 7000, 0.003, 701), 0.0, 0.25)
    sing = np.zeros(len(t))
    for f, g in ((N("D5"), 1.0), (N("A5"), 0.7), (N("D6"), 0.4)):
        sing += g * 0.5 * (np.sin(TAU * (f - 0.7) * t) + np.sin(TAU * (f + 0.7) * t + 1.0))
    sing *= _swell(d, 0.12, 0.45, 1.1)
    x = A.mix_at(x, sing, 0.0, 0.22)
    sw_d = 0.3
    ts = _t(sw_d)
    sw = _svf(A.noise(sw_d, "white", 702), 5000 * (1200 / 5000) ** (ts / sw_d), 1.5, "bp")
    sw = _norm(sw) * np.sin(math.pi * ts / sw_d) ** 2
    x = A.mix_at(x, sw, 0.0, 0.08)
    x = _verb(x, 0.6, 0.28)
    return _finish(x, d, 0.4, lp=7500)


def _shield_pixel() -> np.ndarray:
    """An 8-bit shield: a metallic clang of noise, a quick rising sweep, then a shimmering
    two-note hum that fades."""
    d = 1.0
    nlv = [15, 12, 9, 6, 4, 2, 1]
    noise = _lfsr(np.full(_n(d), 93000.0), short=True, seed=3) * _vol(nlv, d, 0.03)
    sweep = [("D4", 1, 12), ("F#4", 1, 12), ("A4", 1, 12), ("D5", 1, 12), ("F#5", 1, 12), ("A5", 1, 12)]
    shimmer = []
    lev = [12, 12, 11, 11, 10, 10, 9, 9, 8, 8, 7, 7, 6, 6, 5, 5, 4, 4, 3, 3, 2, 2, 1, 1]
    for i, l in enumerate(lev):
        shimmer.append(("A5" if i % 2 == 0 else "D6", 1, l))
    fr, lv = _seq(sweep + shimmer)
    lead = _pulse(_frames(fr, d), 0.25) * _vol(lv, d, 0.08)
    bfr, blv = _seq([("D3", 8, 12), ("D3", 22, [12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1])])
    bass = _tri4(_frames(bfr, d)) * _vol(blv, d, 0.08)
    x = 0.25 * noise + 0.45 * lead + 0.55 * bass
    return _finish(_chip(x), d, 0.12)


# ============================================================================= blocked (immune)
def _blocked_clank() -> np.ndarray:
    """A dull, muffled clank: the blow lands on padded armour and dies at once."""
    d = 0.6
    x = _buf(d + 0.4)
    ratios = [1.0, 1.71, 2.53, 3.48, 4.62]
    plate = _modes(N("A3"), ratios, [1.0, 0.7, 0.45, 0.25, 0.15], [0.2, 0.13, 0.09, 0.07, 0.05], d,
                   beat=0.003)
    x = A.mix_at(x, plate, 0.0, 0.7)
    x = A.mix_at(x, _burst(0.015, 150, 1800, 0.008, 801), 0.0, 0.5)
    x = A.mix_at(x, _thump(150, 100, 0.03, 0.09, d, 1.6), 0.0, 0.6)
    x = A.mix_at(x, plate, 0.05, 0.12)
    x = A.lowpass(x, 2600, 2)
    x = _verb(x, 0.25, 0.1)
    x = _glue(x, 14)
    return _finish(x, d, 0.25, lp=4000)


def _blocked_fizzle() -> np.ndarray:
    """A spell fizzles out: a soft magic note sags and wobbles down while a few weak
    sparks sputter and die."""
    d = 0.9
    t = _t(d)
    x = _buf(d + 0.5)
    rng = np.random.default_rng(851)
    f = N("A4") * (N("D4") / N("A4")) ** np.clip(t / 0.4, 0, 1) ** 0.8
    vr = 9 - 6 * np.clip(t / 0.5, 0, 1)
    f = f * (1 + 0.018 * np.sin(TAU * np.cumsum(vr) / SR))
    ph = TAU * np.cumsum(f) / SR
    tone = (np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph)) * A.adsr(d, 0.004, 0.05, 0.7, 0.0)
    tone *= np.exp(-6.9078 * t / 0.6)
    x = A.mix_at(x, tone, 0.0, 0.55)
    puff = _bn(0.15, 700, 3000, 852, "pink") * A.decay(0.15, 0.09, 0.002)
    x = A.mix_at(x, puff, 0.0, 0.3)
    fz_d = 0.4
    tz = _t(fz_d)
    grains = np.repeat(rng.uniform(0.2, 1.0, int(fz_d * 400) + 1), int(SR / 400) + 1)[:len(tz)]
    fizz = _bn(fz_d, 1500, 4500, 853) * grains * np.exp(-6.9078 * tz / 0.3) * np.clip(tz / 0.01, 0, 1)
    x = A.mix_at(x, fizz, 0.0, 0.18)
    tt = 0.03
    k = 0
    while tt < 0.6:
        g = 0.5 * (1 - tt / 0.65) * rng.uniform(0.5, 1.0)
        fc = rng.uniform(1600, 3600)
        x = A.mix_at(x, _norm(_reson(_fit(np.array([1.0]), 0.03), fc, 0.012)), tt, g * 0.4)
        tt += rng.uniform(0.02, 0.05) * (1 + 3 * tt)
        k += 1
    x = _verb(x, 0.3, 0.12)
    return _finish(x, d, 0.3, lp=5500)


def _blocked_knock() -> np.ndarray:
    """Two dull knocks on a heavy wooden door, the second lower: nothing gets through."""
    d = 0.7
    x = _buf(d + 0.5)
    x = A.mix_at(x, _knock(N("A4"), 0.4, 901), 0.0, 0.9)
    x = A.mix_at(x, _knock(N("F4"), 0.4, 902, 1.2), 0.17, 0.75)
    x = _verb(x, 0.3, 0.1)
    x = _glue(x, 15)
    return _finish(x, d, 0.25, lp=5000)


def _blocked_stone() -> np.ndarray:
    """The blow lands on solid stone: a deep dull thud and a little grit trickling down."""
    d = 0.8
    x = _buf(d + 0.4)
    rng = np.random.default_rng(951)
    x = A.mix_at(x, _thump(105, 62, 0.035, 0.2, d, 2.6), 0.0, 0.9)
    body = A.lowpass(A.noise(0.25, "brown", 952), 900, 2)
    x = A.mix_at(x, _norm(body) * A.decay(0.25, 0.12, 0.0005), 0.0, 0.45)
    x = A.mix_at(x, _burst(0.03, 500, 2500, 0.02, 953), 0.0, 0.4)
    tt = 0.05
    while tt < 0.55:
        g = 0.3 * (1 - tt / 0.6) * rng.uniform(0.4, 1.0)
        fc = rng.uniform(1200, 3200)
        nb = _n(0.001)
        click = _excite(rng.uniform(-1, 1, nb), [(fc, 1.0, 0.015), (fc * 1.7, 0.4, 0.01)], 0.03)
        x = A.mix_at(x, _norm(click), tt, g)
        tt += rng.uniform(0.015, 0.06) * (1 + 2 * tt)
    grit_d = 0.4
    tg = _t(grit_d)
    grains = A.lowpass(np.repeat(rng.uniform(0, 1, int(grit_d * 300) + 1) ** 3, int(SR / 300) + 1)[:len(tg)], 300, 1)
    grit = _bn(grit_d, 900, 3500, 954, "pink") * grains * np.exp(-6.9078 * tg / 0.35)
    x = A.mix_at(x, _norm(grit), 0.02, 0.1)
    x = _verb(x, 0.25, 0.08)
    x = _glue(x, 15)
    return _finish(x, d, 0.25, lp=5000)


def _blocked_pixel() -> np.ndarray:
    """An 8-bit dud: a soft puff and two low blips sagging downwards."""
    d = 0.6
    nlv = [8, 6, 4, 2, 1]
    noise = _lfsr(np.full(_n(d), 7000.0), short=False, seed=5) * _vol(nlv, d, 0.03)
    steps = [("A3", 2, 12), ("G#3", 2, 11), ("G3", 2, 9), (None, 2, 0),
             ("F3", 2, 12), ("E3", 2, 11), ("D#3", 2, 10), ("D3", 8, [9, 8, 7, 6, 5, 4, 3, 2])]
    fr, lv = _seq(steps)
    f = _frames(fr, d)
    tri = _tri4(f) * _vol(lv, d, 0.06)
    sq = _pulse(f * 2, 0.5) * _vol([v * 0.4 for v in lv], d, 0.06)
    x = 0.2 * noise + 0.7 * tri + 0.3 * sq
    return _finish(_chip(x), d, 0.12)


# ============================================================================= the list
CANDIDATES = [
    # heal: warm, restorative, rising
    Candidate("power_heal", "harp_rise", "Harp rise", "A harp sweeps gently up a warm chord and lets it ring.",
              _heal_harp, ["acoustic", "warm"]),
    Candidate("power_heal", "warm_glow", "Warm glow", "A soft mallet note blooms into a warm, glowing swell.",
              _heal_glow, ["soft", "subtle"]),
    Candidate("power_heal", "holy_light", "Holy light", "A choir sings out as bright chimes climb upward.",
              _heal_holy, ["magical", "chimey"]),
    Candidate("power_heal", "potion_bubbles", "Potion bubbles",
              "A healing potion bubbles up, rising to a tiny glass clink.", _heal_bubbles, ["playful", "liquid"]),
    Candidate("power_heal", "pixel_cure", "Pixel cure", "A retro 8-bit healing jingle that climbs and sparkles.",
              _heal_pixel, ["8-bit", "retro"]),
    # double: a power-up, a doubled strike
    Candidate("power_double", "twin_strike", "Twin strike",
              "Two quick sword blows, the second one harder and ringing.", _double_twin, ["realistic", "metal"]),
    Candidate("power_double", "power_surge", "Power surge",
              "Energy gathers fast and bursts in a bright double flash.", _double_surge, ["magical"]),
    Candidate("power_double", "war_drums", "War drums", "Two big drums: boom, then a bigger BOOM.",
              _double_drums, ["wooden", "deep"]),
    Candidate("power_double", "war_horn", "War horn", "A battle horn calls out, doubled by a second horn.",
              _double_horn, ["heroic", "brass"]),
    Candidate("power_double", "pixel_power", "Pixel power-up",
              "A retro 8-bit power-up climb with a double ding at the top.", _double_pixel, ["8-bit", "retro"]),
    # shield: a metallic bash or a protective hum
    Candidate("power_shield", "shield_bash", "Shield bash",
              "A blow thuds into a wooden shield with an iron clank.", _shield_bash, ["realistic", "wooden"]),
    Candidate("power_shield", "steel_ring", "Steel ring", "A steel shield is struck and rings out.",
              _shield_steel, ["metal", "ringing"]),
    Candidate("power_shield", "ward_hum", "Ward hum", "A magic ward hums into place around you.",
              _shield_hum, ["magical", "soft"]),
    Candidate("power_shield", "crystal_ward", "Crystal ward",
              "A glassy dome closes over you with a clear, singing ring.", _shield_crystal, ["chimey", "magical"]),
    Candidate("power_shield", "pixel_shield", "Pixel shield",
              "A retro 8-bit clang and a shimmering shield tone.", _shield_pixel, ["8-bit", "retro"]),
    # blocked: no effect, dull, never harsh
    Candidate("power_blocked", "muffled_clank", "Muffled clank",
              "A dull clank, as if the blow hit padded armour.", _blocked_clank, ["realistic", "dull"]),
    Candidate("power_blocked", "fizzle", "Fizzle", "A spell sags and sputters out with a few weak sparks.",
              _blocked_fizzle, ["magical"]),
    Candidate("power_blocked", "dull_knock", "Dull knock",
              "Two dull knocks on a heavy door, the second lower: nothing gets through.", _blocked_knock,
              ["wooden", "soft"]),
    Candidate("power_blocked", "stone_wall", "Stone wall",
              "A deep thud against solid stone, with a little grit falling.", _blocked_stone, ["realistic", "deep"]),
    Candidate("power_blocked", "pixel_dud", "Pixel dud", "A retro 8-bit puff and two sagging blips.",
              _blocked_pixel, ["8-bit", "retro"]),
]
