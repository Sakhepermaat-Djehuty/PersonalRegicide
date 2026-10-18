"""Discard cards, modelled on the owner's reference: Pythonista's 'casino:CardTakeOutPackage2'.

The owner picked CardTakeOutPackage2 for discarding as the "best of a bad bunch": what
they wanted was "a sound of a few cards being put in a stack". The reference is one long
scrape of cards drawn out of a cardboard box: smooth, even, papery friction noise, flat
per third of an octave from about 1 to 10 kHz, swelling slowly. These candidates keep
that paper, but use it for what the owner asked for: a few cards laid one on top of
another on the discard pile, on a cloth-covered table. They are built from scratch, in
code; no part of the reference recording is used, read or copied (it was only measured,
offline, to set the paper's band, smoothness and level below).

What one card laid on the pile is made of, and what models each part here:
  slide    the card's face brushing the top of the pile as the hand brings it in and
           eases it into place: the reference's paper (``_paper``: smooth noise, even per
           third of an octave, no needles), louder and brighter the faster it moves,
           with the card stock's faint tooth, a few fibres catching and, as in the
           reference, the moving card's own faint ring between 1 and 2 kHz (``_slide``)
  land     the hand lets go and the card comes down flat: its edge meets the pile (a
           short contact ringing the card's bending modes, and the pile's dull knock),
           then its face lands, pushing the air out from under it (a soft "pff") and
           setting the pile, the cloth and the tabletop going: a low, heavily damped
           thump (``_land``). The taller the pile (``depth``), the more card there is
           under it to soak the knock up and the less far the face falls: each landing
           comes a little duller and its two touches a little closer together
  settle   the card skids a few millimetres on the pile and lies still (``_settle``)
  square   the stack pushed together by the fingers (its edges rubbing, ``_slide``
           with a dull band) and knocked square on the cloth: every card's edge landing
           within a couple of milliseconds over the stack's knock and the table's
           padded thump (``_tap``)
  room     the faint early reflections of the room around the table, with no tail to
           fill the gaps between cards (``_room``)

Each card is a little different (its slide's length, speed and brightness, how hard it
comes down, the pitch of its ring); everything is driven by seeded noise, so each
candidate is rebuilt identically. Layers are mixed by their share of the energy
(``_en``), except the landings and taps, mixed by their peak (how hard they come down).
Where the reference sits almost entirely above 400 Hz with its centroid near 6.5 kHz,
these keep its paper in the slides but put a soft body under each landing (most of it
between 100 Hz and 2.5 kHz), so a sound heard many times a game stays gentle.
"""
from __future__ import annotations

import math
from typing import Sequence, Tuple

import numpy as np
from scipy import signal

import synth as A
from catalog import EVENT_BY_ID, Candidate

SR = A.SR
EVENT = EVENT_BY_ID["discard"]
LEAD = 0.004          # a _land or _tap piece's first contact falls this far into its buffer


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


def _curve(n: int, pts: Sequence[Tuple[float, float]]) -> np.ndarray:
    """A piecewise-linear envelope through (fraction of length, value) points."""
    xs, ys = zip(*pts)
    return np.interp(np.linspace(0.0, 1.0, n), xs, ys)


def _wobble(n: int, rate: float, seed: int) -> np.ndarray:
    """Slow random unevenness (about ``rate`` changes a second), zero mean, unit peak."""
    rng = np.random.default_rng(seed)
    m = int(n / SR * rate) + 4
    y = np.interp(_t(n) * rate, np.arange(m), rng.standard_normal(m))
    y -= np.mean(y)
    return _norm(y)


def _lobe(t: np.ndarray, at: float, w: float) -> np.ndarray:
    """A raised-cosine bump ``w`` wide centred on ``at``."""
    x = (t - at) / w
    return np.where(np.abs(x) < 0.5, 0.5 + 0.5 * np.cos(2 * np.pi * x), 0.0)


def _place(parts, dur: float = 0.0) -> np.ndarray:
    """Mix [(sound, at seconds, gain), ...] into one buffer."""
    buf = np.zeros(max(1, _n(dur)))
    for snd, at, g in parts:
        buf = A.mix_at(buf, snd, max(0.0, at), g)
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
             q: float = 2.8, alpha: float = 2.6, cap: float = 3.0) -> np.ndarray:
    """Paper fibres catching: sparse clicks at ``rate`` per second (a per-sample array),
    each with a heavy-tailed strength (Pareto ``alpha``, capped at ``cap``) scaled by
    ``amp``, ringing one of ``k`` small patches of card (short resonances from ``lo`` to
    ``hi``)."""
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
            y += _reso(imp, centres[g], q)
    return y


def _round_top(x: np.ndarray, shave_db: float) -> np.ndarray:
    """Round off the first fraction of a millisecond of a sharp contact, ``shave_db`` off
    its peak (a fast look-ahead limiter with a 3 ms release, so what rings on is
    untouched): a card landing on cards is a soft event, its needle carries no energy."""
    if shave_db <= 0:
        return x
    thr = float(np.max(np.abs(x))) * 10 ** (-shave_db / 20.0)
    return A.limit(x / thr, 0.0, lookahead=0.0005, release=0.003) * thr


def _gentle(x: np.ndarray, crest_db: float) -> np.ndarray:
    """Keep the peak at most ``crest_db`` above the build's loudness measure by shaving
    only the tops of the sharpest contacts (a fast look-ahead limiter), so mastering's
    slower limiter leaves the slides' level alone."""
    for _ in range(4):
        ceil = A._rms_db(x) + crest_db
        if 20 * math.log10(float(np.max(np.abs(x))) + 1e-12) <= ceil + 0.05:
            break
        g = 10 ** (ceil / 20.0)
        x = A.limit(x / g, 0.0, lookahead=0.0008, release=0.012) * g
    return x


def _room(x: np.ndarray, wet: float = 0.12, seed: int = 5, lo: float = 300.0, hi: float = 4500.0) -> np.ndarray:
    """The faint early reflections of a small room around the table: a few delayed,
    band-limited copies (timber and cloth soak up the boom and the hiss) from the
    tabletop's edge, the nearby walls and the ceiling, 3 to 21 ms late and fading, with no
    tail to fill the gaps between cards. ``wet`` is the first reflection's level."""
    rng = np.random.default_rng(seed)
    band = A.bandpass(x, lo, hi, 2)
    delays = np.array([2.9, 5.1, 7.8, 11.2, 15.6, 21.0]) * rng.uniform(0.93, 1.07, 6) / 1000.0
    out = np.concatenate([x, np.zeros(_n(0.03))])
    for k, d in enumerate(delays):
        g = wet * 0.7 ** k * rng.choice([-1.0, 1.0])
        out = A.mix_at(out, A.lowpass(band, hi * 0.85 ** k, 1), float(d), g)
    return out


def _finish(x: np.ndarray, crest_db: float, hp: float = 40.0, lp: float = 0.0, fade: float = 0.25) -> np.ndarray:
    """Take out the sub-bass and DC (and, with ``lp``, the very top), keep the sound inside
    the event's length, let the end fade smoothly and keep the contacts' peaks gentle."""
    y = A.highpass(x, hp, 2)
    if lp:
        y = A.lowpass(y, lp, 2)
    y = y[:_n(EVENT.max_seconds - 0.03)]
    return _gentle(_tail(y, fade), crest_db)


# ----------------------------------------------------------------------------- the physical parts
def _paper(n: int, seed: int, lo: float = 1000.0, hi: float = 12000.0) -> np.ndarray:
    """The reference's paper: smooth noise (no clicks in it), even per third of an octave
    (pink) from ``lo`` to ``hi``, falling away below ``lo`` (12 dB an octave) and above
    ``hi`` (12 dB an octave). Unit RMS."""
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(n + 2048)
    pink = signal.lfilter([0.049922035, -0.095993537, 0.050612699, -0.004408786],
                          [1.0, -2.494956002, 2.017265875, -0.522189400], w)[2048:]
    return _rms1(A.lowpass(A.highpass(pink, lo, 2), hi, 2))


def _slide(dur: float, seed: int, speed: Sequence[Tuple[float, float]], bright: float = 0.9, lo: float = 1000.0,
           hi: float = 12000.0, dull: float = 3800.0, tooth: float = 0.25, crisp: float = 0.15, ring: float = 0.15,
           ring_f: float = 1500.0, wob: float = 0.3) -> np.ndarray:
    """Card stock brushing card stock for ``dur`` seconds, at ``speed`` (0..1, points over
    its length). The faster it moves, the louder it is and the further up its band reaches:
    a duller paper (up to ``dull``) gives way to the full paper (up to ``hi``; ``bright``
    how far). Roughened a little by the stock's ``tooth``, a few fibres catching (``crisp``
    their share), the moving card's own faint ring near ``ring_f`` and the hand's
    unevenness (``wob``). Its stray peaks are rounded off: friction has no needles."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    sp = np.clip(_curve(n, speed), 0.0, 1.0)
    full = _paper(n, seed + 1, lo, hi)
    dark = _paper(n, seed + 2, lo * 0.8, dull)
    b = np.clip(bright * (0.45 + 0.55 * sp), 0.0, 1.0)
    bed = np.sqrt(1.0 - b) * dark + np.sqrt(b) * full
    grain = _norm(np.abs(A.lowpass(rng.standard_normal(n), 380.0, 1)))
    bed *= (1.0 - tooth) + tooth * grain
    bed = _rms1(bed) + ring * _rms1(_reso(bed, ring_f * rng.uniform(0.9, 1.1), 6.0))
    hand = np.clip(1.0 + wob * _wobble(n, 40.0, seed + 3), 0.3, None)
    env = sp ** 1.2 * hand
    cr = _crackle(n, 2500.0 * sp, env, seed + 4, 1800.0, min(hi, 10000.0))
    y = (1.0 - crisp) * _rms1(bed * env) + crisp * _rms1(cr) if np.any(cr) else _rms1(bed * env)
    y = np.tanh(_rms1(y) / 3.5) * 3.5
    k = max(2, _n(0.003))
    y[-k:] *= np.linspace(1.0, 0.0, k) ** 2
    return y


def _land(seed: int, depth: float = 0.0, soft: float = 0.0, thump: float = 0.3, snap: float = 0.4,
          knock: float = 0.7, spit: float = 0.2, clap: float = 0.5, pff: float = 0.45, drop: float = 0.012,
          round_db: float = 5.0, dur: float = 0.09) -> np.ndarray:
    """The card coming down flat on the pile, its first contact ``LEAD`` seconds into the
    buffer. Its edge meets the pile: a contact pulse (wider is softer) rings the card's
    bending modes for a millisecond or two (``snap``), the pile under it gives a dull
    knock (noise struck once, ``knock``) and a few fibres crush (``spit``). ``drop``
    seconds later the face lands: the sheet unbends onto the pile (a quick run of tiny
    clicks) and claps flat (``clap``), and the air pushed out from under it (a small push,
    then a quicker opposite swing; ``pff`` adds its breath of noise) sets the pile, the
    cloth and the tabletop going, a low, heavily damped thump (``thump``). ``depth``
    (0..1) is how tall the pile has grown: more card under it, a duller knock and clap, a
    lower, more damped thump and a shorter fall (edge and face come closer together);
    ``soft`` is a gentler hand (a wider contact, less snap and clap)."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    t = _t(n)
    c = _n(LEAD)
    m = n - c
    d, s = depth, soft
    # the edge: the card's bending modes, rung by a contact pulse
    w = max(2, _n(0.00022 * (1.0 + 0.8 * d + 1.5 * s)))
    exc = np.zeros(n)
    exc[c:c + w] = np.sin(np.pi * np.arange(w) / w)
    exc[c:] += 0.25 * rng.standard_normal(m) * _decay(m, w / SR * 2.0, 0.00005)
    f1 = 2100.0 * (1.0 - 0.2 * d - 0.2 * s) * rng.uniform(0.94, 1.06)
    rt = 0.0014 * (1.0 - 0.3 * d)
    body = _modes(exc, [(f1, 1.0, rt), (f1 * rng.uniform(1.4, 1.6), 0.5, rt * 0.8),
                        (f1 * rng.uniform(2.5, 2.8), 0.22, rt * 0.5), (f1 * rng.uniform(0.3, 0.36), 0.45, rt * 1.6)])
    # the pile's dull knock
    kn = np.zeros(n)
    kn[c:] = A.bandpass(rng.standard_normal(m) * _decay(m, 0.003 * (1.0 + 0.3 * d), 0.0003),
                        420.0 * (1.0 - 0.15 * d), 2700.0 * (1.0 - 0.35 * d - 0.3 * s), 2)
    # crushed fibres
    env = np.zeros(n)
    env[c:] = _decay(m, 0.0012, 0.0002)
    sp_ = _en(_crackle(n, 9000.0 * env, env, seed + 3, 3000.0, 10000.0)) + _en(
        A.bandpass(rng.standard_normal(n), 3000.0, 10000.0, 2) * env)
    # the face: the sheet unbends onto the pile and claps flat
    tc = LEAD + drop * (1.0 - 0.4 * d) * rng.uniform(0.88, 1.12)
    ic = _n(tc)
    k = _n(0.004)
    fe = np.zeros(n)
    fe[ic - k:ic] = np.linspace(0.15, 1.0, k) ** 2
    flap = _crackle(n, 12000.0 * fe, fe, seed + 4, 1500.0, 8000.0 * (1.0 - 0.3 * d), cap=2.0)
    cl = np.zeros(n)
    cl[ic:] = A.bandpass(rng.standard_normal(n - ic) * _decay(n - ic, 0.0009 * (1.0 + 0.6 * d), 0.0002),
                         700.0, 7000.0 * (1.0 - 0.35 * d - 0.3 * s), 2)
    face = 0.5 * _en(flap) + _en(cl)
    # the air and the low thump
    aw = 0.0035 * (1.0 + 0.2 * d + 0.3 * s) * rng.uniform(0.9, 1.1)
    p = 0.4 * _lobe(t, tc - 0.95 * aw, 1.6 * aw) - _lobe(t, tc, aw) + 0.08 * _lobe(t, tc + 1.4 * aw, 2.0 * aw)
    p *= 1.0 + 0.15 * _norm(A.lowpass(rng.standard_normal(n), 800.0, 1))
    damp = 1.0 - 0.25 * d
    low = _modes(np.gradient(p), [(105.0 * (1.0 - 0.1 * d) * rng.uniform(0.95, 1.05), 1.0, 0.007 * damp),
                                  (220.0 * (1.0 - 0.08 * d) * rng.uniform(0.95, 1.05), 0.7, 0.006 * damp),
                                  (450.0 * (1.0 - 0.1 * d) * rng.uniform(0.95, 1.05), 0.35, 0.0035 * damp)])
    i0 = _n(max(0.0, tc - aw))
    br = np.zeros(n)
    br[i0:] = A.bandpass(rng.standard_normal(n - i0), 150.0, 900.0 * (1.0 - 0.2 * d), 2) * _decay(n - i0, 0.005, 0.0015)
    y = (snap * (1.0 - 0.35 * d - 0.5 * s) * _en(body) + knock * _en(kn) + spit * (1.0 - 0.5 * d - 0.6 * s) * sp_
         + clap * (1.0 - 0.3 * d - 0.4 * s) * face + thump * (0.4 * _en(p) + 0.9 * _en(low)) + pff * _en(br))
    return _tail(_round_top(A.highpass(y, 40.0, 2), round_db), 0.35)


def _settle(seed: int, dur: float = 0.05, depth: float = 0.0) -> np.ndarray:
    """The card skidding a few millimetres on the pile and lying still: a short, dull,
    slowing brush of paper and a few last small clicks (duller on a taller pile)."""
    skid = _slide(dur, seed, [(0.0, 0.7), (0.3, 0.45), (1.0, 0.0)], bright=0.35 * (1.0 - 0.5 * depth),
                  dull=3200.0 * (1.0 - 0.25 * depth), crisp=0.3, ring=0.15)
    return _tail(skid, 0.3)


def _tap(seed: int, edges: int = 9, spread: float = 0.0025, soft: float = 0.0, thump: float = 0.8,
         dur: float = 0.08) -> np.ndarray:
    """The stack knocked square on the cloth, its first edge ``LEAD`` seconds into the
    buffer: every card's edge lands within ``spread`` seconds (they are never quite
    aligned), each a small dull click, over the stack's knock (a packet of card is stiff
    but not hard) and the padded table's low, damped thump."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    t = _t(n)
    c = _n(LEAD)
    m = n - c
    imp = np.zeros(n)
    at = c + np.sort(spread * SR * rng.uniform(0.0, 1.0, edges) ** 1.3).astype(int)
    imp[at] += rng.uniform(0.3, 1.0, edges) * rng.choice([-1.0, 1.0], edges)
    clicks = _reso(imp, 1500.0 * (1.0 - 0.25 * soft) * rng.uniform(0.9, 1.1), 2.5) + 0.5 * _reso(
        imp, 2900.0 * (1.0 - 0.3 * soft) * rng.uniform(0.9, 1.1), 3.0)
    kn = np.zeros(n)
    kn[c:] = A.bandpass(rng.standard_normal(m) * _decay(m, 0.0035, 0.0004), 300.0, 1900.0 * (1.0 - 0.3 * soft), 2)
    aw = 0.0028 * rng.uniform(0.9, 1.1)
    p = -_lobe(t, LEAD + 0.6 * aw, aw) + 0.3 * _lobe(t, LEAD + 1.5 * aw, 1.4 * aw)
    low = _modes(np.gradient(p), [(140.0 * rng.uniform(0.95, 1.05), 1.0, 0.006),
                                  (290.0 * rng.uniform(0.95, 1.05), 0.6, 0.004), (600.0, 0.3, 0.002)])
    y = 0.55 * (1.0 - 0.4 * soft) * _en(clicks) + 0.6 * _en(kn) + thump * (0.35 * _en(p) + 0.9 * _en(low))
    return _tail(_round_top(A.highpass(y, 40.0, 2), 4.0), 0.4)


def _card(seed: int, slide: float = 0.08, depth: float = 0.0, swish: float = 0.85, land: float = 1.0,
          settle: float = 0.15, speed=None, slide_kw=None, land_kw=None) -> Tuple[np.ndarray, float]:
    """One card laid on the pile: the slide (about ``slide`` seconds, ``swish`` its share),
    the landing at ``depth`` (mixed by its peak: ``land`` is how hard it comes down) and
    the settle, each card a little different. Returns the sound and when, in it, the card
    lands (its first contact)."""
    rng = np.random.default_rng(seed)
    sl = slide * rng.uniform(0.88, 1.12)
    skw = dict(bright=rng.uniform(0.72, 0.9), ring_f=rng.uniform(1200.0, 1900.0))
    skw.update(slide_kw or {})
    sp = speed or [(0.0, 0.0), (0.35, 1.0), (0.7, 0.75), (1.0, 0.25)]
    lg = land * 10 ** (rng.uniform(-0.8, 0.8) / 20.0)
    sg = swish * 10 ** (rng.uniform(-1.2, 1.2) / 20.0)
    t_land = sl + 0.002
    parts = [(_en(_slide(sl, seed + 1, sp, **skw)), 0.0, sg),
             (_norm(_land(seed + 2, depth, **(land_kw or {}))), t_land - LEAD, lg),
             (_en(_settle(seed + 3, rng.uniform(0.04, 0.06), depth)), t_land + 0.004, settle * lg)]
    return _place(parts, sl + 0.1), t_land


def _lay(cards, lands: Sequence[float], dur: float) -> np.ndarray:
    """Place each (sound, its landing) so the cards land at ``lands`` seconds."""
    return _place([(snd, at - tl, 1.0) for (snd, tl), at in zip(cards, lands)], dur)


# ----------------------------------------------------------------------------- the candidates
def disc_ref_three():
    # three cards laid one on another: each brushed in over the pile and let go flat, the
    # second and third a little quicker, duller and closer than the one before; then the
    # fingers give the stack one light tap square
    cards = [_card(4100, 0.085, depth=0.0, land=1.0), _card(4120, 0.075, depth=0.45, land=0.85),
             _card(4140, 0.07, depth=0.85, land=0.78)]
    x = _lay(cards, (0.09, 0.265, 0.42), 0.7)
    x = _place([(x, 0.0, 1.0), (_norm(_tap(4160, soft=0.4, thump=0.4)), 0.56 - LEAD, 0.32)], 0.7)
    return _finish(_room(x), 19.5)


def disc_ref_two_soft():
    # two cards set down gently: slower, darker brushes and soft pats onto the pile
    soft_slide = dict(lo=750.0, hi=7000.0, dull=3000.0, crisp=0.1, tooth=0.2)
    soft_land = dict(soft=1.0, snap=0.3, spit=0.1, thump=0.2, round_db=8.0, drop=0.014)
    sp = [(0.0, 0.0), (0.35, 0.85), (0.7, 0.7), (1.0, 0.25)]
    cards = [_card(5100, 0.1, depth=0.1, swish=0.45, land=0.7, speed=sp, slide_kw=soft_slide, land_kw=soft_land),
             _card(5120, 0.095, depth=0.6, swish=0.45, land=0.6, speed=sp, slide_kw=soft_slide, land_kw=soft_land)]
    x = _lay(cards, (0.105, 0.31), 0.48)
    return _finish(_room(x, 0.14), 18.5, lp=8000)


def disc_ref_handful():
    # a small handful let fall onto the pile: the cards slip apart as the fingers open,
    # land almost together in a quick soft ripple (the bottom one bringing the others'
    # weight down with it) and skid; then the fingers push them together, edges rubbing,
    # and knock the stack square twice
    slip = _en(_slide(0.03, 6100, [(0.0, 0.0), (0.5, 1.0), (1.0, 0.2)], bright=0.6, crisp=0.2))
    parts = [(slip, 0.0, 0.4)]
    ripple = ((0.0, 0.0, 1.0), (0.011, 0.35, 0.55), (0.024, 0.6, 0.42), (0.04, 0.85, 0.3))
    t0 = 0.075
    for i, (dt, d, g) in enumerate(ripple):
        th = 0.45 if i == 0 else 0.2
        parts.append((_norm(_land(6110 + i, d, thump=th, drop=0.008)), t0 + dt - LEAD, g))
        parts.append((_en(_settle(6120 + i, 0.05, d)), t0 + dt + 0.004, 0.25 * g))
    push = _en(_slide(0.075, 6130, [(0.0, 0.0), (0.4, 1.0), (0.8, 0.7), (1.0, 0.1)], bright=0.35, dull=3000.0,
                      crisp=0.35, ring=0.2, tooth=0.35))
    parts += [(push, 0.24, 0.6), (_norm(_tap(6140, thump=0.45)), 0.325 - LEAD, 0.72),
              (_norm(_tap(6150, soft=0.5, thump=0.4)), 0.44 - LEAD, 0.45)]
    return _finish(_room(_place(parts, 0.66)), 19.5)


# ============================================================================= the list
C = Candidate
CANDIDATES = [
    C("discard", "ref_three", "Three on the pile",
      "Three cards laid one on another: a papery brush and a soft flat pat each, then a light tap square.",
      disc_ref_three, ["acoustic", "modelled"]),
    C("discard", "ref_two_soft", "Two soft cards",
      "Two cards set down gently on the pile: a darker brush and a soft pat each.",
      disc_ref_two_soft, ["acoustic", "modelled", "soft"]),
    C("discard", "ref_handful", "Handful squared",
      "A small handful let fall onto the pile in a quick soft ripple, pushed together and knocked square.",
      disc_ref_handful, ["acoustic", "modelled"]),
]
