"""Button taps modelled on the owner's reference: Pythonista's 'ui:switch21'.

The owner picked switch21, a small toggle switch, as how a menu button should feel, and
wondered about "something deeper". These candidates are built from scratch, in code,
from what happens when a small lever is thrown or a box is knocked; no part of the
reference recording is used, read or copied (it was only measured, offline, to set the
timings, levels and bands below). Nothing here is plastic: the materials are brass,
oak and a felt-topped wooden box.

What the reference is made of, and what models each part here:
  lift     the lever breaking away from its rest: a soft tick, then the detent's plunger
           riding up its ramp, a quick scuffing train of tiny contacts for about 6 ms
           (``_scuff``), ringing the housing 15 dB under the snap
  touch    4.5 ms before the snap, the lever brushing its far stop
  snap     27 ms after the lift. Brass meets brass: a tiny contact leaf rings at
           5-10 kHz for about 1.5 ms, with a spit of contact noise (``_grit``); half a
           millisecond later the lever strikes its stop (its own quick knock at
           1-2.5 kHz) and pushes the wooden housing through its bushing over about a
           millisecond (``_force``: each part feels its own force, whose width is how
           hard the contact is), so the housing's damped modes, 580 Hz to 2 kHz
           (``_ring``), swell for a few milliseconds before they die
  bounce   the lever rebounding in its seat, 5 and 11 ms after the snap, much weaker
  tail     two housing modes ringing on a little longer, 25-30 dB down, for 20 ms

Wood loses a fixed fraction of its energy each cycle, so each mode is given as how many
cycles it rings for (per 1/e), not a time: high modes die sooner, as in real timber, and
the sound stays a dry "tock" instead of a tone. Each mode's pitch is nudged by a seeded
random amount, the scuff's contacts fall at seeded random moments with heavy-tailed
strengths and each part is a slightly detuned pair, so nothing is perfectly regular;
every render comes out the same.

The reference is an 8-bit recording, so a faint hiss of its coding surrounds the click
and trails it to a quarter of a second. That hiss is left out (it also pulls the
reference's magnitude-weighted centroid up to 5.3 kHz; its power centroid, 2.2 kHz, is
the fair comparison). Its brightness is real, though: in the snap's first 2 ms the
reference is as loud at 6-12 kHz as at 400-1000 Hz, and the leaf and the lever give that
here. The close model was tuned against the reference band by band in 2 ms steps until
it measured like it: one onset, the lift 15 dB down and 26-27 ms ahead, the same band
split (half the energy at 400-1000 Hz, a quarter at 1-2.5 kHz, a tenth each at 2.5-6
and 6-12 kHz), 20 dB down 13 ms after the snap.

The other two answer the owner's "something deeper". The latch keeps the gesture (a
lift, a touch, the drop, small bounces), slower and in oak, its weight moved down to
150-1000 Hz; the knock is the deepest, a single felt-damped blow on a box, its weight at
150-400 Hz with enough at 400-1000 Hz to carry on a phone's small speaker. All three are
dry (20 dB down within 17 ms of the main hit) and under 0.12 s, for rapid taps.
"""
from __future__ import annotations

import math
from typing import Sequence, Tuple

import numpy as np
from scipy import signal

import synth as A
from catalog import EVENT_BY_ID, Candidate

SR = A.SR
TAU = 2 * math.pi
EVENT = "button"


# ----------------------------------------------------------------------------- basics
def _n(t: float) -> int:
    return int(round(t * SR))


def _t(n: int) -> np.ndarray:
    return np.arange(n) / SR


def _en(x: np.ndarray) -> np.ndarray:
    """Unit energy, so mixing gains set each part's share of the energy (gain squared)."""
    e = math.sqrt(float(np.sum(x ** 2)) / SR * 1000.0)
    return x / e if e > 0 else x


def _tail(x: np.ndarray, frac: float = 0.3) -> np.ndarray:
    """Fade the last ``frac`` of a buffer to zero (a raised cosine)."""
    k = min(len(x), max(2, int(len(x) * frac)))
    y = x.copy()
    y[-k:] *= 0.5 + 0.5 * np.cos(np.pi * np.linspace(0.0, 1.0, k))
    return y


def _gentle(x: np.ndarray, crest_db: float) -> np.ndarray:
    """A guard: keep the peak at most ``crest_db`` above the build's loudness measure by
    shaving only the first fraction of a millisecond of the sharpest contact (a fast
    look-ahead limiter). The candidates below are shaped to stay under it on their own,
    since shaving a low knock's peak would smear its spectrum."""
    for _ in range(3):
        ceil = A._rms_db(x) + crest_db
        if 20 * math.log10(float(np.max(np.abs(x))) + 1e-12) <= ceil + 0.05:
            break
        g = 10 ** (ceil / 20.0)
        x = A.limit(x / g, 0.0, lookahead=0.0006, release=0.01) * g
    return x


def _finish(x: np.ndarray, crest_db: float, hp: float, lp: float, fade: float = 0.3) -> np.ndarray:
    """Take out what a phone cannot play (below ``hp``) and the top above ``lp``, keep the
    sound well inside the event's length, let its end fade smoothly and guard the
    contact's peak."""
    y = A.lowpass(A.highpass(x, hp, 2), lp, 2)
    y = y[:_n(EVENT_BY_ID[EVENT].max_seconds - 0.02)]
    return _gentle(_tail(y, fade), crest_db)


# ----------------------------------------------------------------------------- the physical parts
def _pulse(width: float) -> np.ndarray:
    """What strikes, as a force: a Hann pulse ``width`` seconds wide with unit area. Its
    spectrum falls away above about 1 / width: brass on brass is a tenth of a
    millisecond, wood on wood a few tenths, a knuckle through felt over a millisecond."""
    k = _n(width)
    if k < 3:
        return np.array([1.0])
    w = np.hanning(k + 2)[1:-1]
    return w / np.sum(w)


def _force(n: int, hits: Sequence[Tuple[float, float, float]]) -> np.ndarray:
    """The force on one part: hits [(seconds, strength, width), ...]."""
    f = np.zeros(n)
    for at, amp, width in hits:
        p = _pulse(width) * amp
        i = _n(at)
        k = min(len(p), n - i)
        if k > 0:
            f[i:i + k] += p[:k]
    return f


def _scuff(n: int, start: float, dur: float, rate: float, amp: float, width: float, seed: int) -> np.ndarray:
    """A plunger (or a wooden bar) scuffing over its ramp: tiny contacts at about ``rate``
    a second for ``dur`` seconds from ``start``, at random moments, their strengths
    heavy-tailed and fading as it goes, each a narrow force pulse."""
    rng = np.random.default_rng(seed)
    hits = []
    t = start
    while True:
        t += rng.exponential(1.0 / rate)
        if t >= start + dur:
            break
        fall = 1.0 - 0.6 * (t - start) / dur
        s = min(2.5, rng.pareto(2.5) + 0.4) * fall * amp
        hits.append((t, s, width * rng.uniform(0.7, 1.4)))
    return _force(n, hits)


def _reson(x: np.ndarray, f: float, tau: float) -> np.ndarray:
    """A two-pole resonator at ``f`` whose ring falls by 1/e in ``tau`` seconds, heard as
    the pressure it radiates (zeros at 0 Hz and at the top: a vibrating panel pushes no
    air at a standstill); a unit impulse gives a unit-amplitude damped cosine, so a wider
    force rings it less."""
    w = TAU * min(f, SR * 0.45) / SR
    r = math.exp(-1.0 / (max(tau, 1e-5) * SR))
    return signal.lfilter([0.5, 0.0, -0.5], [1.0, -2 * r * math.cos(w), r * r], x)


def _ring(force: np.ndarray, modes: Sequence[Tuple[float, float, float]], seed: int, jitter: float = 0.015,
          split: float = 0.0) -> np.ndarray:
    """A struck part's damped modes [(Hz, gain, cycles), ...] driven by ``force``: each
    rings for ``cycles`` periods per 1/e (a fixed loss per cycle, as in wood: higher modes
    die sooner), its pitch nudged by up to ``jitter``; ``split`` makes each a slightly
    detuned beating pair (no real part is perfectly symmetric)."""
    rng = np.random.default_rng(seed)
    y = np.zeros(len(force))
    for f, g, cycles in modes:
        f = f * (1.0 + jitter * rng.uniform(-1.0, 1.0))
        tau = cycles / f
        if split:
            d = f * split * rng.uniform(0.5, 1.0)
            y += g * 0.5 * (_reson(force, f - d / 2, tau) + _reson(force, f + d / 2, tau))
        else:
            y += g * _reson(force, f, tau)
    return y


def _grit(n: int, at: float, tau: float, lo: float, hi: float, seed: int) -> np.ndarray:
    """The noise radiated right at a hard contact: a band-passed breath of noise, gone in
    a few tenths of a millisecond."""
    y = np.zeros(n)
    i = _n(at)
    m = min(n - i, _n(tau * 9))
    if m <= 0:
        return y
    y[i:i + m] = np.random.default_rng(seed).standard_normal(m) * np.exp(-_t(m) / tau)
    return A.bandpass(y, lo, hi, 2)


def _struck_again(modes, seed: int):
    """The same part struck somewhere else: its modes answer in other proportions."""
    rng = np.random.default_rng(seed)
    return [(f, g * rng.uniform(0.6, 1.4), c) for f, g, c in modes]


# ----------------------------------------------------------------------------- the candidates
# a small wooden box (the switch's housing): heavily damped, its first modes near 580 Hz,
# the ones above 1 kHz ringing a little longer (they carry the reference's short body)
HOUSING = ((578.0, 1.0, 3.6), (652.0, 0.8, 3.6), (762.0, 0.6, 3.8), (1015.0, 1.1, 9.0),
           (1290.0, 1.05, 10.0), (1480.0, 0.65, 8.0), (1675.0, 0.65, 8.0), (2050.0, 0.4, 6.0))
# a brass lever, held by its spring: it knocks at 1-2.5 kHz and glints above, all briefly
LEVER = ((1060.0, 0.7, 1.7), (1380.0, 1.0, 1.8), (1750.0, 0.8, 2.0), (2150.0, 0.6, 2.4), (2612.0, 0.6, 5.0),
         (2858.0, 0.35, 5.0), (4312.0, 0.35, 6.0), (6352.0, 0.25, 7.0))
# the brass contact leaf the lever lands on: tiny, so it rings very high and for a moment
LEAF = ((5200.0, 0.45, 4.0), (6900.0, 1.0, 4.5), (8300.0, 0.6, 4.5), (10400.0, 0.3, 4.5))


def btn_ref_toggle() -> np.ndarray:
    # the reference's events: the lever lifts off its rest (a soft tick and a 6 ms scuff of
    # the detent, ringing the housing 15 dB under the snap), travels, brushes its far stop
    # 4.5 ms early and snaps home 27 ms after the lift: brass meets brass (the contact
    # leaf's bright ring, about 1.5 ms), the lever strikes its stop a moment later (its own
    # quick knock at 1-2.5 kHz) and pushes the wooden housing through its bushing over
    # about a millisecond, so the housing's ring swells for a few milliseconds before it
    # dies; two small bounces in the seat, and two housing modes linger faintly
    n = _n(0.11)
    t_snap = 0.027
    lift = _force(n, [(0.0, 0.2, 0.0003)]) + _scuff(n, 0.0012, 0.0065, 1100.0, 0.07, 0.0002, 11)
    meet = _force(n, [(t_snap - 0.0008, 1.0, 0.00005)])
    strike = _force(n, [(t_snap - 0.0045, 0.05, 0.00015), (t_snap - 0.0004, 1.0, 0.00015),
                        (t_snap + 0.0052, 0.15, 0.0002), (t_snap + 0.0108, 0.06, 0.0002)])
    press = _force(n, [(t_snap - 0.0045, 0.04, 0.0003), (t_snap - 0.0007, 1.0, 0.0011),
                       (t_snap + 0.0052, 0.11, 0.0005), (t_snap + 0.0108, 0.03, 0.0005)])
    housing = 0.7 * _ring(lift, _struck_again(HOUSING, 12), 13) + _ring(press, HOUSING, 14, split=0.012)
    linger = _ring(press, ((832.0, 1.0, 8.0), (590.0, 0.5, 7.0)), 15)
    lever = _ring(strike, LEVER, 16, split=0.004)
    leaf = _ring(meet, LEAF, 17, split=0.01)
    grit = (_grit(n, t_snap - 0.0008, 0.0004, 3000.0, 14000.0, 18)
            + 0.3 * _grit(n, 0.0, 0.0006, 2000.0, 9000.0, 19))
    x = 0.66 * _en(housing) + 0.22 * _en(linger) + 0.5 * _en(lever) + 0.4 * _en(leaf) + 0.14 * _en(grit)
    return _finish(x, 23.0, hp=360.0, lp=13000.0)


# an oak cupboard door (the latch's keeper is screwed to it): its low panel modes, unevenly
# strong and unevenly spaced, as a real panel's are (even ones would beat into a buzz)
DOOR = ((198.0, 0.35, 2.2), (271.0, 1.0, 2.6), (329.0, 0.55, 2.8), (408.0, 0.8, 3.0), (451.0, 0.4, 3.0),
        (577.0, 0.5, 3.4), (733.0, 0.3, 3.6), (948.0, 0.25, 3.8), (1243.0, 0.15, 4.0))
# the oak latch bar, a short free bar: its bending modes at 1 : 2.76 : 5.4
BAR = ((880.0, 1.0, 4.0), (2430.0, 0.55, 5.0), (4750.0, 0.25, 5.0))
# the keeper, a small block of hard wood the bar lands in: a brief, higher knock
KEEPER = ((1480.0, 0.8, 4.0), (1930.0, 0.65, 4.0), (3300.0, 0.7, 4.0), (5100.0, 0.3, 4.0))


def btn_ref_latch() -> np.ndarray:
    # the same gesture, heavier and lower: the thumb lifts an oak latch bar out of its
    # keeper (a soft wooden tick and a short scuff of wood on wood, 15 dB under the drop);
    # 32 ms later the bar brushes the keeper's ramp and drops into its notch 3.5 ms after:
    # a wood-on-wood knock (the keeper's brief knock and the bar's own short ring near
    # 900 Hz) that pushes the cupboard door's panel modes, 200-450 Hz, into a round,
    # quickly damped "tock"; a small bounce or two
    n = _n(0.12)
    t_drop = 0.032
    lift = _force(n, [(0.0, 0.31, 0.0005)]) + _scuff(n, 0.0015, 0.006, 800.0, 0.09, 0.0004, 21)
    strike = _force(n, [(t_drop - 0.0035, 0.05, 0.0003), (t_drop, 1.0, 0.0003), (t_drop + 0.0072, 0.16, 0.0003),
                        (t_drop + 0.0145, 0.04, 0.0003)])
    press = _force(n, [(t_drop - 0.0035, 0.04, 0.0006), (t_drop - 0.0005, 1.0, 0.0016),
                       (t_drop + 0.0072, 0.15, 0.0008), (t_drop + 0.0145, 0.04, 0.0008)])
    door = 0.5 * _ring(lift, _struck_again(DOOR, 22), 23) + _ring(press, DOOR, 24, split=0.015)
    bar = 0.25 * _ring(lift, BAR, 25) + _ring(strike, BAR, 26, split=0.006)
    keeper = _ring(_force(n, [(t_drop - 0.0004, 1.0, 0.00012)]), KEEPER, 27, split=0.01)
    grit = _grit(n, t_drop, 0.0004, 1500.0, 7000.0, 28) + 0.1 * _grit(n, 0.0, 0.0005, 1200.0, 5000.0, 29)
    x = 0.76 * _en(door) + 0.5 * _en(bar) + 0.27 * _en(keeper) + 0.12 * _en(grit)
    return _finish(x, 22.5, hp=140.0, lp=9000.0)


# a small wooden box (a chest with a felt-topped lid): the lid and the air inside move
# together in its lowest mode; the felt soaks up the rest quickly
BOX = ((150.0, 0.5, 1.6), (222.0, 1.0, 1.9), (296.0, 0.9, 2.2), (392.0, 0.75, 2.5), (530.0, 0.55, 2.8),
       (730.0, 0.35, 3.0), (1000.0, 0.18, 3.2))


def btn_ref_knock() -> np.ndarray:
    # the deepest: a knuckle knocks once on the felt-topped lid of a wooden box; the felt
    # spreads the blow over more than a millisecond (so nothing bright is struck) and a
    # second knuckle lands 2.4 ms later, lighter; the box answers with its low, heavily
    # damped modes and the felt gives a short muffled pat as its fibres are pressed
    n = _n(0.1)
    blow = _force(n, [(0.0, 1.0, 0.0013), (0.0024, 0.4, 0.0015)])
    box = _ring(blow, BOX, 31, split=0.02)
    m = _n(0.012)
    pat = np.zeros(n)
    rise = np.sin(np.pi * np.minimum(1.0, _t(m) / 0.001) / 2)
    pat[:m] = np.random.default_rng(32).standard_normal(m) * np.exp(-_t(m) / 0.0022) * rise
    pat = A.bandpass(pat, 300.0, 2000.0, 2)
    x = 0.93 * _en(box) + 0.36 * _en(pat)
    return _finish(x, 19.0, hp=110.0, lp=3000.0)


# ============================================================================= the list
C = Candidate
CANDIDATES = [
    C(EVENT, "ref_toggle", "Brass toggle",
      "A small brass toggle on a wooden box: a faint tick, then a crisp snap with a short woody ring.",
      btn_ref_toggle, ["acoustic", "modelled", "crisp"]),
    C(EVENT, "ref_latch", "Wooden latch",
      "An oak latch lifted and dropped: the same two-part click, lower and rounder.",
      btn_ref_latch, ["acoustic", "modelled", "wooden"]),
    C(EVENT, "ref_knock", "Box knock",
      "A soft knuckle knock on a felt-topped wooden box: deep, round and dry.",
      btn_ref_knock, ["acoustic", "modelled", "soft"]),
]
