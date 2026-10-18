"""Select a card, modelled on the owner's reference: Pythonista's 'casino:CardPlace1'.

The owner picked CardPlace1 as how selecting a card should feel. These candidates are
built from scratch, in code, from what happens when a card is laid down on a table; no
part of the reference recording is used, read or copied (it was only measured, offline,
to set the timings, levels and bands below).

What the reference is made of, and what models each part here:
  brush    the card's edge skimming the cloth as it comes down: a faint, grainy, high
           friction noise, swelling unevenly as the card nears the table (``_brush``)
  edge     its leading edge meeting the table: a sharp contact pulse ringing the card's
           own bending modes (near 1.2 kHz on cloth) for a few cycles, with a spit of
           high crackle (``_edge``)
  flap     about 10 ms later the face settles flat: a quick, dense cluster of tiny
           paper clicks as the sheet unbends against the surface, ending in a light clap
           (``_flap``)
  air      the air squeezed out from under the card: a soft pressure pulse (a small
           push, a bigger opposite swing) that sets the table's low, heavily damped
           modes going for a cycle or two: the felt "thump" (``_air``)
  settle   the last faint flutter of the card and the cloth (``_settle``)
  room     the faint early reflections of the room around the table (``_room``), where
           the reference has a faint tail of its own
  wood     for the bare-table candidate: an oak top's short, damped modes struck by the
           landing (``_table``)

Each candidate is one fixed file, so its naturalness has to live inside the file: every
part is driven by seeded noise, with heavy-tailed click strengths, jittered timings and
uneven swells rather than smooth curves. Layers are mixed by their share of the energy
(``_en``): most in the air pulse, a quarter in the edge, a fifth in the face's landing and
a trace in the brush, tuned until the closest candidate measures like the reference (its
band split, its two transients 10 ms apart with the landing the stronger onset, their
decays). The softer and crisper candidates then move away from it on purpose.
"""
from __future__ import annotations

import math
from typing import Sequence, Tuple

import numpy as np
from scipy import signal

import synth as A
from catalog import EVENT_BY_ID, Candidate

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
        buf = A.mix_at(buf, snd, at, g)
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


def _crackle(n: int, rate: np.ndarray, amp: np.ndarray, seed: int, lo: float, hi: float, k: int = 6,
             q: float = 3.0, alpha: float = 2.0, cap: float = 6.0) -> np.ndarray:
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


def _gentle(x: np.ndarray, crest_db: float, max_shave_db: float = 3.0) -> np.ndarray:
    """Keep the peak near ``crest_db`` above the build's loudness measure by shaving only
    the first fraction of a millisecond of the sharpest click (a fast look-ahead limiter
    with a 5 ms release, so the body after it keeps its level), and never by more than
    ``max_shave_db``. On a sound this short the click is most of the loudness measure, so
    shaving it also lowers the target; the highest threshold that meets the target is
    therefore found once, by bisection, instead of limiting again and again (which ran
    away, squashing the clicks by up to 8 dB). Softness comes from the design."""
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


def _room(x: np.ndarray, wet: float = 0.08, size: float = 0.12, tail: float = 0.08, lo: float = 300.0,
          hi: float = 6000.0) -> np.ndarray:
    """The faint early reflections of the room around the table, band-limited (timber and
    cloth soak up the boom and the hiss), added to ``x``: a sound heard in a place."""
    full = A.reverb(x, size, wet, damping=0.7, tail=tail)
    dry = np.concatenate([x, np.zeros(len(full) - len(x))])
    gain = 2.0 * (1.0 - wet * 0.5)     # Freeverb's own dry path (it scales the dry by 2)
    return dry + A.bandpass(full - dry * gain, lo, hi, 2) / gain


def _finish(x: np.ndarray, crest_db: float, hp: float = 35.0, lp: float = 0.0, fade: float = 0.25) -> np.ndarray:
    """Take out the sub-bass and DC (and, with ``lp``, the very top), keep the sound inside
    the event's length, let the end fade smoothly and keep the click's peak gentle."""
    y = A.highpass(x, hp, 2)
    if lp:
        y = A.lowpass(y, lp, 2)
    y = y[:_n(EVENT_BY_ID["card_select"].max_seconds - 0.02)]
    return _gentle(_tail(y, fade), crest_db)


# ----------------------------------------------------------------------------- the physical parts
def _brush(dur: float, seed: int, shape: Sequence[Tuple[float, float]], lo: float = 2500.0, hi: float = 9000.0,
           grain: float = 0.7, clicks: float = 0.5) -> np.ndarray:
    """The card's edge skimming the cloth: band-limited friction noise, roughened by the
    fibres it catches (a fast random grain and tiny clicks, ``clicks`` their share), its
    loudness following ``shape`` ((seconds, level) points) unevenly."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    bed = A.bandpass(rng.standard_normal(n), lo, hi, 2)
    rough = np.abs(A.lowpass(rng.standard_normal(n), 350.0, 1))
    bed *= (1.0 - grain) + grain * _norm(rough)
    xs, ys = zip(*shape)
    env = np.interp(_t(n), xs, ys) * np.clip(1.0 + 0.35 * _wobble(n, 60.0, seed + 1), 0.2, None)
    cr = _crackle(n, 1800.0 * env, env, seed + 2, lo * 1.2, hi, q=2.5)
    y = _norm(bed * env) + clicks * _norm(cr)
    return _tail(y, 0.08)


def _edge(seed: int, ring: float = 1200.0, ring_tau: float = 0.0015, width: float = 0.00012,
          spit: float = 0.5, spit_lo: float = 2500.0, spit_hi: float = 9000.0, knock: float = 0.15,
          dur: float = 0.03) -> np.ndarray:
    """The card's leading edge meeting the table: a contact pulse ``width`` long (shorter
    is harder) rings the card's bending modes (``ring``, a close second mode and a weak
    upper one; ``ring_tau`` how fast they die), with a spit of high crackle as the edge's
    fibres crush, and a small low knock of the table under it."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    w = max(2, _n(width))
    pulse = np.zeros(n)
    pulse[:w] = np.sin(np.pi * np.arange(w) / w)
    exc = pulse + 0.25 * rng.standard_normal(n) * _decay(n, width * 2.0, 0.00005)
    f1 = ring * rng.uniform(0.96, 1.04)
    body = _modes(exc, [(f1, 1.0, ring_tau), (f1 * rng.uniform(1.13, 1.22), 0.55, ring_tau * 0.8),
                        (f1 * rng.uniform(2.55, 2.8), 0.25, ring_tau * 0.45)])
    hiss = A.bandpass(rng.standard_normal(n), spit_lo, spit_hi, 2) * _decay(n, 0.0006, 0.0001)
    env = _decay(n, 0.0012, 0.0001)
    cr = _crackle(n, 9000.0 * env, env, seed + 3, spit_lo, spit_hi, q=3.0)
    low = A.lowpass(rng.standard_normal(n) * _decay(n, 0.0015, 0.0003), 300.0, 2)
    y = _en(body) + spit * (0.6 * _en(hiss) + 0.8 * _en(cr)) + knock * _en(low)
    return _tail(y, 0.4)


def _flap(seed: int, dur: float = 0.0075, rate: float = 7000.0, lo: float = 1300.0, hi: float = 9500.0,
          slap: float = 0.8, ring: float = 1100.0, ring_tau: float = 0.002, clap: float = 0.3,
          clap_lo: float = 700.0, clap_hi: float = 7000.0, spray: float = 0.0, spray_lo: float = 2500.0,
          spray_hi: float = 14000.0, cap: float = 3.5) -> np.ndarray:
    """The face settling flat over ``dur`` seconds: its first contact slaps the card into
    its low bending modes (``ring``, ``slap`` their share), then the sheet unbends against
    the surface from the edge inwards in a dense cluster of tiny paper clicks that swells
    and dies away, ending in a light clap as the last of it touches down; ``spray`` adds
    the faint wide hiss of the air escaping at the card's edges as the gap closes. A
    settling sheet makes many similar clicks, so their strengths are capped low (``cap``)."""
    n = _n(dur + 0.02)
    rng = np.random.default_rng(seed)
    u = _t(n) / dur
    rise = np.clip(u * dur / 0.001, 0.0, 1.0)
    env = np.where(u < 1.0, (0.5 - 0.5 * np.cos(np.pi * rise)) * (1.0 - 0.4 * u),
                   0.6 * np.exp(-(u - 1.0) * dur / 0.0015))
    env *= np.clip(1.0 + 0.4 * _wobble(n, 900.0, seed + 1), 0.3, None)
    cr = _crackle(n, rate * env, env, seed + 2, lo, hi, q=3.2, cap=cap)
    exc = rng.standard_normal(n) * _decay(n, 0.0007, 0.0002)
    f1 = ring * rng.uniform(0.95, 1.05)
    body = _modes(exc, [(f1, 1.0, ring_tau), (f1 * rng.uniform(0.62, 0.7), 0.6, ring_tau * 1.3),
                        (f1 * rng.uniform(1.45, 1.6), 0.5, ring_tau * 0.7)])
    m = _n(0.012)
    cl = A.bandpass(rng.standard_normal(m), clap_lo, clap_hi, 2) * _decay(m, 0.0009, 0.0002)
    parts = [(_en(cr), 0.0, 1.0), (_en(_tail(body, 0.5)), 0.0, slap), (_en(cl), dur * rng.uniform(0.92, 1.0), clap)]
    if spray:
        gush = np.clip(u, 0, 1) ** 2 * np.where(u < 1.0, 1.0, np.exp(-(u - 1.0) * dur / 0.0008))
        parts.append((_en(A.bandpass(rng.standard_normal(n), spray_lo, spray_hi, 2) * gush), 0.0, spray))
    return _tail(_place(parts, n / SR), 0.3)


AIR_LEAD = 2.2   # an _air piece's main swing falls this many ``width``s into its buffer


def _air(seed: int, width: float = 0.0034, pre: float = 0.45, rebound: float = 0.08,
         modes=((64.0, 0.9, 0.006), (148.0, 0.55, 0.004), (270.0, 0.25, 0.0025)), push: float = 1.0,
         body: float = 0.45, pff: float = 0.25, pff_lo: float = 120.0, pff_hi: float = 900.0,
         dur: float = 0.06) -> np.ndarray:
    """The air squeezed out from under the landing card, and what it does to the table:
    a soft pressure pulse (a small push as the air is compressed, then a bigger, quicker
    opposite swing ``width`` long as the card meets the surface, and a slight rebound),
    slightly uneven, which rings the table's low, heavily damped ``modes`` for a cycle or
    two, with a breath of the air rushing out through the cloth (``pff``). ``push``,
    ``body`` and ``pff`` are the three parts' shares."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    t = _t(n)

    def lobe(at: float, w: float) -> np.ndarray:
        x = (t - at) / w
        return np.where(np.abs(x) < 0.5, 0.5 + 0.5 * np.cos(2 * np.pi * x), 0.0)

    w = width * rng.uniform(0.95, 1.05)
    tm = AIR_LEAD * width
    p = pre * lobe(tm - 0.95 * width, 1.6 * w) - lobe(tm, w) + rebound * lobe(tm + 1.4 * width, 2.0 * w)
    p *= 1.0 + 0.15 * _norm(A.lowpass(rng.standard_normal(n), 800.0, 1))
    ring = _modes(np.gradient(p), [(f * rng.uniform(0.97, 1.03), g, tau) for f, g, tau in modes])
    br = A.bandpass(rng.standard_normal(n), pff_lo, pff_hi, 2) * lobe(tm, 2.5 * w)
    y = push * _en(p) + body * _en(ring) + pff * _en(br)
    return _tail(y, 0.35)


def _settle(seed: int, dur: float = 0.07, lo: float = 2000.0, hi: float = 9000.0, tau: float = 0.018,
            hush: float = 0.5) -> np.ndarray:
    """The card's last faint flutter on the cloth: a few dying clicks and a breath of the
    cloth's hush."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    env = _decay(n, tau, 0.002) * np.clip(1.0 + 0.6 * _wobble(n, 120.0, seed + 1), 0.1, None)
    cr = _crackle(n, 2500.0 * env, env, seed + 2, lo, hi, q=2.5)
    hs = A.bandpass(rng.standard_normal(n), lo, hi, 2) * env
    return _tail(_en(cr) + hush * _en(hs), 0.3)


def _table(seed: int, width: float = 0.0005, scale: float = 1.0, dur: float = 0.04) -> np.ndarray:
    """A thick oak tabletop struck lightly by the landing card: its short, heavily damped
    modes (a light card barely sets them going, so they give a dry "tk" of wood, not a
    ring), driven by a soft pulse with a little grit."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    w = max(2, _n(width))
    exc = np.zeros(n)
    exc[:w] = np.sin(np.pi * np.arange(w) / w)
    exc += 0.2 * rng.standard_normal(n) * _decay(n, width, 0.0001)
    modes = [(f * scale * rng.uniform(0.97, 1.03), g, tau) for f, g, tau in
             ((230.0, 0.6, 0.003), (410.0, 1.0, 0.003), (720.0, 0.8, 0.0025), (1100.0, 0.55, 0.002),
              (1650.0, 0.35, 0.0018), (2500.0, 0.2, 0.0012))]
    return _tail(_modes(exc, modes), 0.4)


# ----------------------------------------------------------------------------- the candidates
def sel_ref_place():
    # the reference's events, cleaner: a faint brush of the card's edge over the cloth (a
    # little shorter, darker and without the recording's gating) that drags on faintly as
    # the card pivots down, the edge's tick ringing the card near 1.2 kHz, then 10.5 ms
    # later the face settling with a quick crackle over the felt-covered table's soft low
    # thump, and a last faint flutter
    t_edge, gap, flap_dur, aw = 0.042, 0.0105, 0.0072, 0.0040
    land = t_edge + gap + flap_dur
    brush = _en(_brush(land, 101, ((0.0, 0.0), (0.015, 0.2), (0.032, 0.75), (0.041, 1.0), (0.0425, 0.45),
                                   (0.048, 0.55), (0.054, 0.4), (land, 0.0)), lo=2800, hi=8500))
    edge = _en(_edge(102, ring=1200, ring_tau=0.0019, width=0.00012, spit=0.4, spit_hi=7500))
    flap = _en(_flap(103, dur=flap_dur, rate=8000, lo=1300, hi=8000, slap=0.8, ring=1100, spray=0.5,
                     spray_hi=12000))
    air = _en(_air(104, width=aw, pre=0.5, modes=((64.0, 0.4, 0.006), (150.0, 1.0, 0.0045), (285.0, 0.5, 0.003)),
                   body=0.75))
    settle = _en(_settle(105, 0.08, hi=7000, tau=0.02))
    x = _place([(brush, 0.0, 0.11), (edge, t_edge, 0.52), (flap, t_edge + gap, 0.48),
                (air, land - AIR_LEAD * aw, 0.78), (settle, land + 0.001, 0.09)], land + 0.07)
    return _finish(_room(x, 0.12), 21.5, hp=35.0, lp=11000)


def sel_ref_felt():
    # the same card laid on thick baize: the cloth swallows the edge's tick (a wider, softer
    # contact, ringing lower and briefly) and most of the face's crackle, so what is left is
    # a short hush and a soft, round pat of air on the cloth, its weight up where a phone's
    # speaker plays it (150-400 Hz) rather than in the deep thump; gentler peaks
    t_edge, gap, flap_dur, aw = 0.024, 0.011, 0.008, 0.0045
    land = t_edge + gap + flap_dur
    brush = _en(A.lowpass(_brush(land, 201, ((0.0, 0.0), (0.012, 0.4), (0.022, 1.0), (0.025, 0.5), (0.034, 0.4),
                                             (land, 0.0)), lo=1500, hi=4500, grain=0.6, clicks=0.35), 5000, 2))
    edge = _en(A.lowpass(_edge(202, ring=780, ring_tau=0.0010, width=0.0005, spit=0.15, spit_lo=1500,
                               spit_hi=4000, knock=0.4), 3000, 2))
    flap = _en(A.lowpass(_flap(203, dur=flap_dur, rate=3000, lo=900, hi=4200, slap=0.55, ring=700, ring_tau=0.0016,
                               clap=0.4, clap_lo=350, clap_hi=2500, cap=2.5), 3800, 2))
    air = _en(_air(204, width=aw, pre=0.5, rebound=0.0, modes=((75.0, 0.35, 0.004), (170.0, 1.0, 0.0045),
                                                                  (310.0, 0.6, 0.003)),
                   push=0.55, body=1.0, pff=0.8, pff_lo=180, pff_hi=700))
    settle = _en(A.lowpass(_settle(205, 0.06, lo=1300, hi=4000, tau=0.014, hush=0.9), 4500, 2))
    x = _place([(brush, 0.0, 0.11), (edge, t_edge, 0.26), (flap, t_edge + gap, 0.32),
                (air, land - AIR_LEAD * aw, 0.86), (settle, land + 0.001, 0.08)], land + 0.06)
    return _finish(x, 18.5, hp=45.0, lp=6000)


def sel_ref_wood():
    # the card laid on a bare oak table: a short dry scrape, its edge clicking crisply on the
    # hard top (a sharper contact ringing the card higher), the face landing in a quicker,
    # brighter clack, and the wood answering with a dry "tk"; the air escapes faster on a
    # hard top, so its thump is shorter and higher
    t_edge, gap, flap_dur, aw = 0.016, 0.009, 0.0045, 0.0022
    land = t_edge + gap + flap_dur
    brush = _en(_brush(land, 301, ((0.0, 0.0), (0.009, 0.5), (0.0155, 1.0), (0.0165, 0.4), (0.024, 0.3),
                                   (land, 0.0)), lo=3000, hi=10000, grain=0.8, clicks=0.6))
    edge = _en(_edge(302, ring=1650, ring_tau=0.0012, width=0.0001, spit=0.45, spit_lo=3000, spit_hi=10000,
                     knock=0.1))
    flap = _en(_flap(303, dur=flap_dur, rate=9000, lo=1800, hi=10000, slap=0.7, ring=1500, ring_tau=0.0014,
                     clap=1.0, clap_lo=1000, clap_hi=9000, spray=0.4))
    air = _en(_air(304, width=aw, pre=0.35, rebound=0.06, modes=((90.0, 0.5, 0.003), (200.0, 0.8, 0.0025),
                                                                    (380.0, 0.5, 0.002)), pff=0.15))
    wood = _en(_table(305, width=0.0004))
    settle = _en(_settle(306, 0.05, lo=2500, hi=9000, tau=0.01, hush=0.3))
    x = _place([(brush, 0.0, 0.10), (edge, t_edge, 0.47), (flap, t_edge + gap, 0.46),
                (air, land - AIR_LEAD * aw, 0.72), (wood, land - 0.0004, 0.46), (settle, land, 0.06)], land + 0.05)
    return _finish(_room(x, 0.045), 22.5, hp=40.0, lp=12000)


# ============================================================================= the list
C = Candidate
CANDIDATES = [
    C("card_select", "ref_place", "Card laid down",
      "A card laid on a cloth-covered table: a faint brush, its edge's tick and a soft felt thump.",
      sel_ref_place, ["acoustic", "modelled"]),
    C("card_select", "ref_felt", "Soft felt",
      "The same card laid on thick baize: a hush and a soft, round pat, muffled and gentle.",
      sel_ref_felt, ["acoustic", "modelled", "soft"]),
    C("card_select", "ref_wood", "Card on wood",
      "A card laid on a bare oak table: a crisp edge click and a short, dry wooden clack.",
      sel_ref_wood, ["acoustic", "modelled", "crisp"]),
]
