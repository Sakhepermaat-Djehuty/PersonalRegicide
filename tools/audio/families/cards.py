"""Card sounds: select, deselect, play, draw, shuffle and discard (five candidates each).

Everything here is acoustic: card stock, felt, an oak table, a wooden tray and, lightly, in
one candidate per event, a courtly instrument (a harp, a lute; the shuffle's "fairy" one a
harp and a celesta) recorded in the General MIDI banks (``sf.py``). Each event offers a
realistic sound, a soft one for long sessions, a wooden tavern one, an instrument-coloured
one and a second, different piece of card handling (a corner flick, a fanned toss, a deck
washed round the felt, ...). Nothing is 8-bit, and no tone is a bare oscillator.

The card handling itself is built from its physical parts, the way it happens:
  crackle   paper is crisp because its sound is made of many tiny separate events (fibres
            catching, the sheet buckling): sparse impulses with a heavy-tailed spread of
            strengths, each ringing a small random patch of card (a short resonance
            between 1 and 8 kHz), at a rate that follows how fast the card moves
  rub       card stock sliding on card stock or felt: a pink-tilted friction noise whose
            band rises and falls with the slide's speed, unevenly (the hand is never
            steady), with the crackle on top
  snap      a card's edge springing free: a click of noise and the card's brief ring
  slap      a card landing flat: the impact, the "pff" of air pushed out from under it
            and a short flutter of the card settling
  thud      a soft knock on a padded table: noise through the table's low, heavily damped
            resonance (not a pitched sine), with a low-passed knock
  modal     wood: damped resonators struck by a short mallet pulse (a thick tabletop, a
            hollow tray)
Real recordings from the banks add what is hard to model: wire brushes on a drum head
(the brush kit; filtered, and with a swirl's own fade divided out, they give a real
felt-and-paper grain under a slap or a slide), a woodblock (small wooden ticks and tocks,
and the strike of real wood under a tabletop's or a tray's modes), a harp, a nylon-strung
guitar played like a lute, and a celesta (the "fairy" twinkle). The harp and celesta come
from the MuseScore bank (its upper harp notes are cleaner), the rest from Fluid. The
banks' notes start a few milliseconds late; that silence is cut (``sf.onset``) so each
sound starts at once, and a hand on the strings (``_damp``) stops a note before the
event's length runs out. The slides and the instrument-coloured sounds get the faint
early reflections of a room (``_close``); the quick slaps stay dry so they get out of the
way of the sounds that follow them in a turn.
Layers are mixed by their share of the energy (``_en``), not their peaks, and each sound
keeps body between 300 Hz and 3 kHz, so a phone's small speaker still hears it. Tonal
parts use D major pentatonic (D E F# A B) or D dorian (with F natural). Everything is
seeded, so each sound is rebuilt identically.
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


# ----------------------------------------------------------------------------- basics
def _n(t: float) -> int:
    return int(round(t * SR))


def _t(n: int) -> np.ndarray:
    return np.arange(n) / SR


def _norm(x: np.ndarray) -> np.ndarray:
    p = float(np.max(np.abs(x))) if len(x) else 0.0
    return x / p if p > 0 else x


def _en(x: np.ndarray) -> np.ndarray:
    """Scale to unit energy, so mixing gains set each layer's share of the energy
    (gain squared), not its peak: a 5 ms slap and a 40 ms thud compare fairly."""
    e = math.sqrt(float(np.sum(x ** 2)) / SR * 1000.0)
    return x / e if e > 0 else x


def _rms1(x: np.ndarray) -> np.ndarray:
    r = math.sqrt(float(np.mean(x ** 2))) if len(x) else 0.0
    return x / r if r > 0 else x


def _tail(x: np.ndarray, frac: float = 0.3, min_s: float = 0.006) -> np.ndarray:
    """Fade the last part of a piece's buffer to zero, so nothing is cut off while still
    ringing when the buffer ends."""
    k = min(len(x), max(_n(min_s), int(len(x) * frac)))
    y = x.copy()
    if k > 1:
        y[-k:] *= 0.5 + 0.5 * np.cos(np.pi * np.linspace(0.0, 1.0, k))
    return y


def _decay_env(n: int, tau: float, attack: float = 0.0005) -> np.ndarray:
    """exp(-t / tau) with a raised-cosine rise over ``attack`` (starts at exactly 0)."""
    e = np.exp(-_t(n) / max(tau, 1e-5))
    na = min(n, max(2, _n(attack)))
    e[:na] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(na) / na)
    return e


def _curve(n: int, pts: Sequence[Tuple[float, float]]) -> np.ndarray:
    """A piecewise-linear envelope through (fraction of length, value) points."""
    xs, ys = zip(*pts)
    return np.interp(np.linspace(0.0, 1.0, n), xs, ys)


def _arr(v, n: int) -> np.ndarray:
    """A per-sample array from a number, a list of (fraction, value) points or an array."""
    if isinstance(v, np.ndarray):
        out = np.zeros(n)
        m = min(n, len(v))
        out[:m] = v[:m]
        if m < n and m:
            out[m:] = v[m - 1]
        return out
    if isinstance(v, (list, tuple)):
        return _curve(n, v)
    return np.full(n, float(v))


def _fade_in(x: np.ndarray, t: float) -> np.ndarray:
    k = min(len(x), max(2, _n(t)))
    y = x.copy()
    y[:k] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(k) / k)
    return y


def _place(parts, dur: float = 0.0) -> np.ndarray:
    """Mix [(sound, at seconds, gain), ...] into one buffer."""
    buf = np.zeros(max(1, _n(dur)))
    for snd, at, g in parts:
        buf = A.mix_at(buf, snd, at, g)
    return buf


def _smooth_noise(n: int, rate: float, seed: int) -> np.ndarray:
    """Slow random wobble (about ``rate`` changes a second), zero mean, unit peak."""
    rng = np.random.default_rng(seed)
    m = int(n / SR * rate) + 4
    pts = rng.standard_normal(m)
    y = np.interp(_t(n) * rate, np.arange(m), pts)
    y = A.lowpass(y, max(2.0, rate), 1)
    y -= np.mean(y)
    return _norm(y)


def _soften(x: np.ndarray, k: float = 1.3) -> np.ndarray:
    """Round off the very tops of the sharpest transients (a gentle tanh), so a slap keeps
    its body after mastering instead of being squeezed by the limiter."""
    p = float(np.max(np.abs(x))) or 1.0
    return np.tanh(k * x / p) / math.tanh(k) * p


def _loud_db(x: np.ndarray) -> float:
    """The build's loudness measure (gated RMS in 50 ms blocks)."""
    return A._rms_db(x)


def _tame(x: np.ndarray, loudness_db: float, ceiling_db: float = -1.0, margin_db: float = 1.5,
          max_shave_db: float = 4.0) -> np.ndarray:
    """Keep the peak within what mastering allows above the event's loudness (ceiling minus
    a margin), by shaving only the first milliseconds of the sharpest attacks (a 20 ms
    release, so the body that follows keeps its level), so the master's slower limiter has
    little or nothing to do. The highest threshold that meets the target is found by
    bisection; it never shaves more than ``max_shave_db`` (a slam keeps its snap)."""
    allowed = ceiling_db - margin_db - loudness_db

    def crest(y):
        return 20 * math.log10(float(np.max(np.abs(y))) + 1e-12) - _loud_db(y)

    def shave(th_db):
        thr = 10 ** (th_db / 20.0)
        return A.limit(x / thr, 0.0, lookahead=0.0015, release=0.02) * thr

    if crest(x) <= allowed:
        return x
    top = _loud_db(x) + allowed
    floor = max(top - 12.0, 20 * math.log10(float(np.max(np.abs(x)))) - max_shave_db)
    if floor >= top:
        return shave(floor)
    lo, hi = floor, top
    best = None
    for _ in range(12):
        mid = 0.5 * (lo + hi)
        y = shave(mid)
        if crest(y) <= allowed:
            best, lo = y, mid
        else:
            hi = mid
    return best if best is not None else shave(floor)


def _fit(x: np.ndarray, event: str, fade: float = 0.05, hp: float = 45.0, lp: float = 0.0,
         shave: float = 4.0, crest: float = 0.0) -> np.ndarray:
    """Finish a sound for ``event``: take out sub-bass and DC (and, with ``lp``, the top),
    keep it inside the event's length (with room for the build's own trim), let whatever
    still sounds fade out smoothly, and tame its sharpest peak for the event's loudness
    (shaving ``shave`` dB at most; with ``crest``, down to that many dB above the loudness:
    the frequent taps stay gentle)."""
    ev = EVENT_BY_ID[event]
    y = A.highpass(x, hp, 2)
    if lp:
        y = A.lowpass(y, lp, 2)
    n = _n(ev.max_seconds - 0.02)
    if len(y) > n:
        y = y[:n]
    y = _tail(y, _n(fade) / len(y)) if len(y) > _n(fade) else y
    if crest:
        return _tame(y, ev.loudness_db, margin_db=-1.0 - ev.loudness_db - crest, max_shave_db=shave)
    return _tame(y, ev.loudness_db, max_shave_db=shave)


# ----------------------------------------------------------------------------- recordings (the banks)
@functools.lru_cache(maxsize=None)
def _bank_cached(key: tuple, seconds: float, bank: str) -> np.ndarray:
    return sf.render([Note(*k) for k in key], seconds, bank=bank)


def _bank(notes: Sequence[Note], seconds: float, bank: str = "fluid", cut: bool = True) -> np.ndarray:
    """Render ``notes`` from a bank (cached: candidates share their samples), with the
    bank's attack latency cut so the first note sounds at once."""
    key = tuple(dataclasses.astuple(n) for n in notes)
    x = _bank_cached(key, round(float(seconds), 4), bank).copy()
    return x[sf.onset(x, -50.0):] if cut else x


def _damp(x: np.ndarray, hold: float, tau: float, total: float = 0.0) -> np.ndarray:
    """A hand on the strings: full level for ``hold`` seconds, then an exponential fall
    (``tau``), ending at zero by ``total`` (default: 7 time constants after the hold)."""
    total = total or hold + 7 * tau
    n = min(len(x), _n(total))
    t = _t(n)
    env = np.where(t < hold, 1.0, np.exp(-(t - hold) / max(tau, 1e-4)))
    return _tail(x[:n] * env, 0.15)


def _brush(key: int, vel: int, hp: float = 500.0, lp: float = 7000.0, bank: str = "fluid") -> np.ndarray:
    """A wire brush on a drum head (the brush kit: 38 a tap, 39 a slap, 40 a swirl),
    with the drum's own low ring filtered out: what is left is a real, irregular
    papery-felt texture."""
    x = _bank([Note(DRUM, key, 0.0, 0.3, vel=vel, kit="brush")], 1.2, bank)
    x = A.highpass(x, hp, 2)
    return A.lowpass(x, lp, 2) if lp else x


def _woodblock(pitch: str, vel: int, tau: float, lp: float = 6000.0, bank: str = "fluid") -> np.ndarray:
    """A real woodblock note, held for its strike and then damped (the recording's room
    flutter is cut away with its tail)."""
    x = _bank([Note(GM["woodblock"], pitch, 0.0, 0.2, vel=vel)], 0.8, bank)
    x = _damp(x, 0.002, tau)
    return A.lowpass(x, lp, 2) if lp else x


# ----------------------------------------------------------------------------- physical pieces
def _reso(x: np.ndarray, f: float, q: float) -> np.ndarray:
    """A two-pole resonance at ``f`` (unity gain at its centre)."""
    b, a = signal.iirpeak(min(f, SR * 0.45), q, fs=SR)
    return signal.lfilter(b, a, x)


def _crackle(n: int, rate, amp, seed: int, lo: float = 1500.0, hi: float = 7000.0, k: int = 7,
             q: float = 3.5, alpha: float = 2.2, cap: float = 8.0, lp: float = 8000.0) -> np.ndarray:
    """Crisp paper: impulses at ``rate`` per second (a number, points or an array), each
    with a heavy-tailed strength (Pareto, ``alpha``) scaled by ``amp``, ringing one of
    ``k`` small patches of card (resonances spread from ``lo`` to ``hi``, ``q`` sets how
    long each rings: about q / (pi f), a fraction of a millisecond). The clicks' very top
    is rounded off above ``lp`` (a card's crackle is crisp, not a hiss)."""
    rng = np.random.default_rng(seed)
    r = _arr(rate, n)
    am = _arr(amp, n)
    idx = np.nonzero(rng.random(n) < r / SR)[0]
    if not len(idx):
        return np.zeros(n)
    s = np.minimum(rng.pareto(alpha, len(idx)) + 1.0, cap) * np.where(rng.random(len(idx)) < 0.5, -1.0, 1.0)
    s *= am[idx]
    centres = np.geomspace(lo, hi, k) * rng.uniform(0.9, 1.1, k)
    grp = rng.integers(0, k, len(idx))
    y = np.zeros(n)
    for g in range(k):
        sel = grp == g
        if not np.any(sel):
            continue
        imp = np.zeros(n)
        imp[idx[sel]] = s[sel]
        # higher patches ring a little less: q falls slightly with frequency
        y += _reso(imp, centres[g], q * (1500.0 / centres[g]) ** 0.15)
    return A.lowpass(y, min(lp, max(hi * 1.25, 2000.0)), 2) if lp else y


def _rub(dur: float, speed, seed: int, lo: float = 900.0, hi: float = 6500.0, bright: float = 0.5,
         crisp: float = 0.4, rate: float = 3000.0, wobble: float = 0.35, tilt: float = 0.35) -> np.ndarray:
    """Card stock sliding over card stock (or felt). ``speed`` (0..1: points over the
    slide's length or an array) drives the loudness, how far up the band climbs (the
    "fwip" of a slide) and how often the fibres catch; ``crisp`` is the crackle's share;
    ``wobble`` the unevenness of the hand; ``tilt`` darkens the band's top (pink-ish)."""
    n = _n(dur)
    sp = np.clip(_arr(speed, n), 0.0, 1.0)
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(n)
    K = 7
    cs = np.geomspace(lo * 1.3, hi / 1.3, K)
    bands = np.stack([_rms1(A.bandpass(w, c / 1.4, c * 1.4, 2)) * (c / cs[0]) ** (-tilt) for c in cs])
    pos = sp * (K - 1) * (0.3 + 0.7 * bright)
    i0 = np.minimum(pos.astype(int), K - 2)
    fr = pos - i0
    ar = np.arange(n)
    swept = (1 - fr) * bands[i0, ar] + fr * bands[i0 + 1, ar]
    wide = _rms1(A.bandpass(rng.standard_normal(n), lo, hi, 2)) * 0.5
    mod = np.clip(1.0 + wobble * _smooth_noise(n, 35.0, seed + 11), 0.15, None)
    bed = (0.85 * swept + 0.15 * wide) * sp * mod
    cr = _crackle(n, rate * sp ** 1.3, sp ** 0.6 * mod, seed + 7, lo * 1.3, hi, q=3.0)
    y = (1.0 - crisp) * _rms1(bed) + crisp * _rms1(cr) if np.any(cr) else _rms1(bed)
    return _tail(_fade_in(y * 0.25, 0.0015), 0.1)


def _snap(seed: int, center: float = 2800.0, tau: float = 0.0025, dur: float = 0.03, ring: float = 0.3,
          spread: float = 1.8, lp: float = 8000.0) -> np.ndarray:
    """A card edge springing free: an impulse of noise filtered around ``center`` plus the
    card's own brief ring near it (two close plate modes)."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    exc = rng.standard_normal(n) * _decay_env(n, tau, 0.0003)
    y = _norm(A.bandpass(exc, center / spread, min(center * spread, 16000.0), 2))
    if ring:
        imp = np.zeros(n)
        imp[0] = 1.0
        f1 = center * rng.uniform(0.85, 1.0)
        f2 = f1 * rng.uniform(1.3, 1.6)
        r = _reso(imp, f1, 6.0) + 0.6 * _reso(imp, f2, 5.0)
        y = y + ring * _norm(r)
    if lp:
        y = A.lowpass(y, lp, 2)
    return _tail(_norm(y), 0.25)


def _burst(dur: float, lo: float, hi: float, tau: float, seed: int, attack: float = 0.0004) -> np.ndarray:
    """Noise struck once (fast rise, exponential fall), then band-passed."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    exc = rng.standard_normal(n) * _decay_env(n, tau, attack)
    return _tail(_norm(A.bandpass(exc, lo, hi, 2)), 0.25)


def _flutter(dur: float, seed: int, rate: float = 4000.0, lo: float = 1300.0, hi: float = 6500.0,
             tau: float = 0.012) -> np.ndarray:
    """A card settling after it lands (or flexing in the fingers): a short decaying burst
    of crackle."""
    n = _n(dur)
    env = _decay_env(n, tau, 0.0008)
    return _tail(_crackle(n, rate * env, env, seed, lo, hi, q=2.5), 0.2)


def _slap(seed: int, lo: float = 450.0, hi: float = 4500.0, tau: float = 0.006, air: float = 0.5,
          air_lp: float = 900.0, flutter: float = 0.35, dur: float = 0.08) -> np.ndarray:
    """A card landing flat: the impact (noise struck once, ``lo``..``hi``), the "pff" of the
    air pushed out from under it (``air``) and the card's short flutter as it settles."""
    hit = _en(_burst(dur, lo, hi, tau, seed))
    pff = _en(_burst(dur, 90.0, air_lp, tau * 1.8, seed + 1, attack=0.001))
    fl = _en(_flutter(dur * 0.6, seed + 2, tau=tau * 1.6))
    return _norm(_place([(hit, 0, 1.0), (pff, 0, air), (fl, 0.001, flutter)], dur))


def _thud(seed: int, f: float = 190.0, tau: float = 0.02, q: float = 2.0, knock: float = 0.6,
          knock_lp: float = 900.0, dur: float = 0.0) -> np.ndarray:
    """A soft knock on a padded table: a burst of noise through the table's low, heavily
    damped resonance (an unpitched "thup"), plus a low-passed knock. Lasts until it has
    died away by itself."""
    dur = dur or max(0.06, 8 * tau)
    n = _n(dur)
    rng = np.random.default_rng(seed)
    exc = rng.standard_normal(n) * _decay_env(n, tau * 0.35, 0.0006)
    body = _norm(_reso(exc, f, q) + 0.6 * _reso(exc, f * 1.9, q * 1.2))
    body *= _decay_env(n, tau, 0.0008)
    kn = _norm(A.lowpass(rng.standard_normal(n) * _decay_env(n, tau * 0.25, 0.0004), knock_lp, 2))
    y = _norm(body) + knock * kn
    return _tail(np.tanh(1.3 * _norm(y)) / math.tanh(1.3), 0.3)


def _mallet(dur: float, width: float = 0.0008, seed: int = 0, noise: float = 0.25) -> np.ndarray:
    """A strike: a half-sine pulse ``width`` long (shorter = harder) with a little noise."""
    n = _n(dur)
    w = max(2, _n(width))
    y = np.zeros(n)
    y[:w] = np.sin(np.pi * np.arange(w) / w)
    rng = np.random.default_rng(seed)
    m = min(n, w * 4)
    y[:m] += noise * rng.standard_normal(m) * np.exp(-np.arange(m) / w)
    return y


def _modal(exc: np.ndarray, modes) -> np.ndarray:
    """Damped resonators driven by ``exc``: modes are (freq, gain, tau); each mode is
    scaled to its own peak so the gains read directly. Fades out at the buffer's end."""
    y = np.zeros(len(exc))
    for f, g, tau in modes:
        r = math.exp(-1.0 / (tau * SR))
        w = 2 * math.pi * f / SR
        out = signal.lfilter([1.0], [1.0, -2 * r * math.cos(w), r * r], exc)
        y += g * _norm(out)
    return _tail(y, 0.3)


def _room(x: np.ndarray, room: float = 0.3, wet: float = 0.15, damping: float = 0.6, tail: float = 0.4,
          lo: float = 250.0, hi: float = 3500.0) -> np.ndarray:
    """A small room's reflections added to ``x``, with the reverb's own sound band-limited
    (stone and timber soak up the highs and the boom), so its tail never hisses or rumbles.
    The wet part is what the reverb adds beyond its dry path."""
    full = A.reverb(x, room, wet, damping, tail=tail)
    dry = np.concatenate([x, np.zeros(len(full) - len(x))])
    w = full - dry * 2.0 * (1.0 - wet * 0.5)
    return dry + A.bandpass(w, lo, hi, 2) / (2.0 * (1.0 - wet * 0.5))


def _close(x: np.ndarray) -> np.ndarray:
    """The faint early reflections of a room around a card table (a short, quiet,
    band-limited tail), so a close-up sound is heard in a place rather than in a void."""
    return _room(x, room=0.08, wet=0.06, damping=0.7, tail=0.2, lo=300, hi=5000)


# ----------------------------------------------------------------------------- composite pieces
def _table_knock(seed: int, scale: float = 1.0, hard: float = 0.0009, real: float = 0.6) -> np.ndarray:
    """A deck knocked on a thick oak tabletop: the strike of real wood (a woodblock,
    damped at once), the table's own damped low modes under it (D3, A3, A4, E5: the modes
    that ring long enough to be heard as a pitch sit on the D scale), short inharmonic
    ones above, and the papery edge of the cards."""
    modes = [(147 * scale, 0.3, 0.05), (220 * scale, 0.45, 0.045), (440 * scale, 1.0, 0.04),
             (659 * scale, 0.6, 0.028), (905 * scale, 0.45, 0.016), (1380 * scale, 0.25, 0.01),
             (2150 * scale, 0.12, 0.006)]
    wood = _en(_modal(_mallet(0.3, hard, seed, 0.35), modes))
    strike = _en(_woodblock("A2" if scale < 1.01 else "D3", 105, 0.022, lp=5000))
    pap = _en(_burst(0.04, 700, 4500, 0.003, seed + 1))
    return _norm(_place([(wood, 0, 1.0), (strike, 0, real), (pap, 0, 0.55)]))


def _snaps(times: Sequence[float], seed: int, centers=(3000.0, 2400.0), amps=None, tau=(0.0014, 0.0028),
           ring: float = 0.3, lp: float = 8000.0, body: float = 0.0, clump: float = 0.0) -> np.ndarray:
    """A run of card snaps at ``times`` (a riffle, a cascade), alternating between two
    halves' pitches, each a little different. ``body`` adds the low patter of each card
    slapping onto the one below; ``clump`` is the chance that two cards let go together
    (a second snap a few milliseconds after the first)."""
    rng = np.random.default_rng(seed)
    end = (max(times) if len(times) else 0.0) + 0.06
    buf = np.zeros(_n(end))
    for i, t0 in enumerate(times):
        c = centers[i % len(centers)] * rng.uniform(0.85, 1.15)
        a = (amps[i] if amps is not None else 1.0) * rng.uniform(0.55, 1.0)
        s = _snap(seed * 1000 + i, center=c, tau=float(rng.uniform(*tau)), dur=0.022, ring=ring, lp=lp)
        if body:
            s = s + body * _burst(0.022, 300.0, 1300.0, 0.003, seed * 1000 + 500 + i)
        buf = A.mix_at(buf, s, float(t0), a)
        if clump and rng.random() < clump:
            s2 = _snap(seed * 1000 + 700 + i, c * rng.uniform(0.9, 1.1), float(rng.uniform(*tau)), 0.022, ring, lp=lp)
            buf = A.mix_at(buf, s2, float(t0 + rng.uniform(0.0012, 0.004)), a * float(rng.uniform(0.45, 0.85)))
    return buf


def _riffle(n_cards: int, length: float, seed: int, centers=(3100.0, 2500.0), rustle: float = 0.2,
            lp: float = 8000.0, loud_mid: float = 0.45) -> np.ndarray:
    """A riffle: the two halves' cards flick free one by one, alternating sides, slower at
    the start and the end, now and then two at once, each landing with a little patter,
    over the rustle of the halves' faces rubbing."""
    rng = np.random.default_rng(seed)
    u = np.linspace(0.0, 1.0, n_cards)
    prof = (1.0 + 0.9 * (2 * u - 1) ** 2) * rng.uniform(0.6, 1.4, n_cards)
    times = np.concatenate([[0.0], np.cumsum(prof[:-1])])
    times *= length / times[-1]
    amps = (1.0 - loud_mid + loud_mid * np.sin(np.pi * u) ** 0.5)
    buf = _snaps(times, seed, centers, amps, lp=lp, body=0.35, clump=0.2)
    bed = _rub(length + 0.04, [(0, 0.5), (0.5, 0.8), (0.92, 0.5), (1, 0.0)], seed + 5, 1000, 6500,
               bright=0.4, crisp=0.3)
    return _place([(_norm(buf), 0, 1.0), (_norm(bed), 0, rustle)])


def _cascade(dur: float, n_cards: int, seed: int, center: float = 2000.0) -> np.ndarray:
    """The bridge: the bent deck lets go and the cards fall together in a soft, fast purr."""
    rng = np.random.default_rng(seed)
    u = np.sort(rng.uniform(0, 1, n_cards)) ** 1.15
    amps = (0.55 + 0.45 * np.sin(np.pi * np.minimum(1.0, u * 1.2)))
    buf = _snaps(u * dur, seed, (center, center * 1.15), amps, tau=(0.0015, 0.003), ring=0.15, lp=5000)
    bed = _rub(dur + 0.03, [(0, 0.8), (0.6, 0.6), (1, 0.0)], seed + 3, 700, 4500, bright=0.3, crisp=0.25)
    return _place([(_norm(buf), 0, 1.0), (_norm(bed), 0, 0.3)])


def _deck_tap(seed: int) -> np.ndarray:
    """A squared deck tapped on felt: the papery knock of its edge over a short soft thud."""
    th = _en(_thud(seed, 210, 0.016, knock=0.7, knock_lp=1400))
    pap = _en(A.lowpass(_burst(0.05, 500, 3500, 0.004, seed + 1), 4000))
    return _norm(_place([(th, 0, 0.6), (pap, 0, 1.0)]))


def _retexture(x: np.ndarray, env: np.ndarray, win: float = 0.006, floor_db: float = -24.0) -> np.ndarray:
    """Give a real recording's texture a new loudness curve: divide out its own (smoothed)
    envelope, where it is within ``floor_db`` of its peak, and apply ``env`` instead."""
    n = min(len(x), len(env))
    y = x[:n]
    k = max(3, _n(win))
    e = np.sqrt(np.convolve(y ** 2, np.ones(k) / k, mode="same"))
    pk = float(np.max(e)) or 1.0
    e = np.maximum(e, pk * 10 ** (floor_db / 20.0))
    return _tail(y / e * env[:n], 0.1)


def _swirl_flat(src: int, hp: float, lp: float) -> np.ndarray:
    """0.3 s of a real brush swirl with its own decay divided out (unit loudness): one of
    four takes (two banks, two strengths)."""
    bank = ("fluid", "musescore")[src % 2]
    vel = (70, 100)[(src // 2) % 2]
    x = _brush(40, vel, hp, lp, bank)[:_n(0.3)]
    return _retexture(x, np.ones(len(x)), floor_db=-36.0)


def _swirl(dur: float, env, seed: int = 0, hp: float = 450.0, lp: float = 5000.0) -> np.ndarray:
    """A real brush swirl's bristle-on-skin texture, as long as needed (takes overlapped
    with 50 ms crossfades) and shaped to ``env`` (points or an array): the grain of a card
    dragged over felt."""
    n = _n(dur)
    out = np.zeros(n + _n(0.3))
    hop = _n(0.25)
    xf = _n(0.05)
    pos, k = 0, seed
    while pos < n:
        c = _rms1(_swirl_flat(k, hp, lp))
        w = np.ones(len(c))
        w[:xf] = np.sin(0.5 * np.pi * np.arange(xf) / xf) if pos else 1.0
        w[-xf:] = np.cos(0.5 * np.pi * np.arange(xf) / xf)
        out[pos:pos + len(c)] += c * w
        pos += hop
        k += 1
    return _tail(_fade_in(out[:n] * _arr(env, n), 0.001), 0.1)


# ============================================================================= card_select
def sel_card_lift():
    # the thumb pushes the card up: its face rubs on its neighbours (quickening, then
    # easing), a breath of air moves with it, and its edge clears the fan with a tiny flick
    start = _en(_snap(12, center=2400, tau=0.0018, dur=0.02, ring=0.25, lp=6500))
    rub = _en(_rub(0.056, [(0, 0.35), (0.35, 1.0), (0.75, 0.55), (1, 0.0)], 11, lo=1000, hi=5500, bright=0.4,
                   crisp=0.45, rate=3500))
    flap = _en(_burst(0.05, 250, 1000, 0.01, 14, attack=0.003))
    edge = _en(_snap(13, center=3100, tau=0.0014, dur=0.02, ring=0.3, lp=7000))
    x = _place([(start, 0, 0.65), (rub, 0.001, 0.8), (flap, 0, 0.3), (edge, 0.05, 0.3)], 0.12)
    return _fit(x, "card_select", 0.03, lp=7500, crest=18.0)


def sel_felt_tap():
    # a fingertip on a card lying on felt: the soft knock of the tip, the card's dull tick,
    # and the felt's own hush (a real brush, barely touching)
    tip = _en(A.lowpass(_snap(22, center=1300, tau=0.0016, dur=0.02, ring=0.15), 3000))
    th = _en(_thud(21, f=320, tau=0.008, q=1.5, knock=0.6, knock_lp=1500))
    hush = _en(_damp(_brush(38, 45, 300, 3500), 0.0, 0.008))
    x = _place([(tip, 0, 0.55), (th, 0, 0.6), (hush, 0, 0.5)], 0.1)
    return _fit(x, "card_select", 0.03, lp=3800, crest=18.0)


def sel_oak_tick():
    # a small wooden counter set on an oak board: a real woodblock's strike, damped at once,
    # over the board's short low knock
    wb = _en(_woodblock("A5", 62, 0.011, lp=6000))
    board = _en(_modal(_mallet(0.1, 0.0006, 31), [(294, 0.6, 0.012), (587, 0.45, 0.008), (1190, 0.2, 0.004)]))
    x = _place([(wb, 0, 1.0), (board, 0, 0.35)], 0.12)
    return _fit(x, "card_select", 0.04, crest=18.0)


def sel_harp_touch():
    # the lightest touch of a harp string (A5), damped by the palm, under a card's tick
    harp = _bank([Note(GM["harp"], "A5", 0.0, 0.1, vel=58)], 0.6, "musescore")
    harp = _en(_damp(harp, 0.03, 0.03, 0.22))
    tick = _en(_snap(41, 2400, 0.0016, 0.02, ring=0.2, lp=5000))
    x = _place([(tick, 0, 0.65), (harp, 0, 0.8)], 0.23)
    return _fit(x, "card_select", 0.04, lp=7000, crest=18.0)


def sel_corner_flick():
    # a thumbnail bends the card's corner (a faint crackle) and lets it go: a crisp snap with
    # the card's short ring and the soft "tup" of the card flexing back, then the corner
    # patting against its neighbour
    bend = _en(_flutter(0.012, 51, rate=3000, lo=1600, hi=5500, tau=0.006))
    snap = _en(_snap(52, center=2600, tau=0.0015, dur=0.03, ring=0.4, lp=7000))
    tup = _en(_burst(0.03, 500, 1600, 0.004, 54, attack=0.0008))
    back = _en(_snap(53, center=2000, tau=0.002, dur=0.025, ring=0.25, lp=5500))
    x = _place([(bend, 0, 0.3), (snap, 0.004, 1.0), (tup, 0.004, 0.55), (back, 0.022, 0.35)], 0.08)
    return _fit(x, "card_select", 0.025, lp=7000, crest=18.0)


# ============================================================================= card_deselect
def des_card_tuck():
    # the card slides back down among its neighbours (the band falling as it slows) and
    # settles with a soft pat
    start = _en(A.lowpass(_snap(52, 1900, 0.0018, 0.02, ring=0.15), 4500))
    rub = _en(_rub(0.075, [(0, 0.7), (0.4, 0.6), (1, 0.05)], 51, lo=800, hi=4200, bright=0.25, crisp=0.4))
    settle = _en(_slap(54, 400, 2200, 0.004, air=0.6, air_lp=700, flutter=0.2, dur=0.04))
    x = _place([(start, 0, 0.5), (rub, 0.001, 0.8), (settle, 0.066, 0.5)], 0.15)
    return _fit(x, "card_deselect", 0.03, lp=5000, crest=18.0)


def des_soft_pat():
    # an even softer, lower pat of the fingertip on felt
    th = _en(_thud(61, f=250, tau=0.01, q=1.4, knock=0.5, knock_lp=900))
    pff = _en(_burst(0.03, 250, 1100, 0.005, 63))
    hush = _en(_damp(_brush(38, 35, 250, 2400), 0.0, 0.01))
    x = _place([(th, 0, 0.6), (pff, 0, 0.55), (hush, 0, 0.45)], 0.1)
    return _fit(x, "card_deselect", 0.03, lp=2600, crest=18.0)


def des_oak_tock():
    # the same wood a fourth lower and struck more softly: rounder, darker
    wb = _en(_woodblock("D5", 52, 0.018, lp=4000))
    board = _en(_modal(_mallet(0.12, 0.0009, 71), [(220, 0.6, 0.014), (440, 0.4, 0.01)]))
    x = _place([(wb, 0, 1.0), (board, 0, 0.35)], 0.15)
    return _fit(x, "card_deselect", 0.04, crest=18.0)


def des_lute_thumb():
    # a lute's D string plucked softly with the thumb and stopped by the palm, as the card
    # settles back
    lute = _bank([Note(GM["nylon_guitar"], "D4", 0.0, 0.08, vel=62)], 0.6)
    lute = _en(_damp(lute, 0.02, 0.035, 0.22))
    settle = _en(_slap(72, 400, 2500, 0.004, air=0.5, flutter=0.15, dur=0.04))
    x = _place([(settle, 0, 0.6), (lute, 0, 0.8)], 0.23)
    return _fit(x, "card_deselect", 0.04, crest=18.0)


def des_slip_back():
    # just the slide: the card slips back down against the next one and is still
    rub = _rub(0.11, [(0, 0.55), (0.2, 0.7), (1, 0.0)], 81, lo=700, hi=3800, bright=0.3, crisp=0.35, wobble=0.25)
    return _fit(rub, "card_deselect", 0.04, lp=4500, crest=18.0)


# ============================================================================= play
def play_felt_slap():
    # a card slapped down firmly: the slap, the air pushed out from under it, the felt's
    # brushy hush (a real brush slap), the table's soft thud and a short skid
    slap = _en(_slap(101, 450, 4200, 0.007, air=0.55, air_lp=1000, flutter=0.35))
    hush = _en(_damp(_brush(39, 95, 400, 6000), 0.0, 0.018))
    th = _en(_thud(103, 200, 0.022, q=1.6, knock=0.5))
    skid = _en(_rub(0.09, [(0, 0.7), (1, 0.0)], 104, 500, 3500, bright=0.3, crisp=0.4))
    x = _place([(slap, 0, 1.0), (hush, 0, 0.5), (th, 0, 0.5), (skid, 0.008, 0.3)], 0.4)
    return _fit(x, "play", 0.08, lp=8000)


def play_soft_place():
    # a card laid down gently (a soft pat and its air) and slid a little into place over the
    # felt (a real brush swirl's grain under the card's rub)
    pat = _en(A.lowpass(_slap(112, 350, 2600, 0.009, air=0.8, air_lp=800, flutter=0.15, dur=0.06), 3000))
    th = _en(_thud(111, 190, 0.02, q=1.4, knock=0.4, knock_lp=800))
    sp = [(0, 0.3), (0.25, 0.65), (0.7, 0.4), (1, 0.0)]
    slide = _en(_rub(0.18, sp, 113, 500, 3200, bright=0.25, crisp=0.35))
    grain = _en(_swirl(0.18, sp, 1, 450, 3500))
    x = _place([(pat, 0, 1.0), (th, 0, 0.5), (slide, 0.03, 0.5), (grain, 0.03, 0.4)], 0.3)
    return _fit(_close(x), "play", 0.06, lp=4000)


def play_tavern_slam():
    # cards slammed onto a heavy oak tavern table: its wooden knock, the slap, a second card
    # landing, and a short echo off stone walls
    table = _en(_table_knock(121))
    slap = _en(_slap(122, 600, 5200, 0.009, air=0.4, flutter=0.4))
    slap2 = _en(_burst(0.05, 800, 5000, 0.005, 123))
    x = _place([(table, 0, 1.0), (slap, 0, 0.8), (slap2, 0.04, 0.35)], 0.5)
    x = _room(_soften(x, 1.6), room=0.25, wet=0.12, damping=0.65, tail=0.35, lo=250, hi=3000)
    return _fit(x, "play", 0.2, lp=8000, shave=6.0)


def play_lute_strike():
    # the card slapped down with a quick downward strum of a lute (D, A, D, F#, A), the
    # strings stopped by the palm almost at once
    slap = _en(_slap(131, 450, 4500, 0.007, air=0.5, flutter=0.3))
    th = _en(_thud(132, 200, 0.02, q=1.5, knock=0.5))
    chord = ("D3", "A3", "D4", "F#4", "A4")
    lute = _bank([Note(GM["nylon_guitar"], p, 0.011 * i, 0.2, vel=78 - 4 * i) for i, p in enumerate(chord)], 1.2)
    lute = _en(_damp(lute, 0.12, 0.05, 0.6))
    x = _place([(_soften(_place([(slap, 0, 1.0), (th, 0, 0.45)]), 1.4), 0, 1.0), (lute, 0.008, 0.75)], 0.7)
    return _fit(_close(x), "play", 0.08, lp=8000, shave=6.0)


def play_fan_toss():
    # a fanned handful tossed down: a flicker of card edges in the air, then the cards land
    # one on another in a quick ripple, and skid to a stop
    rng = np.random.default_rng(141)
    parts = [(_en(_flutter(0.02, 140, rate=5000, lo=1500, hi=6500, tau=0.008)), 0, 0.3)]
    for i, (t0, g) in enumerate(((0.012, 1.0), (0.026, 0.8), (0.043, 0.72), (0.055, 0.55), (0.071, 0.45))):
        lo = 420 * rng.uniform(0.85, 1.2)
        s = _en(_slap(142 + i, lo, lo * 9.5, float(rng.uniform(0.004, 0.007)), air=0.45, flutter=0.3, dur=0.06))
        parts.append((s, t0, g))
    parts.append((_en(_thud(150, 210, 0.02, q=1.5, knock=0.5)), 0.012, 0.45))
    parts.append((_en(_rub(0.12, [(0, 0.7), (1, 0.0)], 151, 600, 4000, bright=0.35, crisp=0.45)), 0.06, 0.35))
    return _fit(_place(parts, 0.3), "play", 0.08, lp=8000)


# ============================================================================= draw
def _draw_one(seed: int, length: float = 0.17, lo: float = 900, hi: float = 6500, crisp: float = 0.45) -> np.ndarray:
    """One card pushed off the deck by the thumb: the push, the slide over the next card,
    the snap as it clears the deck's edge, and a soft landing in the hand."""
    push = _en(_snap(seed, center=2200, tau=0.0022, dur=0.03, ring=0.2, lp=7000))
    slide = _en(_rub(length, [(0, 0.3), (0.45, 1.0), (0.8, 0.55), (1, 0.0)], seed + 1, lo, hi, bright=0.5, crisp=crisp))
    edge = _en(_snap(seed + 2, center=3200, tau=0.0025, dur=0.03, ring=0.35, lp=7500))
    land = _en(_slap(seed + 3, 500, 3000, 0.004, air=0.6, flutter=0.2, dur=0.04))
    return _place([(push, 0, 0.4), (slide, 0.002, 1.0), (edge, length * 0.85, 0.32), (land, length + 0.02, 0.3)])


def draw_deck_slide():
    x = _place([(_draw_one(201, hi=5500), 0, 1.0), (_draw_one(211, length=0.15, hi=5500), 0.27, 0.9)], 0.65)
    return _fit(_close(x), "draw", 0.05, lp=7500)


def draw_quiet_draw():
    # one card drawn slowly: a soft push, a long gentle slide (with the felt's real grain
    # under it) and a quiet pat as it joins the hand
    push = _en(A.lowpass(_snap(221, 1500, 0.002, 0.03, ring=0.1), 3000))
    sp = [(0, 0.4), (0.3, 0.8), (0.7, 0.65), (1, 0.0)]
    slide = _en(_rub(0.32, sp, 222, 500, 3500, bright=0.3, crisp=0.35))
    grain = _en(_swirl(0.32, sp, 2, 400, 3200))
    pat = _en(_slap(224, 300, 1500, 0.005, air=0.7, flutter=0.1, dur=0.05))
    th = _en(_thud(223, 220, 0.014, knock=0.5, knock_lp=1000))
    x = _place([(push, 0, 0.4), (slide, 0.002, 0.8), (grain, 0.002, 0.5), (pat, 0.31, 0.35), (th, 0.31, 0.25)], 0.45)
    return _fit(_close(x), "draw", 0.05, lp=4500)


def draw_dealer():
    # three cards dealt across a wooden table: each a flick from the deck, a short skim and
    # a slap with the table's small knock (real wood under it), in a small room
    parts = []
    for k, t0 in enumerate((0.0, 0.14, 0.28)):
        s = 230 + 10 * k
        flick = _snap(s, center=3600, tau=0.002, dur=0.03, ring=0.4)
        skim = _rub(0.06, [(0, 0.9), (1, 0.1)], s + 1, 1200, 7000, bright=0.6, crisp=0.5)
        knock = _norm(_modal(_mallet(0.12, 0.0012, s + 2), [(330, 0.7, 0.03), (494, 0.8, 0.025),
                                                              (880, 0.6, 0.018), (1350, 0.3, 0.012)]))
        wood = _norm(_woodblock("D4", 70, 0.012, lp=4500))
        slap = A.lowpass(_slap(s + 3, 700, 4500, 0.0035, air=0.4, flutter=0.3, dur=0.05), 5000)
        parts += [(flick, t0, 0.6), (_norm(skim), t0 + 0.002, 0.35), (slap, t0 + 0.075, 0.7), (knock, t0 + 0.075, 0.4),
                  (wood, t0 + 0.075, 0.25)]
    x = _room(_place(parts, 0.55), room=0.22, wet=0.12, damping=0.6, tail=0.35, lo=250, hi=3000)
    return _fit(x, "draw", 0.2, lp=8000)


def draw_harp_draw():
    # a short, soft card slide with a light rising harp run (D, E, F#, A), let ring and then
    # hushed
    slide = _en(_rub(0.14, [(0, 0.45), (0.3, 0.9), (1, 0.0)], 241, 900, 5000, bright=0.4))
    push = _en(_snap(242, 2300, 0.002, 0.03, ring=0.2, lp=6500))
    run = (("D5", 56), ("E5", 56), ("F#5", 58), ("A5", 62))
    harp = _bank([Note(GM["harp"], p, 0.055 * i, 0.4, vel=v) for i, (p, v) in enumerate(run)], 1.6, "musescore")
    harp = _en(_damp(harp, 0.4, 0.11, 0.92))
    x = _place([(push, 0, 0.4), (slide, 0.002, 0.7), (harp, 0.03, 0.85)], 0.97)
    return _fit(_close(x), "draw", 0.08, lp=7500)


def draw_thumb_peel():
    # the thumb presses the top card (a soft press) and bends it up (a creak of card stock,
    # quickening); it snaps free of the deck with a ring, flaps once through the air and
    # lands in the hand
    press = _en(_slap(250, 500, 3000, 0.004, air=0.5, flutter=0.2, dur=0.04))
    n = _n(0.07)
    bend = _crackle(n, [(0, 600), (1, 3200)], [(0, 0.45), (1, 1.0)], 251, 900, 4500, q=3.0)
    bend = _en(_tail(_fade_in(bend, 0.001), 0.15))
    snap = _en(_snap(252, center=2600, tau=0.003, dur=0.04, ring=0.5, lp=7500))
    flap = _en(_burst(0.07, 180, 1100, 0.014, 253, attack=0.004))
    fl = _en(_flutter(0.04, 254, rate=3000, tau=0.01))
    land = _en(_slap(255, 400, 2500, 0.005, air=0.6, flutter=0.15, dur=0.05))
    x = _place([(press, 0, 0.35), (bend, 0.004, 0.45), (snap, 0.072, 1.0), (flap, 0.074, 0.4), (fl, 0.076, 0.35),
                (land, 0.19, 0.45)], 0.35)
    return _fit(_close(x), "draw", 0.05, lp=7500)


# ============================================================================= shuffle
def shuf_riffle():
    rif = _riffle(46, 0.6, 301, centers=(3100, 2500), rustle=0.2)
    bridge = _cascade(0.26, 48, 311, center=2000)
    tap = _deck_tap(312)
    x = _place([(rif, 0, 1.0), (bridge, 0.72, 0.7), (tap, 1.06, 0.8)], 1.4)
    return _fit(_close(x), "shuffle", 0.1, lp=9000)


def shuf_overhand():
    # small packets slid off the deck into the other hand, one after another, softly
    rng = np.random.default_rng(321)
    parts = [(_en(A.lowpass(_snap(339, 1800, 0.002, 0.02, ring=0.1), 4000)), 0, 0.3)]
    for k, t0 in enumerate((0.0, 0.2, 0.37, 0.56, 0.74, 0.95)):
        L = float(rng.uniform(0.09, 0.13))
        sl = _en(_rub(L, [(0, 0.5), (0.2, 1.0), (1, 0.0)], 322 + k, 600, 4200, bright=0.3, crisp=0.4))
        pat = _en(_slap(340 + k, 350, 2000, 0.004, air=0.6, flutter=0.15, dur=0.04))
        th = _en(_thud(330 + k, 240, 0.01, knock=0.6, knock_lp=1200))
        parts += [(sl, t0, float(rng.uniform(0.8, 1.0))), (pat, t0 + L * 0.9, 0.4), (th, t0 + L * 0.9, 0.25)]
    return _fit(_close(_place(parts, 1.15)), "shuffle", 0.06, lp=4500)


def shuf_tavern():
    rif = _riffle(40, 0.48, 341, centers=(3300, 2700), rustle=0.15)
    k1 = _table_knock(342, 1.0)
    k2 = _table_knock(343, 1.02)
    x = _place([(rif, 0, 1.0), (k1, 0.62, 0.8), (k2, 0.80, 0.7)], 1.1)
    x = _room(x, room=0.25, wet=0.12, damping=0.65, tail=0.4, lo=250, hi=3000)
    return _fit(x, "shuffle", 0.25, lp=9000)


def shuf_fairy():
    # cards fluttering up through the air (soft flaps of card), a harp glissando swirling up
    # the D pentatonic, celesta twinkles scattered through it, and a soft celesta chord
    # (D, F#, A) as the cards settle
    rng = np.random.default_rng(351)
    parts = []
    for i in range(24):
        t0 = 0.0 if i == 0 else float(rng.uniform(0.0, 0.7))
        sw = math.sin(math.pi * min(1.0, t0 / 0.7)) ** 0.7
        flap = A.lowpass(_burst(0.04, 500, 3500, float(rng.uniform(0.006, 0.011)), 35200 + i, attack=0.002), 4500)
        parts.append((flap, t0, (0.3 + 0.35 * sw) * float(rng.uniform(0.7, 1.0)) if i else 0.6))
    gl = ("D5", "E5", "F#5", "A5", "B5", "D6", "E6", "F#6", "A6")
    harp = _bank([Note(GM["harp"], p, 0.04 * i, 0.3, vel=50 + 2 * i) for i, p in enumerate(gl)], 2.0, "musescore")
    parts.append((_damp(_norm(harp), 0.55, 0.15, 1.35), 0.0, 0.5))
    # celesta: twinkles from 0.10 s, the chord at 0.66 s (times below are from 0.10 s)
    tw = (("A6", 0.0, 46), ("F#6", 0.12, 44), ("B6", 0.21, 48), ("D7", 0.32, 44), ("E6", 0.4, 42),
          ("D6", 0.56, 52), ("F#6", 0.575, 48), ("A6", 0.59, 50))
    cel = _bank([Note(GM["celesta"], p, t, 0.25, vel=v) for p, t, v in tw], 2.2, "musescore")
    parts.append((_damp(_norm(cel), 0.65, 0.16, 1.3), 0.10, 0.55))
    return _fit(_place(parts, 1.55), "shuffle", 0.15)


def shuf_table_wash():
    # the flat hands land on the spread deck, then swirl it round the felt (two circling
    # rubs, cards clicking against cards), push it together and square it with a tap
    n = _n(1.1)
    t = _t(n)
    parts = [(_en(_slap(360, 300, 2400, 0.006, air=0.8, air_lp=700, flutter=0.3, dur=0.05)), 0, 0.55)]
    for h, (rate, ph, seed) in enumerate(((2.2, 0.6, 361), (2.7, 2.1, 362))):
        circ = 0.25 + 0.75 * np.sin(2 * np.pi * rate * t + ph) ** 2
        env = circ * np.clip(0.4 + t / 0.05, 0, 1) * np.clip((1.1 - t) / 0.2, 0, 1)
        parts.append((_en(_rub(1.1, env, seed, 500, 4500, bright=0.35, rate=2500)), 0.002, 0.8))
        parts.append((_en(_swirl(1.1, env, h, 450, 4000)), 0.002, 0.45))
    rng = np.random.default_rng(363)
    k = 28
    clicks = np.sort(rng.uniform(0.03, 1.0, k))
    parts.append((_en(_snaps(clicks, 364, (2200.0, 1700.0), rng.uniform(0.3, 1.0, k), ring=0.2, lp=5000,
                             body=0.4)), 0, 0.55))
    gather = _en(_rub(0.14, [(0, 0.6), (0.5, 1.0), (1, 0.0)], 365, 500, 3500, bright=0.3))
    parts += [(gather, 1.12, 0.7), (_en(_deck_tap(366)), 1.3, 0.85)]
    return _fit(_close(_place(parts, 1.5)), "shuffle", 0.08, lp=5500)


# ============================================================================= discard
def disc_pile_toss():
    # a few cards flicked from the hand, fluttering briefly, landing on the pile one after
    # another and skidding to rest
    flick = _en(_snap(401, 2600, 0.0022, 0.03, ring=0.25))
    flut = _en(_flutter(0.07, 402, rate=4500, lo=1100, hi=5500, tau=0.05))
    land1 = _en(_slap(403, 600, 5000, 0.005, air=0.5, flutter=0.3))
    pile = _en(_thud(404, 230, 0.016, knock=0.6, knock_lp=1400))
    land2 = _en(_slap(405, 700, 5200, 0.004, air=0.4, flutter=0.3, dur=0.05))
    land3 = _en(_slap(406, 800, 5000, 0.003, air=0.35, flutter=0.3, dur=0.05))
    skid = _en(_rub(0.1, [(0, 0.6), (1, 0.0)], 407, 700, 4500, bright=0.35, crisp=0.45))
    x = _place([(flick, 0, 0.45), (flut, 0.004, 0.35), (land1, 0.075, 1.0), (pile, 0.075, 0.5),
                (land2, 0.1, 0.6), (land3, 0.135, 0.4), (skid, 0.08, 0.4)], 0.45)
    return _fit(x, "discard", 0.06, lp=8000)


def disc_soft_drop():
    # cards let fall gently onto the pile: a muffled pat, a soft thud and a sigh of card
    pat = _en(A.lowpass(_slap(411, 400, 2000, 0.01, air=0.8, air_lp=800, flutter=0.15, dur=0.06), 2500))
    th = _en(_thud(412, 200, 0.02, q=1.4, knock=0.5, knock_lp=900))
    sigh = _en(_rub(0.15, [(0, 0.6), (1, 0.0)], 413, 400, 2200, bright=0.2, crisp=0.3))
    x = _place([(pat, 0, 1.0), (th, 0, 0.55), (sigh, 0.01, 0.55)], 0.3)
    return _fit(x, "discard", 0.05, lp=3000)


def disc_crate_drop():
    # cards dropped into a small hollow wooden tray: the strike of real hollow wood, the
    # tray's note on D4 and its panels on A4, F#5 and B5 (and one short rough mode), struck
    # three times as the cards land
    modes = [(294, 0.8, 0.07), (440, 0.9, 0.05), (740, 0.5, 0.035), (988, 0.35, 0.022), (1650, 0.18, 0.014)]
    parts = []
    for i, (at, g) in enumerate(((0.0, 1.0), (0.045, 0.45), (0.08, 0.2))):
        box = _en(_modal(_mallet(0.4, 0.0015, 421 + i, 0.3), modes))
        wood = _en(_woodblock("D4", 90 - 20 * i, 0.03, lp=4500))
        slap = _en(_slap(425 + i, 600, 4500, 0.004, air=0.3, flutter=0.3, dur=0.05))
        parts += [(box, at, g), (wood, at, 0.55 * g), (slap, at, 0.55 * g)]
    x = _room(_place(parts, 0.5), room=0.18, wet=0.1, damping=0.6, tail=0.3, lo=250, hi=3000)
    return _fit(x, "discard", 0.2)


def disc_lute_sigh():
    # a soft toss onto the pile and three falling lute notes, A, F, D (D dorian): a sigh for
    # the cards lost
    flick = _en(_snap(431, 2400, 0.0025, 0.03, ring=0.2))
    land = _en(_slap(432, 450, 3500, 0.005, air=0.6, flutter=0.25, dur=0.05))
    fall = (("A4", 0.0, 64), ("F4", 0.12, 60), ("D4", 0.24, 62))
    lute = _bank([Note(GM["nylon_guitar"], p, t, 0.3, vel=v) for p, t, v in fall], 1.5)
    lute = _en(_damp(lute, 0.42, 0.1, 0.84))
    x = _place([(flick, 0, 0.45), (land, 0.02, 0.6), (lute, 0.02, 1.0)], 0.88)
    return _fit(_close(x), "discard", 0.08)


def disc_swept_aside():
    # the flat of the hand comes down on the cards and sweeps them off the table (palm and
    # cards dragging over the felt, edges knocking together, the hand pushing unevenly),
    # dropping them onto the pile in a short patter
    sp = [(0, 0.6), (0.15, 1.0), (0.4, 0.7), (0.6, 0.95), (0.85, 0.75), (1, 0.0)]
    pat = _en(_slap(440, 300, 2200, 0.006, air=0.8, air_lp=700, flutter=0.2, dur=0.05))
    sweep = _en(_rub(0.3, sp, 441, 400, 3800, bright=0.3, rate=3500, wobble=0.5))
    grain = _en(_swirl(0.3, sp, 3, 350, 3500))
    palm = _en(_burst(0.3, 150, 700, 0.12, 442, attack=0.02))
    rng = np.random.default_rng(448)
    knocks = np.sort(rng.uniform(0.02, 0.28, 7))
    edges = _en(_snaps(knocks, 449, (2000.0, 1500.0), rng.uniform(0.3, 1.0, 7), ring=0.2, lp=5000, body=0.4))
    parts = [(pat, 0, 0.5), (sweep, 0.003, 0.8), (grain, 0.003, 0.55), (palm, 0, 0.25), (edges, 0, 0.35)]
    for i, (t0, g) in enumerate(((0.31, 1.0), (0.335, 0.65), (0.37, 0.45))):
        parts.append((_en(_slap(443 + i, 500, 4000, 0.005, air=0.5, flutter=0.3, dur=0.05)), t0, g))
    parts.append((_en(_thud(447, 220, 0.016, knock=0.6, knock_lp=1200)), 0.31, 0.45))
    return _fit(_close(_place(parts, 0.6)), "discard", 0.06, lp=5500)


# ============================================================================= the list
C = Candidate
CANDIDATES = [
    # card_select: tiny, gentle tap feedback
    C("card_select", "card_lift", "Card lift",
      "A card nudged up out of your hand: a brief rub against its neighbours and a tiny flick.",
      sel_card_lift, ["realistic"]),
    C("card_select", "felt_tap", "Felt tap", "A soft, muffled fingertip tap on a card lying on felt, barely there.",
      sel_felt_tap, ["soft"]),
    C("card_select", "oak_tick", "Oak tick", "A small dry tick of real wood, like a wooden counter set on an oak board.",
      sel_oak_tick, ["wooden"]),
    C("card_select", "harp_touch", "Harp touch", "A card's tick with the lightest touch of a harp string, hushed at once.",
      sel_harp_touch, ["courtly"]),
    C("card_select", "corner_flick", "Corner flick", "A thumbnail flicking a card's corner: one small, crisp snap.",
      sel_corner_flick, ["crisp"]),
    # card_deselect: the select sounds' softer, lower cousins
    C("card_deselect", "card_tuck", "Card tuck", "The card slipping back down into your hand and settling.",
      des_card_tuck, ["realistic"]),
    C("card_deselect", "soft_pat", "Soft pat", "An even softer, lower pat on the felt.", des_soft_pat, ["soft"]),
    C("card_deselect", "oak_tock", "Oak tock", "A lower, rounder tock of real wood.", des_oak_tock, ["wooden"]),
    C("card_deselect", "lute_thumb", "Lute thumb",
      "The card settling back with one low lute string plucked softly and stopped by the palm.",
      des_lute_thumb, ["courtly"]),
    C("card_deselect", "slip_back", "Slip back", "Just a short, smooth slide of card against card, then stillness.",
      des_slip_back, ["soft"]),
    # play
    C("play", "felt_slap", "Felt slap", "A card slapped down firmly on a felt table.", play_felt_slap, ["realistic"]),
    C("play", "soft_place", "Soft place", "A card laid down gently on the felt and slid a little into place.",
      play_soft_place, ["soft"]),
    C("play", "tavern_slam", "Tavern slam", "Cards slammed onto a heavy wooden tavern table, with a little room echo.",
      play_tavern_slam, ["wooden"]),
    C("play", "lute_strike", "Lute strike", "A card slapped down with a quick strum of a lute, stopped short.",
      play_lute_strike, ["courtly"]),
    C("play", "fan_toss", "Fan toss", "A fanned handful of cards tossed down, landing in a quick ripple.",
      play_fan_toss, ["realistic"]),
    # draw
    C("draw", "deck_slide", "Deck slide", "Two cards slid off the top of the deck, one after the other.",
      draw_deck_slide, ["realistic"]),
    C("draw", "quiet_draw", "Quiet draw", "One card drawn slowly and softly across the felt into your hand.",
      draw_quiet_draw, ["soft"]),
    C("draw", "dealer", "Dealer's three", "Three quick cards dealt to you across a wooden table.", draw_dealer,
      ["wooden"]),
    C("draw", "harp_draw", "Harp draw", "A soft card slide with a light rising run on a harp.", draw_harp_draw,
      ["courtly"]),
    C("draw", "thumb_peel", "Thumb peel", "The top card bent up by the thumb, snapping free of the deck.",
      draw_thumb_peel, ["crisp"]),
    # shuffle
    C("shuffle", "riffle_bridge", "Riffle bridge",
      "A classic riffle shuffle: the purr of cards, the bridge, and a tap to square the deck.", shuf_riffle,
      ["realistic"]),
    C("shuffle", "overhand", "Soft overhand", "A gentle overhand shuffle: soft slides of small packets of cards.",
      shuf_overhand, ["soft"]),
    C("shuffle", "tavern_riffle", "Tavern riffle",
      "A quick riffle on a wooden table, finished with two knocks to square the deck.", shuf_tavern, ["wooden"]),
    C("shuffle", "fairy_flutter", "Fairy flutter",
      "Cards fluttering through the air with a swirling harp glissando and twinkling celesta.", shuf_fairy,
      ["magical"]),
    C("shuffle", "table_wash", "Table wash",
      "The deck swirled face down round the felt with both hands, then gathered and squared.", shuf_table_wash,
      ["realistic"]),
    # discard
    C("discard", "pile_toss", "Pile toss", "A few cards tossed onto the discard pile.", disc_pile_toss, ["realistic"]),
    C("discard", "soft_drop", "Soft drop", "Cards let fall gently onto the pile, muffled and quiet.", disc_soft_drop,
      ["soft"]),
    C("discard", "crate_drop", "Crate drop", "Cards dropped into a hollow wooden tray.", disc_crate_drop, ["wooden"]),
    C("discard", "lute_sigh", "Lute sigh", "A soft toss onto the pile and three falling lute notes, like a sigh.",
      disc_lute_sigh, ["courtly"]),
    C("discard", "swept_aside", "Swept aside", "The cards swept off the table by hand and dropped onto the pile.",
      disc_swept_aside, ["realistic"]),
]


# ============================================================================= the editor's pass
# A turn's sounds follow each other closely: the app starts the class power once 60% of
# the play's file has played (0.18 s after it at the soonest). The play sounds' last
# quiet ring (the room, the lute string) is damped from ``start`` and over by ``end``, so
# the power is not held back by a tail no one hears under it.
TAILS = {("play", "soft_place"): (0.22, 0.36), ("play", "tavern_slam"): (0.20, 0.45),
         ("play", "lute_strike"): (0.25, 0.42)}


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
    if not tail:
        return c
    render = c.render
    return dataclasses.replace(c, render=lambda: _hasten(render(), *tail))


CANDIDATES = [_edited(c) for c in CANDIDATES]
