"""Shuffle, modelled on the owner's reference: Pythonista's 'casino:CardFan1'.

The owner liked CardFan1 for a shuffle ("a bit less speedy. its a good sound tho!"). The
reference is a riffle, 0.72 s in all: a faint rustle with a stray tick or two as the
thumbs bend the deck; then about twenty cards flicking free roughly 17 ms apart, some
louder than others, so the flicks one hears come every 25 to 60 ms, the train quickening
and growing louder (its low thrum most: half the sound's energy is below 150 Hz); the
hands choke the deck into a near-silent pause; then the squaring snap, its brightest
moment, and a faint settling rattle. These candidates are built from scratch, in code,
from what happens in a riffle; no part of the reference recording is used, read or copied
(it was only measured, offline, to set the timings, levels and bands below).

What a riffle is made of, and what models each part here:
  bend     the thumbs lifting the deck's corners before the riffle: a dry creak of card
           stock and a stray card or two slipping early (``_bend``)
  flick    one card springing free of the thumb: its edge snapping onto the card below
           rings the card's stiff bending modes for a millisecond (the bright tick, most
           of it above 2.5 kHz), with a puff of crushed fibres and air, a dull slap of
           card on card, and the half-deck in the hand kicked by the release: the hand's
           and the deck's low, heavily damped modes near 115 to 135 Hz and nearly twice
           that, the thrum (``_flick``)
  halves   the cards come off the two halves by turns, but the thumbs never quite
           alternate: often two, now and then three, come off one half together. The near
           half's edges face the listener and are heard plainly, the far half's softly, so
           the ear follows an uneven train of flicks, now spread out, now bunched, with
           softer ticks between (``_riffle``)
  purr     the bent halves never stop moving while the cards stream off them: a low
           rumble under the separate thrums, swelling with each card (``_riffle``)
  rustle   the thumb's skin running over the card edges between the flicks (``_rustle``)
  square   the two interleaved halves pushed together: their faces rushing over each
           other, a first edge meeting the palm, then the whole packet: the big snap with
           its low thump, and a faint rattle as the cards settle (``_square``)
  cascade  (the bridge) the deck bowed up between the hands and let go: the cards fall
           flat onto each other in a fast, soft purr that slows as the deck closes
           (``_cascade``)
  room     the faint early reflections of a small room around the table, with no long
           tail (``_room``)

The owner asked for "a bit less speedy": these riffles keep the reference's shape (a quiet
bend, a quickening crescendo whose low thrum swells most, the hands choking the deck into
a near-silent pause, and the squaring snap), but the cards flick free 23 to 44 ms apart
instead of about 17, so the flicks one hears come 20 to 125 ms apart (most 40 to 80)
instead of 25 to 60, and the whole sound lasts 0.9 to 1.1 s instead of 0.72. Each flick
differs a little (its timing, strength, the pitch of its tick, some cards slipping off
softly, now and then two letting go together), and the halves interleave unevenly, so the
flicks one hears never fall into a steady beat: a slow riffle whose cards alternated
strictly would tick like a ratchet. A slow riffle is peakier than a fast one (the same
ticks with more quiet between them), so the ticks' very tops are rounded off
(``_round_ticks``) rather than left to the build's limiter, which would duck the whole
sound under each loud tick and flatten the crescendo. Everything is driven by seeded
noise, so each candidate is rebuilt identically. Layers are mixed by their share of the
energy (``_en``).
"""
from __future__ import annotations

import math
from typing import Sequence, Tuple

import numpy as np
from scipy import signal

import synth as A
from catalog import EVENT_BY_ID, Candidate

SR = A.SR
EVENT = EVENT_BY_ID["shuffle"]


# ----------------------------------------------------------------------------- basics
def _n(t: float) -> int:
    return int(round(t * SR))


def _t(n: int) -> np.ndarray:
    return np.arange(n) / SR


def _norm(x: np.ndarray) -> np.ndarray:
    p = float(np.max(np.abs(x))) if len(x) else 0.0
    return x / p if p > 0 else x


def _rms1(x: np.ndarray) -> np.ndarray:
    r = math.sqrt(float(np.mean(x ** 2))) if len(x) else 0.0
    return x / r if r > 0 else x


def _en(x: np.ndarray) -> np.ndarray:
    """Unit energy, so mixing gains set each layer's share of the energy (gain squared)."""
    e = math.sqrt(float(np.sum(x ** 2)) / SR * 1000.0)
    return x / e if e > 0 else x


def _db(v: float) -> float:
    return 10 ** (v / 20.0)


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


def _curve(u: np.ndarray, pts: Sequence[Tuple[float, float]]) -> np.ndarray:
    """A piecewise-linear curve through (position 0..1, value) points, read at ``u``."""
    xs, ys = zip(*pts)
    return np.interp(u, xs, ys)


def _lobe(t: np.ndarray, at: float, w: float) -> np.ndarray:
    """A raised-cosine bump ``w`` wide centred on ``at``."""
    x = (t - at) / w
    return np.where(np.abs(x) < 0.5, 0.5 + 0.5 * np.cos(2 * np.pi * x), 0.0)


def _over(x: np.ndarray, ref: np.ndarray, db: float, hp: float = 2500.0) -> float:
    """The gain that puts ``x``'s ticks (its peak above ``hp``, 2.5 kHz by default, where
    a snap is heard) ``db`` above ``ref``'s: the low thrum's swings do not count. With
    ``hp`` 0 the whole sound's peaks are compared."""
    def pk(y):
        return float(np.max(np.abs(A.highpass(y, hp, 2) if hp else y))) or 1.0
    return _db(db) * pk(ref) / pk(x)


def _place(parts, dur: float = 0.0) -> np.ndarray:
    """Mix [(sound, at seconds, gain), ...] into one buffer."""
    buf = np.zeros(max(1, _n(dur)))
    for snd, at, g in parts:
        buf = A.mix_at(buf, snd, max(0.0, at), g)
    return buf


def _modes(exc: np.ndarray, modes) -> np.ndarray:
    """Damped resonators driven by ``exc``: modes are (freq, gain, tau seconds); each is
    scaled to its own peak, so the gains read directly."""
    y = np.zeros(len(exc))
    for f, g, tau in modes:
        r = math.exp(-1.0 / (tau * SR))
        w = 2 * math.pi * min(f, SR * 0.45) / SR
        y += g * _norm(signal.lfilter([1.0], [1.0, -2 * r * math.cos(w), r * r], exc))
    return y


def _crackle(n: int, rate, amp, seed: int, lo: float, hi: float, k: int = 6, q: float = 3.0,
             alpha: float = 2.2, cap: float = 4.0) -> np.ndarray:
    """Paper fibres: sparse clicks at ``rate`` per second (a number or a per-sample array),
    each with a heavy-tailed strength scaled by ``amp``, ringing one of ``k`` small patches
    of card (short resonances spread from ``lo`` to ``hi``)."""
    rng = np.random.default_rng(seed)
    rate = np.broadcast_to(np.asarray(rate, dtype=float), (n,))
    amp = np.broadcast_to(np.asarray(amp, dtype=float), (n,))
    idx = np.nonzero(rng.random(n) < rate / SR)[0]
    y = np.zeros(n)
    if not len(idx):
        return y
    s = np.minimum(rng.pareto(alpha, len(idx)) + 1.0, cap) * rng.choice([-1.0, 1.0], len(idx)) * amp[idx]
    centres = np.geomspace(lo, hi, k) * rng.uniform(0.9, 1.1, k)
    grp = rng.integers(0, k, len(idx))
    for g in range(k):
        sel = grp == g
        if np.any(sel):
            imp = np.zeros(n)
            imp[idx[sel]] = s[sel]
            b, a = signal.iirpeak(min(centres[g], SR * 0.45), q, fs=SR)
            y += signal.lfilter(b, a, imp)
    return y


def _round_ticks(x: np.ndarray, crest_db: float, split: float = 1500.0, knee: float = 0.6) -> np.ndarray:
    """Round off the very tops of the card ticks, as a slightly softer edge would: the part
    of the sound above ``split`` is bent smoothly (a tanh past ``knee`` of the limit) so it
    never stands more than ``crest_db`` above the build's loudness measure, and the part
    below is left alone. A slow riffle is peakier than a fast one (the same ticks, more
    quiet between them), and this keeps the build's limiter from ducking the thrum and
    rustle under every loud tick, which would flatten the crescendo."""
    lo = A.lowpass(x, split, 2)
    hi = x - lo
    lim = _db(A._rms_db(x) + crest_db)
    k = knee * lim
    over = np.maximum(np.abs(hi) - k, 0.0)
    bent = k + (lim - k) * np.tanh(over / (lim - k))
    return lo + np.where(np.abs(hi) > k, np.sign(hi) * bent, hi)


def _gentle(x: np.ndarray, crest_db: float) -> np.ndarray:
    """Keep the peak at most ``crest_db`` above the build's loudness measure by shaving
    only the first fraction of a millisecond of the sharpest snaps (a fast look-ahead
    limiter), so mastering leaves the riffle's level alone."""
    for _ in range(3):
        ceil = A._rms_db(x) + crest_db
        if 20 * math.log10(float(np.max(np.abs(x))) + 1e-12) <= ceil + 0.05:
            break
        g = _db(ceil)
        x = A.limit(x / g, 0.0, lookahead=0.0008, release=0.012) * g
    return x


def _room(x: np.ndarray, wet: float = 0.2, seed: int = 7, lo: float = 300.0, hi: float = 5000.0) -> np.ndarray:
    """The faint early reflections of a small room around the table: a few delayed,
    band-limited copies (timber and cloth soak up the boom and the hiss), 3 to 23 ms late
    and fading, with no long tail to blur the flicks. ``wet`` is the first one's level."""
    rng = np.random.default_rng(seed)
    band = A.bandpass(x, lo, hi, 2)
    delays = np.array([3.1, 5.4, 8.2, 11.7, 16.3, 22.8]) * rng.uniform(0.93, 1.07, 6) / 1000.0
    out = np.concatenate([x, np.zeros(_n(0.03))])
    for k, d in enumerate(delays):
        g = wet * 0.72 ** k * rng.choice([-1.0, 1.0])
        out = A.mix_at(out, A.lowpass(band, hi * 0.85 ** k, 1), float(d), g)
    return out


def _finish(x: np.ndarray, crest_db: float = 19.5, ticks_db: float = 18.0, hp: float = 35.0, lp: float = 0.0,
            fade: float = 0.15) -> np.ndarray:
    """Take out the sub-bass and DC (and, with ``lp``, the very top), keep the sound inside
    the event's length, let the end fade smoothly, round off the ticks' tops (``ticks_db``)
    and keep what peaks remain gentle (``crest_db``)."""
    y = A.highpass(x, hp, 2)
    if lp:
        y = A.lowpass(y, lp, 2)
    y = y[:_n(EVENT.max_seconds - 0.03)]
    return _gentle(_round_ticks(_tail(y, fade), ticks_db), crest_db)


# ----------------------------------------------------------------------------- the physical parts
FLICK_LEAD = 0.001   # a _flick's release falls this many seconds into its buffer


def _flick(seed: int, ring: float = 4800.0, click: float = 1.0, body: float = 1.0, low: float = 110.0,
           low_tau: float = 0.014, slap: float = 0.3, width: float = 0.00012, puff: float = 0.75,
           lp: float = 16000.0, dur: float = 0.06) -> np.ndarray:
    """One card springing free of the thumb, its release ``FLICK_LEAD`` seconds into the
    buffer: the edge chatters off the thumb's skin in two or three contacts over a
    millisecond or so (each about ``width`` long; shorter is crisper), ringing the card's
    bending modes around ``ring`` and puffing out crushed fibres and air (``click`` sets
    their share, ``lp`` their top: lower for a card whose edge faces away); the card's face
    slaps the card below (a dull knock, ``slap``); and the half-deck in the hand, kicked by
    the release (a pressure bump a few milliseconds wide), sets the hand's and the deck's
    heavily damped modes near ``low`` and nearly twice it going for ``low_tau``
    seconds: the thrum (``body``)."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    t = _t(n)
    c = _n(FLICK_LEAD)
    m = n - c
    # the edge's release: two or three short contacts as it chatters free, a little rough
    exc = np.zeros(n)
    at, amp = c, 1.0
    for _ in range(int(rng.integers(2, 4))):
        w = max(2, _n(width * rng.uniform(0.75, 1.3)))
        exc[at:at + w] += amp * rng.choice([-1.0, 1.0]) * np.sin(np.pi * np.arange(w) / w)
        at += _n(rng.uniform(0.00025, 0.0007))
        amp *= rng.uniform(0.45, 0.75)
    exc[c:] += 0.2 * rng.standard_normal(m) * _decay(m, 0.0006, 0.00003)
    f = ring * rng.uniform(0.9, 1.1)
    edge = _modes(exc, [(f, 1.0, 0.0009), (f * rng.uniform(1.5, 1.7), 1.0, 0.0007),
                        (f * rng.uniform(2.2, 2.5), 0.7, 0.0005)])
    # the puff of fibres and air, with a few crackles
    env = np.zeros(n)
    env[c:] = _decay(m, 0.0012, 0.0002)
    hs = A.bandpass(rng.standard_normal(n), 2800.0, 16000.0, 2) * env
    cr = _crackle(n, 9000.0 * env, env, seed + 1, 2800.0, 12000.0, q=3.0, cap=3.0)
    pf = _en(hs) + (0.6 * _en(cr) if np.any(cr) else 0.0)
    # the slap of the card's face onto the one below: a dull, low knock
    kn = np.zeros(n)
    kn[c:] = A.bandpass(rng.standard_normal(m) * _decay(m, 0.0022, 0.0002), 400.0, 1800.0, 2)
    # the half-deck kicked by the release: the hand's and the deck's low modes
    pw = 0.003 * rng.uniform(0.85, 1.15)
    p = _lobe(t, FLICK_LEAD + 0.5 * pw, pw)
    lf = low * rng.uniform(0.88, 1.12)
    th = _modes(np.gradient(p), [(lf, 1.0, low_tau), (lf * rng.uniform(1.6, 2.0), 0.5, low_tau * 0.7)])
    hi = A.lowpass(0.55 * _en(edge) + puff * _en(pf), lp, 2)
    y = click * hi + slap * _en(kn) + body * _en(th)
    return _tail(A.highpass(y, 40.0, 2), 0.4)


def _rustle(n: int, env: np.ndarray, seed: int, lo: float = 3000.0, hi: float = 13000.0,
            grain: float = 0.6) -> np.ndarray:
    """The thumb's skin running over the card edges: grainy, bright friction noise with
    a few fibre clicks, following ``env`` (peak 1). Unit RMS where ``env`` is 1."""
    rng = np.random.default_rng(seed)
    bed = _rms1(A.bandpass(rng.standard_normal(n), lo, hi, 2))
    tooth = _norm(np.abs(A.lowpass(rng.standard_normal(n), 300.0, 1)))
    bed = bed * ((1.0 - grain) + grain * tooth)
    cr = _crackle(n, 1800.0 * env, env, seed + 1, lo, hi, q=2.5, cap=3.0)
    y = 0.75 * _rms1(bed) * env
    if np.any(cr):
        y = y + 0.4 * _rms1(cr) * float(np.sqrt(np.mean(env ** 2)))
    return y


def _gaps(count: int, first: float, last: float, seed: int, jitter: float = 0.2) -> np.ndarray:
    """Release times (from 0) of ``count`` cards whose spacing runs from ``first`` to
    ``last`` seconds (geometrically), each gap a little uneven (``jitter``)."""
    rng = np.random.default_rng(seed)
    g = first * (last / first) ** np.linspace(0.0, 1.0, count - 1)
    g *= rng.uniform(1.0 - jitter, 1.0 + jitter, count - 1)
    return np.concatenate([[0.0], np.cumsum(g)])


def _riffle(count: int, first: float, last: float, seed: int,
            click_db=((0, -23), (0.15, -14.5), (0.65, -12.5), (0.88, -5.5), (1, -9.5)),
            body_db=((0, -12), (0.6, -8), (0.88, -3), (1, -3.5)), accent: float = 12.0, far_lp: float = 7000.0,
            slip: float = 0.3, rustle: float = 0.45, pair: float = 0.12, soft: float = 0.15, slap: float = 0.7,
            purr: float = 0.8, ring=(5100.0, 4100.0), low=(115.0, 135.0), low_tau=(0.012, 0.022),
            jitter: float = 0.25, choke: float = 0.012, tail: float = 0.06) -> Tuple[np.ndarray, float]:
    """The riffle proper: ``count`` cards flicking free from ``first`` to ``last`` seconds
    apart (the thumbs speed up as the halves empty), their ticks following ``click_db`` and
    the thrum ``body_db`` (dB along the riffle, 0..1; a steady hand: no tick more than half a
    decibel above the crescendo's top), each gap uneven by up to ``jitter``. The cards come
    off the two halves by turns, each half with its own tick pitch (``ring``): the near half,
    whose edges face the listener, is heard plainly; the far half's ticks are ``accent`` dB
    softer and duller (above ``far_lp`` the deck shadows them) and its thrum muffled too. The
    turns are uneven: after each card the same half lets the next one go too with odds
    ``slip``, so the near half's flicks come now spread out, now bunched, as in a real riffle,
    and never in a steady beat. A card let go softly also lands softly: its slap on the card
    below follows its tick (``slap`` of it). Now and then two cards let go together (``pair``)
    or a card slides off softly instead of snapping (``soft``). The held packet's low mode
    rises from ``low[0]`` to ``low[1]`` and rings longer as the thumbs press harder
    (``low_tau``); under it all run the deck's purr (``purr``) and the thumbs' rustle
    (``rustle``). ``choke`` seconds after the last card the hands close on the deck and damp
    its thrum. Returns the sound and its last release."""
    rng = np.random.default_rng(seed)
    times = _gaps(count, first, last, seed + 1, jitter)
    u = np.linspace(0.0, 1.0, count)
    cg = _curve(u, click_db)
    bg = _curve(u, body_db)
    top = float(np.max(cg)) + 0.5
    half = np.zeros(count, dtype=int)
    for i in range(1, count):
        half[i] = half[i - 1] if rng.random() < slip else 1 - half[i - 1]
    end = float(times[-1]) + tail
    parts, bds = [], []
    for i, t0 in enumerate(times):
        far = bool(half[i])
        kw = dict(ring=ring[half[i]], low=low[0] + (low[1] - low[0]) * u[i],
                  low_tau=low_tau[0] + (low_tau[1] - low_tau[0]) * u[i], lp=far_lp if far else 14000.0)
        quiet = rng.random() < soft and 0 < i < count - 1
        ck = _db(min(cg[i] + rng.uniform(-2.5, 2.5), top) - (accent if far else 0.0)
                 - (rng.uniform(4.0, 8.0) if quiet else 0.0))
        bd = _db(bg[i] + rng.uniform(-2.0, 2.0) - (0.8 * accent if far else 0.0) - (3.0 if quiet else 0.0))
        bds.append(bd)
        parts.append((_flick(seed * 100 + i, click=ck, body=bd, slap=slap * ck, **kw), float(t0), 1.0))
        if rng.random() < pair:
            c2 = ck * rng.uniform(0.4, 0.7)
            parts.append((_flick(seed * 100 + 60 + i, click=c2, body=bd * 0.3, slap=slap * c2, **kw),
                          float(t0 + rng.uniform(0.002, 0.005)), 1.0))
    x = _place(parts, end)
    n = len(x)
    if purr:
        # the deck's purr: the bent halves never stop moving while the cards stream off
        # them, so under the cards' separate thrums runs a low rumble that swells softly
        # with each card (as much as its thrum) and dies with the last
        swell = np.zeros(n)
        for i, t0 in enumerate(times):
            k0 = _n(float(t0) + FLICK_LEAD)
            swell[k0:] += bds[i] * _decay(n - k0, 0.02, 0.008)
        rum = _rms1(A.bandpass(np.random.default_rng(seed + 9).standard_normal(n), 50.0, 200.0, 2))
        lf = float(np.sqrt(np.mean(A.lowpass(x, 300.0, 2) ** 2)))
        x = x + purr * lf * rum * swell / (float(np.sqrt(np.mean(swell ** 2))) or 1.0)
    env = np.clip(_curve(np.linspace(0.0, 1.0, n), [(0, 0.0), (0.04, 0.5), (0.8, 1.0), (0.95, 0.6), (1, 0.0)]), 0, 1)
    ref = float(np.sqrt(np.mean(np.concatenate([p[0] for p in parts]) ** 2)))
    x = x + rustle * ref * _rustle(n, env, seed + 7)
    k = _n(float(times[-1]) + FLICK_LEAD + choke)
    if k < n:
        x[k:] *= np.exp(-_t(n - k) / 0.005)
    return x, float(times[-1]) + FLICK_LEAD


def _bend(seed: int, strays: Sequence[float] = (0.006, 0.05, 0.1), dur: float = 0.13, level_db: float = -20.0,
          ring: float = 5200.0) -> np.ndarray:
    """The thumbs lifting the deck's corners: a dry creak (low crackle) and a hush of card
    stock rubbing, with a stray card or two slipping early (faint flicks at ``strays``)."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    env = _curve(np.linspace(0.0, 1.0, n), [(0, 0.0), (0.15, 0.7), (0.6, 1.0), (1, 0.3)])
    creak = _crackle(n, 600.0 * env, env, seed + 1, 900.0, 4000.0, q=4.0, cap=3.0)
    hush = _rustle(n, env, seed + 2, 1800.0, 9000.0)
    bed = 0.5 * _rms1(hush) * env + (0.6 * _rms1(creak) if np.any(creak) else 0.0)
    parts = [(_flick(seed * 10 + k, ring=ring * rng.uniform(0.9, 1.1), click=1.0, body=0.35, slap=0.2), at,
              rng.uniform(0.6, 1.0)) for k, at in enumerate(strays)]
    fl = _place(parts, dur)
    bed = np.concatenate([bed / (float(np.max(np.abs(bed))) or 1.0), np.zeros(len(fl) - n)])
    return _db(level_db) * (fl / (float(np.max(np.abs(fl))) or 1.0) + 0.12 * bed)


SQUARE_LEAD = 0.03   # a _square's main contact falls this many seconds into its buffer


def _square(seed: int, ring: float = 4300.0, width: float = 0.00018, spread: float = 0.0035, snap: float = 1.0,
            puff: float = 0.75, knock: float = 0.22, knock_f: float = 950.0, thump: float = 1.0, low: float = 100.0,
            low_tau: float = 0.006, pre: float = 0.22, gap: float = 0.015, rush: float = 0.25, settle: float = 0.05,
            lp: float = 0.0, dur: float = 0.2) -> np.ndarray:
    """The interleaved halves pushed together and squared, the main contact ``SQUARE_LEAD``
    seconds into the buffer: the cards' faces rushing over each other (``rush``), a first
    edge meeting the palm ``gap`` seconds early (``pre``, against the main contact), then
    the whole packet: its cards' edges meet the palm not all at once but in a dense
    cluster of small contacts over ``spread`` seconds (each about ``width`` long), ringing
    the thick packet's modes near ``ring`` with a puff of fibres (``snap``, ``puff``); the
    packet's body knocks dully a few milliseconds later (``knock``, near ``knock_f``) and
    the push sets the hand's and the table's low modes thumping (``thump``, near ``low``);
    then a faint rattle as the cards settle (``settle``). ``lp`` muffles it all (a packet
    set down on cloth rather than snapped against the palm)."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    t = _t(n)
    c = _n(SQUARE_LEAD)
    m = n - c
    # the packet's edges: a cluster of contacts, the biggest at the main contact
    w = max(2, _n(width))
    exc = np.zeros(n)
    hits = int(rng.integers(9, 14))
    offs = np.concatenate([[0], (rng.beta(1.6, 2.4, hits - 1) - 0.35) * _n(spread)]).astype(int)
    amps = np.concatenate([[1.0], rng.uniform(0.2, 0.7, hits - 1)]) * rng.choice([-1.0, 1.0], hits)
    for o, a in zip(offs, amps):
        exc[c + o:c + o + w] += a * np.sin(np.pi * np.arange(w) / w)
    exc[c:] += 0.25 * rng.standard_normal(m) * _decay(m, 0.0008, 0.00003)
    f = ring * rng.uniform(0.95, 1.05)
    edge = _modes(exc, [(f, 1.0, 0.0015), (f * 1.45, 0.8, 0.001), (f * 2.1, 0.5, 0.0007), (f * 2.9, 0.3, 0.0005)])
    env = np.zeros(n)
    env[c - _n(0.4 * spread):] = _decay(m + _n(0.4 * spread), 0.0024, 0.0008)
    hs = A.bandpass(rng.standard_normal(n), 2200.0, 9000.0, 2) * env
    cr = _crackle(n, 8000.0 * env, env, seed + 1, 2000.0, 10000.0, q=3.0, cap=3.0)
    pf = _en(hs) + (0.6 * _en(cr) if np.any(cr) else 0.0)
    # the packet's body: a dull knock just after
    kp = _lobe(t, SQUARE_LEAD + 0.0035, 0.0006)
    kn = _modes(np.gradient(kp), [(knock_f * rng.uniform(0.95, 1.05), 1.0, 0.0025), (knock_f * 1.6, 0.2, 0.0015)])
    # the push: the hand's and the table's low modes
    pw = 0.005 * rng.uniform(0.9, 1.1)
    p = _lobe(t, SQUARE_LEAD + 0.3 * pw, pw)
    th = _modes(np.gradient(p), [(low, 1.0, low_tau), (low * 2.2, 0.7, low_tau * 0.6), (low * 3.7, 0.2, 0.003)])
    main = snap * (0.8 * _en(edge) + puff * _en(pf)) + knock * _en(kn) + thump * _en(th)
    # the first edge, a little early
    first = _flick(seed + 2, ring=ring * 1.3, click=1.0, body=0.4, slap=0.4, dur=0.03)
    # the faces rushing together, cut off by the contact
    k = _n(gap + 0.012)
    r = A.bandpass(rng.standard_normal(k), 2500.0, 9000.0, 2) * np.linspace(0.0, 1.0, k) ** 2
    r[-_n(0.0015):] *= np.linspace(1.0, 0.0, _n(0.0015))
    # the settling rattle
    s_len = n - c - _n(0.012)
    s_env = _decay(s_len, 0.018, 0.004)
    rattle = _crackle(s_len, 2500.0 * s_env, s_env, seed + 3, 2200.0, 8000.0, q=2.5, cap=3.0)
    hush = A.bandpass(rng.standard_normal(s_len), 2000.0, 7000.0, 2) * s_env
    st = (_en(rattle) if np.any(rattle) else 0.0) + 0.7 * _en(hush)
    pk = float(np.max(np.abs(main))) or 1.0
    y = _place([(main, 0.0, 1.0),
                (_norm(first), SQUARE_LEAD - gap - FLICK_LEAD, pre * pk),
                (_norm(r), SQUARE_LEAD - gap - 0.012 + 0.002, rush * pre * pk),
                (_norm(st), SQUARE_LEAD + 0.012, settle * pk)], dur)
    if lp:
        y = A.lowpass(y, lp, 2)
    return _tail(A.highpass(y, 40.0, 2), 0.25)


def _cascade(dur: float, count: int, seed: int, first: float = 0.003, last: float = 0.011,
             lo: float = 500.0, hi: float = 3800.0, body: float = 0.6, flutter: float = 0.08,
             lp: float = 5500.0) -> np.ndarray:
    """The bridge: the deck bowed up between the hands and let go, the cards falling flat
    onto each other in a fast, soft purr (``count`` soft pats, ``first`` to ``last``
    seconds apart as the deck slows and closes), each a short puff of card face on card
    face (``lo``..``hi``) with a little low patter (``body``), over the flutter of the
    bent cards (``flutter``): it swells as the top cards peel off, then fades as the last
    ones settle. Faces landing on faces have no edge's crackle, so it is all below ``lp``."""
    rng = np.random.default_rng(seed)
    times = _gaps(count, first, last, seed + 1, 0.35)
    times = times * (dur - 0.03) / times[-1]
    u = np.linspace(0.0, 1.0, count)
    amps = _curve(u, [(0, 0.3), (0.25, 1.0), (0.65, 0.7), (1, 0.3)]) * rng.uniform(0.6, 1.0, count)
    parts = []
    for i, t0 in enumerate(times):
        m = _n(0.025)
        pat = A.bandpass(rng.standard_normal(m), lo * rng.uniform(0.85, 1.15), hi, 2)
        pat = pat * _decay(m, rng.uniform(0.0012, 0.0025), 0.0002)
        tk = _flick(seed * 100 + i, ring=3200.0 * rng.uniform(0.85, 1.15), click=0.3, body=body, slap=0.8,
                    low=150.0, low_tau=0.006, width=0.00025, dur=0.025)
        parts.append((_norm(_en(pat) + 0.7 * _en(tk)), float(t0), float(amps[i])))
    x = _place(parts, dur)
    n = len(x)
    env = np.clip(_curve(np.linspace(0.0, 1.0, n), [(0, 0.0), (0.25, 1.0), (0.6, 0.7), (1, 0.0)]), 0, 1)
    fl = _rustle(n, env, seed + 7, 1500.0, 6000.0, grain=0.8)
    x = x + flutter * float(np.max(np.abs(x))) * fl / (float(np.max(np.abs(fl))) or 1.0)
    return A.lowpass(x, lp, 2)


# ----------------------------------------------------------------------------- the candidates
def shuf_ref_riffle():
    # the reference at about three quarters of its speed (0.91 s against 0.72): the thumbs
    # bend the deck (a stray card or two slipping), 21 cards flick free 34 ms apart easing
    # to 23 (the reference: about 17), the flicks one hears spread out at first and
    # bunching up as it builds (20 to 120 ms apart), with a swelling thrum; the hands
    # close on the deck, and the squaring snap is the brightest moment, as in the
    # reference
    t_rif = 0.19
    bend = _bend(4100, strays=(0.008, 0.06, 0.12), dur=0.15)
    rif, last = _riffle(21, 0.034, 0.023, 4214)
    snap_at = t_rif + last + 0.08
    sq = _square(4130)
    x = _place([(bend, 0.0, _over(bend, rif, -18.0)), (rif, t_rif, 1.0),
                (sq, snap_at - SQUARE_LEAD, _over(sq, rif, 1.0))], snap_at + 0.17)
    return _finish(_room(x), 19.5)


def shuf_ref_gentle():
    # slower still (20 cards 44 ms apart easing to 33, under half the reference's pace;
    # the flicks one hears 30 to 125 ms apart, unevenly; 1.1 s in all), a gentler, darker
    # crescendo, and a soft finish: the halves are pressed together slowly, their faces
    # whispering in, and the packet comes to rest on the felt with a muffled pat (a wide
    # contact ringing the packet low, more thump than click), softer than the riffle's
    # loudest flicks
    t_rif = 0.21
    # (the first stray card slips a little later than in the riffle, so the sound opens on
    # the faint rustle of the bend rather than on a tick)
    bend = _bend(5100, strays=(0.02, 0.075, 0.14), dur=0.17, ring=4600.0)
    rif, last = _riffle(20, 0.044, 0.033, 5303, ring=(4900.0, 3900.0), soft=0.2,
                        click_db=((0, -21), (0.15, -13.5), (0.65, -12), (0.88, -6.5), (1, -10)))
    snap_at = t_rif + last + 0.1
    sq = _square(5130, ring=3000.0, width=0.0004, spread=0.006, snap=0.6, puff=0.4, knock=0.3, knock_f=800.0,
                 thump=0.6, low=95.0, low_tau=0.009, pre=0.15, gap=0.026, rush=0.4, settle=0.04, lp=4500.0)
    x = _place([(bend, 0.0, _over(bend, rif, -18.0)), (rif, t_rif, 1.0),
                (sq, snap_at - SQUARE_LEAD, _over(sq, rif, -1.0, hp=0.0))], snap_at + 0.17)
    return _finish(_room(x, 0.24), 19.5, lp=12000)


def shuf_ref_bridge():
    # a shorter riffle at about three quarters of the reference's pace (16 cards 33 ms
    # apart easing to 24, the far half a little softer still), then the bridge: the hands
    # choke the deck, bow it up (a faint creak) and let it go, the cards cascading back
    # together in a quick purr that slows as the deck closes, and the squaring snap last,
    # the brightest moment, as in the reference
    t_rif = 0.13
    bend = _bend(6100, strays=(0.008, 0.07), dur=0.11)
    rif, last = _riffle(16, 0.033, 0.024, 6341, click_db=((0, -23), (0.15, -15), (0.65, -13), (0.88, -7), (1, -10.5)),
                        accent=14.0)
    bow_at = t_rif + last + 0.05
    bow = _bend(6120, strays=(), dur=0.06, ring=3000.0)
    cas_at = bow_at + 0.055
    cas = _cascade(0.24, 40, 6130)
    snap_at = cas_at + 0.24 + 0.06
    sq = _square(6140, gap=0.012, pre=0.18)
    x = _place([(bend, 0.0, _over(bend, rif, -18.0)), (rif, t_rif, 1.0), (bow, bow_at, _over(bow, rif, -24.0)),
                (cas, cas_at, _over(cas, rif, -8.0, hp=0.0)), (sq, snap_at - SQUARE_LEAD, _over(sq, rif, 1.0))],
               snap_at + 0.17)
    return _finish(_room(x), 19.5)


# ============================================================================= the list
C = Candidate
CANDIDATES = [
    C("shuffle", "ref_riffle", "Slower riffle",
      "A slower riffle: cards flicking free over a soft thrum, building up, then the deck snapped square.",
      shuf_ref_riffle, ["acoustic", "modelled"]),
    C("shuffle", "ref_gentle", "Gentle riffle",
      "Slower still and gentler, ending with the deck pressed softly together instead of a snap.",
      shuf_ref_gentle, ["acoustic", "modelled", "soft"]),
    C("shuffle", "ref_bridge", "Riffle and bridge",
      "A slower riffle, then the bridge: the cards cascade back together in a soft purr, then the snap.",
      shuf_ref_bridge, ["acoustic", "modelled"]),
]
