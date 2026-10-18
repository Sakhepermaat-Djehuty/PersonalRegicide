"""Draw cards, modelled on the owner's reference: Pythonista's 'casino:CardShuffle'.

The owner liked CardShuffle for drawing cards ("similar, less shuffle more drawing
individual cards. i like the sound"). Despite its name the reference is seven separate
deals: each a short rising swish of a card sliding off the deck, ending in a soft snap as
it lands. These candidates are built from scratch, in code, from what happens when a
card is drawn; no part of the reference recording is used, read or copied (it was only
measured, offline, to set the timings, levels and bands below).

What one drawn card is made of, and what models each part here:
  push     the thumb pressing on the top card and setting it moving: a slow, soft
           pressure bump that the deck and the hand answer with a low "whump", and a faint
           tick of skin on card (``_push``); some cards are pushed off firmly, some barely
  slide    the card's face sliding off the deck over the next card's back, speeding up:
           friction noise that grows louder and brighter with speed (most of it above
           2.5 kHz, as in the reference), roughened by the grain of the card stock, by the
           fibres it catches (tiny clicks) and by the hand's unevenness; under it, while
           the thumb still presses the card onto the deck, the deck and the hand flexing
           (a low drag rumble that fades as the card gets going); and when the card's
           edge touches down it does not stop dead but skids on over the hand for a few
           milliseconds, pressed harder for an instant (``_slide``)
  land     the card arriving on the cards already in the hand: its edge's contact snap
           ringing the card's bending modes for a millisecond or two, the stack's dull
           knock (most of it between 120 and 500 Hz), a spit of crushed fibres, and, as
           the face comes down flat a few milliseconds later, the air pushed out from
           under it setting the hand's and the table's low modes going: a small thump,
           damped within a cycle or two (``_land``)
  settle   the card's last faint flutter as it lies down (``_settle``)
  room     the faint early reflections of the room around the table, with no long tail
           to fill the silence between cards (``_room``)

Measured against the reference, a deal's swish keeps about a tenth of its energy below
150 Hz (the drag) and its landing about two fifths (the thump) with nearly as much again
above 2.5 kHz (the snap and the skid): the landing is a snap with a little weight under it, not
a thud. Where the reference deals one card every 0.43 s, these draw them one after
another, two to four in under a second, each card a little different (its speed, its
brightness, how firmly it is pushed and how it lands), and with no riffle. Everything is
driven by seeded noise, so each candidate is rebuilt identically. Layers are mixed by
their share of the energy (``_en``), except each landing, mixed by its peak (how hard
the card comes down).

The reference's firmest landings stand 25 to 31 dB above its loudness; mastered to the
draw's loudness, a sound may peak only 20 dB above it. So the landings here sit a little
lower against the slides (as the reference's middle deals do, 13 to 17 dB over the swish
before them), the first half-millisecond of each contact is rounded off, and the silence
between cards is kept clean (no long reverb tail) so it does not count against them.
"""
from __future__ import annotations

import math
from typing import Sequence, Tuple

import numpy as np
from scipy import signal

import synth as A
from catalog import EVENT_BY_ID, Candidate

SR = A.SR
EVENT = EVENT_BY_ID["draw"]


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


def _wobble(n: int, rate: float, seed: int) -> np.ndarray:
    """Slow random unevenness (about ``rate`` changes a second), zero mean, unit peak."""
    rng = np.random.default_rng(seed)
    m = int(n / SR * rate) + 4
    y = np.interp(_t(n) * rate, np.arange(m), rng.standard_normal(m))
    y -= np.mean(y)
    return _norm(y)


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
        w = 2 * math.pi * f / SR
        y += g * _norm(signal.lfilter([1.0], [1.0, -2 * r * math.cos(w), r * r], exc))
    return y


def _bands(n: int, seed: int, shares) -> np.ndarray:
    """Noise with its energy split between bands: [(lo, hi, share), ...], unit RMS."""
    rng = np.random.default_rng(seed)
    y = np.zeros(n)
    for lo, hi, s in shares:
        y += math.sqrt(s) * _rms1(A.bandpass(rng.standard_normal(n), lo, hi, 2))
    return _rms1(y)


def _crackle(n: int, rate: np.ndarray, amp: np.ndarray, seed: int, lo: float, hi: float, k: int = 6,
             q: float = 3.0, alpha: float = 2.0, cap: float = 5.0) -> np.ndarray:
    """Paper fibres: sparse clicks at ``rate`` per second (per sample array), each with a
    heavy-tailed strength scaled by ``amp``, ringing one of ``k`` small patches of card
    (short resonances spread from ``lo`` to ``hi``)."""
    rng = np.random.default_rng(seed)
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


def _lobe(t: np.ndarray, at: float, w: float) -> np.ndarray:
    """A raised-cosine bump ``w`` wide centred on ``at``."""
    x = (t - at) / w
    return np.where(np.abs(x) < 0.5, 0.5 + 0.5 * np.cos(2 * np.pi * x), 0.0)


def _round_top(x: np.ndarray, shave_db: float) -> np.ndarray:
    """Round off the first fraction of a millisecond of a sharp contact, ``shave_db`` off its
    peak (a fast look-ahead limiter with a 3 ms release, so what rings on is untouched):
    a card landing on cards is a soft event, and its needle carries almost no energy."""
    if shave_db <= 0:
        return x
    thr = float(np.max(np.abs(x))) * 10 ** (-shave_db / 20.0)
    return A.limit(x / thr, 0.0, lookahead=0.0005, release=0.003) * thr


def _gentle(x: np.ndarray, crest_db: float) -> np.ndarray:
    """Keep the peak at most ``crest_db`` above the build's loudness measure by shaving
    only the tops of the sharpest snaps (a fast look-ahead limiter), so mastering's
    slower limiter leaves the slides' level alone."""
    for _ in range(3):
        ceil = A._rms_db(x) + crest_db
        if 20 * math.log10(float(np.max(np.abs(x))) + 1e-12) <= ceil + 0.05:
            break
        g = 10 ** (ceil / 20.0)
        x = A.limit(x / g, 0.0, lookahead=0.0008, release=0.012) * g
    return x


def _room(x: np.ndarray, wet: float = 0.15, seed: int = 7, lo: float = 300.0, hi: float = 5000.0) -> np.ndarray:
    """The faint early reflections of a small room around the table: a few delayed,
    band-limited copies (timber and cloth soak up the boom and the hiss) from the
    tabletop's edge, the nearby walls and the ceiling, 3 to 23 ms late and fading, with no
    long tail to fill the silence between cards. ``wet`` is the first reflection's level."""
    rng = np.random.default_rng(seed)
    band = A.bandpass(x, lo, hi, 2)
    delays = np.array([3.1, 5.4, 8.2, 11.7, 16.3, 22.8]) * rng.uniform(0.93, 1.07, 6) / 1000.0
    out = np.concatenate([x, np.zeros(_n(0.03))])
    for k, d in enumerate(delays):
        g = wet * 0.72 ** k * rng.choice([-1.0, 1.0])
        out = A.mix_at(out, A.lowpass(band, hi * 0.85 ** k, 1), float(d), g)
    return out


def _finish(x: np.ndarray, crest_db: float, hp: float = 32.0, lp: float = 0.0, fade: float = 0.2) -> np.ndarray:
    """Take out the sub-bass and DC (and, with ``lp``, roll the very top off gently), keep
    the sound inside the event's length, let the end fade smoothly and keep the snaps'
    peaks gentle."""
    y = A.highpass(x, hp, 2)
    if lp:
        y = A.lowpass(y, lp, 1)
    y = y[:_n(EVENT.max_seconds - 0.03)]
    return _gentle(_tail(y, fade), crest_db)


# ----------------------------------------------------------------------------- the physical parts
def _push(seed: int, width: float = 0.016, low=(55.0, 120.0), tick: float = 0.25, dur: float = 0.06) -> np.ndarray:
    """The thumb pressing the top card and starting it off the deck: a slow pressure bump
    ``width`` long (a press, then a smaller release) that the deck and hand answer with
    their low, heavily damped modes (``low``), and a faint tick of skin on card stock."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    t = _t(n)
    w = width * rng.uniform(0.85, 1.15)
    p = _lobe(t, 0.6 * w, w) - 0.45 * _lobe(t, 1.35 * w, 0.9 * w)
    ring = _modes(np.gradient(p), [(low[0] * rng.uniform(0.9, 1.1), 1.0, 0.006),
                                    (low[1] * rng.uniform(0.9, 1.1), 0.5, 0.004)])
    m = _n(0.01)
    tk = A.bandpass(rng.standard_normal(m), 1500.0, 6000.0, 2) * _decay(m, 0.0012, 0.0004)
    y = 0.7 * _en(p) + 0.5 * _en(ring)
    return _tail(_place([(y, 0.0, 1.0), (_en(tk), 0.2 * w, tick)], dur), 0.4)


# the drag's energy per band, from the reference's swishes (below 150 Hz, 150-400, 400 Hz-1 kHz)
DRAG_BANDS = ((40.0, 150.0, 0.62), (150.0, 400.0, 0.28), (400.0, 1000.0, 0.10))


def _slide(dur: float, seed: int, curve: float = 1.3, start: float = 0.05, lo: float = 1100.0,
           mid: float = 3800.0, hi: float = 17000.0, bright: float = 0.85, grain: float = 0.55,
           crisp: float = 0.25, wob: float = 0.3, drag: float = 0.08, skid: float = 0.006,
           press: float = 2.0) -> np.ndarray:
    """The card's face sliding off the deck over the next card, speeding up over ``dur``
    seconds (from ``start`` of full speed, rising as a power ``curve``). Friction noise
    louder and brighter the faster it goes: a duller rub (``lo``..``mid``) giving way to a
    bright hiss (``mid``..``hi``; ``bright`` how far), grainy with the card stock's tooth
    (``grain``), with fibre clicks (``crisp`` their share) and the hand's unevenness
    (``wob``). Under it, ``drag`` (its share of the energy): the deck and the hand flexing
    while the thumb still presses the card down, a low uneven rumble that swells with the
    push and fades as the card gets going. Where the card touches down (``dur``) the
    friction does not stop dead: the card skids on over the hand, pressed ``press`` times
    harder for an instant, and stops within a few ``skid`` time constants. Stray peaks are
    rounded off, so only the landing snaps."""
    n = _n(dur)
    m = _n(6 * skid)
    rng = np.random.default_rng(seed)
    u = np.linspace(0.0, 1.0, n)
    sp = start + (1.0 - start) * u ** curve
    # after the touch-down: the speed falls away as the card skids to a stop
    ts = _t(m)
    sk = np.exp(-ts / skid)
    sp_all = np.concatenate([sp, sk])
    b = np.clip(bright * (0.35 + 0.65 * sp_all), 0.0, 1.0)
    dull = _rms1(A.bandpass(rng.standard_normal(n + m), lo, mid, 2))
    hiss = _rms1(A.bandpass(rng.standard_normal(n + m), mid, hi, 2))
    bed = np.sqrt(1.0 - b) * dull + np.sqrt(b) * hiss
    tooth = _norm(np.abs(A.lowpass(rng.standard_normal(n + m), 420.0, 1)))
    bed *= (1.0 - grain) + grain * tooth
    hand = np.clip(1.0 + wob * _wobble(n + m, 45.0, seed + 1), 0.25, None)
    k = min(m, max(2, _n(0.0008)))
    bump = np.ones(m)
    bump[:k] = 1.0 + (press - 1.0) * np.sin(0.5 * np.pi * np.arange(k) / k)
    bump[k:] = press
    env = np.concatenate([sp ** 1.3, sk * bump]) * hand
    cr = _crackle(n + m, 3500.0 * sp_all, env, seed + 2, max(lo, 1800.0), min(hi, 11000.0), q=2.6, alpha=2.6,
                  cap=3.0)
    fr = (1.0 - crisp) * _rms1(bed * env) + crisp * _rms1(cr) if np.any(cr) else _rms1(bed * env)
    fr = np.tanh(_rms1(fr) / 4.0) * 4.0     # friction has no needles: round off stray peaks
    k = max(2, int(0.25 * n))             # it starts from nothing: the thumb only just moves it
    fr[:k] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(k) / k)
    # the drag: the deck and the hand under the thumb, strongest early in the push
    pr = np.concatenate([(1.0 - np.exp(-u / 0.12)) * (1.0 - 0.75 * u ** 1.5), np.zeros(m)])
    stick = np.clip(1.0 + 0.5 * _wobble(n + m, 60.0, seed + 3), 0.2, None)
    rumble = _bands(n + m, seed + 4, DRAG_BANDS) * pr * stick
    y = math.sqrt(1.0 - drag) * _en(fr) + math.sqrt(drag) * _en(rumble)
    y[-_n(0.002):] *= np.linspace(1.0, 0.0, _n(0.002))
    return y


LAND_LEAD = 0.006   # a _land piece's contact falls this many seconds into its buffer
LAND_PEAK = 0.85    # a landing's peak, against its card's other parts at unit energy


def _land(seed: int, flat: float = 0.5, ring: float = 2000.0, ring_tau: float = 0.0016, width: float = 0.0002,
          snap: float = 0.5, knock: float = 0.42, knock_lo: float = 120.0, knock_hi: float = 480.0,
          knock_tau: float = 0.004, spit: float = 0.5, spit_lo: float = 2500.0, spit_hi: float = 13000.0,
          aw: float = 0.0034, low: float = 62.0, low_tau: float = 0.0055, thump: float = 0.55, pre: float = 0.4,
          face: float = 0.003, round_db: float = 5.5, dur: float = 0.07) -> np.ndarray:
    """The card arriving on the cards in the hand, its contact ``LAND_LEAD`` seconds into
    the buffer: the edge's contact pulse ``width`` long (shorter is harder) rings the
    card's bending modes near ``ring`` (``snap`` their share); the stack it lands on gives
    a dull knock (noise struck once, ``knock_lo``..``knock_hi``); a spit of crushed fibres
    and hiss (``spit``); and ``face`` seconds after the edge, as the face comes down flat,
    the air squeezed out from under it (a small push, then a quicker opposite swing ``aw``
    wide, ``pre`` the push's size) sets the hand's and the table's low modes going, the
    lowest near ``low`` Hz, all damped within a cycle or two (``low_tau``): the small thump
    (``thump`` its share). ``flat`` (0..1) is how flat the card comes down: edge first
    (0) it snaps and spits and barely thumps; flat (1) it thumps and its edge hardly
    snaps. The contact's needle is rounded off by ``round_db``."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    t = _t(n)
    c = _n(LAND_LEAD)
    m = n - c
    # the snap: the card's own bending modes
    w = max(2, _n(width))
    exc = np.zeros(n)
    exc[c:c + w] = np.sin(np.pi * np.arange(w) / w)
    exc[c:] += 0.25 * rng.standard_normal(m) * _decay(m, width * 2.0, 0.00005)
    f1 = ring * rng.uniform(0.95, 1.05)
    body = _modes(exc, [(f1, 1.0, ring_tau), (f1 * rng.uniform(1.4, 1.6), 0.5, ring_tau * 0.8),
                        (f1 * rng.uniform(2.5, 2.8), 0.3, ring_tau * 0.5),
                        (f1 * rng.uniform(0.3, 0.36), 0.2, ring_tau * 1.6)])
    # the stack's dull knock
    kn = np.zeros(n)
    kn[c:] = A.bandpass(rng.standard_normal(m) * _decay(m, knock_tau, 0.0003), knock_lo, knock_hi, 2)
    # the spit of crushed fibres
    env = np.zeros(n)
    env[c:] = _decay(m, 0.0016, 0.0002)
    cr = _crackle(n, 9000.0 * env, env, seed + 3, spit_lo, spit_hi, q=3.0, cap=3.0)
    hs = np.zeros(n)
    hs[c:] = A.bandpass(rng.standard_normal(m), spit_lo, spit_hi, 2) * _decay(m, 0.0016, 0.0002)
    # the air and the small, quickly damped thump
    aw_ = aw * rng.uniform(0.92, 1.08)
    tc = LAND_LEAD + face
    p = pre * _lobe(t, tc - 0.95 * aw_, 1.6 * aw_) - _lobe(t, tc, aw_) + 0.08 * _lobe(t, tc + 1.4 * aw_, 2.0 * aw_)
    p *= 1.0 + 0.15 * _norm(A.lowpass(rng.standard_normal(n), 800.0, 1))
    f0 = low * rng.uniform(0.85, 1.15)
    lowm = _modes(np.gradient(p), [(f0, 1.0, low_tau), (f0 * rng.uniform(2.1, 2.5), 0.4, low_tau * 0.7),
                                   (f0 * rng.uniform(4.6, 5.4), 0.3, low_tau * 0.4)])
    edge = 1.6 - 1.2 * flat           # 1.6 edge first .. 0.4 flat
    face_ = 0.3 + 1.4 * flat          # 0.3 edge first .. 1.7 flat
    y = (edge * (snap * _en(body) + spit * (0.6 * _en(cr) + 0.6 * _en(hs))) + knock * _en(kn)
         + face_ * thump * (0.45 * _en(p) + 0.9 * _en(lowm)))
    return _tail(_round_top(A.highpass(y, 40.0, 2), round_db), 0.35)


def _settle(seed: int, dur: float = 0.07, lo: float = 2200.0, hi: float = 11000.0, tau: float = 0.016,
            hush: float = 1.0) -> np.ndarray:
    """The card's last faint flutter as it lies down: a hush and many small, even, dying
    clicks (a settling sheet's clicks are alike, so their strengths are capped low)."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    env = _decay(n, tau, 0.003) * np.clip(1.0 + 0.6 * _wobble(n, 120.0, seed + 1), 0.1, None)
    cr = _crackle(n, 3000.0 * env, env, seed + 2, lo, hi, q=2.5, alpha=3.0, cap=2.0)
    hs = A.bandpass(rng.standard_normal(n), lo, hi, 2) * env
    return _tail(_en(cr) + hush * _en(hs), 0.3)


def _card(seed: int, slide: float = 0.12, swish: float = 0.7, land: float = 1.0, flat: float = 0.5,
          push: float = 0.1, settle: float = 0.16, slide_kw=None, land_kw=None) -> Tuple[np.ndarray, float]:
    """One card drawn: the thumb's push, the slide (about ``slide`` seconds) and the landing,
    each card a little different (its speed, its brightness, how firmly the thumb pushes
    it, how hard and how flat it lands, the pitch of its ring and of its thump). The
    landing is mixed by its peak (``land`` sets how hard the card comes down, ``flat`` how
    flat: see ``_land``), the other parts by their energy. Returns the sound and when, in
    it, the card lands."""
    rng = np.random.default_rng(seed)
    sl = slide * rng.uniform(0.88, 1.12)
    skw = dict(curve=rng.uniform(1.1, 1.6), bright=rng.uniform(0.8, 0.95), drag=rng.uniform(0.05, 0.11))
    skw.update(slide_kw or {})
    lkw = dict(land_kw or {})
    lkw["ring"] = lkw.get("ring", 2000.0) * rng.uniform(0.92, 1.08)
    lkw["aw"] = lkw.get("aw", 0.0034) * rng.uniform(0.9, 1.12)
    lkw["flat"] = float(np.clip(flat + rng.uniform(-0.1, 0.1), 0.0, 1.0))
    lg = land * 10 ** (rng.uniform(-0.6, 0.6) / 20.0)
    sg = swish * 10 ** (rng.uniform(-1.0, 1.0) / 20.0)
    pg = push * rng.uniform(0.3, 1.4)
    parts = [(_en(_push(seed + 1)), 0.0, pg),
             (_en(_slide(sl, seed + 2, **skw)), 0.002, sg),
             (_norm(_land(seed + 3, **lkw)), 0.002 + sl - LAND_LEAD, LAND_PEAK * lg),
             (_en(_settle(seed + 4)), 0.002 + sl + 0.003, settle)]
    return _place(parts, sl + 0.08), 0.002 + sl


def _hand(cards, lands: Sequence[float], dur: float) -> np.ndarray:
    """Place each (sound, its landing) so the cards land at ``lands`` seconds."""
    return _place([(snd, at - tl, 1.0) for (snd, tl), at in zip(cards, lands)], dur)


# ----------------------------------------------------------------------------- the candidates
def draw_ref_three():
    # the reference's swish and landing, three cards drawn one after another, about a
    # quarter of a second apart instead of 0.43 s, and not evenly (0.285 s, then 0.25: a
    # hand finding its rhythm, not a metronome): the first a touch firmer and landing edge
    # first (a crisp snap, as the reference's first deals), the second coming down flatter
    # (more thump), the third in between
    cards = [_card(1100, 0.12, swish=0.8, land=0.95, flat=0.15), _card(1120, 0.11, swish=0.8, land=0.76, flat=0.7),
             _card(1140, 0.115, swish=0.8, land=0.8, flat=0.4)]
    x = _hand(cards, (0.13, 0.415, 0.665), 0.8)
    return _finish(_room(x), 19.8)


def draw_ref_two_soft():
    # two cards drawn gently: slower, less bright slides and soft pats onto the hand (a
    # wider contact ringing the card lower, little spit, a lighter thump and knock), the
    # very top rolled off a little
    soft_slide = dict(lo=1000.0, mid=3400.0, hi=14000.0, crisp=0.2, grain=0.45, bright=0.75, press=1.3)
    soft_land = dict(ring=1500.0, ring_tau=0.0012, width=0.0004, snap=0.4, spit=0.3, spit_hi=10000.0,
                     aw=0.0042, low=70.0, low_tau=0.005, thump=0.4, knock=0.3, knock_hi=400.0, round_db=8.0)
    cards = [_card(2100, 0.13, swish=0.6, land=0.6, flat=0.4, slide_kw=soft_slide, land_kw=soft_land),
             _card(2120, 0.12, swish=0.6, land=0.54, flat=0.5, slide_kw=soft_slide, land_kw=soft_land)]
    x = _hand(cards, (0.135, 0.45), 0.57)
    return _finish(_room(x, 0.18), 18.5, lp=13000)


def draw_ref_refill():
    # a hand refilled: four quick cards about a fifth of a second apart, a little uneven
    # as a hand is, each slide shorter and each landing a little lighter than a single
    # draw's
    cards = [_card(3100 + 20 * k, 0.085, land=g, flat=f)
             for k, (g, f) in enumerate(((0.9, 0.25), (0.8, 0.6), (0.85, 0.2), (0.8, 0.5)))]
    x = _hand(cards, (0.09, 0.295, 0.48, 0.70), 0.82)
    return _finish(_room(x), 19.8)


# ============================================================================= the list
C = Candidate
CANDIDATES = [
    C("draw", "ref_three", "Three cards",
      "Three cards drawn one by one: a quick rising swish off the deck and a soft snap as each lands.",
      draw_ref_three, ["acoustic", "modelled"]),
    C("draw", "ref_two_soft", "Two soft cards",
      "Two cards drawn gently: a slower, softer slide and a light pat onto the hand.",
      draw_ref_two_soft, ["acoustic", "modelled", "soft"]),
    C("draw", "ref_refill", "Hand refill",
      "Four quick cards drawn into the hand, each with its own little swish and tap.",
      draw_ref_refill, ["acoustic", "modelled"]),
]
