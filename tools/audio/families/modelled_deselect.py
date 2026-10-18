"""Deselect a card, modelled on the owner's reference: Pythonista's 'casino:CardPlace4'.

The owner picked CardPlace4 as how taking a selected card back should feel: a card slid
back across the cloth and tapped into place. These candidates rebuild that from its
physical events, in code, from noise and damped resonances only. No part of the
reference recording is used, read or copied: it was only measured, offline, to set the
timings, levels and bands below.

What the reference is made of, and what models each part here:
  slide    the card's face dragged back over the felt under a fingertip: a friction noise
           whose band (about 1-2.5 kHz) rises and sinks with the card's speed, unevenly
           (the hand is never steady), with the cloth's fibres catching on the card
           (crackle), a duller top and the low rumble of the fingertip pressing the card
           into the cloth (``_slide``)
  edge     a card's edge meeting the cloth or the card beside it: a short contact pulse
           ringing the card's own bending modes for a few cycles, a spit of crackle and a
           small low knock (``_edge``)
  slap     the face meeting the table: noise struck once through a few random patches
           of card (no card is a perfect plate), so the slap is broad and uneven (``_slap``)
  air      the air squeezed out from under the falling card: a soft pressure pulse (a
           small push, then a bigger, quicker opposite swing) that rings the felt-covered
           table's low, heavily damped modes for a cycle or two: the thump, never a
           pitched tone (``_air``)
  rock     the card rocking to rest on the cloth: a few tiny, dying pats (``_rock``)
The reference is a slide, the far edge dropping (a first tap) and, 18 ms later, the
face landing flat (the loudest moment, ``_land``), then the rocking. Each candidate is
one fixed file, so its naturalness lives inside it: every grain, click and pat is drawn
from its own seed (the two taps are never alike) and every render is identical. The
table's modes are the select sound's (``modelled_select``: the same felt over the same
wood), so the two read as a pair; the deselect is the slide back and the settle.
"""
from __future__ import annotations

import math
from typing import Sequence, Tuple

import numpy as np
from scipy import signal

import synth as A
from catalog import EVENT_BY_ID, Candidate

SR = A.SR
EVENT = "card_deselect"
# the felt-covered table's low, heavily damped modes (Hz, decay time in seconds): the select
# sound's table, so the two read as a pair. A landing excites them in its own proportions.
TABLE = ((64.0, 0.006), (150.0, 0.0045), (285.0, 0.003))


def _table(g_low: float, g_mid: float, g_high: float, damp: float = 1.0):
    """The table's modes with a landing's own gains (low, middle, high); ``damp`` scales how
    long they ring (below 1: a thicker cloth deadens them)."""
    return tuple((f, g, tau * damp) for (f, tau), g in zip(TABLE, (g_low, g_mid, g_high)))


FELT_TABLE = _table(0.9, 0.65, 0.25, 1.2)


# ----------------------------------------------------------------------------- basics
def _n(t: float) -> int:
    return int(round(t * SR))


def _t(n: int) -> np.ndarray:
    return np.arange(n) / SR


def _norm(x: np.ndarray) -> np.ndarray:
    p = float(np.max(np.abs(x))) if len(x) else 0.0
    return x / p if p > 0 else x


def _en(x: np.ndarray) -> np.ndarray:
    """Unit energy, so mixing gains set each layer's share of the energy (gain squared)."""
    e = math.sqrt(float(np.sum(x ** 2)) / SR * 1000.0)
    return x / e if e > 0 else x


def _rms1(x: np.ndarray) -> np.ndarray:
    r = math.sqrt(float(np.mean(x ** 2))) if len(x) else 0.0
    return x / r if r > 0 else x


def _decay(n: int, tau: float, attack: float = 0.0003) -> np.ndarray:
    """exp(-t / tau) with a raised-cosine rise over ``attack`` (starts at exactly 0)."""
    e = np.exp(-_t(n) / max(tau, 1e-5))
    k = min(n, max(2, _n(attack)))
    e[:k] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(k) / k)
    return e


def _tail(x: np.ndarray, frac: float = 0.3) -> np.ndarray:
    """Fade the last ``frac`` of a buffer to zero (a raised cosine)."""
    k = min(len(x), max(2, int(len(x) * frac)))
    y = x.copy()
    y[-k:] *= 0.5 + 0.5 * np.cos(np.pi * np.linspace(0.0, 1.0, k))
    return y


def _fade_in(x: np.ndarray, t: float) -> np.ndarray:
    k = min(len(x), max(2, _n(t)))
    y = x.copy()
    y[:k] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(k) / k)
    return y


def _wobble(n: int, rate: float, seed: int) -> np.ndarray:
    """Random unevenness (about ``rate`` changes a second), zero mean, unit peak."""
    rng = np.random.default_rng(seed)
    m = int(n / SR * rate) + 4
    y = np.interp(_t(n) * rate, np.arange(m), rng.standard_normal(m))
    return _norm(y - np.mean(y))


def _place(parts, dur: float = 0.0) -> np.ndarray:
    """Mix [(sound, at seconds, gain), ...] into one buffer."""
    buf = np.zeros(max(1, _n(dur)))
    for snd, at, g in parts:
        buf = A.mix_at(buf, snd, at, g)
    return buf


def _reso(x: np.ndarray, f: float, q: float) -> np.ndarray:
    """A two-pole resonance at ``f`` (unity gain at its centre)."""
    b, a = signal.iirpeak(min(f, SR * 0.45), q, fs=SR)
    return signal.lfilter(b, a, x)


def _modes(exc: np.ndarray, modes) -> np.ndarray:
    """Damped resonators driven by ``exc``: modes are (freq, gain, tau seconds); each is
    scaled to its own peak, so the gains read directly."""
    y = np.zeros(len(exc))
    for f, g, tau in modes:
        r = math.exp(-1.0 / (tau * SR))
        w = 2 * math.pi * f / SR
        y += g * _norm(signal.lfilter([1.0], [1.0, -2 * r * math.cos(w), r * r], exc))
    return y


def _crackle(n: int, rate: np.ndarray, amp: np.ndarray, seed: int, lo: float, hi: float, k: int = 6,
             q: float = 3.0) -> np.ndarray:
    """Paper and cloth fibres catching: sparse clicks at ``rate`` per second (a per-sample
    array), each with a heavy-tailed strength scaled by ``amp``, ringing one of ``k``
    small patches of card (short resonances spread from ``lo`` to ``hi``)."""
    rng = np.random.default_rng(seed)
    idx = np.nonzero(rng.random(n) < rate / SR)[0]
    y = np.zeros(n)
    if not len(idx):
        return y
    s = np.minimum(rng.pareto(2.2, len(idx)) + 1.0, 7.0) * rng.choice([-1.0, 1.0], len(idx)) * amp[idx]
    centres = np.geomspace(lo, hi, k) * rng.uniform(0.9, 1.1, k)
    grp = rng.integers(0, k, len(idx))
    for g in range(k):
        sel = grp == g
        if np.any(sel):
            imp = np.zeros(n)
            imp[idx[sel]] = s[sel]
            y += _reso(imp, centres[g], q)
    return y


# ----------------------------------------------------------------------------- the physical parts
def _slide(dur: float, speed: Sequence[Tuple[float, float]], seed: int, centre: float = 1600.0, spread: float = 0.2,
           top: float = 9000.0, crisp: float = 0.25, sheen: float = 0.3, rumble: float = 0.5, rumble_lp: float = 110.0,
           wobble: float = 0.3, rate: float = 2500.0) -> np.ndarray:
    """A card dragged over felt. ``speed`` is (seconds, 0..1) points: it sets the loudness,
    where the friction band sits (from 1 - ``spread`` to 1 + ``spread`` times ``centre``:
    a card speeding up rises, one slowing down sinks) and how often fibres catch.
    ``sheen`` is the share of the band's rolled-off top (up to ``top``), ``rumble`` the
    fingertip's low pressure noise on the cloth (below ``rumble_lp``), ``wobble`` the
    hand's unevenness on top of the given curve."""
    n = _n(dur)
    ts, vs = zip(*speed)
    sp = np.clip(np.interp(_t(n), ts, vs), 0.0, 1.0)
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(n)
    lo_c, hi_c = centre * (1.0 - spread), centre * (1.0 + spread)
    low = _rms1(A.bandpass(w, lo_c / 1.45, lo_c * 1.45, 2))
    high = _rms1(A.bandpass(w, hi_c / 1.45, hi_c * 1.45, 2))
    band = (1.0 - sp) * low + sp * high
    sh = _rms1(A.lowpass(A.highpass(rng.standard_normal(n), centre * 1.8, 1), top, 2))
    press = _rms1(A.highpass(A.lowpass(rng.standard_normal(n), rumble_lp, 2), 35.0, 2))
    hand = np.clip(1.0 + wobble * _wobble(n, 90.0, seed + 1), 0.15, None)
    cr = _crackle(n, rate * sp ** 1.2, sp ** 0.6 * hand, seed + 2, centre * 0.9, min(top, centre * 3.5))
    bed = _rms1((band + sheen * sh) * sp * hand)
    y = (1.0 - crisp) * bed + crisp * (_rms1(cr) if np.any(cr) else 0.0) + rumble * press * sp * hand
    return _tail(_fade_in(y, 0.0005), 0.05)


def _edge(seed: int, ring: float = 2000.0, ring_tau: float = 0.0012, width: float = 0.00015, spit: float = 0.4,
          spit_lo: float = 2500.0, spit_hi: float = 9000.0, knock: float = 0.25, knock_f: float = 120.0,
          dur: float = 0.03) -> np.ndarray:
    """A card's edge meeting the cloth or another card: a contact pulse ``width`` long
    (shorter is harder) rings the card's bending modes (``ring``, a close second mode and
    a weak upper one; ``ring_tau`` how fast they die), with a spit of crackle as the edge's
    fibres crush and a small, damped low knock of the table at ``knock_f``."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    w = max(2, _n(width))
    pulse = np.zeros(n)
    pulse[:w] = np.sin(np.pi * np.arange(w) / w)
    exc = pulse + 0.25 * rng.standard_normal(n) * _decay(n, width * 2.0, 0.00005)
    f1 = ring * rng.uniform(0.95, 1.05)
    body = _modes(exc, [(f1, 1.0, ring_tau), (f1 * rng.uniform(1.12, 1.24), 0.5, ring_tau * 0.8),
                        (f1 * rng.uniform(2.4, 2.8), 0.3, ring_tau * 0.5)])
    env = _decay(n, 0.0012, 0.0001)
    cr = _crackle(n, 9000.0 * env, env, seed + 3, spit_lo, spit_hi, q=3.0)
    low = _modes(rng.standard_normal(n) * _decay(n, 0.0012, 0.0003), [(knock_f * rng.uniform(0.95, 1.05), 1.0, 0.004)])
    y = _en(body) + spit * _en(cr) + knock * _en(low)
    return _tail(y, 0.4)


def _slap(seed: int, lo: float = 800.0, hi: float = 8000.0, tau: float = 0.0016, attack: float = 0.0003,
          patches: float = 0.5, body: Tuple[float, float] = (0.0, 0.0), spread: float = 0.001,
          dur: float = 0.03) -> np.ndarray:
    """The face meeting the table: noise struck once (``tau``), band-passed ``lo``..``hi``,
    plus five patches of the card ringing briefly, spread over ``body`` (Hz, Hz; by
    default the slap's own band). A card never lands everywhere at once (the air under
    it lets it down from one side), so each patch is struck on its own within ``spread``
    seconds: a wider spread is a softer, flatter landing. Broad but uneven, never the
    same twice."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    exc = rng.standard_normal(n) * _decay(n, tau, attack)
    y = _norm(A.bandpass(exc, lo, hi, 2))
    b_lo, b_hi = body if body[0] else (lo * 1.3, hi / 1.3)
    for f in np.geomspace(b_lo, b_hi, 5) * rng.uniform(0.85, 1.15, 5):
        k = _n(float(rng.uniform(0.0, spread)))
        e = np.zeros(n)
        e[k:] = rng.standard_normal(n - k) * _decay(n - k, tau, attack)
        y = y + patches * float(rng.uniform(0.3, 1.0)) * _norm(_reso(e, f, 4.0))
    return _tail(y, 0.3)


def _air(seed: int, width: float = 0.0032, pre: float = 0.4, modes=FELT_TABLE, body: float = 0.7,
         pff: float = 0.25, pff_lp: float = 900.0, dur: float = 0.06) -> np.ndarray:
    """The air squeezed out from under a falling card, and what it does to the table: a
    soft pressure pulse (a small push as the air is compressed, then a bigger, quicker
    opposite swing ``width`` long as the card meets the cloth, and a little rebound),
    slightly uneven, ringing the table's low, damped ``modes``, with a breath of the air
    escaping through the cloth (``pff``). The swing's centre is at 2.2 widths."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    t = _t(n)

    def lobe(at: float, w: float) -> np.ndarray:
        x = (t - at) / w
        return np.where(np.abs(x) < 0.5, 0.5 + 0.5 * np.cos(2 * np.pi * x), 0.0)

    w = width * rng.uniform(0.95, 1.05)
    c = 2.2 * width
    p = pre * lobe(c - 0.95 * width, 1.6 * w) - lobe(c, w) + 0.2 * lobe(c + 1.3 * width, 2.2 * w)
    p *= 1.0 + 0.15 * _norm(A.lowpass(rng.standard_normal(n), 800.0, 1))
    ring = _modes(np.gradient(p), [(f * rng.uniform(0.96, 1.04), g, tau) for f, g, tau in modes])
    br = A.lowpass(A.highpass(rng.standard_normal(n), 150.0, 1), pff_lp, 2) * lobe(c, 2.5 * w)
    y = _en(p) + body * _en(ring) + pff * _en(br)
    return _tail(y, 0.35)


def _lead(width: float) -> float:
    """How far into a ``_land`` buffer the card meets the table (the air is pushed first)."""
    return 2.2 * width - 0.001


def _land(seed: int, ring: float = 2000.0, edge: float = 0.5, slap: float = 0.6, air: float = 1.0,
          lo: float = 800.0, hi: float = 8000.0, slap_tau: float = 0.0016, attack: float = 0.0003,
          width: float = 0.0032, modes=FELT_TABLE, body: float = 0.7, pff: float = 0.25, settle: float = 0.0,
          settle_tau: float = 0.02, card: Tuple[float, float] = (0.0, 0.0), contact: float = 0.00015,
          spit: float = 0.35, spread: float = 0.001, pre: float = 0.4, dur: float = 0.06) -> np.ndarray:
    """A card landing flat: the air pushed out ahead of it (``pre``, see ``_air``), then
    its edge's contact and the face's slap at ``_lead(width)`` seconds in, with the air's
    main swing (the table's thump) a millisecond later and, with ``settle``, the table's
    low rumble dying away (noise below 110 Hz falling over ``settle_tau``: wood under
    cloth, no ringing tone). ``card`` and ``spread`` are where and how evenly the face
    lands (see ``_slap``); ``contact`` and ``spit`` are the edge's (see ``_edge``: a wider
    contact is a softer one). Place it ``_lead(width)`` before the moment of impact."""
    t0 = _lead(width)
    rng = np.random.default_rng(seed + 3)
    e = _en(_edge(seed, ring=ring, ring_tau=0.0012, width=contact, spit=spit, knock=0.15))
    s = _en(_slap(seed + 1, lo, hi, slap_tau, attack, body=card, spread=spread))
    a = _en(_air(seed + 2, width=width, pre=pre, modes=modes, body=body, pff=pff, dur=dur))
    m = _n(dur)
    rum = _en(_tail(A.lowpass(rng.standard_normal(m), 110.0, 2) * _decay(m, settle_tau, 0.003), 0.3))
    return _place([(a, 0.0, air), (e, t0, edge), (s, t0 + 0.0003, slap), (rum, t0, settle)], dur + 0.01)


def _rock(seed: int, times: Sequence[float], level: float = 1.0, lo: float = 900.0, hi: float = 7000.0,
          dur: float = 0.08) -> np.ndarray:
    """The card rocking to rest on the cloth: its corners patting down at ``times``, each a
    tiny, short slap with a little low knock, dying away, each a little different."""
    rng = np.random.default_rng(seed)
    buf = np.zeros(_n(dur) + _n(0.04))
    for i, t0 in enumerate(times):
        a = level * (0.75 ** i) * float(rng.uniform(0.6, 1.0))
        s = _en(_slap(seed * 10 + i, lo, hi, float(rng.uniform(0.0006, 0.0011)), 0.0004, dur=0.012))
        k = _en(A.lowpass(rng.standard_normal(_n(0.012)) * _decay(_n(0.012), 0.002, 0.0008), 120.0, 2))
        buf = A.mix_at(buf, _place([(s, 0.0, 0.85), (k, 0.0, 0.5)], 0.015), float(t0), a)
    return _tail(buf[:_n(dur)], 0.15)


# ----------------------------------------------------------------------------- finishing
def _gentle(x: np.ndarray, crest_db: float, max_shave_db: float = 3.0) -> np.ndarray:
    """Keep the peak near ``crest_db`` above the build's loudness measure by shaving only
    the first fraction of a millisecond of the sharpest click (a fast look-ahead limiter
    with a 5 ms release, so the body after it keeps its level), and never by more than
    ``max_shave_db``: the highest threshold that meets the target is found by bisection
    once, so shaving a tap never lowers the target it is measured against. A sound that
    still has more crest needs a softer design, not more limiting."""
    def crest(y):
        return 20 * math.log10(float(np.max(np.abs(y))) + 1e-12) - A._rms_db(y)

    def shave(th_db):
        g = 10 ** (th_db / 20.0)
        return A.limit(x / g, 0.0, lookahead=0.0008, release=0.005) * g

    if crest(x) <= crest_db:
        return x
    pk = 20 * math.log10(float(np.max(np.abs(x))))
    lo, hi, best = pk - max_shave_db, pk, None
    for _ in range(12):
        mid = 0.5 * (lo + hi)
        y = shave(mid)
        if crest(y) <= crest_db:
            best, lo = y, mid
        else:
            hi = mid
    return best if best is not None else shave(pk - max_shave_db)


def _finish(x: np.ndarray, crest_db: float, hp: float = 35.0, lp: float = 0.0, fade: float = 0.2,
            shave: float = 3.0) -> np.ndarray:
    """Take out the sub-bass and DC (and, with ``lp``, the very top), keep the sound inside
    the event's length (with room for the build's trim), let the end fade smoothly and
    keep the taps' peaks gentle (shaving ``shave`` dB at most)."""
    y = A.highpass(x, hp, 2)
    if lp:
        y = A.lowpass(y, lp, 2)
    y = y[:_n(EVENT_BY_ID[EVENT].max_seconds - 0.02)]
    return _gentle(_tail(y, fade), crest_db, shave)


# ============================================================================= the candidates
def des_ref_slide_tap():
    # the reference's own story: a small catch as the fingertip starts the card moving, an
    # uneven slide back over the felt that eases mid-way and quickens again near its end,
    # the far edge dropping onto the cloth at 65 ms, the face landing flat 17 ms later
    # (the loudest moment: a broad slap and the table's thump, the air pushed out just
    # ahead of it, the wood's low rumble dying under it), the card's last few millimetres
    # of slide, then the card rocking to rest in a few faint, dying pats
    slide = _en(_slide(0.087, [(0.0, 0.75), (0.008, 0.3), (0.012, 0.7), (0.02, 0.4), (0.026, 0.5), (0.032, 0.75),
                               (0.036, 0.28), (0.04, 0.5), (0.048, 0.35), (0.052, 0.5), (0.058, 0.45), (0.062, 0.6),
                               (0.07, 0.8), (0.076, 0.85), (0.08, 1.0), (0.084, 0.6), (0.087, 0.0)], 11,
                       centre=1600, spread=0.15, top=13000, crisp=0.2, sheen=0.35, rumble=0.9))
    after = _en(_slide(0.025, [(0.0, 0.0), (0.003, 0.5), (0.012, 0.6), (0.02, 0.3), (0.025, 0.0)], 16,
                       centre=1500, spread=0.15, top=12000, crisp=0.3, sheen=0.35, rumble=0.6))
    catch = _en(_edge(12, ring=2200, ring_tau=0.0006, width=0.0004, spit=0.8, knock=0.5))
    w1, w2 = 0.0026, 0.0038
    tap = _en(_land(13, ring=2000, edge=0.6, slap=0.55, air=0.4, lo=900, hi=5000, slap_tau=0.0022,
                    attack=0.0015, width=w1, modes=_table(0.35, 1.0, 0.25, 0.8),
                    body=0.8, pff=0.2, contact=0.0004, spread=0.0015))
    land = _en(_land(14, ring=2100, edge=0.45, slap=1.1, air=0.6, lo=600, hi=14000, slap_tau=0.002,
                     width=w2, modes=_table(0.4, 1.0, 0.12),
                     body=1.2, pff=0.15, settle=0.5, settle_tau=0.025, card=(900.0, 6000.0), pre=0.7))
    rock = _en(_rock(15, [0.024, 0.036, 0.046, 0.051, 0.060], lo=1000, hi=13000))
    x = _place([(slide, 0.0, 0.36), (catch, 0.0, 0.2), (tap, 0.065 - _lead(w1), 0.52),
                (land, 0.082 - _lead(w2), 1.0), (after, 0.085, 0.18), (rock, 0.082, 0.08)], 0.22)
    return _finish(x, 22.0, lp=16000)


def des_ref_soft_slide():
    # shorter and softer: a 45 ms slide back that slows as it goes (its band sinking), the
    # far edge barely touching down, and 11 ms later a gentle, rounder landing (a slower,
    # darker slap over more of the felt's thump) with one small rock
    slide = _en(_slide(0.046, [(0.0, 0.45), (0.006, 0.65), (0.02, 0.6), (0.034, 0.45), (0.042, 0.3), (0.046, 0.0)],
                       21, centre=1350, spread=0.25, top=6000, crisp=0.12, sheen=0.2, rumble=0.6))
    w1, w2 = 0.003, 0.0045
    tap = _en(_land(23, ring=1700, edge=0.5, slap=0.4, air=0.5, lo=700, hi=3200, slap_tau=0.004,
                    attack=0.002, width=w1, modes=_table(0.4, 1.0, 0.15, 0.9),
                    contact=0.0006, spit=0.1))
    land = _en(_land(24, ring=1700, edge=0.3, slap=0.6, air=0.45, lo=500, hi=4500, slap_tau=0.0055,
                     attack=0.003, width=w2, modes=_table(0.5, 1.0, 0.12),
                     pff=0.4, settle=0.25, settle_tau=0.02, card=(600.0, 3000.0), contact=0.0007, spit=0.1,
                     spread=0.006))
    rock = _en(_rock(25, [0.022], lo=700, hi=4500))
    x = _place([(slide, 0.0, 0.22), (tap, 0.041 - _lead(w1), 0.22), (land, 0.052 - _lead(w2), 1.0),
                (rock, 0.052, 0.06)], 0.15)
    return _finish(x, 18.0, lp=5000, shave=3.5)


def des_ref_low_tap():
    # the select sound's table and card, slid back and settled a touch lower: the slide's
    # band sits lower, the card rings about three semitones under the select sound's edge
    # (near 1 kHz), and the face lands nearer the middle of the board with a wider push of
    # air, so the table's lowest mode answers most (a deeper thump), and its slap has no
    # bright top
    slide = _en(_slide(0.083, [(0.0, 0.7), (0.008, 0.35), (0.014, 0.65), (0.024, 0.45), (0.032, 0.7), (0.04, 0.35),
                               (0.05, 0.5), (0.058, 0.45), (0.066, 0.7), (0.074, 0.85), (0.078, 0.9), (0.081, 0.5),
                               (0.083, 0.0)], 31, centre=1250, spread=0.15, top=8000, crisp=0.15, sheen=0.25,
                       rumble=0.8))
    after = _en(_slide(0.022, [(0.0, 0.0), (0.002, 0.6), (0.01, 0.4), (0.022, 0.0)], 36, centre=1200, spread=0.15,
                       top=7500, crisp=0.25, sheen=0.25, rumble=0.6))
    catch = _en(_edge(32, ring=1500, ring_tau=0.0006, width=0.0005, spit=0.6, knock=0.5))
    w1, w2 = 0.0028, 0.004
    tap = _en(_land(33, ring=1000, edge=0.6, slap=0.5, air=0.45, lo=650, hi=3500, slap_tau=0.0024,
                    attack=0.0015, width=w1, contact=0.0005, spit=0.2, spread=0.0015))
    land = _en(_land(34, ring=1000, edge=0.35, slap=1.0, air=0.85, lo=500, hi=6500, slap_tau=0.0032,
                     width=w2, modes=_table(1.0, 0.6, 0.15, 1.2), body=1.2,
                     pff=0.2, settle=0.35, settle_tau=0.025, card=(700.0, 3500.0), contact=0.0003, spit=0.2,
                     spread=0.002))
    rock = _en(_rock(35, [0.026, 0.040, 0.050, 0.061], lo=700, hi=5500))
    x = _place([(slide, 0.0, 0.34), (catch, 0.0, 0.14), (tap, 0.062 - _lead(w1), 0.28),
                (land, 0.08 - _lead(w2), 1.0), (after, 0.083, 0.13), (rock, 0.08, 0.075)], 0.22)
    return _finish(x, 21.0, lp=8500)


# ============================================================================= the list
CANDIDATES = [
    Candidate(EVENT, "ref_slide_tap", "Slide and tap",
              "A card slid back over the felt, then a quick double tap as it settles into place.",
              des_ref_slide_tap, ["acoustic", "modelled"]),
    Candidate(EVENT, "ref_soft_slide", "Soft slide back",
              "A short, slowing slide over the cloth and a gentle, muffled pat into place.",
              des_ref_soft_slide, ["acoustic", "modelled", "soft"]),
    Candidate(EVENT, "ref_low_tap", "Lower tap",
              "The same slide and double tap on the select sound's table, a touch deeper.",
              des_ref_low_tap, ["acoustic", "modelled", "warm"]),
]
