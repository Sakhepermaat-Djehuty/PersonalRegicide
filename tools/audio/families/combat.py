"""Combat sounds: the blow that lands, the enemy's fall, the exact kill that wins its card,
the next enemy's arrival, the enemy's strike back, the Jester and the yield.

Everything here is acoustic: real instruments and real materials in a stone hall. Five
candidates per event, each a different character: the action itself as foley, a soft
one for long sessions, a tavern or wooden one, a courtly instrumental one, and a regal
or mysterious one. Tonal parts are in D (D major pentatonic, or D dorian with F natural
for the darker ones).

Where a recording exists it is used: the instruments and drums are General MIDI samples
rendered by FluidSynth from the MIT banks (``sf.py``), cut at their onset so a sound
starts the moment it is played. Materials no bank records (a blade, a breastplate, an
oak shield, a cloak, a table top) are modelled physically: struck plates and planks are
banks of resonators driven by a short noise burst (each mode rings and beats like real
metal or wood), and cloth and air are noise shaped by the movement. Low weight always
comes with body between 250 Hz and 3 kHz, so a phone's small speaker still carries it.

Private helpers (the shared toolkit is not edited):
  _sf / _stem / _hit   cached FluidSynth renders, cut at their onset
  _repitch             play a recording slower or faster (a deeper woodblock, a cymbal)
  _choke               damp a ringing recording, as a hand stops a cymbal
  _reson / _excite / _plate / _plank   struck metal and wood
  _svf / _air          moving filters: air past a blade, cloth, a swing
  _creak               a wooden gate's stick-slip creak
  _finish              cut to length with a natural fade and band limits
"""
from __future__ import annotations

import dataclasses
import functools
import math
from typing import Optional, Sequence, Tuple

import numpy as np
from scipy import signal

import sf
import synth as A
from catalog import Candidate
from sf import DRUM, GM, Note

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


def _bn(d: float, lo: float, hi: float, seed: int, color: str = "white", order: int = 2) -> np.ndarray:
    """Band-limited noise, peak-normalised."""
    return _norm(A.bandpass(A.noise(d, color, seed), lo, hi, order))


def _env(d: float, pts: Sequence[Tuple[float, float]]) -> np.ndarray:
    """A piecewise-linear envelope through (time, level) points."""
    t = _t(d)
    return np.interp(t, [p[0] for p in pts], [p[1] for p in pts])


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


def _verb(x: np.ndarray, room: float, wet: float, damping: float = 0.5, tail: float = 0.6) -> np.ndarray:
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


def _en(x: np.ndarray) -> np.ndarray:
    """Scale to unit loudness (by the build's measure), so layers mix by how loud they
    sound rather than by their peaks."""
    return x / (10 ** (_loudness(x) / 20.0))


# ============================================================================= recordings
@functools.lru_cache(maxsize=None)
def _render(spec: tuple, seconds: float, bank: str) -> np.ndarray:
    notes = [Note(*s) for s in spec]
    return sf.render(notes, seconds, bank=bank)


def _sf(notes: Sequence[Note], seconds: float, bank: str = "fluid") -> np.ndarray:
    """A cached FluidSynth render (mono, the bank's own level)."""
    spec = tuple((n.program, n.pitch, round(n.start, 5), round(n.dur, 5), int(n.vel), round(n.pan, 3),
                  n.reverb, n.chorus, n.bend, n.swell, n.kit) for n in notes)
    return _render(spec, round(seconds, 4), bank).copy()


def _cut(x: np.ndarray, floor_db: float = -50.0, pre: float = 0.0004) -> np.ndarray:
    """Start at the recording's onset (the bank's notes begin a few ms late), with a tiny
    fade-in so the cut cannot click."""
    i = max(0, sf.onset(x, floor_db) - _n(pre))
    y = x[i:].copy()
    k = _n(pre) or 1
    y[:k] *= np.linspace(0, 1, k)
    return y


def _stem(notes: Sequence[Note], seconds: float, bank: str = "fluid", floor_db: float = -50.0) -> np.ndarray:
    """Render notes and cut at the first onset (later notes keep their timing)."""
    return _cut(_sf(notes, seconds, bank), floor_db)


def _hit(key, vel: int = 100, kit: str = "standard", bank: str = "fluid", seconds: float = 1.5) -> np.ndarray:
    """One drum or percussion hit, cut at its onset."""
    return _stem([Note(DRUM, key, 0.0, 0.2, vel=vel, kit=kit)], seconds, bank)


def _one(program: str, pitch, dur: float, vel: int = 100, bank: str = "fluid", seconds: Optional[float] = None,
         **kw) -> np.ndarray:
    """One instrument note, cut at its onset."""
    return _stem([Note(GM[program], pitch, 0.0, dur, vel=vel, **kw)], seconds or dur + 1.2, bank)


def _repitch(x: np.ndarray, ratio: float) -> np.ndarray:
    """Play a recording ``ratio`` times faster (pitch up) or slower (pitch down), as a
    tape or sampler would."""
    if ratio > 1:
        x = A.lowpass(x, 0.45 * SR / ratio, 4)
    pos = np.arange(0, len(x) - 1, ratio)
    return np.interp(pos, np.arange(len(x)), x)


def _choke(x: np.ndarray, at: float, fall: float) -> np.ndarray:
    """Damp a ringing sound after ``at`` seconds, its level falling 60 dB in ``fall``."""
    t = _t(len(x) / SR)
    g = np.where(t < at, 1.0, np.exp(-6.9078 * np.clip(t - at, 0, None) / fall))
    return x * g


# ============================================================================= physical models
def _reson(x: np.ndarray, f: float, t60: float) -> np.ndarray:
    """A two-pole resonator ringing at f for t60 seconds (an impulse gives a unit sine)."""
    w = TAU * f / SR
    r = 0.001 ** (1.0 / (t60 * SR))
    return signal.lfilter([math.sin(w)], [1.0, -2 * r * math.cos(w), r * r], x)


def _excite(burst: np.ndarray, modes: Sequence[Tuple[float, float, float]], d: float) -> np.ndarray:
    """Drive a bank of (freq, gain, t60) resonators with a short burst."""
    ex = _fit(burst, d)
    return sum(g * _reson(ex, f, T) for f, g, T in modes)


def _plate(f0: float, d: float, seed: int, t60: float = 0.4, bright: float = 1.0, count: int = 14,
           contact: float = 0.002) -> np.ndarray:
    """A struck steel plate (a breastplate, a blade, a helmet): many inharmonic modes,
    each a detuned pair, driven by a short noise burst (the strike's contact time sets how
    bright it is: a sharp edge is short, a blunt mace long)."""
    rng = np.random.default_rng(seed)
    modes = []
    r = 1.0
    for k in range(count):
        f = f0 * r
        if f > 7600:
            break
        g = (0.55 + 0.45 * rng.random()) * (1.0 if k < 3 else bright * 0.85 ** (k - 2))
        T = t60 * (1.0 / (1 + 0.25 * k)) * rng.uniform(0.8, 1.2)
        modes.append((f * (1 - 0.0015), g, T))
        modes.append((f * (1 + 0.0015), g * 0.8, T * 0.9))
        r *= rng.uniform(1.18, 1.42)
    burst = A.lowpass(np.random.default_rng(seed + 1).standard_normal(_n(contact)), 2500 + 5000 * bright, 2)
    burst *= np.hanning(len(burst))
    return _excite(burst, modes, d)


def _plank(modes: Sequence[Tuple[float, float, float]], d: float, seed: int, contact: float = 0.003,
           lo: float = 80.0, hi: float = 4000.0) -> np.ndarray:
    """Struck wood: damped resonators driven by a soft noise pulse (knuckle, mallet, mace)."""
    burst = _bn(contact, lo, hi, seed) * np.hanning(_n(contact))
    return _excite(burst, modes, d)


def _svf(x: np.ndarray, fc, q: float = 0.707, mode: str = "bp") -> np.ndarray:
    """A state-variable filter whose cutoff ``fc`` may change every sample. 'bp' has unit
    gain at the centre."""
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


def _air(d: float, f0: float, f1: float, seed: int, q: float = 1.2, pts=None) -> np.ndarray:
    """Air rushing past something moving (a blade, a cloak, a staff): pink noise through two
    band-passes whose centre follows the speed, with the speed's swell as its loudness."""
    fc = A.glide(f0, f1, d)
    y = _svf(_svf(A.noise(d, "pink", seed), fc, q, "bp"), fc, q, "bp")
    env = _env(d, pts or [(0, 0), (0.004, 0.4), (0.6 * d, 1.0), (d, 0)])
    return _norm(y * env)


def _cloth(d: float, seed: int, lo: float = 500.0, hi: float = 3500.0, pts=None) -> np.ndarray:
    """Woven cloth brushing: band-passed noise with the weave's grainy flutter."""
    rng = np.random.default_rng(seed)
    grain = A.lowpass(rng.standard_normal(_n(d)), 70, 1)
    grain = 1 + 0.7 * grain / (np.max(np.abs(grain)) or 1)
    y = A.bandpass(A.noise(d, "pink", seed + 1), lo, hi, 2) * grain
    return _norm(y * _env(d, pts or [(0, 0), (0.01, 1.0), (d, 0)]))


# ============================================================================= hit
def _hit_sword() -> np.ndarray:
    d = 1.0
    x = _buf(d)
    # the edge bites: a few ms of bright scrape
    x = A.mix_at(x, _bn(0.012, 2200, 7000, 101, "white", 4) * A.decay(0.012, 0.006, 0.0002), 0, 0.5)
    # the blade rings (a long, narrow steel bar on D) and the breastplate answers, darker
    x = A.mix_at(x, _en(_plate(N("D5"), 0.9, 102, t60=0.5, bright=1.0, contact=0.0006)), 0, 0.6)
    x = A.mix_at(x, _en(_plate(N("A3"), 0.6, 103, t60=0.18, bright=0.6, contact=0.002)), 0, 0.5)
    # a ride cymbal's bell, damped by the hand: real steel for the shimmer
    bell = _choke(_hit("ride_bell", 110, seconds=1.0), 0.04, 0.3)
    x = A.mix_at(x, _en(A.lowpass(bell, 7000, 4)), 0.001, 0.35)
    # the weight of the blow behind it: a hand drum's thump, damped at once
    x = A.mix_at(x, _en(_choke(_hit("low_conga", 120, seconds=0.6), 0.05, 0.15)), 0, 0.3)
    return _finish(_glue(_verb(x, 0.25, 0.1), 15.0), 0.9, 0.35, hp=60, lp=7800)


def _hit_leather() -> np.ndarray:
    d = 0.7
    x = _buf(d)
    # a fist into a padded gambeson: a hand drum's deep thump, its slap, and a brush's swat
    x = A.mix_at(x, _en(_choke(_hit("low_conga", 115, seconds=0.6), 0.07, 0.2)), 0, 1.0)
    x = A.mix_at(x, _en(_choke(_hit("mute_conga", 90, seconds=0.4), 0.04, 0.15)), 0.002, 0.45)
    x = A.mix_at(x, _en(_choke(_hit("snare", 70, kit="brush", seconds=0.5), 0.06, 0.2)), 0.001, 0.4)
    x = A.mix_at(x, _en(_cloth(0.25, 111, 400, 2500, [(0, 0), (0.01, 1.0), (0.08, 0.4), (0.25, 0)])), 0.005, 0.2)
    return _finish(_glue(x, 14.0), 0.65, 0.3, hp=70, lp=5500)


OAK = [(N("A2") * 1.02, 0.7, 0.16), (N("F#3"), 1.0, 0.12), (N("D4") * 0.99, 0.8, 0.09),
       (480.0, 0.6, 0.07), (735.0, 0.45, 0.05), (1120.0, 0.3, 0.035), (1690.0, 0.18, 0.025)]


def _hit_oak() -> np.ndarray:
    d = 0.6
    x = _buf(d)
    # the mace meets the boards: a big woodblock (a recording played two octaves down) ...
    x = A.mix_at(x, _en(_choke(_one("woodblock", "D3", 0.2, 120, seconds=0.6), 0.07, 0.35)), 0, 0.8)
    # ... the shield's planks ring, damped by the arm behind them
    x = A.mix_at(x, _en(_plank(OAK, d, 121, 0.004)), 0, 0.8)
    # and the blow's weight: a concert bass drum, struck short
    x = A.mix_at(x, _en(_choke(_hit("bass_drum", 100, kit="orchestra", seconds=0.6), 0.06, 0.2)), 0, 0.08)
    return _finish(_glue(x, 14.0), 0.55, 0.25, hp=60, lp=6500)


def _hit_arcane() -> np.ndarray:
    d = 1.0
    # the bolt flies: a harp swept up two octaves, a rush of air with it ...
    run = ["D5", "E5", "F#5", "A5", "B5", "D6", "E6", "F#6", "A6"]
    gl = [Note(GM["harp"], n, 0.009 * i, 0.3, vel=70 + 5 * i) for i, n in enumerate(run)]
    burst = 0.085
    # ... and bursts: a timpani strike, glockenspiel and celesta ringing D and A over it
    notes = gl + [Note(GM["glockenspiel"], "D6", burst, 0.4, vel=115),
                  Note(GM["glockenspiel"], "A6", burst + 0.004, 0.4, vel=100),
                  Note(GM["celesta"], "D6", burst, 0.4, vel=110),
                  Note(GM["celesta"], "A5", burst + 0.006, 0.4, vel=100),
                  Note(GM["timpani"], "D3", burst, 0.3, vel=120)]
    x = _choke(_fit(_stem(notes, 1.6, "musescore"), d), 0.22, 0.75)
    x = A.mix_at(x, 0.25 * _air(burst + 0.01, 900, 3200, 131, 1.0, [(0, 0.2), (burst, 1.0), (burst + 0.01, 0)]), 0)
    x = A.mix_at(x, 0.5 * _norm(_choke(_hit("splash", 80, kit="orchestra", seconds=0.8), 0.06, 0.3)), burst)
    return _finish(_glue(_verb(x, 0.4, 0.16), 15.5), 0.95, 0.4, hp=60, lp=6800)


def _hit_drum() -> np.ndarray:
    d = 0.8
    x = _buf(d)
    # a war drum: the field drum's snares rattle over a concert bass drum and a timpani on D
    x = A.mix_at(x, _en(_choke(_hit("snare", 120, kit="orchestra", bank="musescore"), 0.05, 0.3)), 0, 0.8)
    x = A.mix_at(x, _en(_choke(_hit("bass_drum", 115, kit="orchestra"), 0.1, 0.35)), 0, 0.3)
    x = A.mix_at(x, _en(_choke(_one("timpani", "D3", 0.3, 120, "musescore"), 0.12, 0.4)), 0.002, 0.6)
    return _finish(_glue(_verb(x, 0.4, 0.12), 15.0), 0.75, 0.3, hp=55, lp=7500)


# ============================================================================= defeat_enemy
def _tambourine(times_vels, d: float, seed: int = 0, lp: float = 6500.0) -> np.ndarray:
    """A tambourine (or chain mail: the same small loose discs) shaken at (time, velocity),
    its sizzle above the jingles' ring taken down."""
    notes = [Note(DRUM, "tambourine", t, 0.1, vel=v) for t, v in times_vels]
    return A.lowpass(_fit(_stem(notes, d + 0.6), d), lp, 4)


def _defeat_armor() -> np.ndarray:
    d = 2.0
    rng = np.random.default_rng(201)
    x = _buf(d)
    # the body lands: a concert bass drum, a hand drum's thud and the leather's slap
    x = A.mix_at(x, _en(_choke(_hit("bass_drum", 120, kit="orchestra"), 0.12, 0.45)), 0, 0.5)
    x = A.mix_at(x, _en(_choke(_hit("low_conga", 120), 0.05, 0.2)), 0.004, 0.45)
    x = A.mix_at(x, _en(_choke(_hit("snare", 90, kit="brush"), 0.06, 0.2)), 0.002, 0.3)
    # the first clanks, then plates and buckles landing, some muffled under the body
    x = A.mix_at(x, _en(_plate(440, 0.7, 203, t60=0.4, bright=0.8, contact=0.002)), 0, 0.5)
    x = A.mix_at(x, _en(_plate(622, 0.6, 204, t60=0.3, bright=0.7, contact=0.002)), 0.025, 0.4)
    tt = 0.07
    for i in range(12):
        tt += rng.exponential(0.05) + 0.015
        if tt > 0.8:
            break
        g = rng.uniform(0.4, 1.0) * 0.4 * math.exp(-tt / 0.45)
        x = A.mix_at(x, _en(_plate(rng.uniform(480, 1300), 0.45, 210 + i, rng.uniform(0.12, 0.3),
                                   rng.uniform(0.3, 0.9), contact=rng.uniform(0.001, 0.003))), tt, g)
    # chain mail settling: the same little loose rings as a tambourine's, shaken ever softer
    x = A.mix_at(x, _en(_tambourine([(0.01, 90), (0.09, 70), (0.2, 55), (0.36, 40), (0.55, 28)], 1.2)), 0, 0.3)
    # the helmet rocks and settles: clinks closing in, ever softer
    tt, gap, k = 0.86, 0.15, 0
    helm = [_en(_plate(N("A5"), 0.3, 230, 0.22, 0.6, contact=0.0015)),
            _en(_plate(N("A5") * 1.06, 0.3, 231, 0.18, 0.5, contact=0.0015))]
    while gap > 0.022:
        x = A.mix_at(x, helm[k % 2], tt, 0.09 * 0.8 ** k)
        tt += gap
        gap *= 0.8
        k += 1
    return _finish(_glue(_verb(x, 0.45, 0.14), 14.5), 1.95, 0.4, hp=50, lp=7600)


PENTA = ["D", "E", "F#", "A", "B"]


def _penta(lo: str, hi: str) -> list:
    """D major pentatonic notes from ``lo`` to ``hi`` inclusive (names like 'D4')."""
    out = []
    for octave in range(1, 9):
        for nm in PENTA:
            n = "%s%d" % (nm, octave)
            if A.midi(lo) <= A.midi(n) <= A.midi(hi):
                out.append(n)
    return out


def _defeat_harp() -> np.ndarray:
    d = 1.9
    run = list(reversed(_penta("D4", "D6")))
    notes = [Note(GM["harp"], n, 0.036 * i, 0.4, vel=84 - 2 * i) for i, n in enumerate(run)]
    end = 0.036 * len(run)
    notes += [Note(GM["harp"], "D3", end, 1.0, vel=66), Note(GM["harp"], "A3", end + 0.012, 1.0, vel=54)]
    x = _choke(_fit(_stem(notes, d + 0.5, "musescore"), d), end + 0.4, 1.2)
    return _finish(_verb(x, 0.5, 0.18), 1.9, 0.6, hp=60, lp=7500)


def _defeat_lute() -> np.ndarray:
    d = 2.0
    # a quick run up the lute, then a full strummed chord
    run = [Note(GM["nylon_guitar"], n, 0.06 * i, 0.25, vel=96) for i, n in enumerate(["D4", "F#4", "A4", "D5"])]
    strum = [Note(GM["nylon_guitar"], n, 0.27 + 0.014 * i, 1.4, vel=100 - 3 * i)
             for i, n in enumerate(["D3", "A3", "D4", "F#4", "A4", "D5"])]
    x = _fit(_stem(run + strum, d + 0.6), d)
    # a tavern drum (a frame drum: a brushed floor tom's skin with a hand drum's thump, as
    # the Tavern Band's bodhran) under the first note and the chord, a tambourine on the chord
    drum = A.mix_at(_buf(0.8), _en(_choke(_hit("low_floor_tom", 100, kit="brush"), 0.1, 0.35)), 0)
    drum = A.mix_at(drum, _en(_choke(_hit("low_conga", 95), 0.06, 0.25)), 0, 0.8)
    x = _choke(x, 0.9, 1.1)
    x = A.mix_at(x, 0.22 * _norm(drum), 0, 1.0)
    x = A.mix_at(x, 0.28 * _norm(drum), 0.27, 1.0)
    x = A.mix_at(x, 0.12 * _norm(_tambourine([(0.0, 80)], 0.6)), 0.272, 1.0)
    return _finish(_glue(_verb(x, 0.4, 0.16), 14.0), 1.95, 0.55, hp=55, lp=7500)


def _defeat_bells() -> np.ndarray:
    d = 2.0
    # tubular bells ring down D major's pentatonic over a deep bell and a timpani
    notes = [Note(GM["tubular_bells"], n, 0.09 * i, 0.6, vel=100 - 3 * i)
             for i, n in enumerate(["D6", "A5", "F#5", "E5", "D5"])]
    notes += [Note(GM["tubular_bells"], "D4", 0.0, 1.2, vel=110), Note(GM["timpani"], "D3", 0.0, 0.5, vel=110),
              Note(GM["timpani"], "A2", 0.36, 0.5, vel=90)]
    x = _fit(_stem(notes, d + 0.6), d)
    x = _choke(x, 0.6, 1.3)
    return _finish(_verb(x, 0.55, 0.2), 1.95, 0.6, hp=60, lp=7200)


def _defeat_horns() -> np.ndarray:
    d = 2.0
    # the hunt's 'mort': two horns call the quarry down (D, D, A, a long D), a timpani under it
    call = [("D4", 0.0, 0.16), ("D4", 0.18, 0.16), ("A4", 0.36, 0.2), ("D5", 0.58, 0.75)]
    notes = [Note(GM["french_horn"], n, t, dur, vel=112) for n, t, dur in call]
    notes += [Note(GM["french_horn"], h, t, dur, vel=100) for h, (n, t, dur) in zip(["A3", "A3", "D4", "A4"], call)]
    notes += [Note(GM["timpani"], "D3", 0.0, 0.3, vel=105), Note(GM["timpani"], "A2", 0.58, 0.4, vel=110),
              Note(GM["trumpet"], "D5", 0.58, 0.7, vel=80)]
    x = _fit(_stem(notes, d + 0.6, "musescore"), d)
    return _finish(_verb(x, 0.6, 0.2), 1.95, 0.5, hp=60, lp=7000)


# ============================================================================= exact_kill
def _flutter(d: float, seed: int) -> np.ndarray:
    """A playing card fluttering through the air: a rising swish of air, beating as it spins."""
    t = _t(d)
    fc = A.glide(700, 2600, d)
    env = np.interp(t, [0, 0.003, 0.7 * d, 0.92 * d, d], [0, 0.6, 1.0, 0.15, 0.0])
    spin = 1 + 0.45 * np.sin(TAU * 22 * t)
    y = _svf(_svf(A.noise(d, "pink", seed), fc, 1.3, "bp"), fc, 1.3, "bp")
    return _norm(y * env * spin)


def _card_land(seed: int) -> np.ndarray:
    """A card slapping down onto the deck: a crisp paper slap, the card stock's brief ring
    and the deck's soft knock on the felt."""
    d = 0.15
    slap = _bn(0.03, 900, 6500, seed) * A.decay(0.03, 0.016, 0.0002)
    ring = _excite(_bn(0.002, 1500, 6000, seed + 1), [(2350, 1.0, 0.02), (3150, 0.7, 0.015), (4300, 0.4, 0.01)], d)
    knock = _plank([(190, 1.0, 0.04), (330, 0.8, 0.03), (540, 0.5, 0.02)], d, seed + 2, 0.003)
    return _fit(slap, d) + 0.3 * _norm(ring) + 0.5 * _norm(knock)


def _exact_card() -> np.ndarray:
    d = 2.3
    x = _buf(d)
    land = 0.28
    # the card flutters through the air and lands on your deck ...
    x = A.mix_at(x, _flutter(0.32, 321), 0, 0.45)
    x = A.mix_at(x, _norm(_card_land(322)), land, 0.6)
    # ... and the deck answers with a golden ring: celesta, glockenspiel and a soft bell,
    # then a few celesta notes drifting up like gold dust
    ding = [Note(GM["celesta"], "D6", land, 0.5, vel=112), Note(GM["glockenspiel"], "A6", land, 0.5, vel=88),
            Note(GM["tubular_bells"], "D5", land, 0.8, vel=56), Note(GM["harp"], "D5", land, 0.8, vel=42)]
    dust = [Note(GM["celesta"], n, land + 0.17 + 0.06 * i, 0.3, vel=62 - 3 * i)
            for i, n in enumerate(["E6", "F#6", "A6", "B6", "D7"])]
    x = A.mix_at(x, 0.8 * _norm(_fit(_sf(ding + dust, d + 0.3, "musescore"), d)), 0)
    return _finish(_glue(_verb(x, 0.45, 0.18), 15.0), 2.3, 0.6, hp=60, lp=7000)


def _exact_harp() -> np.ndarray:
    d = 2.4
    run = _penta("D4", "D6")
    notes = [Note(GM["harp"], n, 0.032 * i, 0.5, vel=74 + 3 * i) for i, n in enumerate(run)]
    top = 0.032 * len(run)
    notes += [Note(GM["harp"], "D3", top + 0.02, 1.6, vel=100), Note(GM["harp"], "A3", top + 0.03, 1.6, vel=80),
              Note(GM["harp"], "D7", top + 0.02, 1.2, vel=60)]
    x = _fit(_stem(notes, d + 0.4, "musescore"), d)
    x = _choke(x, 1.0, 1.6)
    return _finish(_verb(x, 0.55, 0.22), 2.35, 0.7, hp=60, lp=7600)


def _exact_pipe() -> np.ndarray:
    d = 2.2
    # a recorder runs up to a trilled high D and holds it, over a tabor's taps
    run = ["D5", "E5", "F#5", "A5", "B5", "D6"]
    step = 0.065
    notes = [Note(GM["recorder"], n, step * i, step, vel=100) for i, n in enumerate(run)]
    tt, k = step * len(run), 0
    while tt < 0.75:
        notes.append(Note(GM["recorder"], "E6" if k % 2 == 0 else "D6", tt, 0.04, vel=96))
        tt += 0.04
        k += 1
    notes.append(Note(GM["recorder"], "D6", tt, 0.75, vel=104))
    x = _fit(_stem(notes, d + 0.4, "musescore"), d)
    tabor = _choke(_hit("snare", 70, kit="orchestra", bank="musescore"), 0.04, 0.25)
    for at, g in ((0.0, 0.12), (step * 5, 0.14), (tt, 0.16)):
        x = A.mix_at(x, g * _norm(tabor), at, 1.0)
    return _finish(_verb(x, 0.45, 0.2), 2.2, 0.5, hp=80, lp=7500)


def _exact_fanfare() -> np.ndarray:
    d = 2.2
    # three herald trumpets: a triplet pick-up to D, then up to F# and a long A, with a
    # timpani roll under the last note
    lead = [("A4", 0.0, 0.07), ("A4", 0.09, 0.07), ("A4", 0.18, 0.07), ("D5", 0.27, 0.32), ("F#5", 0.62, 0.13),
            ("A5", 0.78, 0.75)]
    harm = ["F#4", "F#4", "F#4", "A4", "D5", "F#5"]
    low = ["D4", "D4", "D4", "F#4", "A4", "D5"]
    notes = [Note(GM["trumpet"], n, t, dur, vel=112) for n, t, dur in lead]
    notes += [Note(GM["trumpet"], h, t, dur, vel=98, pan=-0.2) for h, (n, t, dur) in zip(harm, lead)]
    notes += [Note(GM["trombone"], h, t, dur, vel=96, pan=0.2) for h, (n, t, dur) in zip(low, lead)]
    roll = [Note(GM["timpani"], "D3", 0.78 + 0.04 * i, 0.04, vel=60 + 2 * i) for i in range(16)]
    notes += [Note(GM["timpani"], "D3", 0.0, 0.3, vel=96), Note(GM["timpani"], "A2", 0.27, 0.3, vel=104)] + roll
    notes += [Note(GM["timpani"], "D3", 1.42, 0.5, vel=110)]
    x = _fit(_stem(notes, d + 0.4), d)
    return _finish(_verb(x, 0.6, 0.18), 2.2, 0.5, hp=60, lp=7200)


def _exact_celesta() -> np.ndarray:
    d = 2.0
    # a celesta climbs D major's arpeggio to a high D, a glockenspiel touching the top note,
    # over a soft harp chord
    arp = ["D5", "F#5", "A5", "D6", "F#6", "A6", "D7"]
    notes = [Note(GM["celesta"], n, 0.055 * i, 0.5, vel=72 + 4 * i) for i, n in enumerate(arp)]
    top = 0.055 * (len(arp) - 1)
    notes += [Note(GM["glockenspiel"], "D7", top, 0.6, vel=64), Note(GM["harp"], "D4", 0.0, 1.2, vel=38),
              Note(GM["harp"], "A4", 0.012, 1.2, vel=34), Note(GM["harp"], "F#5", top, 1.0, vel=40)]
    x = _fit(_stem(notes, d + 0.4, "musescore"), d)
    return _finish(_verb(x, 0.55, 0.22), 2.0, 0.6, hp=80, lp=7600)


# ============================================================================= new_enemy
BAR = [1.0, 2.756, 5.404, 8.933]        # a free steel bar's modes (a blade)


def _new_blade() -> np.ndarray:
    d = 2.0
    x = _buf(d)
    # the scabbard's catch unlatches: a small steel click
    x = A.mix_at(x, _en(_plate(2600, 0.08, 401, t60=0.04, bright=0.8, contact=0.0006)), 0, 0.3)
    x = A.mix_at(x, _bn(0.006, 1500, 6000, 400, "white", 4) * A.decay(0.006, 0.003, 0.0001), 0, 0.5)
    # the blade slides out: rough friction drives narrow resonances of the steel that glide
    # up as the contact runs along the blade (the 'shiiing'), and sets the blade ringing
    sd = 0.55
    t = _t(sd)
    rough = 0.55 + 0.45 * _norm(A.lowpass(np.random.default_rng(402).standard_normal(_n(sd)), 150, 2))
    fric = A.lowpass(A.noise(sd, "white", 403), 5500, 4) * rough
    rise = A.glide(1.0, 1.6, sd)
    whine = sum(g * _svf(fric, f * rise, 14.0, "bp")
                for f, g in [(1250, 1.0), (1720, 0.8), (2310, 0.65), (3080, 0.5), (4150, 0.35)])
    hiss = _bn(sd, 2000, 5000, 404, "white", 4) * rough
    ring = _excite(fric * 0.05, [(N("D5") * 2.756, 1.0, 0.25), (N("D5") * 5.404, 0.7, 0.2)], sd)
    env = np.interp(t, [0, 0.003, 0.48, 0.53, sd], [0, 0.5, 1.0, 0.3, 0.0])
    x = A.mix_at(x, (_norm(whine) + 0.25 * hiss + 0.4 * _norm(ring)) * env, 0.004, 0.5)
    # the tip leaves the scabbard: the blade rings free
    f0 = N("D5")
    bar = [(f0 * r * (1 + s), g, T) for r, g, T in zip(BAR, [0.35, 1.0, 0.7, 0.35], [1.2, 1.0, 0.6, 0.35])
           for s in (-0.0015, 0.0015)]
    tip = _bn(0.0015, 1500, 7000, 405) * np.hanning(_n(0.0015))
    x = A.mix_at(x, _norm(_excite(tip, bar, 1.4)), 0.52, 0.45)
    return _finish(_glue(_verb(x, 0.5, 0.2), 15.0), 1.9, 0.45, lp=7500)


def _new_horn() -> np.ndarray:
    d = 2.0
    # a low horn call through the castle hall: A, then a long D swelling, a timpani under
    # each note and a trombone an octave below
    notes = [Note(GM["french_horn"], "A2", 0.0, 0.26, vel=118), Note(GM["trombone"], "A1", 0.0, 0.26, vel=90),
             Note(GM["french_horn"], "D3", 0.3, 1.0, vel=122, swell=(85, 127)),
             Note(GM["trombone"], "D2", 0.3, 1.0, vel=96, swell=(70, 110)),
             Note(GM["timpani"], "A2", 0.0, 0.3, vel=95), Note(GM["timpani"], "D3", 0.3, 0.4, vel=100)]
    x = _fit(_stem(notes, d + 0.5, "musescore"), d)
    return _finish(_verb(x, 0.8, 0.3, damping=0.55), 2.0, 0.45, hp=55)


def _new_drum() -> np.ndarray:
    d = 2.0
    x = _buf(d)
    # two deep booms: a concert bass drum with timpani on D (the upper one carries on a phone)
    for tt, g in ((0.0, 1.0), (0.36, 0.72)):
        x = A.mix_at(x, _en(_hit("bass_drum", 127, kit="orchestra", seconds=1.8)), tt, 0.32 * g)
        x = A.mix_at(x, _en(_stem([Note(GM["timpani"], "D2", 0.0, 0.5, vel=118),
                                   Note(GM["timpani"], "D3", 0.0, 0.5, vel=127)], 1.8, "musescore")), tt, 0.9 * g)
        # the drum's wooden shell answers the stick with a hollow knock
        x = A.mix_at(x, _en(_choke(_one("woodblock", "D2", 0.3, 100, seconds=0.8), 0.05, 0.3)), tt, 0.25 * g)
    # under them, low strings hold a dark D minor chord
    drone = [Note(GM["cello"], "D3", 0.0, 1.3, vel=100, swell=(70, 115)),
             Note(GM["contrabass"], "D2", 0.0, 1.3, vel=80),
             Note(GM["strings"], "F3", 0.0, 1.3, vel=86), Note(GM["strings"], "A3", 0.0, 1.3, vel=80),
             Note(GM["strings"], "D4", 0.0, 1.3, vel=70)]
    x = A.mix_at(x, 0.6 * _en(_fit(_stem(drone, d + 0.4, "musescore"), d)), 0)
    return _finish(_glue(_verb(x, 0.7, 0.22), 16.0), 1.95, 0.45, hp=45)


def _creak(d: float, seed: int) -> np.ndarray:
    """Wood creaking under strain: stick-slip pulses, their rate wandering, driving the
    plank's resonances."""
    rng = np.random.default_rng(seed)
    t = _t(d)
    rate = np.interp(t, [0, 0.4 * d, 0.8 * d, d], [120, 230, 170, 200])
    wob = A.lowpass(rng.standard_normal(len(t)), 8, 1)
    rate = rate * (1 + 0.06 * wob / (np.max(np.abs(wob)) or 1))
    ph = np.cumsum(rate) / SR
    idx = np.nonzero(np.diff(np.floor(ph)) > 0)[0] + 1
    idx = np.clip(idx + rng.integers(-12, 13, len(idx)), 0, len(t) - 1)      # the wood slips unevenly
    pulses = np.zeros(len(t))
    pulses[idx] = rng.uniform(0.5, 1.0, len(idx))
    modes = [(380, 1.0, 0.05), (640, 0.8, 0.04), (1020, 0.7, 0.03), (1550, 0.5, 0.025), (2300, 0.3, 0.02)]
    return sum(g * _reson(pulses, f, T) for f, g, T in modes)


def _new_gate() -> np.ndarray:
    d = 2.0
    x = _buf(d)
    # the iron latch lifts
    x = A.mix_at(x, _en(_plate(1450, 0.15, 431, t60=0.07, bright=0.7, contact=0.0008)), 0, 0.35)
    x = A.mix_at(x, _en(_plate(330, 0.15, 432, t60=0.05, bright=0.5, contact=0.002)), 0.004, 0.35)
    # the gate swings, creaking on its hinges
    cd = 1.0
    t = _t(cd)
    env = np.interp(t, [0, 0.01, 0.25, 0.75, 0.95, cd], [0, 0.4, 1.0, 0.9, 0.2, 0.0])
    x = A.mix_at(x, _en(_creak(cd, 433) * env), 0.06, 0.3)
    # and stops against the stone: a deep woodblock and the gate's planks, the bass drum's
    # weight, the chain rattling
    hit = 1.1
    x = A.mix_at(x, _en(_choke(_one("woodblock", "A2", 0.3, 120, seconds=0.8), 0.08, 0.4)), hit, 0.6)
    x = A.mix_at(x, _en(_plank([(N("D3"), 1.0, 0.25), (233, 0.7, 0.18), (390, 0.5, 0.12), (610, 0.3, 0.08)],
                               0.7, 434, 0.006)), hit, 0.5)
    x = A.mix_at(x, _en(_choke(_hit("bass_drum", 110, kit="orchestra"), 0.1, 0.4)), hit, 0.3)
    x = A.mix_at(x, _en(_tambourine([(0.0, 50), (0.07, 34), (0.16, 22)], 0.5, lp=5000)), hit + 0.02, 0.12)
    return _finish(_glue(_verb(x, 0.6, 0.22), 15.0), 1.95, 0.4, lp=7000)


def _new_strings() -> np.ndarray:
    d = 2.0
    # a timpani rolls in softly and low strings shiver into a dark D minor chord
    roll = [Note(GM["timpani"], "D3", 0.045 * i, 0.05, vel=min(100, 70 + 3 * i)) for i in range(18)]
    chord = [Note(GM["tremolo_strings"], n, 0.0, 1.25, vel=v, swell=(55, 120))
             for n, v in (("D3", 104), ("A3", 100), ("D4", 96), ("F4", 96))]
    chord += [Note(GM["cello"], "D3", 0.0, 1.25, vel=100, swell=(60, 115)),
              Note(GM["contrabass"], "D2", 0.0, 1.25, vel=70)]
    x = _fit(_stem(roll + chord, d + 0.4, "musescore"), d)
    return _finish(_verb(x, 0.7, 0.24), 2.0, 0.5, hp=50)


# ============================================================================= suffer
def _suffer_heavy() -> np.ndarray:
    d = 1.1
    x = _buf(d)
    # a deep, dull body blow: a concert bass drum's weight, a hand drum's chest-deep thud,
    # the slap of leather and a brush's swat, all damped at once
    x = A.mix_at(x, _en(_choke(_hit("bass_drum", 127, kit="orchestra"), 0.1, 0.4)), 0, 0.28)
    x = A.mix_at(x, _en(_choke(_hit("low_conga", 127), 0.06, 0.2)), 0.002, 0.8)
    x = A.mix_at(x, _en(_choke(_one("timpani", "A2", 0.2, 100, "musescore"), 0.05, 0.25)), 0.0, 0.4)
    x = A.mix_at(x, _en(_choke(_hit("mute_conga", 100), 0.03, 0.12)), 0.003, 0.4)
    x = A.mix_at(x, _en(_choke(_hit("snare", 90, kit="brush"), 0.05, 0.2)), 0.001, 0.35)
    x = A.mix_at(x, _en(_cloth(0.3, 501, 300, 2000, [(0, 0), (0.02, 1.0), (0.1, 0.4), (0.3, 0)])), 0.01, 0.15)
    return _finish(_glue(_verb(x, 0.25, 0.08), 15.0), 1.0, 0.35, hp=55, lp=5000)


def _suffer_armor() -> np.ndarray:
    d = 1.3
    x = _buf(d)
    # a blunt blow on your breastplate: a dark steel clang (a mace's long contact keeps it
    # dull), a cymbal's bell played an octave down for the steel's grain, and the thud behind
    x = A.mix_at(x, _en(_plate(N("A3"), 1.2, 511, t60=0.6, bright=0.75, contact=0.003)), 0, 0.7)
    bell = _choke(_repitch(_hit("ride_bell", 120, seconds=1.6), 0.5), 0.1, 0.6)
    x = A.mix_at(x, _en(A.lowpass(bell, 5000, 4)), 0.001, 0.55)
    x = A.mix_at(x, _en(_choke(_hit("bass_drum", 115, kit="orchestra"), 0.08, 0.35)), 0, 0.25)
    x = A.mix_at(x, _en(_choke(_hit("low_conga", 110), 0.05, 0.18)), 0.002, 0.25)
    return _finish(_glue(_verb(x, 0.35, 0.12), 15.0), 1.3, 0.45, hp=50, lp=5500)


def _suffer_drum() -> np.ndarray:
    d = 1.0
    # a timpani stroked softly and damped by the hand, with a low harp string under it
    notes = [Note(GM["timpani"], "A2", 0.0, 0.3, vel=78), Note(GM["harp"], "D3", 0.004, 0.6, vel=70),
             Note(GM["harp"], "D2", 0.004, 0.6, vel=62)]
    x = _choke(_fit(_stem(notes, d + 0.4, "musescore"), d), 0.12, 0.7)
    return _finish(_verb(x, 0.3, 0.1), 1.0, 0.35, hp=60, lp=3000)


def _suffer_shadow() -> np.ndarray:
    d = 1.4
    x = _buf(d)
    hit = 0.14
    # a dark rush of air, falling ...
    rush = _air(0.24, 2200, 350, 531, 1.4, [(0, 0), (0.003, 0.7), (0.12, 1.0), (0.2, 0.2), (0.24, 0)])
    x = A.mix_at(x, rush, 0, 0.35)
    # ... into low strings struck hard together (D minor), a timpani and a bass drum
    notes = [Note(GM["tremolo_strings"], n, 0.0, 0.2, vel=127) for n in ("D3", "F3", "A3")]
    notes += [Note(GM["cello"], "D3", 0.0, 0.2, vel=127), Note(GM["contrabass"], "D2", 0.0, 0.2, vel=96),
              Note(GM["timpani"], "D3", 0.0, 0.4, vel=120)]
    x = A.mix_at(x, _norm(_choke(_stem(notes, 1.6, "musescore"), 0.16, 0.6)), hit, 0.9)
    x = A.mix_at(x, 0.35 * _norm(_choke(_hit("bass_drum", 120, kit="orchestra"), 0.1, 0.4)), hit, 1.0)
    return _finish(_glue(_verb(x, 0.6, 0.22, damping=0.7), 15.5), 1.35, 0.45, hp=50, lp=6000)


def _suffer_toll() -> np.ndarray:
    d = 1.4
    # a low bell tolls once over a muffled timpani
    notes = [Note(GM["tubular_bells"], "D4", 0.0, 1.0, vel=112), Note(GM["tubular_bells"], "A3", 0.0, 1.0, vel=70),
             Note(GM["timpani"], "D2", 0.0, 0.4, vel=110), Note(GM["timpani"], "D3", 0.0, 0.4, vel=90)]
    x = _choke(_fit(_stem(notes, d + 0.4), d), 0.4, 1.0)
    return _finish(_verb(x, 0.6, 0.2), 1.35, 0.5, hp=55, lp=6000)


# ============================================================================= jester
BELLS = ["D6", "E6", "F#6", "A6", "B6", "D7", "E7"]


def _cap_bells(shakes: Sequence[Tuple[float, float]], d: float, seed: int, per: int = 5,
               spread: float = 0.03) -> np.ndarray:
    """The little bells on a jester's cap, shaken at (time, strength): each shake rings a
    handful of small bells a few milliseconds apart."""
    rng = np.random.default_rng(seed)
    notes = []
    for t0, s in shakes:
        for b in range(per):
            at = t0 + (rng.uniform(0, spread) if b else 0.0)
            notes.append(Note(GM["tinkle_bell"], str(rng.choice(BELLS)), round(at, 4), 0.12,
                              vel=int(np.clip(s * rng.uniform(70, 110), 20, 127))))
    return _fit(_sf(notes, d + 0.6, "musescore"), d)


def _jester_bells() -> np.ndarray:
    d = 2.0
    shakes = [(0.0, 1.0), (0.12, 0.75), (0.24, 0.85), (0.48, 0.7), (0.6, 0.8), (0.72, 1.0)]
    x = _cut(_cap_bells(shakes, d + 0.1, 601))
    # the cap's cloth and the bells' slots: a shaken rattle under the ring
    x = A.mix_at(x, 0.22 * _norm(_tambourine([(t, int(60 * s)) for t, s in shakes], 1.2, lp=6000)), 0, 1.0)
    x = A.peak_eq(x, 6000, -3.0, 0.8)
    return _finish(_verb(x, 0.35, 0.15), 1.6, 0.5, hp=150, lp=7000)


def _jester_jig() -> np.ndarray:
    d = 2.0
    e = 0.11
    tune = ["A5", "B5", "A5", "F#5", "D5", "F#5", "A5", "B5", "D6"]
    notes = []
    for i, n in enumerate(tune):
        t0 = i * e
        if i == 3:                                   # a cut: a flick of a higher note
            notes += [Note(GM["recorder"], "B5", t0, 0.02, vel=96),
                      Note(GM["recorder"], n, t0 + 0.02, e - 0.02, vel=104)]
        elif i == len(tune) - 1:                     # the last note, held, with a cut into it
            notes += [Note(GM["recorder"], "E6", t0, 0.025, vel=100),
                      Note(GM["recorder"], n, t0 + 0.025, 0.55, vel=108)]
        else:
            notes.append(Note(GM["recorder"], n, t0, e, vel=104 if i % 3 == 0 else 92))
    x = _fit(_stem(notes, d + 0.4, "musescore"), d)
    end = (len(tune) - 1) * e
    # a tabor and a tambourine on the beats, the cap's bells on the last note
    tabor = _choke(_hit("snare", 64, kit="orchestra", bank="musescore"), 0.04, 0.2)
    for tt in (0.0, 3 * e, 6 * e, end):
        x = A.mix_at(x, 0.1 * _norm(tabor), tt, 1.0)
    x = A.mix_at(x, 0.1 * _norm(_tambourine([(0.0, 70), (3 * e, 55), (6 * e, 60)], 1.0)), 0, 1.0)
    x = A.mix_at(x, 0.18 * _norm(_cap_bells([(0.0, 0.8)], 0.8, 612, per=4)), end, 1.0)
    return _finish(_verb(x, 0.35, 0.16), 1.95, 0.45, hp=100, lp=7600)


def _jester_fiddle() -> np.ndarray:
    d = 2.0
    # a fiddler's trick: a plucked string, then the bow slides up an octave, turns a quick
    # tune, and two more plucks end it
    notes = [Note(GM["pizzicato"], "A4", 0.0, 0.15, vel=118), Note(GM["pizzicato"], "D5", 0.0, 0.15, vel=100),
             Note(GM["violin"], "D6", 0.07, 0.28, vel=112, bend=(-12.0, 0.0))]
    for i, n in enumerate(["B5", "A5", "F#5", "A5"]):
        notes.append(Note(GM["violin"], n, 0.37 + 0.085 * i, 0.085, vel=108))
    notes.append(Note(GM["violin"], "D6", 0.71, 0.32, vel=112))
    notes += [Note(GM["pizzicato"], "D4", 1.1, 0.2, vel=110), Note(GM["pizzicato"], "A4", 1.24, 0.2, vel=118)]
    x = _fit(_stem(notes, d + 0.4, "musescore"), d)
    return _finish(_verb(x, 0.4, 0.16), 1.9, 0.45, hp=120, lp=7500)


def _jester_musicbox() -> np.ndarray:
    d = 2.0
    # "nyah-nyah": the teasing chant (A F# B A F#) on a music box, with D under it
    tune = [(0.0, "A5"), (0.22, "F#5"), (0.33, "B5"), (0.44, "A5"), (0.66, "F#5")]
    notes = [Note(GM["music_box"], n, t, 0.4, vel=104) for t, n in tune]
    notes += [Note(GM["music_box"], "D5", 0.0, 0.5, vel=80), Note(GM["music_box"], "D5", 0.66, 0.5, vel=80),
              Note(GM["music_box"], "D7", 0.9, 0.4, vel=60)]
    x = _fit(_stem(notes, d + 0.4, "musescore"), d)
    x = A.mix_at(x, 0.1 * _norm(_cap_bells([(0.0, 0.6)], 0.8, 631, per=4)), 0.88, 1.0)
    return _finish(_verb(x, 0.4, 0.2), 1.95, 0.5, hp=150, lp=7600)


def _jester_bassoon() -> np.ndarray:
    d = 2.0
    # the orchestra's clown: a bassoon hops about, then droops with a comic slide down,
    # a woodblock knocking under the hops
    hops = [("D3", 0.0), ("A2", 0.12), ("D3", 0.24), ("F#3", 0.36), ("A3", 0.48)]
    notes = [Note(GM["bassoon"], n, t, 0.08, vel=112) for n, t in hops]
    notes += [Note(GM["bassoon"], "A3", 0.66, 0.55, vel=116, bend=(0.0, -7.0))]
    notes += [Note(GM["pizzicato"], "D3", 0.0, 0.2, vel=90), Note(GM["pizzicato"], "D3", 0.24, 0.2, vel=80)]
    x = _fit(_stem(notes, d + 0.4, "musescore"), d)
    tok = _choke(_one("woodblock", "A4", 0.1, 90, seconds=0.4), 0.03, 0.15)
    for t in (0.0, 0.24, 0.48):
        x = A.mix_at(x, 0.15 * _norm(tok), t, 1.0)
    return _finish(_verb(x, 0.35, 0.14), 1.6, 0.4, hp=80, lp=7000)


# ============================================================================= yield
def _yield_cloth() -> np.ndarray:
    d = 0.9
    t = _t(d)
    rng = np.random.default_rng(701)
    grain = A.lowpass(rng.standard_normal(len(t)), 60, 1)
    grain = 1 + 0.6 * grain / (np.max(np.abs(grain)) or 1)
    # a cloak swings back (a quick swell), then settles with a long soft breath out
    env = _env(d, [(0, 0), (0.003, 0.45), (0.12, 1.0), (0.3, 0.6), (0.55, 0.25), (0.8, 0.0), (d, 0)])
    swish = _svf(_svf(A.noise(d, "pink", 702), A.glide(1400, 650, d), 0.8, "bp"), A.glide(1400, 650, d), 0.8, "bp")
    x = _norm(swish * grain * env)
    breath = A.lowpass(_one("breath", "D5", 0.5, 70, seconds=0.9), 2500, 2)
    breath = breath * _env(len(breath) / SR, [(0, 0), (0.1, 1.0), (0.5, 0.4), (0.8, 0)])
    x = A.mix_at(x, 0.25 * _norm(breath), 0.12, 1.0)
    return _finish(x, d, 0.25, lp=4000)


def _knock(seed: int, shift: float = 1.0) -> np.ndarray:
    """A knuckle rap on an oak table: the knuckle's soft click, the table top's damped
    modes and a woodblock's grain played an octave down."""
    d = 0.3
    modes = [(185 * shift, 0.6, 0.09), (N("D4") * shift, 1.0, 0.07), (440 * shift, 0.8, 0.06),
             (690 * shift, 0.55, 0.045), (1050 * shift, 0.35, 0.03), (1600 * shift, 0.2, 0.02)]
    y = _norm(_plank(modes, d, seed, 0.0015, 100, 3000))
    grain = _choke(_repitch(_hit("low_woodblock", 70, seconds=0.5), 0.5 * shift), 0.015, 0.06)
    y = A.mix_at(y, 0.35 * _norm(A.lowpass(grain, 2500, 2)), 0, 1.0)
    return y


def _yield_knock() -> np.ndarray:
    x = _buf(0.6)
    x = A.mix_at(x, _knock(721), 0, 1.0)
    x = A.mix_at(x, _knock(723, 1.03), 0.15, 0.8)
    return _finish(x, 0.6, 0.15)


def _yield_lute() -> np.ndarray:
    d = 1.2
    # one soft low lute note, its fifth brushed just after
    notes = [Note(GM["nylon_guitar"], "D3", 0.0, 0.9, vel=72), Note(GM["nylon_guitar"], "A3", 0.035, 0.9, vel=56)]
    x = _choke(_fit(_stem(notes, d + 0.4), d), 0.45, 1.0)
    return _finish(_verb(x, 0.35, 0.12), 1.15, 0.45, hp=70, lp=4500)


def _yield_viol() -> np.ndarray:
    d = 1.2
    # a viol sighs: two bowed notes falling a fifth, fading as the bow slows
    notes = [Note(GM["cello"], "A3", 0.0, 0.3, vel=88, swell=(110, 90)),
             Note(GM["cello"], "D3", 0.3, 0.55, vel=80, swell=(95, 40))]
    x = _fit(_stem(notes, d + 0.4, "musescore"), d)
    return _finish(_verb(x, 0.4, 0.14), 1.15, 0.4, hp=80, lp=4500)


def _yield_bell() -> np.ndarray:
    d = 1.2
    # a small chapel bell, struck softly and far away
    notes = [Note(GM["tubular_bells"], "D5", 0.0, 0.8, vel=64), Note(GM["harp"], "D4", 0.0, 0.6, vel=40)]
    x = _choke(_fit(_stem(notes, d + 0.4), d), 0.4, 1.0)
    return _finish(_verb(x, 0.6, 0.28, damping=0.6), 1.15, 0.45, hp=150, lp=3500)


CANDIDATES = [
    # hit: your attack lands and the enemy survives
    Candidate("hit", "sword_strike", "Sword strike",
              "A steel blade bites into a breastplate and rings, with the dull weight of the blow behind it.",
              _hit_sword, ["metal", "real"]),
    Candidate("hit", "leather_thump", "Leather thump",
              "A heavy, muffled thump into padded leather armour.",
              _hit_leather, ["soft", "real"]),
    Candidate("hit", "oak_shield", "Oak shield", "A mace knocks hard on a wooden shield.", _hit_oak, ["wooden"]),
    Candidate("hit", "arcane_bolt", "Arcane bolt",
              "A harp sweeps up and bursts into bright chiming bells over a kettledrum strike.",
              _hit_arcane, ["magic"]),
    Candidate("hit", "war_drum", "War drum",
              "A war drum's rattling snares over a deep bass drum and a kettledrum, struck once.",
              _hit_drum, ["drum", "grand"]),
    # defeat_enemy
    Candidate("defeat_enemy", "armor_collapse", "Armour collapse",
              "The enemy crashes down: plates clatter, chain mail settles, the helmet rocks still.",
              _defeat_armor, ["metal", "real"]),
    Candidate("defeat_enemy", "harp_descent", "Harp descent",
              "A gentle harp run falls two octaves to a low, quiet chord.",
              _defeat_harp, ["soft", "strings"]),
    Candidate("defeat_enemy", "lute_flourish", "Lute flourish",
              "A quick lute run and a full strummed chord over a tavern drum and a tambourine.",
              _defeat_lute, ["tavern"]),
    Candidate("defeat_enemy", "falling_bells", "Falling bells",
              "Church bells ring down a scale over a deep bell and a kettledrum.",
              _defeat_bells, ["bells", "grand"]),
    Candidate("defeat_enemy", "hunting_horns", "Hunting horns",
              "Two hunting horns sound the 'quarry is down' call over a kettledrum.",
              _defeat_horns, ["brass", "grand"]),
    # exact_kill
    Candidate("exact_kill", "gilded_card", "Gilded card",
              "A card flutters into your deck, slaps down and rings gold with chiming bells.",
              _exact_card, ["card", "bells"]),
    Candidate("exact_kill", "harp_glissando", "Harp glissando",
              "A harp sweeps up two octaves and rings out over a low note.",
              _exact_harp, ["strings"]),
    Candidate("exact_kill", "pipe_flourish", "Pipe flourish",
              "A wooden pipe runs up to a trilled high note over little drum taps.",
              _exact_pipe, ["tavern"]),
    Candidate("exact_kill", "royal_fanfare", "Herald trumpets",
              "Herald trumpets play a short fanfare over a rolling kettledrum.",
              _exact_fanfare, ["brass", "grand"]),
    Candidate("exact_kill", "golden_celesta", "Golden celesta",
              "A soft bell-piano (a celesta) climbs to a high chime over a quiet harp.",
              _exact_celesta, ["soft", "magic"]),
    # new_enemy
    Candidate("new_enemy", "drawn_blade", "Drawn blade",
              "A sword is drawn from its scabbard with a steely 'shiing' and rings free.",
              _new_blade, ["metal", "real"]),
    Candidate("new_enemy", "war_horn", "War horn",
              "A low horn call swells through the castle hall over a kettledrum.",
              _new_horn, ["brass", "ominous"]),
    Candidate("new_enemy", "doom_drum", "Doom drum",
              "Two deep drum booms over dark, low strings.",
              _new_drum, ["drum", "ominous"]),
    Candidate("new_enemy", "castle_gate", "Castle gate",
              "An iron latch lifts, an old oak gate creaks open and thuds against the stone.",
              _new_gate, ["wooden", "real"]),
    Candidate("new_enemy", "dark_strings", "Dark strings",
              "A soft drum roll as low strings shiver into a dark chord.",
              _new_strings, ["strings", "mysterious"]),
    # suffer
    Candidate("suffer", "heavy_blow", "Heavy blow",
              "A deep, dull body blow: a muffled drum thud and the slap of leather.",
              _suffer_heavy, ["real", "dark"]),
    Candidate("suffer", "armor_dent", "Armour dent",
              "A blunt mace dents your breastplate: a dark steel clang with a heavy thud.",
              _suffer_armor, ["metal", "dark"]),
    Candidate("suffer", "muffled_drum", "Muffled drum",
              "A soft, hand-muffled kettledrum and a low harp string: the gentle choice.",
              _suffer_drum, ["soft"]),
    Candidate("suffer", "shadow_strike", "Shadow strike",
              "A dark rush of air into a hard stab of low strings and drums.",
              _suffer_shadow, ["strings", "dark"]),
    Candidate("suffer", "tolling_bell", "Heavy bell",
              "A low church bell tolls once over a muffled drum.",
              _suffer_toll, ["bells", "dark"]),
    # jester
    Candidate("jester", "jester_bells", "Jester bells",
              "The little bells on a jester's cap, shaken to a playful rhythm.",
              _jester_bells, ["bells", "real"]),
    Candidate("jester", "whistle_jig", "Whistle jig",
              "A quick jig on a wooden whistle with a little drum, a tambourine and cap bells.",
              _jester_jig, ["tavern"]),
    Candidate("jester", "fiddle_trick", "Fiddle trick",
              "A plucked string, then a fiddle slides up, turns a quick tune and ends on two plucks.",
              _jester_fiddle, ["strings", "funny"]),
    Candidate("jester", "music_box", "Music box",
              "A tinkly music box plays the teasing 'nyah-nyah' tune, then a jingle of bells.",
              _jester_musicbox, ["funny"]),
    Candidate("jester", "bassoon_prank", "Bassoon prank",
              "A bassoon hops about over woodblock knocks, then droops with a comic slide.",
              _jester_bassoon, ["funny"]),
    # yield
    Candidate("yield", "cloth_sigh", "Cloth sigh",
              "A cloak swishes back and settles with a soft breath out, like a sigh.",
              _yield_cloth, ["soft", "real"]),
    Candidate("yield", "table_knock", "Table knock",
              "Two gentle knuckle knocks on an oak table: a card player's 'pass'.",
              _yield_knock, ["wooden", "real"]),
    Candidate("yield", "soft_lute", "Soft lute",
              "One soft, low lute note with its fifth brushed after it.",
              _yield_lute, ["soft", "strings"]),
    Candidate("yield", "viol_sigh", "Viol sigh",
              "A viol (a low bowed string) plays two quiet falling notes, fading as the bow slows.",
              _yield_viol, ["soft", "strings"]),
    Candidate("yield", "chapel_bell", "Chapel bell",
              "A small chapel bell struck softly, far away.",
              _yield_bell, ["soft", "bells"]),
]


# ============================================================================= the editor's pass
# Two finishing touches over the whole family, applied after each candidate renders:
#  - a phone's small speaker plays almost nothing below 300 Hz: a sound that would lose
#    more than PHONE_MAX_LOSS dB of its loudness there (less for the big moments, which
#    must stay the most present) gets a gentle low shelf (at most -8 dB below about
#    250 Hz), so after mastering its body is that much more present;
#  - in a turn the next sound follows closely (the app starts it once 60% of the previous
#    file has played), so the long ringers among the hits, defeats and exact kills are
#    damped from ``start`` (a hand on the strings, the bell or the drum) and over by ``end``.
PHONE_MAX_LOSS = {"defeat_enemy": 1.5, "exact_kill": 1.5}          # any other event: 3 dB
TAILS = {
    ("hit", "arcane_bolt"): (0.30, 0.62), ("hit", "sword_strike"): (0.20, 0.55), ("hit", "war_drum"): (0.22, 0.55),
    ("defeat_enemy", "lute_flourish"): (0.90, 1.40), ("defeat_enemy", "falling_bells"): (0.75, 1.30),
    ("defeat_enemy", "harp_descent"): (0.85, 1.35), ("defeat_enemy", "armor_collapse"): (1.15, 1.60),
    ("defeat_enemy", "hunting_horns"): (1.30, 1.70),
    ("exact_kill", "gilded_card"): (1.10, 1.75), ("exact_kill", "golden_celesta"): (0.90, 1.50),
    ("exact_kill", "harp_glissando"): (1.10, 1.65),
}


def _low_shelf(x: np.ndarray, f0: float, gain_db: float, q: float = 0.707) -> np.ndarray:
    """A low shelf (RBJ biquad): ``gain_db`` below ``f0``, half of it at ``f0``."""
    a_ = 10 ** (gain_db / 40.0)
    w0 = TAU * f0 / SR
    al = math.sin(w0) / (2 * q)
    c = math.cos(w0)
    s2 = 2 * math.sqrt(a_) * al
    b = [a_ * ((a_ + 1) - (a_ - 1) * c + s2), 2 * a_ * ((a_ - 1) - (a_ + 1) * c), a_ * ((a_ + 1) - (a_ - 1) * c - s2)]
    a = [(a_ + 1) + (a_ - 1) * c + s2, -2 * ((a_ - 1) + (a_ + 1) * c), (a_ + 1) + (a_ - 1) * c - s2]
    return signal.lfilter(b, a, x)


def _phone_loss(x: np.ndarray) -> float:
    return A._rms_db(x) - A._rms_db(A.highpass(x, 300, 4))


def _phone(x: np.ndarray, most: float) -> np.ndarray:
    if _phone_loss(x) <= most:
        return x
    for g in range(1, 9):
        y = _low_shelf(x, 250.0, -float(g))
        if _phone_loss(y) <= most:
            break
    return y


def _hasten(x: np.ndarray, start: float, end: float, drop_db: float = 40.0) -> np.ndarray:
    """Damp what still rings after ``start``: an extra fall of ``drop_db`` by ``end``,
    where the sound stops (the last few milliseconds faded)."""
    i0, i1 = _n(start), min(len(x), _n(end))
    if len(x) <= i0:
        return x
    y = x[:i1].copy()
    y[i0:] *= 10 ** (-drop_db / 20.0 * np.arange(i1 - i0) / max(1, i1 - i0))
    k = min(len(y), _n(0.006))
    y[-k:] *= np.linspace(1.0, 0.0, k)
    return y


def _edited(c: Candidate) -> Candidate:
    tail = TAILS.get((c.event, c.id))
    render = c.render

    def run() -> np.ndarray:
        x = _phone(render(), PHONE_MAX_LOSS.get(c.event, 3.0))
        return _hasten(x, *tail) if tail else x
    return dataclasses.replace(c, render=run)


CANDIDATES = [_edited(c) for c in CANDIDATES]
