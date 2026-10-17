"""Table and menu sounds: a button tap, a card pop-up, coins and the "not allowed" tone.

Everything here is acoustic: real wood, felt, card stock, parchment, leather and coins,
modelled from their physics, and real instruments recorded in the General MIDI banks
(``sf.py``): a woodblock, a nylon-strung guitar played like a lute, a harp, a celesta, a
glockenspiel, small hand bells, a bassoon and a soft hummed voice. Nothing is 8-bit and
no tone is a bare oscillator. Five candidates per event, each a different character:
the action itself, a soft one for long sessions, a wooden or tavern one, a courtly
instrumental one and a magical one (an event's taste decides which of these it gets).
The owner's picks keep their ids and names (wood_tick, card_flip), remade with real
recordings and better physics in the same spirit.

The button plays dozens of times a game, so its candidates are tiny (under a tenth of
a second), soft-edged and low in the high frequencies. Every sound starts at once (the
banks' few milliseconds of attack latency are cut, ``sf.onset``), decays on its own, has
its body between 300 Hz and 3 kHz where a phone's speaker plays, and keeps its energy
below about 8 kHz (only the crisp card has a little above). Tonal parts use D major
pentatonic (D E F# A B), with D dorian's F natural where a sound says "no".

The physical models (private to this file):
  _modal    struck objects (wood, a box, card stock, a casket): one resonator per mode,
            driven by a short pulse whose width is the hardness of what strikes (a
            fingertip 2-3 ms, a knuckle 1-1.5 ms, a fingernail or a coin 0.1-0.3 ms)
  _coin     a coin is a small free metal disc: modes at 1, 1.73, 2.33, 3.91 and 4.11
            times its lowest, each a close beating pair (no coin is perfectly round);
            every impact excites each mode by its own amount, and later impacts ring on
            top of what still sounds
  _crackle  card and parchment fibres: sparse tiny impacts, each a short ring at a
            random pitch, at a rate that follows how fast the sheet moves
  _creak    leather or a hinge under strain: stick-slip, a quick irregular train of tiny
            releases ringing the material's damped body
"""
from __future__ import annotations

import dataclasses
import functools
import math
from typing import Sequence, Tuple

import numpy as np
from scipy import signal

import sf
import synth as A
from catalog import EVENT_BY_ID, Candidate
from sf import DRUM, GM, Note

SR = A.SR
TAU = 2 * math.pi


def N(name: str) -> float:
    return A.note_hz(name)


# ----------------------------------------------------------------------------- basics
def _n(t: float) -> int:
    return int(round(t * SR))


def _t(d: float) -> np.ndarray:
    return np.arange(_n(d)) / SR


def _len(x: np.ndarray, d: float) -> np.ndarray:
    n = _n(d)
    return x[:n].copy() if len(x) >= n else np.concatenate([x, np.zeros(n - len(x))])


def _en(x: np.ndarray) -> np.ndarray:
    """Unit energy, so mixing gains set each layer's share of the energy."""
    e = math.sqrt(float(np.sum(x ** 2)) / SR * 1000.0)
    return x / e if e > 0 else x


def _rise(n: int, attack: float) -> np.ndarray:
    e = np.ones(n)
    k = min(n, max(2, _n(attack)))
    e[:k] = 0.5 - 0.5 * np.cos(np.pi * np.arange(k) / k)
    return e


def _env(d: float, tau: float, attack: float = 0.0005) -> np.ndarray:
    """exp(-t / tau) after a raised-cosine rise."""
    return np.exp(-_t(d) / max(tau, 1e-5)) * _rise(_n(d), attack)


def _tail(x: np.ndarray, sec: float) -> np.ndarray:
    k = min(len(x), max(2, _n(sec)))
    y = x.copy()
    y[-k:] *= 0.5 + 0.5 * np.cos(np.pi * np.linspace(0.0, 1.0, k))
    return y


def _mix(parts, d: float) -> np.ndarray:
    """[(sound, at seconds, gain), ...] mixed into one buffer ``d`` seconds long."""
    buf = np.zeros(max(1, _n(d)))
    for snd, at, g in parts:
        buf = A.mix_at(buf, snd, at, g)
    return buf[:_n(d)]


def _noise(n: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal(n)


def _band(x: np.ndarray, lo: float, hi: float, order: int = 2) -> np.ndarray:
    return A.bandpass(x, lo, hi, order)


# ----------------------------------------------------------------------------- recordings
@functools.lru_cache(maxsize=None)
def _bank_cached(key: tuple, seconds: float, bank: str) -> np.ndarray:
    return sf.render([Note(*k) for k in key], seconds, bank=bank)


def _bank(notes: Sequence[Note], seconds: float, bank: str = "fluid", cut: float = -50.0) -> np.ndarray:
    """Render ``notes`` from a bank (cached), the bank's attack latency cut (at ``cut``
    dB below the peak) so the first note sounds at once."""
    key = tuple(dataclasses.astuple(n) for n in notes)
    x = _bank_cached(key, round(float(seconds), 4), bank).copy()
    if not cut:
        return x
    i = sf.onset(x, cut)
    k = min(_n(0.0004), i)
    y = x[i - k:]
    y[:k] *= np.linspace(0.0, 1.0, k) if k else 1.0
    return y


def _one(program: int, pitch, dur: float, vel: int, seconds: float, bank: str = "fluid", **kw) -> np.ndarray:
    return _bank([Note(program, pitch, 0.0, dur, vel=vel, **kw)], seconds, bank)


def _drum(key, vel: int, seconds: float, kit: str = "standard", bank: str = "fluid") -> np.ndarray:
    return _bank([Note(DRUM, key, 0.0, 0.2, vel=vel, kit=kit)], seconds, bank)


def _damp(x: np.ndarray, hold: float, tau: float, total: float = 0.0) -> np.ndarray:
    """A hand on the strings (or on the bell): full level for ``hold`` seconds, then an
    exponential fall (time constant ``tau``) to zero by ``total``."""
    total = total or hold + 7 * tau
    n = min(len(x), _n(total))
    t = np.arange(n) / SR
    env = np.where(t < hold, 1.0, np.exp(-(t - hold) / max(tau, 1e-4)))
    return _tail(x[:n] * env, min(0.03, total * 0.2))


# ----------------------------------------------------------------------------- physics
def _reson(x: np.ndarray, f: float, t60: float) -> np.ndarray:
    """A two-pole resonator at ``f`` ringing for ``t60`` seconds; an impulse gives a
    unit-amplitude damped sine."""
    w = TAU * min(f, SR * 0.45) / SR
    r = 10 ** (-3.0 / (max(t60, 1e-4) * SR))
    return signal.lfilter([math.sin(w)], [1.0, -2 * r * math.cos(w), r * r], x)


def _strike(width: float, seed: int = 0, rough: float = 0.0) -> np.ndarray:
    """What strikes: a Hann pulse ``width`` seconds wide with unit area (its spectrum
    falls away above about 1 / width), roughened a little for a gritty contact."""
    k = _n(width)
    if k < 3:
        return np.array([1.0])
    w = np.hanning(k + 2)[1:-1]
    if rough:
        w = w * (1 + rough * np.random.default_rng(seed).uniform(-1, 1, k))
    return w / np.sum(np.abs(w))


def _modal(d: float, modes, width: float, hits=((0.0, 1.0),), seed: int = 0, rough: float = 0.0,
           split: float = 0.0) -> np.ndarray:
    """An object with modes [(Hz, t60, gain), ...] struck at ``hits`` [(seconds, amp)];
    ``split`` makes each mode a slightly detuned, beating pair."""
    n = _n(d)
    exc = np.zeros(n)
    for at, amp in hits:
        i = _n(at)
        if i < n:
            exc[i] += amp
    exc = np.convolve(exc, _strike(width, seed, rough))[:n]
    rng = np.random.default_rng(seed + 7)
    y = np.zeros(n)
    for f, t60, g in modes:
        if f >= SR * 0.45 or g == 0:
            continue
        if split:
            dv = f * split * rng.uniform(0.5, 1.0)
            y += g * 0.5 * (_reson(exc, f - dv / 2, t60) + _reson(exc, f + dv / 2, t60))
        else:
            y += g * _reson(exc, f, t60)
    return y


def _click(d: float, lo: float, hi: float, tau: float, seed: int) -> np.ndarray:
    """The contact noise of an impact: a breath of band-passed noise."""
    return _band(_noise(_n(d), seed) * _env(d, tau, 0.0002), lo, hi)


def _crackle(d: float, rate, band: Tuple[float, float], seed: int, ring: float = 0.002, spread: float = 1.0,
             shape=None) -> np.ndarray:
    """Sparse tiny impacts (Poisson at ``rate`` per second, (start, end) or a function of
    time), each a short ring at a random pitch in ``band``, strengths heavy-tailed."""
    rng = np.random.default_rng(seed)
    n = _n(d)
    y = np.zeros(n)
    m = _n(ring * 7)
    imp = np.zeros(m)
    imp[0] = 1.0
    t = 0.0
    while True:
        r = rate(t) if callable(rate) else rate[0] + (rate[1] - rate[0]) * min(1.0, t / d)
        if r <= 0:
            break
        t += rng.exponential(1.0 / r)
        if t >= d:
            break
        f = math.exp(rng.uniform(math.log(band[0]), math.log(band[1])))
        amp = min(1.0, rng.pareto(2.0) * 0.4 + 0.1) ** spread
        if shape is not None:
            amp *= shape(t)
        s = _reson(imp, f, ring)
        i = _n(t)
        k = min(m, n - i)
        y[i:i + k] += amp * s[:k] * (1 if rng.random() < 0.5 else -1)
    return y


def _creak(d: float, seed: int, rate: float, f: float, swell: bool = True, jitter: float = 0.7,
           glide: float = 1.0) -> np.ndarray:
    """Leather or a hinge under strain: stick-slip, a train of tiny releases (``rate`` a
    second at the strain's peak, gliding by ``glide`` over the sound), each ringing the
    material's damped body. Leather slips irregularly (``jitter`` near 1, a crackly
    groan); a hinge slips almost regularly (a low ``jitter``: a pitched creak)."""
    rng = np.random.default_rng(seed)
    n = _n(d)
    exc = np.zeros(n)
    t = 0.0
    while t < d:
        u = t / d
        k = (0.35 + 0.65 * math.sin(math.pi * u)) if swell else 1.0
        r = rate * (0.5 + 0.5 * k) * glide ** u
        t += rng.exponential(1.0 / r) * jitter + (1 - jitter) / r
        i = _n(t)
        if i < n:
            exc[i] = rng.uniform(0.3, 1.0) * k
    y = sum(g * _reson(exc, f * m, T) for m, g, T in ((1.0, 1.0, 0.012), (1.83, 0.6, 0.008), (2.9, 0.3, 0.005),
                                                       (0.55, 0.5, 0.015)))
    return _band(y, 250, 4000, 1)


# (ratio to the lowest mode, share of the ring time, gain): a thin free disc
_COIN = ((1.0, 1.0, 1.0), (1.73, 0.8, 0.8), (2.33, 0.65, 0.65), (3.91, 0.4, 0.3), (4.11, 0.35, 0.25))


def _coin(d: float, hits, f1: float, t60: float, seed: int, width: float = 0.00012,
          fmax: float = 7800.0, split: float = 0.0022, hi_gain: float = 1.0) -> np.ndarray:
    """A coin whose lowest mode is ``f1``, struck at ``hits`` [(seconds, amp)]."""
    n = _n(d)
    rng = np.random.default_rng(seed)
    k = _strike(width)
    y = np.zeros(n)
    for j, (ratio, ts, g) in enumerate(_COIN):
        f = f1 * ratio
        if f > fmax:
            continue
        if j >= 3:
            g *= hi_gain
        dv = f * split * rng.uniform(0.5, 1.0)
        for ff in (f - dv / 2, f + dv / 2):
            exc = np.zeros(n)
            for at, amp in hits:
                i = _n(at)
                if i < n:
                    exc[i] += amp * rng.uniform(0.3, 1.0)
            y += g * _reson(np.convolve(exc, k)[:n], ff, t60 * ts)
    return y


@functools.lru_cache(maxsize=None)
def _ir(rt60: float, seed: int) -> np.ndarray:
    """A small room's impulse response: early reflections, then dense noise whose highs
    die about twice as fast as its lows."""
    n = _n(rt60 * 1.2)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(n)
    lo = A.lowpass(w, 1200, 2) * np.exp(-6.9078 * t / rt60)
    hi = A.lowpass(A.highpass(w, 1200, 2), 7000, 2) * np.exp(-6.9078 * t / (rt60 * 0.45))
    ir = (lo + 0.7 * hi) * np.clip((t - 0.008) / 0.012, 0, 1)
    ref = math.sqrt(np.mean(ir[:_n(0.05)] ** 2)) * 30
    for k in range(7):
        ir[_n(rng.uniform(0.004, 0.028))] += rng.uniform(0.25, 0.6) * (1 if k % 2 else -1) * ref
    return ir / math.sqrt(float(np.sum(ir ** 2)))


def _room(x: np.ndarray, rt60: float = 0.4, wet: float = 0.15, seed: int = 5) -> np.ndarray:
    """``x`` heard in a small room (the dry sound plus ``wet`` of the room, by energy)."""
    ir = _ir(round(rt60, 3), seed)
    w = signal.fftconvolve(x, ir)[:len(x)]
    return x + wet * w * (math.sqrt(np.sum(x ** 2)) / (math.sqrt(np.sum(w ** 2)) + 1e-12))


def _svf_bp(x: np.ndarray, fc, q: float = 1.0) -> np.ndarray:
    """A band-pass (state-variable, unity gain at the centre) whose centre may move."""
    fc = np.broadcast_to(np.asarray(fc, float), x.shape)
    g = np.tan(np.pi * np.clip(fc, 20.0, SR * 0.45) / SR)
    k = 1.0 / q
    a1 = 1.0 / (1.0 + g * (g + k))
    a2 = g * a1
    a3 = g * a2
    a1, a2, a3, xs = a1.tolist(), a2.tolist(), a3.tolist(), x.tolist()
    out = [0.0] * len(xs)
    ic1 = ic2 = 0.0
    for i, v0 in enumerate(xs):
        v3 = v0 - ic2
        v1 = a1[i] * ic1 + a2[i] * v3
        v2 = ic2 + a2[i] * ic1 + a3[i] * v3
        ic1 = 2 * v1 - ic1
        ic2 = 2 * v2 - ic2
        out[i] = k * v1
    return np.asarray(out)


# ----------------------------------------------------------------------------- finishing
def _softlimit(x: np.ndarray, ceil: float, look: float = 0.0015, release: float = 0.02) -> np.ndarray:
    """A peak limiter whose gain never steps: the gain each sample needs, held over the
    look-ahead on both sides, recovered with a one-pole release, then smoothed by a Hann
    window no wider than the hold (so it turns down over a millisecond or two instead of
    clicking)."""
    from scipy.ndimage import minimum_filter1d
    w = max(2, _n(look))
    want = np.minimum(1.0, ceil / np.maximum(np.abs(x), 1e-12))
    g = minimum_filter1d(want, size=2 * w + 1)
    a = math.exp(-1.0 / max(1, _n(release)))
    out = [1.0] * len(g)
    prev = 1.0
    for i, v in enumerate(g.tolist()):
        prev = v if v < prev else prev + (1 - a) * (v - prev)
        out[i] = prev
    k = np.hanning(2 * w + 1)
    g = np.convolve(np.pad(np.asarray(out), (w, w), mode="edge"), k / k.sum(), mode="valid")
    return x * g


def _fit(x: np.ndarray, event: str, hp: float = 40.0, lp: float = 9000.0, fade: float = 0.0,
         margin_db: float = 1.0, max_shave_db: float = 4.0) -> np.ndarray:
    """Finish a sound for its event: no rumble below ``hp``, nothing harsh above ``lp``,
    inside the event's length with a natural fade, and, if its first peak would sit
    above the master's ceiling, that first instant rounded off (``_softlimit``) by
    ``max_shave_db`` at most: an impact's loudness lives in its first few milliseconds,
    so shaving more would only flatten the blow; the master's gentle limiter does the
    rest."""
    ev = EVENT_BY_ID[event]
    y = A.highpass(x, hp, 2) if hp else x - float(np.mean(x))
    if lp:
        y = A.lowpass(y, lp, 2)
    nmax = _n(ev.max_seconds - 0.015)
    if len(y) > nmax:
        y = y[:nmax]
    y = _tail(y, fade or min(0.03, len(y) / SR * 0.3))
    allowed = -1.0 - margin_db - ev.loudness_db
    shaved = 0.0
    for _ in range(6):
        pk = 20 * math.log10(float(np.max(np.abs(y))) + 1e-12)
        c = pk - A._rms_db(y)
        if c <= allowed or shaved >= max_shave_db:
            break
        cut = min(c - allowed + 0.3, max_shave_db - shaved)
        y = _softlimit(y, 10 ** ((pk - cut) / 20.0), release=0.012)
        shaved += cut
    return y


# ============================================================================= button
def _btn_wood() -> np.ndarray:
    """A real woodblock tapped very lightly with a fingernail and stilled at once by the
    other hand, over the faint knock of the small block's own body: a tiny dry tick."""
    wb = _damp(_drum("hi_woodblock", 60, 0.6), 0.006, 0.009, 0.08)
    f = N("D5")
    body = _modal(0.09, [(f, 0.06, 1.0), (f * 2.76, 0.03, 0.35), (N("D4"), 0.05, 0.3)], 0.0009, seed=12)
    y = _mix([(_en(wb), 0.0, 1.0), (_en(body), 0.0, 0.45)], 0.09)
    return A.lowpass(y, 4000, 2)


def _btn_felt() -> np.ndarray:
    """A fingertip on the felt-covered table: the board under the cloth gives a soft,
    damped knock, with the muffled pat of skin on felt (a real brushed drum's tap,
    filtered down to its felt-like grain)."""
    d = 0.08
    body = _modal(d, [(N("F#3"), 0.06, 0.25), (N("F#4"), 0.05, 1.0), (N("E5"), 0.035, 0.8), (N("D6"), 0.02, 0.3)],
                  0.0022, seed=11)
    brush = _damp(_drum(38, 45, 0.5, kit="brush"), 0.01, 0.01, 0.08)
    brush = _band(brush, 400, 2500, 2)
    y = _mix([(_en(body), 0.0, 1.0), (_en(brush), 0.0, 0.4)], d)
    return A.lowpass(A.peak_eq(y, 650, 4.0, 1.0), 3000, 2)


def _btn_card() -> np.ndarray:
    """A fingernail taps the edge of a playing card: a crisp little tick of card stock,
    the card's short papery ring and the faint knock of the deck beneath."""
    d = 0.06
    nail = _click(d, 2000, 6000, 0.0008, 21)
    card = _modal(d, [(1650, 0.022, 1.0), (2380, 0.016, 0.7), (3460, 0.01, 0.35), (1120, 0.026, 0.6)], 0.0006,
                  seed=22, rough=0.5)
    deck = _modal(d, [(N("A4"), 0.04, 1.0), (N("E5"), 0.03, 0.5)], 0.0015, seed=23)
    return _mix([(_en(card), 0.0, 1.0), (_en(nail), 0.0, 0.2), (_en(deck), 0.001, 0.5)], d)


def _btn_lute() -> np.ndarray:
    """A fingertip touches a lute's A string and stills it at once: a tiny, soft, damped
    pluck."""
    s = _bank([Note(GM["nylon_guitar"], "A4", 0.0, 0.1, vel=70)], 0.8, "fluid", cut=-30.0)
    return _damp(s, 0.02, 0.018, 0.12)


def _btn_bell() -> np.ndarray:
    """A tiny hand bell touched on D and stilled by a finger: a soft, short ting."""
    b = _one(GM["tinkle_bell"], "D6", 0.1, 60, 0.8, "musescore")
    b = _damp(b, 0.012, 0.022, 0.13)
    return A.lowpass(b, 5000, 2)


# ============================================================================= popup
def _pop_flip() -> np.ndarray:
    """A card flipped over onto the felt: the thumb lets the edge go (a crisp snap of
    card stock), the card turns in the air (a soft rush of air), then lands flat (a
    paper slap, the 'pff' of air pushed out from under it and the felt's soft thump)
    and settles with a faint papery crackle."""
    d = 0.4
    snap = _click(0.03, 1800, 7000, 0.0016, 31)
    stock = _modal(0.05, [(1650, 0.012, 1.0), (2380, 0.009, 0.7), (3460, 0.006, 0.4), (1120, 0.015, 0.5)], 0.0003,
                   seed=32, rough=0.5)
    m = _n(0.085)
    tt = np.linspace(0.0, 1.0, m)
    fc = 900.0 * (2200.0 / 900.0) ** np.sin(np.pi * tt * 0.8)
    grain = np.clip(0.65 + 0.9 * A.lowpass(np.random.default_rng(33).uniform(-1, 1, m), 150, 1), 0.2, 1.2)
    air = _svf_bp(_noise(m, 33), fc, 1.4) * np.sin(np.pi * tt) ** 2.2 * grain
    land = 0.1
    slap = _click(0.06, 450, 4000, 0.006, 34)
    pff = A.lowpass(_noise(_n(0.04), 35), 900, 2) * _env(0.04, 0.008, 0.002)
    thump = _modal(0.15, [(N("E3"), 0.12, 0.8), (N("F#4"), 0.07, 1.0), (N("F#5"), 0.04, 0.3)], 0.002, seed=36)
    brush = _band(_damp(_drum(38, 40, 0.5, kit="brush"), 0.015, 0.015, 0.1), 400, 6000, 2)
    settle = _crackle(0.06, (500.0, 100.0), (1500.0, 6000.0), 37, ring=0.0012, spread=0.6)
    y = _mix([(_en(snap), 0.0, 0.5), (_en(stock), 0.0, 0.3), (_en(air), 0.008, 0.6),
              (_en(slap), land, 0.7), (_en(pff), land, 0.3), (_en(thump), land, 0.55), (_en(brush), land, 0.3),
              (_en(settle), land + 0.01, 0.12)], d)
    return _room(y, 0.35, 0.08, 38)


def _pop_harp() -> np.ndarray:
    """A harp plays two soft notes, A then D, and lets them ring a moment: a gentle
    'here you are'."""
    x = _bank([Note(GM["harp"], "A4", 0.0, 0.5, vel=72), Note(GM["harp"], "D5", 0.09, 0.5, vel=78)], 1.4,
              "musescore")
    x = _damp(x, 0.38, 0.07, 0.68)
    return _room(_len(x, 0.69), 0.6, 0.12, 41)


def _pop_casket() -> np.ndarray:
    """A small wooden casket is opened: its little iron latch clicks, the lid's hinge
    creaks briefly as it swings, and the lid knocks back against its stop."""
    d = 0.62
    latch = _modal(0.12, [(2650, 0.05, 1.0), (3920, 0.035, 0.5), (1780, 0.04, 0.4)], 0.0003, seed=51, split=0.003)
    latch_wood = _modal(0.12, [(N("A5"), 0.03, 1.0), (N("E6"), 0.02, 0.5)], 0.0008, seed=52)
    creak = _creak(0.17, 53, 330.0, 900.0, jitter=0.04, glide=1.35)
    lid = _modal(0.4, [(N("D4"), 0.07, 0.6), (N("A4") * 1.04, 0.06, 1.0), (N("E5") * 0.97, 0.045, 0.7),
                       (N("B5"), 0.03, 0.4), (2350, 0.02, 0.2)], 0.0012, seed=54, rough=0.3)
    y = _mix([(_en(latch), 0.0, 0.45), (_en(latch_wood), 0.0, 0.4), (_en(creak), 0.04, 0.35), (_en(lid), 0.21, 1.0)],
             d)
    return _room(y, 0.4, 0.12, 55)


def _pop_parchment() -> np.ndarray:
    """A sheet of parchment unrolled on the table (a grainy rustle, the dry crackles of
    its fibres bending and a soft flump as it settles), over a soft lute strum of A and
    D."""
    d = 0.68
    m = _n(0.28)
    pts = [(0, 0.0), (0.003, 0.7), (0.09, 1.0), (0.19, 0.55), (0.28, 0.0)]
    gesture = np.interp(_t(0.28), *zip(*pts))
    rng = np.random.default_rng(61)
    k = max(4, m // 220)
    grains = A.lowpass(np.repeat(rng.uniform(0.05, 1.0, k), int(math.ceil(m / k)))[:m], 400, 1)
    bed = _band(_noise(m, 62), 700, 4000) * grains * gesture
    crack = _crackle(0.28, lambda t: 130.0 * float(np.interp(t, *zip(*pts))) + 5, (1800.0, 6000.0), 63,
                     ring=0.0012, spread=0.8, shape=lambda t: float(np.interp(t, *zip(*pts))))
    flump = _modal(0.12, [(N("E3"), 0.08, 1.0), (N("E4"), 0.05, 0.6)], 0.003, seed=64)
    lute = _bank([Note(GM["nylon_guitar"], "A4", 0.0, 0.5, vel=70), Note(GM["nylon_guitar"], "D5", 0.022, 0.5, vel=66)],
                 1.4, "fluid")
    lute = _damp(lute, 0.42, 0.06)
    y = _mix([(_en(bed), 0.0, 0.45), (_en(crack), 0.0, 0.45), (_en(flump), 0.2, 0.3), (_en(lute), 0.0, 0.85)], d)
    return _room(y, 0.4, 0.1, 65)


def _pop_fairy() -> np.ndarray:
    """A harp ripples up D major pentatonic and a celesta sparkles at the top, like magic
    revealing a card."""
    gl = ["A4", "B4", "D5", "E5", "F#5", "A5", "B5", "D6"]
    harp = _bank([Note(GM["harp"], nm, 0.022 * k, 0.4, vel=66 + 3 * k) for k, nm in enumerate(gl)], 1.4, "musescore")
    cel = _bank([Note(GM["celesta"], "F#6", 0.0, 0.3, vel=70), Note(GM["celesta"], "A6", 0.05, 0.3, vel=72),
                 Note(GM["celesta"], "D7", 0.1, 0.3, vel=74)], 1.4, "musescore")
    y = _mix([(_en(harp), 0.0, 0.9), (_en(cel), 0.15, 0.5)], 0.9)
    y = _damp(y, 0.45, 0.06, 0.69)
    return _room(y, 0.7, 0.16, 71)


# ============================================================================= coin
def _coin_single() -> np.ndarray:
    """One gold coin dropped on the wooden table: it strikes, bounces ever faster, wobbles
    flat with a quickening chatter and is left ringing, damped by the table."""
    d = 1.12
    n = _n(d)
    hits = [(0.0, 1.0)]
    t, T, a = 0.0, 0.12, 1.0
    for _ in range(6):
        t += T
        T *= 0.6
        a *= 0.62
        hits.append((t, a))
    gap, a = 0.034, 0.3
    for _ in range(10):
        t += gap
        gap *= 0.84
        a *= 0.86
        hits.append((t, a))
    flat = t
    ring = _coin(d, hits, N("A6"), 0.9, seed=61)
    ring = ring * np.exp(-np.clip(_t(d) - flat, 0.0, None) / 0.16)
    tock = _modal(d, [(N("A4"), 0.03, 1.0), (N("B5"), 0.02, 0.5)], 0.0004, hits, seed=62)
    clicks = np.zeros(n)
    for k, (at, amp) in enumerate(hits):
        clicks = A.mix_at(clicks, _click(0.01, 2000, 7000, 0.0005, 70 + k), at, amp)
    y = _en(ring) + 0.12 * _en(tock) + 0.06 * _en(clicks[:n])
    return _room(y, 0.4, 0.08, 63)


def _coin_purse() -> np.ndarray:
    """A leather purse of coins set down: a soft heavy thud and a creak of the leather,
    while the coins inside clink against each other and settle, muffled a little."""
    d = 0.95
    rng = np.random.default_rng(81)
    thud = _modal(0.3, [(N("A2"), 0.14, 0.5), (N("A3"), 0.09, 1.0), (N("E4"), 0.06, 0.6), (N("B4"), 0.045, 0.4)],
                  0.004, seed=82, rough=0.3)
    creak = _creak(0.16, 83, 260.0, 520.0)
    sizes = [N("F#6"), N("A6"), N("B6"), N("D7")]
    clinks = []
    t = 0.004
    k = 0
    while t < 0.6:
        amp = rng.uniform(0.35, 1.0) * math.exp(-t / 0.25)
        f1 = sizes[rng.integers(len(sizes))] * rng.uniform(0.985, 1.015)
        f2 = sizes[rng.integers(len(sizes))] * rng.uniform(0.985, 1.015)
        c = _coin(0.28, [(0.0, 1.0)], f1, rng.uniform(0.12, 0.22), seed=100 + k, hi_gain=0.6) + \
            0.7 * _coin(0.28, [(0.0, 1.0)], f2, rng.uniform(0.1, 0.18), seed=200 + k, hi_gain=0.6)
        clinks.append((c, t, amp))
        k += 1
        t += rng.exponential(0.012 + 0.09 * t)
    coins = A.lowpass(_mix(clinks, d), 5000, 1)
    y = _mix([(_en(thud), 0.0, 0.5), (_en(creak), 0.01, 0.3), (_en(coins), 0.0, 1.0)], d)
    return _room(y, 0.4, 0.1, 84)


def _coin_count() -> np.ndarray:
    """Three coins counted onto the tavern table, one after another: each lands with a
    knock of the oak board and a short clink, the second and third onto the first."""
    d = 0.82
    parts = []
    for k, at in enumerate((0.0, 0.17, 0.34)):
        knock = _modal(0.12, [(N("B3"), 0.07, 1.0), (N("D5"), 0.045, 0.6), (N("A5") * 1.3, 0.025, 0.3)], 0.001,
                       seed=90 + k)
        if k == 0:
            clink = _coin(0.5, [(0.0, 1.0)], N("B6"), 0.45, seed=91, width=0.00025)
        else:      # onto the coins already there: two coins ring, a little brighter
            clink = _coin(0.5, [(0.0, 1.0)], N("B6") * (1 + 0.004 * k), 0.4, seed=91 + k, width=0.0002) + \
                0.6 * _coin(0.5, [(0.0, 1.0)], N("B6"), 0.3, seed=95 + k, width=0.0002)
        cl = _click(0.01, 1500, 6000, 0.0006, 97 + k)
        g = (0.9, 0.95, 1.0)[k]
        # the coin's edge touches first, its face lands flat on the wood a moment later
        parts += [(_en(clink), at, 0.9 * g), (_en(cl), at, 0.08 * g), (_en(knock), at + 0.003, 0.45 * g)]
    return _room(_mix(parts, d), 0.45, 0.1, 92)


def _coin_sparkle() -> np.ndarray:
    """A gold coin rings out, and a shower of real little bells (a glockenspiel, a
    celesta and tiny hand bells) falls through D major pentatonic, like coins of light."""
    d = 1.15
    ring = _coin(0.9, [(0.0, 1.0)], N("A6"), 0.8, seed=301)
    fall = ["D7", "B6", "A6", "F#6", "E6", "D6"]
    cel = _bank([Note(GM["celesta"], nm, 0.06 + 0.055 * k, 0.25, vel=82 - 4 * k) for k, nm in enumerate(fall)], 1.6,
                "musescore")
    glock = _bank([Note(GM["glockenspiel"], nm, 0.11 * k, 0.2, vel=58 - 5 * k) for k, nm in
                   enumerate(("A5", "F#5", "D5"))], 1.4, "fluid")
    bells = _bank([Note(GM["tinkle_bell"], nm, 0.09 * k, 0.2, vel=60 - 6 * k) for k, nm in
                   enumerate(("D6", "A5", "F#5"))], 1.4, "musescore")
    y = _mix([(_en(ring), 0.0, 0.8), (_en(cel), 0.0, 0.9), (_en(glock), 0.04, 0.25), (_en(bells), 0.08, 0.3)], d + 0.2)
    y = _damp(y, 0.7, 0.12, d)
    return A.lowpass(_room(y, 0.7, 0.18, 302), 7500, 2)


def _coin_lute() -> np.ndarray:
    """A few coins clink into an open palm, then a lute strums a bright D chord: the
    mercenary is paid."""
    d = 1.15
    parts = []
    for k, (at, f) in enumerate(((0.0, N("A6")), (0.045, N("B6")), (0.08, N("F#6")))):
        parts.append((_en(_coin(0.5, [(0.0, 1.0)], f * (1 + 0.003 * k), 0.22, seed=401 + k, hi_gain=0.7)), at,
                      0.8 - 0.15 * k))
    palm = A.lowpass(_noise(_n(0.05), 404), 800, 2) * _env(0.05, 0.01, 0.001)
    parts.append((_en(palm), 0.0, 0.25))
    strum = _bank([Note(GM["nylon_guitar"], nm, 0.014 * k, 0.6, vel=84 - 2 * k) for k, nm in
                   enumerate(("D4", "A4", "D5", "F#5"))], 1.6, "fluid")
    strum = _damp(strum, 0.5, 0.12)
    parts.append((_en(strum), 0.17, 1.0))
    return _room(_mix(parts, d), 0.6, 0.14, 405)


# ============================================================================= error
def _err_knock() -> np.ndarray:
    """Two knuckle knocks on a hollow wooden box, the second deeper: the box's air (A3,
    then E3) and its wooden walls."""
    def knock(f0: float, seed: int) -> np.ndarray:
        body = _modal(0.4, [(f0, 0.15, 0.45), (f0 * 2.42, 0.09, 1.0), (f0 * 4.1, 0.055, 0.7),
                            (f0 * 6.3, 0.03, 0.3)], 0.0012, seed=seed, rough=0.3)
        return _mix([(_en(body), 0.0, 1.0), (_en(_click(0.02, 700, 3000, 0.002, seed)), 0.0, 0.18)], 0.4)

    y = _mix([(knock(N("A3"), 121), 0.0, 1.0), (knock(N("E3"), 122), 0.17, 1.0)], 0.56)
    y = A.peak_eq(y, 650, 4.0, 0.9)
    return _room(A.lowpass(y, 3500, 2), 0.35, 0.08, 123)


def _err_lute() -> np.ndarray:
    """Two low lute notes muted by the palm, F then D (D dorian's minor third): a
    shrugging 'nuh-uh'."""
    a = _one(GM["nylon_guitar"], "F3", 0.15, 90, 0.8, "fluid")
    b = _one(GM["nylon_guitar"], "D3", 0.2, 92, 0.8, "fluid")
    a = A.lowpass(_damp(a, 0.03, 0.04), 1800, 2)
    b = A.lowpass(_damp(b, 0.05, 0.05), 1800, 2)
    thumb = A.lowpass(_noise(_n(0.03), 131), 1200, 2) * _env(0.03, 0.004, 0.0004)
    y = _mix([(_en(a), 0.0, 1.0), (_en(thumb), 0.0, 0.1), (_en(b), 0.16, 1.05), (_en(thumb), 0.16, 0.1)], 0.56)
    return A.peak_eq(y, 320, 3.0, 1.0)


def _err_bells() -> np.ndarray:
    """Two small hand bells, D then A below it, each stilled by a hand as soon as it
    rings: a polite, falling 'no'."""
    a = _damp(_one(GM["tinkle_bell"], "D5", 0.15, 80, 0.8, "musescore"), 0.06, 0.05)
    b = _damp(_one(GM["tinkle_bell"], "A4", 0.2, 82, 0.8, "musescore"), 0.09, 0.07)
    y = _mix([(_en(a), 0.0, 1.0), (_en(b), 0.15, 1.0)], 0.58)
    return A.lowpass(_room(y, 0.4, 0.1, 141), 5000, 2)


def _hum(pitch: str, hold: float, release: float) -> np.ndarray:
    """A real voice humming one note: the vowel's steady part only (the recording's own
    onset dips about a tenth of a second in, which would split a short note in two),
    entered with a quick, soft 'm' of 12 ms."""
    x = _bank([Note(GM["voice_oohs"], pitch, 0.0, 0.9, vel=92)], 1.4, "fluid")
    x = x[_n(0.16):]
    x = x * _rise(len(x), 0.012)
    return _damp(x, hold, release)


def _err_hum() -> np.ndarray:
    """A soft hummed 'mm-mm' from a real voice: A then F# below it (with the octave below
    sung softly), closed and warm."""
    a = _en(_hum("A4", 0.12, 0.03)) + 0.45 * _en(_hum("A3", 0.12, 0.03))
    b = _en(_hum("F#4", 0.2, 0.05)) + 0.45 * _en(_hum("F#3", 0.2, 0.05))
    y = _mix([(a, 0.0, 1.0), (b, 0.17, 0.95)], 0.58)
    return A.lowpass(y, 2500, 2)


def _err_bassoon() -> np.ndarray:
    """A bassoon says 'uh-uh': two short, soft low notes, A then F#, the second a little
    longer."""
    # the bank's bassoon A3 sits 12 cents flat: a steady bend puts it in tune
    a = _damp(_one(GM["bassoon"], "A3", 0.12, 85, 0.8, "musescore", bend=(0.12, 0.12)), 0.1, 0.03)
    b = _damp(_one(GM["bassoon"], "F#3", 0.2, 85, 0.8, "musescore"), 0.17, 0.05)
    y = _mix([(_en(a), 0.0, 1.0), (_en(b), 0.16, 1.0)], 0.56)
    return A.lowpass(y, 3000, 2)


# ============================================================================= candidates
def _fx(event: str, fn, **kw):
    return lambda: _fit(fn(), event, **kw)


CANDIDATES = [
    Candidate("button", "wood_tick", "Wood tick", "A tiny dry tick on a small wooden block, stilled at once.",
              _fx("button", _btn_wood, hp=120), ["wooden", "tavern"]),
    Candidate("button", "felt_tap", "Felt press", "A muffled fingertip tap on the felt table.",
              _fx("button", _btn_felt, hp=90), ["realistic", "soft"]),
    Candidate("button", "card_tap", "Card tap", "A fingernail taps the edge of a playing card: a crisp little tick.",
              _fx("button", _btn_card, hp=200, lp=8000), ["paper", "crisp"]),
    Candidate("button", "lute_touch", "Lute touch", "A fingertip touches a lute string and stills it: a tiny soft "
              "pluck.", _fx("button", _btn_lute, hp=120), ["courtly", "string"]),
    Candidate("button", "bell_tap", "Bell tap", "A tiny hand bell touched once and stilled: a soft, short ting.",
              _fx("button", _btn_bell, hp=200), ["magical", "bell"]),

    Candidate("popup", "card_flip", "Card flip", "A card snaps off the thumb, turns in the air and lands softly on "
              "the felt.", _fx("popup", _pop_flip, hp=80), ["realistic", "paper"]),
    Candidate("popup", "harp_touch", "Harp greeting", "A harp plays two soft notes, rising, and lets them ring a "
              "moment.", _fx("popup", _pop_harp, hp=80, fade=0.1), ["soft", "harp"]),
    Candidate("popup", "casket", "Casket", "A small wooden casket opens: the latch clicks, the hinge creaks and the "
              "lid knocks back.", _fx("popup", _pop_casket, hp=100), ["wooden", "tavern"]),
    Candidate("popup", "parchment", "Parchment", "A sheet of parchment unrolls over a soft lute strum.",
              _fx("popup", _pop_parchment, hp=80, fade=0.1), ["courtly", "paper"]),
    Candidate("popup", "fairy_reveal", "Fairy reveal", "A harp ripples upward and a celesta sparkles at the top, "
              "like magic revealing a card.", _fx("popup", _pop_fairy, hp=100, fade=0.1), ["magical", "harp"]),

    Candidate("coin", "gold_coin", "Gold coin", "One gold coin dropped on the table: it rings, bounces and settles.",
              _fx("coin", _coin_single, hp=200, fade=0.08), ["realistic", "metal"]),
    Candidate("coin", "coin_purse", "Coin purse", "A leather purse of coins set down with a soft thud and a heavy "
              "jingle.", _fx("coin", _coin_purse, hp=80, fade=0.12), ["realistic", "purse"]),
    Candidate("coin", "counting", "Counting coins", "Three coins counted onto the tavern table: clink, clink, clink.",
              _fx("coin", _coin_count, hp=100, fade=0.1), ["tavern", "wooden"]),
    Candidate("coin", "gold_sparkle", "Gold sparkle", "A gold coin rings and a shower of little bells, a celesta and "
              "a glockenspiel falls after it.", _fx("coin", _coin_sparkle, hp=200, fade=0.15), ["magical", "bells"]),
    Candidate("coin", "lute_coins", "Lute and coins", "A few coins clink into a palm, then a lute strums a bright "
              "chord.", _fx("coin", _coin_lute, hp=80, fade=0.15), ["courtly", "lute"]),

    Candidate("error", "hollow_knock", "Hollow knock", "Two knocks on a hollow wooden box, the second deeper.",
              _fx("error", _err_knock, hp=80, fade=0.08), ["wooden", "realistic"]),
    Candidate("error", "muted_lute", "Muted lute", "Two low lute notes muted by the palm, stepping down like a "
              "shrug.", _fx("error", _err_lute, hp=80, fade=0.08), ["courtly", "string"]),
    Candidate("error", "damped_bells", "Damped bells", "Two small hand bells, falling, each stilled by a hand as "
              "soon as it rings.", _fx("error", _err_bells, hp=150, fade=0.08), ["magical", "bell"]),
    Candidate("error", "low_hum", "Low hum", "A real voice softly hums a falling 'mm-mm'.",
              _fx("error", _err_hum, hp=120, fade=0.08), ["soft", "voice"]),
    Candidate("error", "bassoon_shrug", "Bassoon shrug", "A bassoon gives two short soft low notes going down, like "
              "a shrug.", _fx("error", _err_bassoon, hp=120, fade=0.08), ["tavern", "reed"]),
]
