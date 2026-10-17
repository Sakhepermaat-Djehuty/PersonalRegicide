"""Combat sounds: the blow that lands, the enemy's fall, the exact kill that wins its card,
the next enemy's arrival, the enemy's strike back, the Jester and the yield.

Five candidates per event, each a different character (a real one, a soft one, a wooden or
tavern one, a magical one, an 8-bit one). Tonal parts are tuned to D: D major pentatonic,
or D dorian (with F natural) for the darker ones. A phone speaker plays little below about
200 Hz, so every heavy impact also carries harmonics between 150 and 500 Hz: the weight
still comes through on the phone, and the deep part is there for headphones.

Private helpers here (the shared toolkit is not edited):
  _modes / _reson     modal synthesis (struck metal, wood, membranes)
  _svf                a filter whose cutoff can move (whooshes, brass, scrapes)
  _ks                 a plucked string tuned exactly (synth.pluck runs a little flat)
  _pulse / _tri4 / _lfsr / _frames   the 8-bit voices with 60 Hz frame-stepped control
  _ping / _sparkle / _jingle         small bells, sparkles and jingle bells
  _finish             cut to length with a natural fade and the band limits
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


# ============================================================================= helpers
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
    """Soft saturation (tape-like): adds harmonics so a low thump reads on a small speaker."""
    return np.tanh(drive * _norm(x)) / math.tanh(drive)


def _bn(d: float, lo: float, hi: float, seed: int, color: str = "white", order: int = 2) -> np.ndarray:
    """Band-limited noise, peak-normalised so gains mean the same as for tones."""
    return _norm(A.bandpass(A.noise(d, color, seed), lo, hi, order))


def _hold(f0: float, f1: float, drop: float, d: float) -> np.ndarray:
    """A pitch that falls from f0 to f1 over ``drop`` seconds, then holds (length d)."""
    g = A.glide(f0, f1, drop)
    return np.concatenate([g, np.full(max(0, _n(d) - len(g)), f1)])[:_n(d)]


def _thump(f0: float, f1: float, drop: float, t60: float, d: float, drive: float = 0.0) -> np.ndarray:
    y = A.sine(_hold(f0, f1, drop, d), d) * A.decay(d, t60, 0.0006)
    return _sat(y, drive) * float(np.max(np.abs(y))) if drive else y


def _finish(x: np.ndarray, total: float, fade: float, hp: float = 35.0, lp: float = 0.0) -> np.ndarray:
    """Cut to ``total`` seconds and fade the last ``fade`` seconds with a half cosine;
    a high-pass removes rumble no one hears, a low-pass (if given) keeps the top gentle."""
    y = _fit(x, total)
    y = A.highpass(y, hp, 2)
    if lp:
        y = A.lowpass(y, lp, 4)
    nf = _n(fade)
    y[-nf:] *= 0.5 * (1 + np.cos(np.linspace(0, math.pi, nf)))
    return y


def _verb(x: np.ndarray, room: float, wet: float, damping: float = 0.5, tail: float = 1.0) -> np.ndarray:
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
    """Hold a hit's first peaks to ``crest_db`` above its loudness with a fast limiter.
    Its quick release only touches the attack, where the master's slower limiter would
    instead turn the whole ring down after the hit."""
    y = _norm(x)
    for _ in range(4):
        ceil = _loudness(y) + crest_db
        if 20 * math.log10(np.max(np.abs(y))) <= ceil + 0.2:
            break
        y = A.limit(y, ceil, lookahead=0.0015, release=release)
    return y


def _bp2(x: np.ndarray, fc, q: float = 1.0) -> np.ndarray:
    """Two moving band-passes in a row: a focused band with steep sides (no hiss above)."""
    return _svf(_svf(x, fc, q, "bp"), fc, q, "bp")


def _modes(f0: float, ratios: Sequence[float], gains: Sequence[float], t60s: Sequence[float], d: float,
           beat: float = 0.0, attack: float = 0.0004, fmax: float = 7800.0) -> np.ndarray:
    """Struck-object modes: decaying sines at f0 x ratio. ``beat`` splits each mode into a
    slightly detuned pair (the slow shimmer of real metal)."""
    t = _t(d)
    y = np.zeros(len(t))
    for r, g, T in zip(ratios, gains, t60s):
        f = f0 * r
        if f > fmax or g == 0:
            continue
        e = np.exp(-6.9078 * t / T)
        if beat:
            s = 0.5 * (np.sin(TAU * f * (1 - beat) * t) + np.sin(TAU * f * (1 + beat) * t + 0.7))
        else:
            s = np.sin(TAU * f * t)
        y += g * s * e
    na = _n(attack)
    if na:
        y[:na] *= np.linspace(0, 1, na)
    return y


def _reson(x: np.ndarray, f: float, t60: float) -> np.ndarray:
    """A two-pole resonator ringing at f for t60 seconds (an impulse gives a unit sine)."""
    w = TAU * f / SR
    r = 0.001 ** (1.0 / (t60 * SR))
    return signal.lfilter([math.sin(w)], [1.0, -2 * r * math.cos(w), r * r], x)


def _excite(burst: np.ndarray, modes: Sequence[Tuple[float, float, float]], d: float) -> np.ndarray:
    """Drive a bank of (freq, gain, t60) resonators with a short burst."""
    ex = _fit(burst, d)
    return sum(g * _reson(ex, f, T) for f, g, T in modes)


def _svf(x: np.ndarray, fc, q: float = 0.707, mode: str = "bp") -> np.ndarray:
    """A state-variable filter (topology-preserving) whose cutoff ``fc`` may change every
    sample. 'bp' has unit gain at the centre."""
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
    burst = A.lowpass(burst, 500 + 8000 * bright, 1)
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
    y[:_n(0.0005)] *= np.linspace(0, 1, _n(0.0005))
    return y


def _ping(f: float, t60: float, partial: float = 2.76, pgain: float = 0.2, d: float = 0.0) -> np.ndarray:
    """A small bell or glass ping: a fundamental and one inharmonic partial."""
    d = d or min(t60 * 1.1, 2.5)
    t = _t(d)
    y = np.sin(TAU * f * t) * np.exp(-6.9078 * t / t60)
    if pgain and f * partial < 7800:
        y += pgain * np.sin(TAU * f * partial * t) * np.exp(-6.9078 * t / (t60 * 0.4))
    na = _n(0.0003)
    y[:na] *= np.linspace(0, 1, na)
    return y


SPARK = [N(n) for n in ("D7", "E7", "F#7", "A7", "B7", "D8")]


def _sparkle(d: float, count: int, t0: float, t1: float, seed: int, notes: Sequence[float] = SPARK,
             t60: Tuple[float, float] = (0.08, 0.25), shape: float = 1.0, fall: float = 0.6) -> np.ndarray:
    """A cloud of tiny high pings on D pentatonic notes (magic dust)."""
    rng = np.random.default_rng(seed)
    y = _buf(d)
    times = t0 + (t1 - t0) * rng.random(count) ** shape
    for tt in np.sort(times):
        f = float(rng.choice(notes)) * (1 + rng.uniform(-0.002, 0.002))
        T = rng.uniform(*t60)
        amp = rng.uniform(0.4, 1.0) * (1 - fall * (tt - t0) / max(1e-6, t1 - t0))
        y = A.mix_at(y, _ping(f, T, pgain=0.0), tt, amp)
    return _fit(y, d)


def _jingle(y: np.ndarray, t0: float, strength: float, rng, bells: int = 6, spread: float = 0.035) -> np.ndarray:
    """One shake of a string of jingle bells: each bell's pellet strikes it two to four
    times in quick succession; the bells are small spheres with inharmonic partials."""
    for _ in range(bells):
        f1 = rng.uniform(2150, 2700)
        T = rng.uniform(0.22, 0.38)
        rat = [1.0, 1.58 * rng.uniform(0.98, 1.02), 2.15 * rng.uniform(0.98, 1.02), 2.71 * rng.uniform(0.98, 1.02)]
        snd = _modes(f1, rat, [1.0, 0.55, 0.4, 0.2], [T, T * 0.7, T * 0.5, T * 0.35], T * 1.1, attack=0.0003)
        tt = t0 + rng.uniform(0, spread)
        amp = strength * rng.uniform(0.5, 1.0)
        for _h in range(int(rng.integers(2, 5))):
            y = A.mix_at(y, snd, tt, amp)
            tt += rng.uniform(0.006, 0.018)
            amp *= rng.uniform(0.35, 0.6)
    return y


# ----------------------------------------------------------------------------- 8-bit voices
FPS = 60.0


def _frames(values: Sequence[float], d: float) -> np.ndarray:
    """Per-frame (1/60 s) values held as steps for ``d`` seconds (the last value holds)."""
    v = np.asarray(values, dtype=float)
    per = SR / FPS
    idx = np.minimum((np.arange(_n(d)) / per).astype(int), len(v) - 1)
    return v[idx]


def _smooth(x: np.ndarray, ms: float = 1.2) -> np.ndarray:
    """Round the corners of a stepped envelope just enough that the steps do not click."""
    a = math.exp(-1.0 / (SR * ms / 1000.0))
    return signal.lfilter([1 - a], [1, -a], x)


def _vol(levels: Sequence[float], d: float) -> np.ndarray:
    """A 4-bit (0..15) per-frame volume envelope."""
    return _smooth(_frames(levels, d) / 15.0)


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
    """A band-limited pulse wave of any duty (12.5 %, 25 %, 50 %: the NES's three), with no
    DC: the difference of two PolyBLEP saws."""
    f = np.asarray(freq, dtype=float)
    ph = np.cumsum(f) / SR
    t = ph % 1.0
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
    """The NES noise channel: a 15-bit shift register clocked at ``rate`` per second
    ('short' mode gives the metallic, pitched noise)."""
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


def _hz_frames(names: Sequence, d: float) -> np.ndarray:
    return _frames([N(x) if isinstance(x, str) else float(x) for x in names], d)


# ----------------------------------------------------------------------------- voices
def _line(notes: Sequence[Tuple[float, float]], d: float, glide: float = 0.006) -> np.ndarray:
    """Per-sample pitch for a legato line: (start time, Hz) changes, joined by short glides."""
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


def _tongue(onsets: Sequence[float], d: float, depth: float = 0.55, width: float = 0.006) -> np.ndarray:
    """Short dips at note changes, as a player's tongue articulates each note."""
    t = _t(d)
    g = np.ones(len(t))
    for o in onsets:
        g *= 1 - depth * np.exp(-0.5 * ((t - o) / width) ** 2)
    return g


def _whistle(f: np.ndarray, amp: np.ndarray, seed: int, breath: float = 0.05, h2: float = 0.1,
             h3: float = 0.035) -> np.ndarray:
    """A tin whistle or recorder: a nearly pure tone with a breath of noise."""
    d = len(f) / SR
    ph = TAU * np.cumsum(f) / SR
    tone = np.sin(ph) + h2 * np.sin(2 * ph) + h3 * np.sin(3 * ph)
    # breath: a soft band around the note's upper harmonics, steep-sided so it never hisses
    br = _bn(d, 1200, 4500, seed, "pink", 4) * breath
    return (tone + br) * amp


def _brass(f: np.ndarray, amp: np.ndarray, seed: int, bright: float = 2200.0,
           onsets: Sequence[float] = (0.0,)) -> np.ndarray:
    """A horn: a sawtooth whose brightness follows its loudness (as a real horn's does),
    a brassy flare at each tongued onset, a bell resonance and a little breath."""
    d = len(f) / SR
    t = _t(d)
    saw = A.osc("saw", f, d)
    flare = sum(np.where(t >= o, np.exp(-np.clip(t - o, 0, None) / 0.05), 0.0) for o in onsets)
    fc = 180 + bright * np.clip(amp, 0, None) ** 1.5 + 1600 * flare
    y = _svf(saw, fc, 0.75, "lp")
    y = A.peak_eq(y, 500, 4.0, 1.1)
    y = A.peak_eq(y, 1250, 2.0, 1.4)
    y = y + 0.03 * _bn(d, 700, 2600, seed)
    return y * amp


def _taiko(f0: float, d: float, seed: int, t60: float = 0.8, drive: float = 1.8) -> np.ndarray:
    """A big drum: a membrane's inharmonic modes, the pitch dropping as the skin relaxes,
    and the stick's hit."""
    t = _t(d)
    bend = 1 + 0.22 * np.exp(-t / 0.035)
    ratios = [1.0, 1.594, 2.136, 2.296, 2.653, 2.918, 3.156]
    gains = [1.0, 0.55, 0.4, 0.3, 0.22, 0.15, 0.1]
    y = np.zeros(len(t))
    for k, (r, g) in enumerate(zip(ratios, gains)):
        ph = TAU * np.cumsum(f0 * r * bend) / SR
        y += g * np.sin(ph) * np.exp(-6.9078 * t / (t60 / (1 + 0.9 * k)))
    y[:_n(0.0006)] *= np.linspace(0, 1, _n(0.0006))
    y = _sat(y, drive)
    stick = _fit(_bn(0.04, 300, 2500, seed) * A.decay(0.04, 0.025, 0.0002), d)
    return y + 0.3 * stick


def _metal(f0: float, d: float, seed: int, t60: float = 0.3, bright: float = 1.0) -> np.ndarray:
    """A clank of a struck armour plate: plate-like inharmonic modes plus the contact."""
    rng = np.random.default_rng(seed)
    ratios = [1.0, 1.71 * rng.uniform(0.97, 1.03), 2.53 * rng.uniform(0.97, 1.03),
              3.48 * rng.uniform(0.97, 1.03), 4.62 * rng.uniform(0.97, 1.03)]
    gains = [1.0, 0.8, 0.6 * bright, 0.4 * bright, 0.25 * bright]
    t60s = [t60, t60 * 0.8, t60 * 0.6, t60 * 0.45, t60 * 0.35]
    y = _modes(f0, ratios, gains, t60s, d, beat=0.002)
    hit = _bn(0.012, 1500, 6000, seed + 7) * A.decay(0.012, 0.004, 0.0001)
    y[:len(hit)] += 0.45 * bright * hit
    return y


# ============================================================================= hit
def _hit_sword() -> np.ndarray:
    d = 1.0
    x = _buf(d)
    x = A.mix_at(x, _bn(0.02, 2000, 7000, 101) * A.decay(0.02, 0.006, 0.0002), 0, 0.8)
    # the blade rings: a free bar's modes on D5, each a slowly beating pair
    ring = _modes(N("D5"), [1.0, 2.756, 5.404, 8.933], [0.45, 1.0, 0.6, 0.25], [0.75, 0.55, 0.32, 0.18],
                  0.9, beat=0.0018)
    x = A.mix_at(x, ring, 0, 0.45)
    # the armour it lands on: lower, damped
    plate = _modes(N("A4"), [1.0, 1.71, 2.53, 3.48], [1.0, 0.7, 0.5, 0.3], [0.12, 0.1, 0.08, 0.06], 0.3)
    x = A.mix_at(x, plate, 0, 0.35)
    x = A.mix_at(x, _thump(240, 110, 0.04, 0.12, 0.25, 1.5), 0, 0.6)
    x = A.mix_at(x, _bn(0.08, 300, 1600, 102) * A.decay(0.08, 0.035, 0.0003), 0, 0.4)
    return _finish(_verb(x, 0.25, 0.12, tail=0.3), 0.95, 0.3, lp=8000)


def _hit_leather() -> np.ndarray:
    d = 0.7
    x = _buf(d)
    x = A.mix_at(x, _thump(170, 78, 0.07, 0.26, 0.4, 2.2), 0, 0.9)
    x = A.mix_at(x, _thump(330, 180, 0.03, 0.07, 0.12), 0, 0.45)
    x = A.mix_at(x, _bn(0.06, 700, 3500, 111) * A.decay(0.06, 0.03, 0.0002), 0, 0.5)
    x = A.mix_at(x, _bn(0.15, 180, 900, 112, "pink") * A.decay(0.15, 0.08, 0.0005), 0, 0.6)
    x = A.mix_at(x, _bn(0.25, 500, 2500, 113, "pink") * A.adsr(0.25, 0.02, 0.0, 1.0, 0.22), 0.01, 0.12)
    return _finish(x, 0.65, 0.25, lp=6000)


def _hit_oak() -> np.ndarray:
    d = 0.6
    modes = [(N("A3"), 1.0, 0.22), (N("F#4"), 0.8, 0.16), (N("D5") * 0.99, 0.6, 0.12),
             (845.0, 0.45, 0.085), (1290.0, 0.28, 0.06), (1930.0, 0.15, 0.04)]
    tone = _modes(1.0, [m[0] for m in modes], [m[1] for m in modes], [m[2] for m in modes], d)
    burst = _bn(0.004, 200, 4000, 121) * np.hanning(_n(0.004))
    res = _excite(burst, modes, d)
    x = 0.6 * _norm(tone) + 0.5 * _norm(res)
    x = A.mix_at(x, _bn(0.008, 1500, 6000, 122) * A.decay(0.008, 0.003, 0.0001), 0, 0.35)
    x = A.mix_at(x, A.sine(110, 0.3) * A.decay(0.3, 0.1, 0.0005), 0, 0.35)
    return _finish(x, 0.55, 0.2, lp=7000)


def _hit_arcane() -> np.ndarray:
    d = 1.0
    x = _buf(d)
    zd = 0.14
    fc = A.glide(N("D7"), N("D4"), zd)
    t = _t(zd)
    ph = TAU * np.cumsum(fc) / SR
    zap = np.sin(ph + 2.5 * np.exp(-t / 0.04) * np.sin(1.5 * ph)) * A.decay(zd, 0.12, 0.0003)
    x = A.mix_at(x, zap, 0, 0.45)
    x = A.mix_at(x, _thump(294, 147, 0.05, 0.2, 0.35, 1.6), 0, 0.7)
    x = A.mix_at(x, _bn(0.1, 300, 2500, 131) * A.decay(0.1, 0.05, 0.0003), 0, 0.35)
    x = A.mix_at(x, A.bell(N("D6"), 0.9, ratio=2.0, index=1.2, t60=0.75), 0, 0.3)
    x = A.mix_at(x, A.bell(N("A6"), 0.7, ratio=2.0, index=0.9, t60=0.55), 0.05, 0.2)
    x = x + 0.12 * _sparkle(d, 10, 0.04, 0.5, 132)
    return _finish(_verb(x, 0.35, 0.18, tail=0.5), 0.95, 0.3, lp=7800)


def _hit_pixel() -> np.ndarray:
    d = 0.3
    f = _hz_frames(["D5", "A4", "F#4", "D4", "A3", "F#3", "D3", "A2"], d)
    sq = _pulse(f, 0.25) * _vol([15, 14, 12, 10, 8, 7, 6, 5, 4, 3, 2, 1, 0], d)
    nz = _lfsr(_frames([18000, 14000, 11000, 8500, 6500, 5000, 4000, 3200, 2600, 2100, 1700, 1400, 1100], d),
               seed=3) * _vol([15, 13, 11, 9, 8, 7, 6, 5, 4, 3, 2, 2, 1, 1, 0], d)
    return _finish(0.5 * sq + 0.45 * nz, d, 0.04, lp=6500)


# ============================================================================= defeat_enemy
def _defeat_armor() -> np.ndarray:
    d = 2.0
    rng = np.random.default_rng(201)
    x = _buf(d)
    # the body lands
    x = A.mix_at(x, _thump(140, 62, 0.09, 0.38, 0.6, 2.0), 0, 0.9)
    x = A.mix_at(x, _bn(0.2, 120, 900, 202, "pink") * A.decay(0.2, 0.1, 0.0005), 0, 0.5)
    # the first clanks and the plates that follow
    x = A.mix_at(x, _metal(440, 0.6, 203, 0.4), 0, 0.55)
    x = A.mix_at(x, _metal(622, 0.5, 204, 0.3), 0.025, 0.4)
    for i, (tt, g) in enumerate(zip([0.11, 0.17, 0.24, 0.3, 0.39, 0.5, 0.6, 0.72],
                                    [0.45, 0.35, 0.4, 0.28, 0.3, 0.2, 0.18, 0.12])):
        x = A.mix_at(x, _metal(rng.uniform(520, 1250), 0.4, 210 + i, rng.uniform(0.15, 0.3)), tt, g)
    # chain mail: many tiny ring clinks, thinning out
    for _ in range(70):
        tt = min(rng.exponential(0.18), 0.9)
        x = A.mix_at(x, _ping(rng.uniform(2800, 6200), rng.uniform(0.015, 0.04), pgain=0.0), tt,
                     rng.uniform(0.06, 0.15) * math.exp(-tt / 0.3))
    # the helmet rocks and settles: clinks closing in, ever softer
    tt, gap, k = 0.86, 0.15, 0
    while gap > 0.022:
        x = A.mix_at(x, _metal(N("A5"), 0.3, 230 + k, 0.22, 0.7), tt, 0.3 * 0.82 ** k)
        tt += gap
        gap *= 0.8
        k += 1
    return _finish(_verb(x, 0.45, 0.15, tail=0.6), 1.95, 0.4, lp=7600)


GLASS = [N(n) for n in ("D7", "E7", "F#7", "A7", "B7", "D8", "E8")]


def _defeat_glass() -> np.ndarray:
    d = 1.95
    rng = np.random.default_rng(211)
    x = _buf(d)
    x = A.mix_at(x, _bn(0.05, 1500, 7000, 212) * A.decay(0.05, 0.02, 0.0002), 0, 0.8)
    x = A.mix_at(x, _bn(0.1, 400, 2200, 213) * A.decay(0.1, 0.05, 0.0003), 0, 0.5)
    x = A.mix_at(x, _thump(220, 95, 0.05, 0.12, 0.25), 0, 0.55)
    times = np.sort(np.concatenate([rng.uniform(0, 0.06, 14), rng.exponential(0.3, 50)]))
    for tt in times:
        if tt > 1.4:
            continue
        f = float(rng.choice(GLASS)) * (1 + rng.uniform(-0.003, 0.003))
        amp = rng.uniform(0.35, 1.0) * math.exp(-tt / 0.45)
        x = A.mix_at(x, _ping(f, rng.uniform(0.06, 0.3), 2.76, 0.25), tt, 0.35 * amp)
    return _finish(_verb(x, 0.4, 0.16, damping=0.4, tail=0.6), 1.9, 0.45, lp=7600)


def _drum(pitch: float, d: float, seed: int, t60: float = 0.35, slap: float = 0.3) -> np.ndarray:
    """A hand drum (bodhran): a pitched thump with harmonics, and the skin's slap."""
    body = _thump(pitch * 1.5, pitch, 0.06, t60, d, 1.4)
    body += 0.35 * _thump(pitch * 3.0, pitch * 2.0, 0.04, t60 * 0.5, d)
    skin = _fit(_bn(0.08, 400, 3000, seed) * A.decay(0.08, 0.05, 0.0004), d)
    return body + slap * skin


def _defeat_lute() -> np.ndarray:
    d = 2.0
    x = _buf(d)
    x = A.mix_at(x, _drum(N("A2"), 0.6, 221, 0.35, 0.35), 0, 0.7)
    for i, (tt, n) in enumerate([(0.0, "D4"), (0.06, "F#4"), (0.12, "A4"), (0.18, "D5")]):
        x = A.mix_at(x, _ks(N(n), 0.7, 0.55, 0.6, 222 + i), tt, 0.5)
    for i, n in enumerate(["D3", "A3", "D4", "F#4", "A4", "D5"]):
        x = A.mix_at(x, _ks(N(n), 1.6, 0.45, 1.4, 230 + i), 0.27 + 0.012 * i, 0.45 - 0.03 * i)
    x = A.mix_at(x, _drum(N("D3"), 0.6, 240, 0.3, 0.25), 0.27, 0.7)
    x = A.peak_eq(x, 220, 3, 1.2)
    x = A.peak_eq(x, 2800, 2, 1.5)
    return _finish(_verb(x, 0.4, 0.2, tail=0.6), 1.95, 0.5, lp=7500)


def _defeat_bells() -> np.ndarray:
    d = 2.0
    x = _buf(d)
    x = A.mix_at(x, A.bell(N("D3"), 1.8, ratio=1.4, index=2.5, t60=1.6), 0, 0.5)
    x = A.mix_at(x, A.sine(N("D2"), 0.8) * A.decay(0.8, 0.6, 0.001), 0, 0.4)
    x = A.mix_at(x, _bn(0.05, 80, 800, 251) * A.decay(0.05, 0.03, 0.0003), 0, 0.3)
    for i, (tt, n) in enumerate([(0.0, "D6"), (0.09, "A5"), (0.18, "F#5"), (0.27, "E5"), (0.36, "D5")]):
        x = A.mix_at(x, A.bell(N(n), 1.5, ratio=3.5, index=1.2, t60=1.1), tt, 0.33 + 0.02 * i)
    return _finish(_verb(x, 0.55, 0.25, tail=0.6), 1.95, 0.5, lp=7000)


def _defeat_arcade() -> np.ndarray:
    d = 1.25
    nz = _lfsr(_frames([20000, 15000, 11000, 8000, 6000, 4500, 3500, 2600, 2000, 1500, 1200, 1000, 800], d),
               seed=5) * _vol([15, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 3, 2, 2, 1, 1, 0], d)
    sweep = np.repeat(N("D5") * 2 ** (-np.arange(18) * 2 / 12.0), 1)
    sq = _pulse(_frames(list(sweep), d), 0.5) * _vol([12, 12, 11, 10, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0], d)
    x = 0.45 * nz + 0.35 * sq
    # the victory blip
    vd = 0.75
    seq = ["D5"] * 4 + ["F#5"] * 4 + ["A5"] * 4 + ["D6"] * 30
    f = _hz_frames(seq, vd)
    t = _t(vd)
    f = f * (1 + 0.012 * np.sin(TAU * 6 * t) * (t > 0.3))
    vol = [11] * 12 + [12, 12, 11, 11, 10, 10, 9, 9, 8, 8, 7, 7, 6, 6, 5, 5, 4, 4, 3, 3, 2, 2, 1, 1, 0]
    blip = _pulse(f, 0.25) * _vol(vol, vd)
    echo = _pulse(f * 1.003, 0.125) * _vol([0, 0, 0] + [5] * 12 + [5, 5, 4, 4, 4, 3, 3, 3, 2, 2, 2, 1, 1, 0], vd)
    x = A.mix_at(x, 0.4 * blip + 0.25 * echo, 0.4)
    return _finish(x, d, 0.06, lp=6500)


# ============================================================================= exact_kill
def _glass(f: float, d: float, t60: float) -> np.ndarray:
    """A glass chime: a pure fundamental, a soft octave, and a quick inharmonic ping."""
    return _modes(f, [1.0, 2.0, 3.0, 5.4], [1.0, 0.25, 0.08, 0.06], [t60, t60 * 0.5, t60 * 0.3, t60 * 0.12], d)


def _exact_chimes() -> np.ndarray:
    d = 2.4
    x = _buf(d)
    x = A.mix_at(x, _thump(294, 147, 0.04, 0.15, 0.3), 0, 0.5)
    x = A.mix_at(x, _bn(0.06, 500, 3000, 301) * A.decay(0.06, 0.03, 0.0003), 0, 0.2)
    for i, n in enumerate(["D5", "F#5", "A5", "D6", "F#6", "A6"]):
        x = A.mix_at(x, _glass(N(n), 1.9, 1.5 if i == 5 else 0.9), 0.065 * i, 0.32)
    x = A.mix_at(x, _glass(N("D6"), 1.8, 1.4), 0.39, 0.2)
    pad = sum(A.sine(N(n), 2.0) for n in ("D4", "F#4", "A4", "E5")) / 4
    x = A.mix_at(x, pad * A.adsr(2.0, 0.25, 0.2, 0.8, 1.2), 0.05, 0.18)
    x = x + 0.14 * _sparkle(d, 40, 0.2, 1.8, 302, shape=1.6)
    return _finish(_verb(x, 0.6, 0.28, tail=0.6), 2.35, 0.6, lp=7600)


def _exact_harp() -> np.ndarray:
    d = 2.4
    x = _buf(d)
    notes = ["D4", "E4", "F#4", "A4", "B4", "D5", "E5", "F#5", "A5", "B5", "D6"]
    for i, n in enumerate(notes):
        x = A.mix_at(x, _ks(N(n), 2.0, 0.4, 1.6 - 0.05 * i, 310 + i), 0.032 * i, 0.35 + 0.015 * i)
    x = A.mix_at(x, _ks(N("D3"), 2.0, 0.3, 1.8, 330), 0.36, 0.45)
    # a harmonic (a touched string's pure octave) on the top D
    t = _t(1.8)
    x = A.mix_at(x, np.sin(TAU * N("D6") * t) * A.decay(1.8, 1.6, 0.004), 0.36, 0.18)
    return _finish(_verb(x, 0.6, 0.3, tail=0.6), 2.35, 0.7, lp=7600)


def _exact_card() -> np.ndarray:
    d = 2.3
    x = _buf(d)
    wd = 0.32
    t = _t(wd)
    fc = A.glide(600, 3000, wd)
    env = np.interp(t, [0, 0.003, 0.22, 0.3, wd], [0, 0.35, 1.0, 0.15, 0.0])
    flutter = 1 + 0.5 * np.sin(TAU * 22 * t)
    whoosh = _svf(A.noise(wd, "white", 321), fc, 1.2, "bp") * env * flutter
    x = A.mix_at(x, _norm(whoosh), 0, 0.5)
    x = A.mix_at(x, _bn(0.04, 1000, 5000, 322) * A.decay(0.04, 0.025, 0.0002), 0.28, 0.45)
    x = A.mix_at(x, _thump(200, 150, 0.02, 0.05, 0.1), 0.28, 0.35)
    x = A.mix_at(x, A.bell(N("A5"), 1.8, ratio=2.0, index=1.0, t60=1.5), 0.29, 0.35)
    x = A.mix_at(x, A.bell(N("D6"), 1.6, ratio=2.0, index=0.8, t60=1.3), 0.29, 0.25)
    x = x + 0.1 * _sparkle(d, 14, 0.3, 1.2, 323)
    return _finish(_verb(x, 0.45, 0.2, tail=0.6), 2.3, 0.6, lp=7600)


def _exact_pipe() -> np.ndarray:
    d = 2.2
    run = [(0.0, "D5"), (0.065, "E5"), (0.13, "F#5"), (0.195, "A5"), (0.26, "B5"), (0.33, "D6")]
    notes = [(t0, N(n)) for t0, n in run]
    # a trill on the top D, then the held note
    tt = 0.39
    k = 0
    while tt < 0.72:
        notes.append((tt, N("E6") if k % 2 == 0 else N("D6")))
        tt += 0.036
        k += 1
    notes.append((tt, N("D6")))
    f = _line(notes, d, 0.004)
    t = _t(d)
    f = f * (1 + 0.006 * np.sin(TAU * 5.5 * t) * np.clip((t - 0.9) / 0.3, 0, 1))
    env = np.interp(t, [0, 0.006, 0.33, 1.2, 1.55, d], [0, 1.0, 0.9, 0.85, 0.0, 0.0])
    amp = env * _tongue([o for o, _ in run[1:]], d)
    x = _whistle(f, amp, 341, breath=0.045, h2=0.12, h3=0.05)
    x = A.mix_at(x, _drum(N("A3"), 0.4, 342, 0.15, 0.4), 0, 0.35)
    x = A.mix_at(x, _drum(N("A3"), 0.4, 343, 0.15, 0.4), 0.33, 0.35)
    x = A.mix_at(x, _ping(N("D7"), 0.6, pgain=0.1), 0.33, 0.12)
    return _finish(_verb(x, 0.45, 0.22, tail=0.6), 2.2, 0.5, lp=7500)


def _exact_powerup() -> np.ndarray:
    d = 1.6
    up = ["D4", "F#4", "A4", "D5", "F#5", "A5", "D6", "F#6", "A6", "D7"]
    seq = [n for n in up for _ in range(2)] + ["D6"] * 40
    f = _hz_frames(seq, d)
    t = _t(d)
    f = f * (1 + 0.01 * np.sin(TAU * 7 * t) * (t > 0.5))
    vol = [12] * 20 + [13, 12, 12, 11, 11, 10, 10, 9, 9, 8, 8, 7, 7, 6, 6, 5, 5, 4, 4, 3, 3, 2, 2, 1, 1, 0]
    lead = _pulse(f, 0.25) * _vol(vol, d)
    # the echo: the same line three frames late, thinner and quieter
    echo = _pulse(_hz_frames(seq[:1] * 3 + seq, d) * 1.003, 0.125) * _vol([0, 0, 0] + [v // 2 for v in vol], d)
    bass = _tri4(_hz_frames(["D3"] * 10 + ["A3"] * 10 + ["D4"] * 30, d)) * _vol([15] * 40 + [12, 9, 6, 3, 0], d)
    return _finish(0.4 * lead + 0.22 * echo + 0.35 * bass, d, 0.08, lp=6500)


# ============================================================================= new_enemy
def _new_blade() -> np.ndarray:
    d = 2.0
    x = _buf(d)
    # the hilt unlatches
    x = A.mix_at(x, A.tick(3200, 0.02, 0.4, 401), 0, 0.5)
    x = A.mix_at(x, _modes(2600, [1.0, 1.58], [1.0, 0.5], [0.03, 0.02], 0.05), 0, 0.3)
    # the blade slides out: friction noise, rough and rising, ringing the blade's modes
    sd = 0.55
    t = _t(sd)
    rough = 0.6 + 0.4 * _norm(A.lowpass(np.random.default_rng(402).standard_normal(_n(sd)), 120, 2))
    fric = A.noise(sd, "white", 403) * rough
    sweep = _svf(fric, A.glide(1800, 4800, sd), 2.5, "bp")
    blade = [(N("D5") * 2.756, 1.0, 0.25), (N("D5") * 5.404, 0.7, 0.2), (N("D5") * 8.933, 0.3, 0.12)]
    ring = _excite(fric * 0.05, blade, sd)
    env = np.interp(t, [0, 0.003, 0.48, 0.53, sd], [0, 0.45, 1.0, 0.3, 0.0])
    scrape = (_norm(sweep) + 0.6 * _norm(ring)) * env
    x = A.mix_at(x, scrape, 0.01, 0.5)
    # the tip leaves the scabbard: the blade rings free
    free = _modes(N("D5"), [1.0, 2.756, 5.404, 8.933], [0.6, 1.0, 0.55, 0.25], [1.3, 1.0, 0.6, 0.35], 1.4,
                  beat=0.0015)
    x = A.mix_at(x, free, 0.52, 0.4)
    x = A.mix_at(x, _ping(4700, 0.05, pgain=0), 0.52, 0.15)
    return _finish(_verb(x, 0.5, 0.2, tail=0.6), 1.9, 0.45, lp=7500)


def _new_horn() -> np.ndarray:
    d = 2.0
    t = _t(d)
    f = _line([(0.0, N("A2") * 0.97), (0.04, N("A2")), (0.30, N("D3") * 0.96), (0.35, N("D3"))], d, 0.012)
    f = f * (1 + 0.0035 * np.sin(TAU * 4.8 * t) * np.clip((t - 0.8) / 0.3, 0, 1))
    amp = np.interp(t, [0, 0.005, 0.03, 0.27, 0.30, 0.33, 0.95, 1.45, d],
                    [0, 0.45, 0.85, 0.8, 0.55, 0.75, 1.0, 0.0, 0.0])
    x = _brass(f, amp, 411) + 0.35 * _brass(f * 0.5 * 1.002, amp, 412, 1200.0)
    x = A.mix_at(x, _bn(0.01, 300, 2000, 413) * A.decay(0.01, 0.006, 0.0002), 0, 0.15)
    return _finish(_verb(x, 0.8, 0.32, damping=0.55, tail=0.6), 2.0, 0.4)


def _new_drum() -> np.ndarray:
    d = 2.0
    x = _buf(d)
    x = A.mix_at(x, _taiko(N("D2"), 1.5, 421), 0, 1.0)
    x = A.mix_at(x, _taiko(N("D2"), 1.3, 422, 0.6), 0.36, 0.7)
    t = _t(1.9)
    drone = sum(A.osc("saw", N(n) * (1 + 0.003 * k), 1.9) for k, n in enumerate(("D2", "A2", "F3")))
    drone = A.lowpass(drone, 500, 2) * A.adsr(1.9, 0.3, 0.2, 0.8, 0.8)
    x = A.mix_at(x, drone, 0, 0.08)
    rumble = A.lowpass(A.noise(1.2, "brown", 423), 180, 2) * A.decay(1.2, 0.8, 0.002)
    x = A.mix_at(x, rumble, 0, 0.2)
    return _finish(_verb(x, 0.7, 0.25, tail=0.6), 1.95, 0.45)


def _creak(d: float, seed: int) -> np.ndarray:
    """Wood creaking under strain: stick-slip pulses, their rate wandering, driving the
    plank's resonances."""
    rng = np.random.default_rng(seed)
    t = _t(d)
    rate = np.interp(t, [0, 0.4 * d, 0.8 * d, d], [120, 230, 170, 200])
    wob = A.lowpass(rng.standard_normal(len(t)), 8, 1)
    rate = rate * (1 + 0.5 * wob / (np.max(np.abs(wob)) or 1) * 0.12)
    ph = np.cumsum(rate) / SR
    idx = np.nonzero(np.diff(np.floor(ph)) > 0)[0] + 1
    pulses = np.zeros(len(t))
    pulses[idx] = rng.uniform(0.5, 1.0, len(idx))
    modes = [(380, 1.0, 0.05), (640, 0.8, 0.04), (1020, 0.7, 0.03), (1550, 0.5, 0.025), (2300, 0.3, 0.02)]
    return sum(g * _reson(pulses, f, T) for f, g, T in modes)


def _new_gate() -> np.ndarray:
    d = 2.0
    x = _buf(d)
    # the latch lifts
    x = A.mix_at(x, _modes(1450, [1.0, 1.64, 2.69], [1.0, 0.6, 0.35], [0.06, 0.05, 0.03], 0.1), 0, 0.4)
    x = A.mix_at(x, _modes(300, [1.0, 1.73], [1.0, 0.6], [0.05, 0.04], 0.1), 0, 0.4)
    x = A.mix_at(x, _bn(0.006, 1000, 5000, 431) * A.decay(0.006, 0.003, 0.0001), 0, 0.3)
    # the gate swings, creaking
    cd = 1.0
    t = _t(cd)
    env = np.interp(t, [0, 0.01, 0.25, 0.75, 0.95, cd], [0, 0.4, 1.0, 0.9, 0.2, 0.0])
    x = A.mix_at(x, _norm(_creak(cd, 432)) * env, 0.06, 0.55)
    # and stops against the stone
    wood = [(N("D3"), 1.0, 0.3), (233, 0.7, 0.2), (390, 0.5, 0.12), (610, 0.3, 0.08)]
    burst = _bn(0.006, 100, 2000, 433) * np.hanning(_n(0.006))
    thud = 0.6 * _norm(_excite(burst, wood, 0.7)) + 0.5 * _thump(140, 82, 0.05, 0.3, 0.7, 1.8)
    x = A.mix_at(x, thud, 1.1, 0.9)
    x = A.mix_at(x, _bn(0.15, 60, 500, 434) * A.decay(0.15, 0.08, 0.0005), 1.1, 0.4)
    rng = np.random.default_rng(435)
    for i, tt in enumerate([1.14, 1.19, 1.23, 1.3]):
        x = A.mix_at(x, _metal(rng.uniform(900, 1500), 0.25, 440 + i, 0.12, 0.6), tt, 0.12 * 0.75 ** i)
    return _finish(_verb(x, 0.6, 0.25, tail=0.6), 1.95, 0.4, lp=7000)


def _new_chip() -> np.ndarray:
    d = 1.5
    x = _buf(d)
    for tt in (0.0, 0.18, 0.36):
        nz = _lfsr(_frames([2400], 0.2), seed=7) * _vol([12, 9, 6, 4, 2, 1, 0], 0.2)
        x = A.mix_at(x, nz, tt, 0.35)
    bass = _tri4(_frames([N("D2")], 1.3)) * _vol([15] * 8 + [0] * 3 + [15] * 8 + [0] * 3 + [15] * 40 +
                                                 [12, 9, 6, 3, 0], 1.3)
    x = A.mix_at(x, bass, 0, 0.45)
    stab = _pulse(_frames([N("D3")], 0.14), 0.5) * _vol([13, 12, 11, 10, 8, 6, 3, 0], 0.14)
    x = A.mix_at(x, stab, 0, 0.3)
    x = A.mix_at(x, stab, 0.18, 0.3)
    # the minor chord the NES way: one voice cycling D-F-A every frame
    cd = 1.1
    arp = _frames([N(n) for _ in range(25) for n in ("D4", "F4", "A4")], cd)
    t = _t(cd)
    arp = arp * (1 - 0.06 * np.clip((t - 0.6) / 0.5, 0, 1))
    vol = [13] * 30 + [12, 11, 11, 10, 9, 9, 8, 7, 7, 6, 5, 5, 4, 3, 3, 2, 1, 1, 0]
    x = A.mix_at(x, _pulse(arp, 0.25) * _vol(vol, cd), 0.36, 0.3)
    return _finish(x, d, 0.08, lp=6000)


# ============================================================================= suffer
def _suffer_heavy() -> np.ndarray:
    d = 1.1
    x = _buf(d)
    x = A.mix_at(x, _thump(120, 52, 0.12, 0.45, 0.9, 3.0), 0, 1.0)
    x = A.mix_at(x, _thump(260, 140, 0.05, 0.12, 0.2), 0, 0.4)
    rng = np.random.default_rng(501)
    grain = np.repeat(rng.uniform(0.2, 1.0, 40), _n(0.1) // 40 + 1)[:_n(0.1)]
    x = A.mix_at(x, _bn(0.1, 200, 1400, 502) * grain * A.decay(0.1, 0.1, 0.0003), 0, 0.5)
    x = A.mix_at(x, _bn(0.03, 900, 3500, 503) * A.decay(0.03, 0.02, 0.0002), 0, 0.25)
    x = A.mix_at(x, A.lowpass(A.noise(0.7, "brown", 504), 250, 2) * A.decay(0.7, 0.6, 0.002), 0, 0.25)
    return _finish(_verb(x, 0.25, 0.1, tail=0.4), 1.1, 0.35, lp=4500)


def _suffer_armor() -> np.ndarray:
    d = 1.3
    x = _buf(d)
    clang = _modes(N("A3"), [1.0, 1.83, 2.98, 4.21, 5.7, 7.3], [0.7, 1.0, 0.8, 0.6, 0.4, 0.25],
                   [0.9, 0.8, 0.6, 0.45, 0.35, 0.25], 1.2, beat=0.003)
    x = A.mix_at(x, clang, 0, 0.5)
    x = A.mix_at(x, _thump(150, 70, 0.06, 0.25, 0.5, 2.0), 0, 0.7)
    x = A.mix_at(x, _bn(0.03, 500, 3000, 511) * A.decay(0.03, 0.02, 0.0002), 0, 0.4)
    return _finish(_verb(x, 0.35, 0.12, tail=0.4), 1.3, 0.4, lp=5000)


def _suffer_drum() -> np.ndarray:
    d = 1.0
    x = _buf(d)
    x = A.mix_at(x, _drum(98.0, 0.8, 521, 0.35, 0.25), 0, 0.8)
    x = A.mix_at(x, _ks(N("D2"), 0.9, 0.15, 0.6, 522), 0, 0.6)
    x = A.mix_at(x, _ks(N("D3"), 0.9, 0.2, 0.5, 523), 0, 0.3)
    return _finish(_verb(x, 0.3, 0.12, tail=0.4), 1.0, 0.3, lp=3000)


def _suffer_shadow() -> np.ndarray:
    d = 1.4
    x = _buf(d)
    wd = 0.24
    t = _t(wd)
    env = np.interp(t, [0, 0.003, 0.12, 0.2, wd], [0, 0.5, 1.0, 0.2, 0.0])
    whoosh = _svf(A.noise(wd, "white", 531), A.glide(2600, 350, wd), 1.5, "bp") * env
    x = A.mix_at(x, _norm(whoosh), 0, 0.5)
    # the impact: a low FM growl on D (its partials fall on D's harmonics)
    gd = 1.2
    t = _t(gd)
    ph = TAU * N("D2") * t
    growl = np.sin(ph + 5.0 * np.exp(-t / 0.12) * np.sin(1.5 * ph)) * A.decay(gd, 0.7, 0.001)
    x = A.mix_at(x, _sat(growl, 1.5), 0.14, 0.6)
    x = A.mix_at(x, _thump(N("D3") * 2, N("D3"), 0.04, 0.3, 0.5), 0.14, 0.4)
    x = A.mix_at(x, _bn(0.08, 60, 1200, 532) * A.decay(0.08, 0.05, 0.0003), 0.14, 0.4)
    x = A.mix_at(x, A.bell(N("D3"), 1.2, ratio=1.4, index=1.5, t60=1.0), 0.14, 0.25)
    x = A.mix_at(x, A.bell(N("F3"), 1.2, ratio=1.4, index=1.5, t60=0.9), 0.14, 0.18)
    return _finish(_verb(x, 0.6, 0.25, damping=0.7, tail=0.6), 1.35, 0.4, lp=5000)


def _suffer_8bit() -> np.ndarray:
    d = 0.5
    k = np.arange(20)
    fr = N("D5") * 2 ** (-k * 1.6 / 12.0) * np.where(k % 2 == 1, 1.12, 1.0)
    sq = _pulse(_frames(list(fr), d), 0.5) * _vol([15, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 3, 2, 2, 1, 1, 0], d)
    nz = _lfsr(_frames([4000], d), short=True, seed=9) * _vol([14, 11, 8, 6, 4, 2, 1, 0], d)
    return _finish(0.5 * sq + 0.4 * nz, d, 0.05, lp=6000)


# ============================================================================= jester
def _jester_bells() -> np.ndarray:
    d = 2.0
    rng = np.random.default_rng(601)
    x = _buf(d)
    for tt, s in [(0.0, 1.0), (0.12, 0.75), (0.24, 0.85), (0.48, 0.7), (0.6, 0.8), (0.72, 1.0)]:
        x = _jingle(x, tt, s, rng)
    x = A.peak_eq(x, 6000, -3, 0.8)
    return _finish(_verb(x, 0.3, 0.15, tail=0.5), 1.9, 0.5, lp=7800)


def _jester_jig() -> np.ndarray:
    d = 2.0
    e = 0.11
    tune = ["A5", "B5", "A5", "F#5", "D5", "F#5", "A5", "B5", "D6"]
    notes = []
    onsets = []
    for i, n in enumerate(tune):
        t0 = i * e
        if n == "F#5" and i == 3:
            notes.append((t0, N("B5")))          # a cut: a flick of a higher note
            notes.append((t0 + 0.018, N(n)))
        elif i == len(tune) - 1:
            notes.append((t0, N("E6")))
            notes.append((t0 + 0.02, N(n)))
        else:
            notes.append((t0, N(n)))
        onsets.append(t0)
    f = _line(notes, d, 0.003)
    t = _t(d)
    end = (len(tune) - 1) * e
    f = f * (1 + 0.008 * np.sin(TAU * 5.5 * t) * np.clip((t - end - 0.12) / 0.15, 0, 1))
    env = np.interp(t, [0, 0.006, end, end + 0.45, end + 0.6, d], [0, 1.0, 0.9, 0.8, 0.0, 0.0])
    x = _whistle(f, env * _tongue(onsets[1:], d), 611, breath=0.06, h2=0.08, h3=0.03)
    rng = np.random.default_rng(612)
    for tt, s in [(0.0, 0.6), (3 * e, 0.4), (6 * e, 0.5), (end, 0.8)]:
        x = _jingle(x, tt, s * 0.35, rng, bells=4, spread=0.02)
    for tt in (0.0, 3 * e, 6 * e, end):
        x = A.mix_at(x, _drum(N("A2"), 0.3, 613, 0.2, 0.3), tt, 0.25)
    return _finish(_verb(x, 0.35, 0.18, tail=0.6), 1.95, 0.4, lp=7600)


def _jester_slide() -> np.ndarray:
    d = 1.7
    t = _t(d)
    k = [0.0, 0.28, 0.45, 0.62, d]
    v = [math.log(N("D5")), math.log(N("D6")), math.log(N("A5")), math.log(N("D6")), math.log(N("D6"))]
    lf = np.interp(t, k, v)
    f = np.exp(lf) * (1 + 0.015 * np.sin(TAU * 7 * t) * np.clip((t - 0.65) / 0.08, 0, 1))
    env = np.interp(t, [0, 0.004, 0.1, 0.62, 0.9, 1.05, d], [0, 0.6, 1.0, 1.0, 0.8, 0.0, 0.0])
    x = _whistle(f, env, 621, breath=0.05, h2=0.04, h3=0.01)
    rng = np.random.default_rng(622)
    x = _jingle(x, 0.95, 0.4, rng, bells=4)
    x = _jingle(x, 1.07, 0.3, rng, bells=3)
    return _finish(_verb(x, 0.35, 0.16, tail=0.5), 1.6, 0.4, lp=7600)


def _tine(f: float, d: float, t60: float = 1.2) -> np.ndarray:
    """A music box's steel tine: a pure tone, a soft overtone and the pin's tiny click."""
    t = _t(d)
    y = np.sin(TAU * f * t) * np.exp(-6.9078 * t / t60)
    y += 0.18 * np.sin(TAU * 2 * f * t) * np.exp(-6.9078 * t / (t60 * 0.4))
    if 6.27 * f < 7800:
        y += 0.12 * np.sin(TAU * 6.27 * f * t) * np.exp(-6.9078 * t / (t60 * 0.08))
    y[:_n(0.0003)] *= np.linspace(0, 1, _n(0.0003))
    return y


def _jester_musicbox() -> np.ndarray:
    d = 2.0
    x = _buf(d)
    # "nyah-nyah": the teasing chant (sol mi la sol mi), on a music box
    for tt, n in [(0.0, "A5"), (0.22, "F#5"), (0.33, "B5"), (0.44, "A5"), (0.66, "F#5")]:
        x = A.mix_at(x, _tine(N(n), 1.3), tt, 0.4)
    x = A.mix_at(x, _tine(N("D5"), 1.3, 1.4), 0.0, 0.22)
    x = A.mix_at(x, _tine(N("D5"), 1.3, 1.4), 0.66, 0.22)
    x = A.mix_at(x, _tine(N("D7"), 0.6, 0.5), 0.9, 0.12)
    rng = np.random.default_rng(631)
    x = _jingle(x, 0.88, 0.18, rng, bells=4)
    return _finish(_verb(x, 0.4, 0.2, tail=0.6), 1.95, 0.5, lp=7600)


def _jester_chip() -> np.ndarray:
    d = 1.4
    bounce = ["D5", "F#5", "A5", "D6", "A5", "F#5", "D5", "F#5", "A5", "D6"]
    seq = [n for n in bounce for _ in range(3)]
    slide = [N("D6") * 2 ** (i * 7 / 12.0 / 6) for i in range(1, 7)]
    fr = [N(n) for n in seq] + slide + [N("A6")] * 40
    f = _frames(fr, d)
    t = _t(d)
    f = f * (1 + 0.012 * np.sin(TAU * 8 * t) * (t > 0.62))
    vol = [12] * 36 + [12, 12, 11, 11, 10, 10, 9, 9, 8, 8, 7, 7, 6, 6, 5, 5, 4, 4, 3, 3, 2, 2, 1, 1, 0]
    lead = _pulse(f, 0.125) * _vol(vol, d)
    x = 0.4 * lead
    for i in range(0, 10, 2):
        x = A.mix_at(x, _lfsr(_frames([12000], 0.06), seed=11) * _vol([8, 5, 2, 0], 0.06), i * 0.05, 0.25)
    bass = _tri4(_hz_frames(["D3"] * 15 + ["A2"] * 15 + ["D3"] * 40, d)) * _vol([15] * 60 + [10, 5, 0], d)
    return _finish(x + 0.3 * bass, d, 0.08, lp=6500)


# ============================================================================= yield
def _yield_cloth() -> np.ndarray:
    d = 0.9
    t = _t(d)
    rng = np.random.default_rng(701)
    grain = A.lowpass(rng.standard_normal(len(t)), 60, 1)
    grain = 1 + 0.6 * grain / (np.max(np.abs(grain)) or 1)
    env = np.interp(t, [0, 0.003, 0.13, 0.4, 0.75, d], [0, 0.3, 1.0, 0.55, 0.0, 0.0])
    x = _svf(A.noise(d, "pink", 702), A.glide(1500, 700, d), 0.9, "bp") * grain * env
    return _finish(x, d, 0.2, lp=4500)


def _yield_felt() -> np.ndarray:
    d = 1.15
    t = _t(d)
    x = np.zeros(len(t))
    for root, g in ((N("D3"), 1.0), (N("D4"), 0.5)):
        for k in range(1, 9):
            fk = k * root * math.sqrt(1 + 0.0004 * k * k)
            x += g * k ** -1.3 * np.sin(TAU * fk * t) * np.exp(-6.9078 * t / (0.9 / math.sqrt(k)))
    x[:_n(0.002)] *= np.linspace(0, 1, _n(0.002))
    x = A.lowpass(x, 1400, 2)
    x = A.mix_at(x, _bn(0.03, 60, 700, 711) * A.decay(0.03, 0.02, 0.0005), 0, 0.15)
    return _finish(x, 1.1, 0.4)


def _knock(seed: int, shift: float = 1.0) -> np.ndarray:
    """A knuckle rap on a wooden table: a soft click and the table top's damped modes."""
    d = 0.3
    modes = [(185 * shift, 0.6, 0.09), (N("D4") * shift, 1.0, 0.07), (440 * shift, 0.8, 0.06),
             (690 * shift, 0.55, 0.045), (1050 * shift, 0.35, 0.03), (1600 * shift, 0.2, 0.02)]
    burst = _bn(0.0015, 100, 3000, seed) * np.hanning(_n(0.0015))
    y = 0.6 * _norm(_excite(burst, modes, d))
    y += 0.4 * _norm(_modes(1.0, [m[0] for m in modes], [m[1] for m in modes], [m[2] for m in modes], d))
    y = A.mix_at(y, _bn(0.004, 1000, 3000, seed + 1) * A.decay(0.004, 0.002, 0.0001), 0, 0.2)
    return y


def _yield_knock() -> np.ndarray:
    x = _buf(0.6)
    x = A.mix_at(x, _knock(721), 0, 1.0)
    x = A.mix_at(x, _knock(723, 1.03), 0.15, 0.8)
    return _finish(x, 0.6, 0.15)


def _vibe(f: float, d: float) -> np.ndarray:
    """A vibraphone bar with its motor's slow tremolo: partials 1, 4 and 10 times the note."""
    t = _t(d)
    y = _modes(f, [1.0, 4.0, 10.0], [1.0, 0.25, 0.06], [1.4, 0.4, 0.12], d, attack=0.001)
    return y * (1 - 0.15 * (1 - np.cos(TAU * 5 * t)) / 2)


def _yield_vibes() -> np.ndarray:
    d = 1.2
    x = _buf(d)
    x = A.mix_at(x, _vibe(N("A4"), 1.0), 0, 0.5)
    x = A.mix_at(x, _vibe(N("D4"), 0.98), 0.22, 0.55)
    x = A.mix_at(x, _bn(0.012, 60, 1200, 731) * A.decay(0.012, 0.008, 0.0003), 0, 0.08)
    return _finish(_verb(x, 0.4, 0.2, tail=0.5), 1.15, 0.35)


def _yield_8bit() -> np.ndarray:
    d = 0.45
    f = _hz_frames(["A4"] * 6 + ["D4"] * 30, d)
    x = _tri4(f) * _vol([11, 11, 10, 10, 9, 9, 10, 10, 9, 9, 8, 7, 6, 5, 4, 3, 3, 2, 2, 1, 1, 0], d)
    return _finish(x, d, 0.05, lp=5000)


# ============================================================================= the list
CANDIDATES = [
    # hit: your attack lands and the enemy survives
    Candidate("hit", "sword_strike", "Sword strike", "A steel blade rings off armour with a solid thud.",
              _hit_sword, ["metal", "real"]),
    Candidate("hit", "leather_thump", "Leather thump", "A solid punch into padded leather armour.",
              _hit_leather, ["soft", "real"]),
    Candidate("hit", "oak_shield", "Oak shield", "A mace knocks hard on a wooden shield.",
              _hit_oak, ["wooden"]),
    Candidate("hit", "arcane_bolt", "Arcane bolt", "A magic bolt zaps in and bursts with a bright chime.",
              _hit_arcane, ["magic"]),
    Candidate("hit", "pixel_punch", "Pixel punch", "A crunchy 8-bit hit from an old console.",
              _hit_pixel, ["retro"]),
    # defeat_enemy
    Candidate("defeat_enemy", "armor_collapse", "Armour collapse",
              "The enemy crashes down in clattering armour; the helmet rocks and settles.",
              _defeat_armor, ["metal", "real"]),
    Candidate("defeat_enemy", "crystal_shatter", "Crystal shatter",
              "The enemy shatters like crystal into tinkling shards.", _defeat_glass, ["glass", "bright"]),
    Candidate("defeat_enemy", "lute_flourish", "Lute flourish",
              "A drum thump and a quick lute run ending on a bright chord.", _defeat_lute, ["tavern"]),
    Candidate("defeat_enemy", "falling_bells", "Falling bells",
              "A deep gong and a cascade of bells stepping down.", _defeat_bells, ["magic", "bells"]),
    Candidate("defeat_enemy", "arcade_ko", "Arcade KO",
              "An 8-bit explosion followed by a little victory blip.", _defeat_arcade, ["retro"]),
    # exact_kill
    Candidate("exact_kill", "rising_chimes", "Rising chimes",
              "Glass chimes climb up with a cloud of sparkles.", _exact_chimes, ["magic", "sparkle"]),
    Candidate("exact_kill", "harp_glissando", "Harp glissando",
              "A harp sweeps up two octaves to a ringing high note.", _exact_harp, ["soft", "strings"]),
    Candidate("exact_kill", "gilded_card", "Gilded card",
              "A card flutters into your deck and lands with a golden ding.", _exact_card, ["card", "bell"]),
    Candidate("exact_kill", "pipe_flourish", "Pipe flourish",
              "A pipe runs up to a trilled high note over a tabor tap.", _exact_pipe, ["tavern"]),
    Candidate("exact_kill", "power_up", "Power-up",
              "A classic 8-bit power-up arpeggio climbing to a held note.", _exact_powerup, ["retro"]),
    # new_enemy
    Candidate("new_enemy", "drawn_blade", "Drawn blade",
              "A sword slides out of its scabbard and rings.", _new_blade, ["metal", "real"]),
    Candidate("new_enemy", "war_horn", "War horn",
              "A low horn call echoes through the castle hall.", _new_horn, ["brass", "ominous"]),
    Candidate("new_enemy", "doom_drum", "Doom drum",
              "Two deep drum booms over a dark low drone.", _new_drum, ["drum", "ominous"]),
    Candidate("new_enemy", "castle_gate", "Castle gate",
              "A latch lifts, an old wooden gate creaks open and thuds.", _new_gate, ["wooden"]),
    Candidate("new_enemy", "chiptune_boss", "Chiptune boss",
              "An 8-bit 'dun, dun, DUN' with a minor chord.", _new_chip, ["retro"]),
    # suffer
    Candidate("suffer", "heavy_blow", "Heavy blow",
              "A deep, dull body blow with a gritty crunch.", _suffer_heavy, ["real", "dark"]),
    Candidate("suffer", "armor_dent", "Armour dent",
              "A blunt hit on your breastplate: a dark metal clang.", _suffer_armor, ["metal", "dark"]),
    Candidate("suffer", "muffled_drum", "Muffled drum",
              "A soft, dark drum hit with a low string: the gentle choice.", _suffer_drum, ["soft"]),
    Candidate("suffer", "shadow_strike", "Shadow strike",
              "A dark whoosh into a deep growling magic impact.", _suffer_shadow, ["magic", "dark"]),
    Candidate("suffer", "eight_bit_hurt", "8-bit hurt",
              "The classic retro 'ouch': a wobbling pitch drop.", _suffer_8bit, ["retro"]),
    # jester
    Candidate("jester", "jester_bells", "Jester bells",
              "The jingling bells of a jester's cap, shaken to a playful rhythm.", _jester_bells, ["bells", "real"]),
    Candidate("jester", "whistle_jig", "Whistle jig",
              "A quick tin-whistle jig with a tap of drum and bells.", _jester_jig, ["tavern"]),
    Candidate("jester", "slide_whistle", "Slide whistle",
              "A cheeky slide whistle swoops up and down.", _jester_slide, ["funny"]),
    Candidate("jester", "music_box", "Music box",
              "A tinkly music box plays the teasing 'nyah-nyah' tune.", _jester_musicbox, ["magic", "funny"]),
    Candidate("jester", "chip_jester", "8-bit jester",
              "A bouncy chiptune arpeggio that slides up with a wobble.", _jester_chip, ["retro"]),
    # yield
    Candidate("yield", "cloth_sigh", "Cloth sigh", "A soft swish of a cloak, like a sigh.",
              _yield_cloth, ["soft", "real"]),
    Candidate("yield", "felt_note", "Felt note", "One low, muted piano note.", _yield_felt, ["soft"]),
    Candidate("yield", "table_knock", "Table knock",
              "Two gentle knocks on a wooden table: a card player's 'pass'.", _yield_knock, ["wooden"]),
    Candidate("yield", "soft_vibes", "Soft vibes", "Two soft vibraphone notes stepping down.",
              _yield_vibes, ["soft", "chime"]),
    Candidate("yield", "eight_bit_pass", "8-bit pass", "A gentle two-note 8-bit fall.", _yield_8bit, ["retro"]),
]
