"""Card sounds: select, deselect, play, draw, shuffle and discard (five candidates each).

Each event offers five characters: a realistic one (card stock on a felt table), a soft
and subtle one, a wooden tavern one, a magical chimey one and a retro 8-bit one.

The physical sounds are built from their parts, the way real ones happen:
  snap      a card edge springing free: a few milliseconds of band-passed noise with a
            faint ring of the card itself (a stiff paper plate, 2-4 kHz)
  slide     card stock rubbing on card stock: band-passed noise whose loudness and
            brightness follow the slide's speed, a grainy amplitude, and the sparse
            stick-slip ticks of the fibres catching
  burst     a slap: noise struck once and filtered (paper on felt, paper on paper, air)
  thump     a soft low knock: a damped sine that drops a little in pitch, plus a
            low-passed knock (a fingertip, a deck on felt)
  modal     wood and boxes: damped resonators (each a two-pole filter) struck by a short
            mallet pulse
  chime     a pure tone with a few short-lived inharmonic partials (glass, magic)
  chip      8-bit: a band-limited pulse wave and a 15-bit LFSR noise channel, both with
            volumes that step every 1/60 s like an old console, gently smoothed
Layers are mixed by their share of the energy (``_en``), not their peaks, and the knocks
sit at 150-900 Hz, so a phone's small speaker still hears the body of each sound. Every
piece fades to zero at the end of its own buffer, so nothing is cut off mid-ring.
Tonal parts use D major pentatonic (D E F# A B), with F natural from D dorian once.
Everything is seeded, so each sound is rebuilt identically.
"""
from __future__ import annotations

import math
from typing import List, Sequence, Tuple

import numpy as np
from scipy import signal

import synth as A
from catalog import EVENT_BY_ID, Candidate

SR = A.SR
FRAME = 1.0 / 60.0          # an 8-bit console's volume and pitch step


def _hz(name: str) -> float:
    return A.note_hz(name)


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
    (gain squared), not its peak: a 5 ms slap and a 40 ms thump compare fairly."""
    e = math.sqrt(float(np.sum(x ** 2)) / SR * 1000.0)
    return x / e if e > 0 else x


def _tail(x: np.ndarray, frac: float = 0.3, min_s: float = 0.006) -> np.ndarray:
    """Fade the last part of a piece's buffer to zero, so nothing is cut off while still
    ringing when the buffer ends."""
    k = min(len(x), max(_n(min_s), int(len(x) * frac)))
    y = x.copy()
    if k > 1:
        y[-k:] *= 0.5 + 0.5 * np.cos(np.pi * np.linspace(0.0, 1.0, k))
    return y


def _soften(x: np.ndarray, k: float = 1.3) -> np.ndarray:
    """Round off the very tops of the sharpest transients (a gentle tanh), so a slap keeps
    its body after mastering instead of being squeezed by the limiter."""
    p = float(np.max(np.abs(x))) or 1.0
    return np.tanh(k * x / p) / math.tanh(k) * p


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


def _loud_db(x: np.ndarray) -> float:
    """The build's loudness measure (gated RMS in 50 ms blocks), so a sound can be checked
    against what mastering will do to it."""
    if hasattr(A, "_rms_db"):
        return A._rms_db(x)
    y = A.highpass(x, 100, 1)
    blk = _n(0.05)
    if len(y) < blk:
        return 10 * math.log10(np.mean(y ** 2) + 1e-20)
    k = len(y) // blk
    pw = np.mean(y[:k * blk].reshape(k, blk) ** 2, axis=1)
    keep = pw[pw > np.max(pw) * 10 ** (-4.5)]
    return 10 * math.log10(np.mean(keep) + 1e-20)


def _tame(x: np.ndarray, loudness_db: float, ceiling_db: float = -1.0, margin_db: float = 1.5,
          max_shave_db: float = 4.0) -> np.ndarray:
    """Keep the peak within what mastering allows above the event's loudness (ceiling minus
    a margin), by shaving only the first milliseconds of the sharpest attacks (a 20 ms
    release, so the body that follows keeps its level), so the master's slower limiter has
    little or nothing to do. Shaving also lowers the measured loudness, so the highest
    threshold that meets the target is found by bisection; it never shaves more than
    ``max_shave_db`` (a slam keeps its snap)."""
    allowed = ceiling_db - margin_db - loudness_db

    def crest(y):
        return 20 * math.log10(float(np.max(np.abs(y))) + 1e-12) - _loud_db(y)

    def shave(th_db):
        thr = 10 ** (th_db / 20.0)
        return A.limit(x / thr, 0.0, lookahead=0.0015, release=0.02) * thr

    if crest(x) <= allowed:
        return x
    top = _loud_db(x) + allowed                     # the threshold if loudness did not move
    floor = max(top - 12.0, 20 * math.log10(float(np.max(np.abs(x)))) - max_shave_db)
    if floor >= top:                                # out of reach within the cap: shave the cap
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


def _fit(x: np.ndarray, event: str, fade: float = 0.05, hp: float = 45.0) -> np.ndarray:
    """Finish a sound for ``event``: take out sub-bass and DC, keep it inside the event's
    length (with room for the build's own trim), let whatever still sounds fade out
    smoothly, and tame its sharpest peak for the event's loudness."""
    ev = EVENT_BY_ID[event]
    y = A.highpass(x, hp, 2)
    n = _n(ev.max_seconds - 0.02)
    if len(y) > n:
        y = y[:n]
    y = _tail(y, _n(fade) / len(y)) if len(y) > _n(fade) else y
    return _tame(y, ev.loudness_db)


# ----------------------------------------------------------------------------- physical pieces
def _snap(seed: int, center: float = 2800.0, tau: float = 0.0025, dur: float = 0.03, ring: float = 0.3,
          spread: float = 1.8, lp: float = 8000.0) -> np.ndarray:
    """A card edge springing free: an impulse of noise filtered around ``center`` plus the
    card's own brief ring near it."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    exc = rng.standard_normal(n) * _decay_env(n, tau, 0.0003)
    y = _norm(A.bandpass(exc, center / spread, min(center * spread, 16000.0), 2))
    if ring:
        f = center * rng.uniform(0.9, 1.1)
        y = y + ring * np.sin(2 * np.pi * f * _t(n)) * _decay_env(n, tau * 0.9, 0.0003)
    if lp:
        y = A.lowpass(y, lp, 2)
    return _tail(_norm(y), 0.25)


def _burst(dur: float, lo: float, hi: float, tau: float, seed: int, attack: float = 0.0004) -> np.ndarray:
    """A slap: noise struck once (fast rise, exponential fall), then band-passed."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    exc = rng.standard_normal(n) * _decay_env(n, tau, attack)
    return _tail(_norm(A.bandpass(exc, lo, hi, 2)), 0.25)


def _rms1(x: np.ndarray) -> np.ndarray:
    r = math.sqrt(float(np.mean(x ** 2)))
    return x / r if r > 0 else x


def _slide(dur: float, speed, lo: float = 900.0, hi: float = 6500.0, seed: int = 0, bright: float = 0.5,
           grit: float = 0.25, grain: float = 0.004, depth: float = 0.55, tick_rate: float = 320.0) -> np.ndarray:
    """Card stock rubbing on card stock. ``speed`` (0..1, points over the slide's length,
    or a per-sample array) drives the loudness, how often the fibres catch (stick-slip
    ticks) and where the noise's band sits: the band rises as the card speeds up and
    falls as it slows, the "fwip" of a slide (eight band-passed copies of one noise,
    crossfaded sample by sample). ``bright`` sets how high the band climbs."""
    n = _n(dur)
    sp = speed if isinstance(speed, np.ndarray) else _curve(n, speed)
    sp = np.clip(sp[:n], 0.0, 1.0)
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(n)
    K = 8
    cs = np.geomspace(lo * 1.35, hi / 1.35, K)
    bands = np.stack([_rms1(A.bandpass(w, c / 1.35, c * 1.35, 2)) for c in cs])
    pos = sp * (K - 1) * (0.35 + 0.65 * bright)
    i0 = np.minimum(pos.astype(int), K - 2)
    fr = pos - i0
    ar = np.arange(n)
    swept = (1 - fr) * bands[i0, ar] + fr * bands[i0 + 1, ar]
    wide = _rms1(A.bandpass(rng.standard_normal(n), lo, hi, 2))
    base = (0.9 * swept + 0.15 * wide) * sp
    m = int(dur / grain) + 3
    g = rng.uniform(1.0 - depth, 1.0, m)
    gi = np.interp(_t(n) / grain, np.arange(m), g)
    mid = math.sqrt(lo * hi)
    imp = (rng.random(n) < tick_rate * sp / SR) * rng.uniform(0.25, 1.0, n) * np.sign(rng.standard_normal(n))
    ticks = A.bandpass(imp, mid * 0.6, min(hi * 1.1, 15000.0), 2)
    pk = float(np.max(np.abs(ticks))) or 1.0
    y = (base * gi + 3.0 * grit * ticks / pk) * 0.25
    return _tail(_fade_in(y, 0.0015), 0.1)


def _thump(f0: float, f1: float, tau: float, seed: int = 0, dur: float = 0.0, knock: float = 0.4,
           knock_lp: float = 800.0, drive: float = 1.4) -> np.ndarray:
    """A soft low knock: a damped sine falling from f0 to f1 in 25 ms, plus a low-passed
    knock of noise, gently saturated so a small speaker hears its harmonics. It lasts
    long enough (8 time constants) to die away by itself."""
    dur = dur or max(0.05, 8 * tau)
    n = _n(dur)
    k = min(n, _n(0.025))
    f = np.full(n, float(f1))
    f[:k] = f0 * (f1 / f0) ** np.linspace(0.0, 1.0, k)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * _decay_env(n, tau, 0.0012)
    rng = np.random.default_rng(seed)
    nz = A.lowpass(rng.standard_normal(n) * _decay_env(n, tau * 0.35, 0.0005), knock_lp, 2)
    y = body + knock * _norm(nz)
    return _tail(np.tanh(drive * y) / math.tanh(drive), 0.3)


def _mallet(dur: float, width: float = 0.0008, seed: int = 0, noise: float = 0.15) -> np.ndarray:
    """A strike: a half-sine pulse ``width`` long (shorter = harder) with a little noise."""
    n = _n(dur)
    w = max(2, _n(width))
    y = np.zeros(n)
    y[:w] = np.sin(np.pi * np.arange(w) / w)
    rng = np.random.default_rng(seed)
    m = min(n, w * 3)
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


def _wood(f: float, dur: float, seed: int, ratios=(0.42, 1.0, 2.41, 3.93), gains=(0.3, 1.0, 0.45, 0.2),
          taus=(0.01, 0.022, 0.01, 0.005), mallet: float = 0.0004, contact: float = 0.5,
          contact_center: float = 3000.0) -> np.ndarray:
    """A small piece of hardwood struck: a quick low board mode, a short tuned tock and
    fast-dying upper modes, plus the noisy click of contact (what makes it wood rather
    than glass)."""
    rng = np.random.default_rng(seed)
    exc = _mallet(dur, mallet, seed)
    modes = [(f * r * rng.uniform(0.995, 1.005), g, t) for r, g, t in zip(ratios, gains, taus)]
    y = _norm(_modal(exc, modes))
    if contact:
        c = _snap(seed + 7, contact_center, 0.0012, min(dur, 0.02), ring=0.0)
        y[:len(c)] += contact * c
    return y


def _chime(f: float, dur: float, tau: float, seed: int = 0,
           parts=((2.0, 0.18, 0.5), (2.76, 0.08, 0.25), (5.4, 0.03, 0.12)), strike: float = 0.08,
           attack: float = 0.0015) -> np.ndarray:
    """A clear tone with short-lived inharmonic partials (glass or a small bell) and a
    soft strike; partials above 7.8 kHz are left out."""
    n = _n(dur)
    t = _t(n)
    y = np.sin(2 * np.pi * f * t) * _decay_env(n, tau, attack)
    for r, g, tr in parts:
        if f * r > 7800:
            continue
        y += g * np.sin(2 * np.pi * f * r * t) * _decay_env(n, tau * tr, attack)
    if strike:
        s = _snap(seed, center=min(f * 2.5, 5500.0), tau=0.0012, dur=min(dur, 0.02), ring=0.0, lp=7000)
        y[:len(s)] += strike * s
    return _tail(y, 0.35)


def _room(x: np.ndarray, room: float = 0.3, wet: float = 0.15, damping: float = 0.6, tail: float = 0.4,
          lo: float = 250.0, hi: float = 3500.0) -> np.ndarray:
    """A small room's reflections added to ``x``, with the reverb's own sound band-limited
    (a wooden room soaks up the highs and the boom), so its tail never hisses or rumbles.
    The wet part is what the reverb adds beyond its dry path (pedalboard's dry gain is
    2 x (1 - wet / 2) on a mono input, with no delay)."""
    full = A.reverb(x, room, wet, damping, tail=tail)
    dry = np.concatenate([x, np.zeros(len(full) - len(x))])
    w = full - dry * 2.0 * (1.0 - wet * 0.5)
    return dry + A.bandpass(w, lo, hi, 2) / (2.0 * (1.0 - wet * 0.5))


# ----------------------------------------------------------------------------- 8-bit pieces
def _pulse(freq: np.ndarray, duty: float = 0.25) -> np.ndarray:
    """A band-limited pulse wave (two PolyBLEP saws a duty cycle apart); zero mean."""
    dur = len(freq) / SR
    s1 = A.osc("saw", freq, dur)
    s2 = A.osc("saw", freq, dur, phase=2 * np.pi * duty)
    return 0.5 * (s1 - s2)


def _frames(values: Sequence[float], frame: float = FRAME) -> np.ndarray:
    k = _n(frame)
    return np.repeat(np.asarray(values, dtype=float), k)


def _smooth(v: np.ndarray, ms: float = 1.5) -> np.ndarray:
    a = math.exp(-1.0 / (ms * 0.001 * SR))
    return signal.lfilter([1 - a], [1, -a], v)


def _chip_vol(vols: Sequence[float], frame: float) -> np.ndarray:
    """Per-frame volumes 0..15 as a per-sample gain; the last frame ramps down to silence
    instead of stepping off, and two silent frames follow."""
    v = _frames(list(vols) + [0, 0], frame) / 15.0
    k = _n(frame)
    i = len(vols) - 1
    v[i * k:(i + 1) * k] = vols[-1] / 15.0 * np.linspace(1.0, 0.0, k)
    return _smooth(v)


def _chip(freqs, vols, duty: float = 0.25, lp: float = 5000.0, frame: float = FRAME) -> np.ndarray:
    """A pulse channel: per-frame pitches (Hz, or a per-sample array) and volumes 0..15."""
    v = _chip_vol(vols, frame)
    if isinstance(freqs, np.ndarray) and len(freqs) > len(vols) + 2:
        f = np.concatenate([freqs, np.full(max(0, len(v) - len(freqs)), freqs[-1])])[:len(v)]
    else:
        fl = list(freqs)
        fl = fl + [fl[-1]] * (len(vols) + 2 - len(fl))
        f = _frames(fl, frame)[:len(v)]
    return A.lowpass(_pulse(f, duty) * v, lp, 2)


def _lfsr_bits(count: int, seed: int, short: bool = False) -> np.ndarray:
    reg = ((0x5A3C + 7919 * seed) & 0x7FFF) or 1
    tap = 6 if short else 1
    out = np.empty(count)
    for i in range(count):
        fb = (reg ^ (reg >> tap)) & 1
        reg = (reg >> 1) | (fb << 14)
        out[i] = reg & 1
    return out * 2.0 - 1.0


def _chip_noise(clocks, vols, seed: int = 1, short: bool = False, lp: float = 5500.0,
                frame: float = FRAME) -> np.ndarray:
    """The noise channel: a 15-bit LFSR clocked at per-frame rates (Hz), with per-frame
    volumes 0..15 (``frame`` may be a quarter frame, like the console's envelope unit)."""
    v = _chip_vol(vols, frame)
    cl = list(clocks) + [clocks[-1]] * (len(vols) + 2 - len(clocks))
    c = _frames(cl, frame)[:len(v)]
    idx = np.cumsum(c / SR).astype(int)
    bits = _lfsr_bits(int(idx[-1]) + 1, seed, short)
    y = bits[idx]
    y = (y - np.mean(y)) * v
    return A.lowpass(y, lp, 2)


# ----------------------------------------------------------------------------- composite pieces
def _riffle(n_cards: int, length: float, seed: int, centers=(3100.0, 2500.0), rustle: float = 0.15,
            lp: float = 8000.0, loud_mid: float = 0.45) -> np.ndarray:
    """A riffle: the two halves' cards flick free one by one, alternating sides, slower at
    the start and the end, over a faint rustle."""
    rng = np.random.default_rng(seed)
    u = np.linspace(0.0, 1.0, n_cards)
    prof = (1.0 + 0.9 * (2 * u - 1) ** 2) * rng.uniform(0.75, 1.25, n_cards)
    times = np.concatenate([[0.0], np.cumsum(prof[:-1])])
    times *= length / times[-1]
    buf = np.zeros(_n(length + 0.06))
    for i, t0 in enumerate(times):
        c = centers[i % 2] * rng.uniform(0.85, 1.15)
        amp = (1.0 - loud_mid + loud_mid * math.sin(math.pi * u[i]) ** 0.5) * rng.uniform(0.65, 1.0)
        s = _snap(seed * 1000 + i, center=c, tau=rng.uniform(0.0014, 0.0028), dur=0.022, ring=0.3, lp=lp)
        buf = A.mix_at(buf, s, t0, amp)
    bed = _slide(length + 0.04, [(0, 0.5), (0.5, 0.8), (0.92, 0.5), (1, 0.0)], 1000, 6500, seed + 5,
                 bright=0.4, grit=0.0)
    return _place([(buf, 0, 1.0), (bed, 0, rustle)])


def _cascade(dur: float, n_cards: int, seed: int, center: float = 2000.0) -> np.ndarray:
    """The bridge: the bent deck lets go and the cards fall together in a soft, fast purr."""
    rng = np.random.default_rng(seed)
    u = np.sort(rng.uniform(0, 1, n_cards)) ** 1.15
    buf = np.zeros(_n(dur + 0.04))
    for i, x in enumerate(u):
        amp = (0.55 + 0.45 * math.sin(math.pi * min(1.0, x * 1.2))) * rng.uniform(0.6, 1.0)
        s = _snap(seed * 1000 + i, center=center * rng.uniform(0.8, 1.25), tau=rng.uniform(0.0015, 0.003),
                  dur=0.02, ring=0.15, lp=5000)
        buf = A.mix_at(buf, s, x * dur, amp)
    bed = _slide(dur + 0.03, [(0, 0.8), (0.6, 0.6), (1, 0.0)], 700, 4500, seed + 3, bright=0.3, grit=0.0)
    return _place([(buf, 0, 1.0), (bed, 0, 0.25)])


def _deck_tap(seed: int) -> np.ndarray:
    """A squared deck tapped on felt: mostly the papery knock of its edge, with a short
    low thump under it."""
    th = _en(_thump(230, 170, 0.02, seed, knock=0.7, knock_lp=1400))
    pap = _en(A.lowpass(_burst(0.05, 500, 3500, 0.004, seed + 1), 4000))
    return _norm(_place([(th, 0, 0.6), (pap, 0, 1.0)]))


def _table_knock(seed: int, scale: float = 1.0) -> np.ndarray:
    """A deck knocked on a thick wooden tabletop: a hard wooden tock on A4, damped low
    modes under it (D3, A3, E5: the modes that ring long enough to be heard as a pitch sit
    on the D scale) and short inharmonic ones above, and the papery edge of the cards."""
    modes = [(147 * scale, 0.3, 0.05), (220 * scale, 0.4, 0.045), (440 * scale, 1.0, 0.045),
             (659 * scale, 0.6, 0.03), (905 * scale, 0.45, 0.018), (1380 * scale, 0.25, 0.012)]
    wood = _en(_modal(_mallet(0.3, 0.0009, seed), modes))
    pap = _en(_burst(0.04, 700, 4500, 0.003, seed + 1))
    return _norm(_place([(wood, 0, 1.0), (pap, 0, 0.55)]))


def _glitter(seed: int, count: int, t0: float, t1: float, notes=("D7", "E7", "F#7", "A7", "B7"),
             gain=(0.1, 0.22)) -> List[tuple]:
    """Tiny high pings scattered in time (fairy dust)."""
    rng = np.random.default_rng(seed)
    out = []
    n = _n(0.2)
    for i in range(count):
        f = _hz(notes[int(rng.integers(len(notes)))])
        p = _tail(np.sin(2 * np.pi * f * _t(n)) * _decay_env(n, rng.uniform(0.02, 0.04), 0.0015), 0.3)
        out.append((p, float(rng.uniform(t0, t1)), float(rng.uniform(*gain))))
    return out


# ============================================================================= card_select
def sel_card_lift():
    snap = _en(_snap(11, center=2900, tau=0.0022, dur=0.03, ring=0.3, lp=7000))
    slide = _en(_slide(0.065, [(0, 0.55), (0.35, 0.85), (1, 0.0)], lo=1300, hi=6000, seed=12, bright=0.35,
                       grit=0.2))
    edge = _en(_snap(13, center=3400, tau=0.0015, dur=0.02, ring=0.2, lp=7000))
    x = _place([(snap, 0, 1.0), (slide, 0.002, 0.8), (edge, 0.058, 0.35)], 0.14)
    return _fit(A.lowpass(x, 7000), "card_select", 0.03)


def sel_felt_tap():
    tip = _en(A.lowpass(_snap(22, center=1300, tau=0.0016, dur=0.02, ring=0.1), 3000))
    pff = _en(_burst(0.03, 300, 1600, 0.004, 23))
    th = _en(_thump(330, 260, 0.012, seed=21, knock=0.6, knock_lp=1400))
    x = _place([(tip, 0, 0.6), (pff, 0, 0.6), (th, 0, 0.5)], 0.12)
    return _fit(A.lowpass(x, 3500, 2), "card_select", 0.03)


def sel_oak_tick():
    return _fit(_wood(_hz("A5"), 0.14, seed=31), "card_select", 0.04)


def sel_glass_chime():
    d6 = _chime(_hz("D6"), 0.23, tau=0.045, seed=41)
    a6 = _chime(_hz("A6"), 0.23, tau=0.035, seed=42, parts=((2.0, 0.1, 0.4),), strike=0.0)
    return _fit(d6 + 0.3 * a6, "card_select", 0.05)


def sel_pixel_blip():
    f = [_hz("D5")] * 2 + [_hz("A5")] * 5
    v = [9, 8, 11, 8, 5, 3, 1]
    return _fit(_chip(f, v, duty=0.25, lp=4500), "card_select", 0.02)


# ============================================================================= card_deselect
def des_card_tuck():
    start = _en(A.lowpass(_snap(52, center=1900, tau=0.0018, dur=0.02, ring=0.15), 4500))
    slide = _en(_slide(0.07, [(0, 0.6), (0.4, 0.7), (1, 0.05)], lo=800, hi=4200, seed=51, bright=0.25, grit=0.15))
    settle = _en(_burst(0.03, 400, 2200, 0.004, 54))
    th = _en(_thump(300, 240, 0.01, seed=53, knock=0.7, knock_lp=1600))
    x = _place([(start, 0, 0.6), (slide, 0.001, 0.75), (settle, 0.062, 0.45), (th, 0.062, 0.35)], 0.15)
    return _fit(A.lowpass(x, 5000), "card_deselect", 0.03)


def des_soft_pat():
    tip = _en(A.lowpass(_snap(62, 900, 0.0016, 0.02, ring=0.0), 2000))
    pff = _en(_burst(0.03, 250, 1100, 0.005, 63))
    th = _en(_thump(260, 200, 0.011, seed=61, knock=0.5, knock_lp=900))
    x = _place([(tip, 0, 0.5), (pff, 0, 0.65), (th, 0, 0.55)], 0.1)
    return _fit(A.lowpass(x, 2500), "card_deselect", 0.03)


def des_oak_tock():
    x = _wood(_hz("D5"), 0.17, seed=71, ratios=(0.42, 1.0, 2.62, 3.98), gains=(0.35, 1.0, 0.3, 0.1),
              taus=(0.012, 0.028, 0.012, 0.006), mallet=0.0008, contact=0.3, contact_center=2000)
    return _fit(x, "card_deselect", 0.04)


def des_glass_dip():
    parts = ((2.0, 0.15, 0.5), (2.76, 0.06, 0.25))
    a = _chime(_hz("D6"), 0.2, 0.03, seed=81, parts=parts, strike=0.06)
    b = _chime(_hz("A5"), 0.19, 0.04, seed=82, parts=parts, strike=0.04)
    return _fit(_place([(a, 0, 0.7), (b, 0.05, 1.0)], 0.24), "card_deselect", 0.05)


def des_pixel_drop():
    f = [_hz("A5")] * 2 + [_hz("D5")] * 5
    v = [8, 7, 9, 6, 4, 2, 1]
    return _fit(_chip(f, v, duty=0.25, lp=4500), "card_deselect", 0.02)


# ============================================================================= play
def play_felt_slap():
    slap = _en(_burst(0.06, 450, 4000, 0.007, 101))
    air = _en(_burst(0.06, 150, 1100, 0.01, 102))
    th = _en(_thump(220, 150, 0.025, seed=103, knock=0.5, knock_lp=900))
    skid = _en(_slide(0.09, [(0, 0.7), (1, 0.0)], lo=500, hi=3500, seed=104, bright=0.3, grit=0.2))
    flutter = _en(_burst(0.03, 1200, 5000, 0.003, 105))
    x = _place([(slap, 0, 1.0), (air, 0.001, 0.45), (th, 0, 0.5), (skid, 0.008, 0.3), (flutter, 0.028, 0.22)], 0.4)
    return _fit(_soften(x, 1.2), "play", 0.08)


def play_soft_place():
    pat = _en(A.lowpass(_burst(0.05, 400, 2600, 0.009, 112, attack=0.002), 3000))
    th = _en(_thump(200, 160, 0.022, seed=111, knock=0.5, knock_lp=800))
    slide = _en(_slide(0.17, [(0, 0.25), (0.25, 0.6), (1, 0.0)], lo=500, hi=3200, seed=113, bright=0.25, grit=0.12))
    x = _place([(pat, 0, 1.0), (th, 0, 0.55), (slide, 0.03, 0.6)], 0.3)
    return _fit(A.lowpass(x, 4000), "play", 0.06)


def play_tavern_slam():
    table = _en(_table_knock(121))
    slap = _en(_burst(0.06, 600, 5200, 0.009, 122))
    slap2 = _en(_burst(0.05, 800, 5000, 0.005, 123))
    x = _place([(table, 0, 1.0), (slap, 0, 0.8), (slap2, 0.04, 0.35)], 0.5)
    x = _room(_soften(x, 1.5), room=0.25, wet=0.12, damping=0.65, tail=0.4, lo=250, hi=3000)
    return _fit(x, "play", 0.25)


def play_arcane_strike():
    snap = _snap(131, center=3000, tau=0.003, dur=0.04, ring=0.3)
    slap = _burst(0.05, 600, 4000, 0.005, 132)
    parts = [(snap, 0, 0.8), (slap, 0, 0.6)]
    for i, (nm, at, g) in enumerate((("D5", 0.0, 0.7), ("A5", 0.04, 0.6), ("D6", 0.08, 0.5), ("F#6", 0.12, 0.45))):
        parts.append((_chime(_hz(nm), 0.74, tau=0.16, seed=133 + i, parts=((2.0, 0.12, 0.4), (2.76, 0.05, 0.2)),
                             strike=0.05), at, g))
    n = _n(0.74)
    t = _t(n)
    f = _hz("D6")
    glow = (np.sin(2 * np.pi * f * t) + np.sin(2 * np.pi * f * 1.003 * t) + 0.5 * np.sin(2 * np.pi * _hz("A6") * t))
    genv = (1 - np.exp(-t / 0.05)) * np.exp(-t / 0.18)
    parts.append((_tail(glow * genv, 0.35), 0.04, 0.25))
    return _fit(_place(parts, 0.88), "play", 0.12)


def play_pixel_strike():
    nz = _chip_noise([16000, 11000, 7000, 4500, 3000, 2000], [14, 11, 8, 5, 3, 1], seed=141, lp=5000)
    f = [_hz("D5"), _hz("F#5"), _hz("A5")] + [_hz("D6")] * 13
    v = [12, 12, 12, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 2, 1]
    tone = _chip(f, v, duty=0.25, lp=5000)
    return _fit(_place([(nz, 0, 0.7), (tone, 0, 0.6)]), "play", 0.03)


# ============================================================================= draw
def _draw_one(seed: int, length: float = 0.17, lo: float = 900, hi: float = 6500) -> np.ndarray:
    """One card pushed off the deck by the thumb: the push, the slide over the next card,
    the snap as it clears the deck's edge, and a soft landing in the hand."""
    push = _en(_snap(seed, center=2200, tau=0.0022, dur=0.03, ring=0.2, lp=7000))
    slide = _en(_slide(length, [(0, 0.3), (0.45, 1.0), (0.8, 0.55), (1, 0.0)], lo, hi, seed + 1,
                       bright=0.5, grit=0.25))
    edge = _en(_snap(seed + 2, center=3200, tau=0.0025, dur=0.03, ring=0.35, lp=7500))
    land = _en(A.lowpass(_snap(seed + 3, center=1500, tau=0.004, dur=0.03, ring=0.0), 3500))
    return _place([(push, 0, 0.4), (slide, 0.002, 1.0), (edge, length * 0.85, 0.32), (land, length + 0.02, 0.3)])


def draw_deck_slide():
    x = _place([(_draw_one(201), 0, 1.0), (_draw_one(211, length=0.15), 0.27, 0.9)], 0.65)
    return _fit(x, "draw", 0.05)


def draw_quiet_draw():
    push = _en(A.lowpass(_snap(221, 1500, 0.002, 0.03, ring=0.1), 3000))
    slide = _en(_slide(0.32, [(0, 0.4), (0.3, 0.8), (0.7, 0.65), (1, 0.0)], 500, 3500, 222, bright=0.3, grit=0.12))
    pat = _en(_burst(0.04, 300, 1500, 0.005, 224))
    th = _en(_thump(220, 180, 0.014, seed=223, knock=0.5, knock_lp=1000))
    x = _place([(push, 0, 0.4), (slide, 0.002, 1.0), (pat, 0.31, 0.35), (th, 0.31, 0.25)], 0.45)
    return _fit(A.lowpass(x, 4500), "draw", 0.05)


def draw_dealer():
    parts = []
    for k, t0 in enumerate((0.0, 0.14, 0.28)):
        s = 230 + 10 * k
        flick = _snap(s, center=3600, tau=0.002, dur=0.03, ring=0.4)
        slide = _slide(0.06, [(0, 0.9), (1, 0.1)], 1200, 7000, s + 1, bright=0.6, grit=0.3)
        knock = _norm(_modal(_mallet(0.12, 0.0012, s + 2), [(330, 0.7, 0.03), (494, 0.8, 0.025),
                                                              (880, 0.6, 0.018), (1350, 0.3, 0.012)]))
        slap = A.lowpass(_burst(0.04, 700, 4500, 0.0035, s + 3, attack=0.0008), 5000)
        parts += [(flick, t0, 0.6), (slide, t0 + 0.002, 0.35), (slap, t0 + 0.075, 0.7), (knock, t0 + 0.075, 0.5)]
    x = _place(parts, 0.55)
    x = _room(_soften(x, 1.5), room=0.22, wet=0.12, damping=0.6, tail=0.35, lo=250, hi=3000)
    return _fit(x, "draw", 0.2)


def draw_fairy():
    swish = A.lowpass(_slide(0.28, [(0, 0.45), (0.3, 1.0), (1, 0.0)], 1500, 7000, 241, bright=0.6, grit=0.05), 7500)
    parts = [(swish, 0, 0.35)]
    for i, (nm, at, g) in enumerate((("D6", 0.0, 0.55), ("E6", 0.055, 0.5), ("F#6", 0.11, 0.5), ("A6", 0.165, 0.55))):
        parts.append((_chime(_hz(nm), 0.55, 0.12, seed=242 + i), at, g))
    parts += _glitter(249, 9, 0.03, 0.42)
    x = _place(parts, 0.7)
    x = _room(x, room=0.3, wet=0.12, damping=0.5, tail=0.4, lo=400, hi=6000)
    return _fit(x, "draw", 0.2)


def draw_pixel():
    def bloop(f0, f1):
        n_glide = _n(0.05)
        f = np.concatenate([f0 * (f1 / f0) ** np.linspace(0, 1, n_glide), np.full(_n(0.2), f1)])
        return _chip(f, [10, 10, 10, 8, 6, 4, 2, 1], duty=0.5, lp=4500)
    x = _place([(bloop(_hz("A4"), _hz("A5")), 0, 0.9), (bloop(_hz("D5"), _hz("D6")), 0.13, 0.8)])
    return _fit(x, "draw", 0.03)


# ============================================================================= shuffle
def shuf_riffle():
    rif = _riffle(46, 0.6, 301, centers=(3100, 2500), rustle=0.15)
    bridge = _cascade(0.26, 48, 311, center=2000)
    tap = _deck_tap(312)
    x = _place([(rif, 0, 1.0), (bridge, 0.72, 0.7), (tap, 1.06, 0.8)], 1.4)
    return _fit(x, "shuffle", 0.1)


def shuf_overhand():
    rng = np.random.default_rng(321)
    parts = [(_en(A.lowpass(_snap(339, 1800, 0.002, 0.02, ring=0.1), 4000)), 0, 0.3)]
    for k, t0 in enumerate((0.0, 0.2, 0.37, 0.56, 0.74, 0.95)):
        L = float(rng.uniform(0.09, 0.13))
        sl = _en(_slide(L, [(0, 0.5), (0.2, 1.0), (1, 0.0)], 600, 4200, 322 + k, bright=0.3, grit=0.15))
        pat = _en(_burst(0.03, 350, 2000, 0.004, 340 + k))
        th = _en(_thump(240, 200, 0.01, seed=330 + k, knock=0.6, knock_lp=1200))
        parts += [(sl, t0, rng.uniform(0.8, 1.0)), (pat, t0 + L * 0.9, 0.4), (th, t0 + L * 0.9, 0.25)]
    x = _place(parts, 1.15)
    return _fit(A.lowpass(x, 4500), "shuffle", 0.06)


def shuf_tavern():
    rif = _riffle(40, 0.48, 341, centers=(3300, 2700), rustle=0.12)
    k1 = _table_knock(342, 1.0)
    k2 = _table_knock(343, 1.02)
    x = _place([(rif, 0, 1.0), (k1, 0.62, 0.8), (k2, 0.80, 0.7)], 1.1)
    x = _room(_soften(x, 1.4), room=0.25, wet=0.12, damping=0.65, tail=0.4, lo=250, hi=3000)
    return _fit(x, "shuffle", 0.25)


def shuf_fairy():
    rng = np.random.default_rng(351)
    parts = []
    for i in range(26):
        t0 = 0.0 if i == 0 else float(rng.uniform(0.0, 0.75))
        sw = math.sin(math.pi * min(1.0, t0 / 0.75)) ** 0.7
        flap = A.lowpass(_burst(0.04, 1000, 4000, float(rng.uniform(0.006, 0.01)), 35200 + i, attack=0.002), 5000)
        parts.append((flap, t0, (0.35 + 0.35 * sw) * float(rng.uniform(0.7, 1.0))))
    for i, nm in enumerate(("D6", "E6", "F#6", "A6", "B6", "D7")):
        parts.append((_chime(_hz(nm), 0.5, 0.12, seed=360 + i), 0.08 * i, 0.35))
    for i, nm in enumerate(("D6", "F#6", "A6")):
        parts.append((_chime(_hz(nm), 0.85, 0.25, seed=370 + i), 0.62 + 0.012 * i, 0.45))
    x = _place(parts, 1.4)
    x = _room(x, room=0.3, wet=0.12, damping=0.5, tail=0.3, lo=400, hi=6000)
    return _fit(x, "shuffle", 0.25)


def shuf_pixel():
    # the rattle: short noise ticks on the console's quarter-frame envelope, 40 a second,
    # the two halves alternating in pitch, swelling and fading
    ticks = 22
    clocks, vols = [], []
    for i in range(ticks):
        sw = 0.55 + 0.45 * math.sin(math.pi * (i + 0.5) / ticks)
        clocks += [4000 if i % 2 == 0 else 2600] * 6
        vols += [round(10 * sw), round(4 * sw), 1, 0, 0, 0]
    vols[-1] = 1
    rattle = A.highpass(_chip_noise(clocks, vols, seed=381, lp=4000, frame=FRAME / 4), 200, 2)
    arp = [_hz(n) for n in ("D5", "F#5", "A5", "D6")]
    k = 33
    tone = _chip([arp[(i // 2) % 4] for i in range(k)], [5] * (k - 1) + [2], duty=0.125, lp=4500)
    end_v = [12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
    end = _chip([_hz("D6")] * 12, end_v, duty=0.25, lp=5000)
    end2 = _chip([_hz("A5")] * 12, [e - 1 for e in end_v[:-1]] + [1], duty=0.5, lp=5000)
    x = _place([(rattle, 0, 0.8), (tone, 0, 0.3), (end, 0.6, 0.5), (end2, 0.6, 0.35)])
    return _fit(x, "shuffle", 0.03)


# ============================================================================= discard
def disc_pile_toss():
    flick = _en(_snap(401, 2600, 0.0022, 0.03, ring=0.25))
    n = _n(0.07)
    flut = 0.5 + 0.5 * np.sin(2 * np.pi * 25 * _t(n))
    flutter = _en(_slide(0.07, flut * _curve(n, [(0, 0.8), (1, 0.3)]), 800, 4500, 402, bright=0.4, grit=0.1))
    land1 = _en(_burst(0.05, 600, 5000, 0.005, 403))
    pile = _en(_thump(260, 200, 0.016, seed=404, knock=0.6, knock_lp=1400))
    land2 = _en(_burst(0.04, 700, 5200, 0.004, 405))
    land3 = _en(_burst(0.04, 800, 5000, 0.003, 406))
    skid = _en(_slide(0.1, [(0, 0.6), (1, 0.0)], 700, 4500, 407, bright=0.35, grit=0.2))
    x = _place([(flick, 0, 0.45), (flutter, 0.004, 0.4), (land1, 0.075, 1.0), (pile, 0.075, 0.5),
                (land2, 0.1, 0.6), (land3, 0.135, 0.4), (skid, 0.08, 0.4)], 0.45)
    return _fit(_soften(x, 1.3), "discard", 0.06)


def disc_soft_drop():
    pap = _en(A.lowpass(_burst(0.06, 400, 2000, 0.01, 411, attack=0.002), 2500))
    th = _en(_thump(210, 170, 0.02, seed=412, knock=0.5, knock_lp=900))
    sigh = _en(_slide(0.15, [(0, 0.6), (1, 0.0)], 400, 2200, 413, bright=0.2, grit=0.08))
    x = _place([(pap, 0, 1.0), (th, 0, 0.6), (sigh, 0.01, 0.6)], 0.3)
    return _fit(A.lowpass(x, 3000), "discard", 0.05)


def disc_crate_drop():
    # a small wooden tray: its hollow note on D4, the panels above it on A4, F#5 and B5,
    # and one short inharmonic mode for the wood's roughness
    modes = [(294, 0.8, 0.07), (440, 0.9, 0.05), (740, 0.5, 0.035), (988, 0.35, 0.022), (1650, 0.18, 0.014)]
    parts = []
    for i, (at, g) in enumerate(((0.0, 1.0), (0.045, 0.45), (0.08, 0.2))):
        box = _en(_modal(_mallet(0.4, 0.0015, 421 + i), modes))
        slap = _en(_burst(0.05, 600, 4500, 0.004, 425 + i))
        parts += [(box, at, g), (slap, at, 0.55 * g)]
    x = _place(parts, 0.5)
    x = _room(_soften(x, 1.2), room=0.18, wet=0.1, damping=0.6, tail=0.3, lo=250, hi=3000)
    return _fit(x, "discard", 0.2)


def disc_fading_glyph():
    flick = _snap(431, 2400, 0.0025, 0.03, ring=0.2)
    slide = _slide(0.08, [(0, 0.7), (1, 0.0)], 900, 5000, 432, bright=0.35, grit=0.15)
    parts = [(flick, 0, 0.55), (slide, 0.002, 0.25)]
    # A, F, D falling: a D minor (dorian) sigh, fitting cards lost to a wound
    for i, (nm, at, tau, g) in enumerate((("A5", 0.03, 0.18, 0.55), ("F5", 0.14, 0.2, 0.5), ("D5", 0.25, 0.3, 0.55))):
        parts.append((_chime(_hz(nm), 0.6, tau, seed=433 + i), at, g))
    n = _n(0.6)
    t = _t(n)
    breath = A.bandpass(np.random.default_rng(437).standard_normal(n), 900, 3000) * (1 - np.exp(-t / 0.04)) * np.exp(-t / 0.12)
    parts.append((_tail(_norm(breath), 0.3), 0.0, 0.12))
    x = _place(parts, 0.85)
    x = _room(x, room=0.3, wet=0.12, damping=0.5, tail=0.3, lo=300, hi=5000)
    return _fit(x, "discard", 0.15)


def disc_pixel():
    nz = _chip_noise([3000, 2000, 1500, 1200, 1000], [12, 9, 6, 3, 1], seed=441, lp=5000)
    n = _n(0.22)
    f = _hz("A5") * (_hz("D4") / _hz("A5")) ** np.linspace(0, 1, n)
    tone = _chip(f, [11, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 2, 1, 1], duty=0.5, lp=4500)
    return _fit(_place([(nz, 0, 0.6), (tone, 0, 0.6)]), "discard", 0.03)


# ============================================================================= the list
C = Candidate
CANDIDATES = [
    # card_select: tiny, gentle tap feedback
    C("card_select", "card_lift", "Card lift", "A light flick of a card nudged up out of your hand.", sel_card_lift,
      ["realistic"]),
    C("card_select", "felt_tap", "Felt tap", "A soft, muffled fingertip tap on the card, barely there.", sel_felt_tap,
      ["soft"]),
    C("card_select", "oak_tick", "Oak tick", "A small dry tick, like a wooden counter set on an oak board.",
      sel_oak_tick, ["wooden"]),
    C("card_select", "glass_chime", "Glass chime", "A tiny, soft glass chime.", sel_glass_chime, ["magical"]),
    C("card_select", "pixel_blip", "Pixel blip", "A quick two-note blip from an old handheld game.", sel_pixel_blip,
      ["retro"]),
    # card_deselect: the select sounds' softer, lower cousins
    C("card_deselect", "card_tuck", "Card tuck", "The card slipping back down into your hand.", des_card_tuck,
      ["realistic"]),
    C("card_deselect", "soft_pat", "Soft pat", "An even softer, lower pat on the felt.", des_soft_pat, ["soft"]),
    C("card_deselect", "oak_tock", "Oak tock", "A lower, rounder wooden tock.", des_oak_tock, ["wooden"]),
    C("card_deselect", "glass_dip", "Glass dip", "Two tiny glass notes stepping down.", des_glass_dip, ["magical"]),
    C("card_deselect", "pixel_drop", "Pixel drop", "The two-note blip in reverse, stepping down.", des_pixel_drop,
      ["retro"]),
    # play
    C("play", "felt_slap", "Felt slap", "A card slapped down firmly on a felt table.", play_felt_slap, ["realistic"]),
    C("play", "soft_place", "Soft place", "A card laid down gently and slid into place.", play_soft_place, ["soft"]),
    C("play", "tavern_slam", "Tavern slam", "Cards slammed onto a heavy wooden tavern table, with a little room echo.",
      play_tavern_slam, ["wooden"]),
    C("play", "arcane_strike", "Arcane strike", "A card snap that bursts into a quick rising sparkle of chimes.",
      play_arcane_strike, ["magical"]),
    C("play", "pixel_strike", "Pixel strike", "A punchy retro-game crunch with a fast rising chord.",
      play_pixel_strike, ["retro"]),
    # draw
    C("draw", "deck_slide", "Deck slide", "Two cards slid off the top of the deck, one after the other.",
      draw_deck_slide, ["realistic"]),
    C("draw", "quiet_draw", "Quiet draw", "One card drawn slowly and softly.", draw_quiet_draw, ["soft"]),
    C("draw", "dealer", "Dealer's three", "Three quick cards dealt to you across a wooden table.", draw_dealer,
      ["wooden"]),
    C("draw", "fairy_draw", "Fairy draw", "A soft swish with a rising sprinkle of fairy-like chimes.", draw_fairy,
      ["magical"]),
    C("draw", "pixel_draw", "Pixel draw", "Two quick rising retro bloops, one per card.", draw_pixel, ["retro"]),
    # shuffle
    C("shuffle", "riffle_bridge", "Riffle bridge",
      "A classic riffle shuffle: the purr of cards, the bridge, and a tap to square the deck.", shuf_riffle,
      ["realistic"]),
    C("shuffle", "overhand", "Soft overhand", "A gentle overhand shuffle: soft slides of small packets of cards.",
      shuf_overhand, ["soft"]),
    C("shuffle", "tavern_riffle", "Tavern riffle",
      "A quick riffle on a wooden table, finished with two knocks to square the deck.", shuf_tavern, ["wooden"]),
    C("shuffle", "fairy_flutter", "Fairy flutter", "Cards fluttering through the air in a swirl of twinkling chimes.",
      shuf_fairy, ["magical"]),
    C("shuffle", "pixel_shuffle", "Pixel shuffle", "A retro-game shuffle: a rattle of 8-bit ticks and a rolling arpeggio.",
      shuf_pixel, ["retro"]),
    # discard
    C("discard", "pile_toss", "Pile toss", "A few cards tossed onto the discard pile.", disc_pile_toss, ["realistic"]),
    C("discard", "soft_drop", "Soft drop", "Cards let fall gently onto the pile, muffled and quiet.", disc_soft_drop,
      ["soft"]),
    C("discard", "crate_drop", "Crate drop", "Cards dropped into a hollow wooden tray.", disc_crate_drop, ["wooden"]),
    C("discard", "fading_glyph", "Fading glyph", "A soft toss as the cards fade away with three falling chimes.",
      disc_fading_glyph, ["magical"]),
    C("discard", "pixel_discard", "Pixel discard", "A retro-game falling 'bwoop' as the cards go to the pile.",
      disc_pixel, ["retro"]),
]
