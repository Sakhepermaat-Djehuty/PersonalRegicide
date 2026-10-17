"""Table and menu sounds: a button tap, a card pop-up, coins and the "not allowed" tone
(five candidates each, each one a different character: realistic, soft, wooden or
tavern-like, magical, retro 8-bit).

The pieces, all private to this file:
  _modal     struck objects (felt over wood, a wooden block, a box, glass, a bell): one
             two-pole resonator per mode, driven by a short Hann pulse whose width is
             the hardness of what strikes (a fingertip 2-3 ms, a knuckle 1-1.5 ms, a
             fingernail or a coin 0.1-0.3 ms): a softer strike excites fewer of the high
             modes, as it does in life
  _coin      a coin is a small free metal disc: modes at 1, 1.73, 2.33, 3.91 and 4.11
             times its lowest one, each a close pair (no coin is perfectly round, so each
             mode splits in two and the pair beats: the shimmer of a ringing coin). Every
             impact excites every mode by its own amount (where the coin was struck), and
             a later impact rings on top of what is still sounding
  _pluck     a plucked string (Karplus-Strong with an all-pass for exact tuning: the
             shared synth.pluck runs up to 15 cents flat on high notes)
  _svf_bp    a band-pass whose centre moves (an air swish, a card turning in the air)
  _chip      8-bit: a pulse wave whose pitch and 4-bit volume change once per 1/60 s
             frame, like an old console's sound chip, smoothed over about a millisecond
             so the steps do not click; _lfsr is the console's noise channel
Every sound starts within a millisecond or two, is mixed by each layer's share of the
energy (``_en``), ends by decaying on its own and then a short fade, and keeps its energy
below 8 kHz. Tonal parts use D major pentatonic (D E F# A B), with D dorian's F natural
once (the muted lute's "no"). Everything is seeded, so each sound is rebuilt identically.
"""
from __future__ import annotations

import math
from typing import Sequence, Tuple

import numpy as np
from scipy import signal

import synth as A
from catalog import EVENT_BY_ID, Candidate

SR = A.SR
FRAME = 1.0 / 60.0


# ----------------------------------------------------------------------------- basics
def _hz(name: str) -> float:
    return A.note_hz(name)


def _n(t: float) -> int:
    return int(round(t * SR))


def _t(n: int) -> np.ndarray:
    return np.arange(n) / SR


def _norm(x: np.ndarray) -> np.ndarray:
    p = float(np.max(np.abs(x))) if len(x) else 0.0
    return x / p if p > 0 else x


def _en(x: np.ndarray) -> np.ndarray:
    """Scale to unit energy, so mixing gains set each layer's share of the energy."""
    e = math.sqrt(float(np.sum(x ** 2)) / SR * 1000.0)
    return x / e if e > 0 else x


def _rise(n: int, attack: float) -> np.ndarray:
    """1 everywhere except a raised-cosine rise from exactly 0 over ``attack``."""
    e = np.ones(n)
    k = min(n, max(2, _n(attack)))
    e[:k] = 0.5 - 0.5 * np.cos(np.pi * np.arange(k) / k)
    return e


def _env(n: int, tau: float, attack: float = 0.0005) -> np.ndarray:
    """exp(-t / tau) after a raised-cosine rise."""
    return np.exp(-_t(n) / max(tau, 1e-5)) * _rise(n, attack)


def _curve(n: int, pts: Sequence[Tuple[float, float]]) -> np.ndarray:
    """A piecewise-linear envelope through (seconds, value) points."""
    xs, ys = zip(*pts)
    return np.interp(_t(n), xs, ys)


def _tail(x: np.ndarray, sec: float) -> np.ndarray:
    """A raised-cosine fade over the last ``sec`` (whatever still rings ends smoothly)."""
    k = min(len(x), max(2, _n(sec)))
    y = x.copy()
    y[-k:] *= 0.5 + 0.5 * np.cos(np.pi * np.linspace(0.0, 1.0, k))
    return y


def _place(parts, dur: float) -> np.ndarray:
    """Mix [(sound, at seconds, gain), ...] into one buffer."""
    buf = np.zeros(max(1, _n(dur)))
    for snd, at, g in parts:
        buf = A.mix_at(buf, snd, at, g)
    return buf


def _noise(n: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal(n)


def _band(x: np.ndarray, lo: float, hi: float, order: int = 2) -> np.ndarray:
    return A.bandpass(x, lo, hi, order)


def _loud_db(x: np.ndarray) -> float:
    """The build's loudness measure (gated RMS of 50 ms blocks)."""
    return A._rms_db(x)


def _fit(x: np.ndarray, event: str, hp: float = 25.0, margin_db: float = 1.0) -> np.ndarray:
    """Finish a sound for its event: take out DC and sub-bass, keep it inside the event's
    length (with room for the build's trim), fade whatever still rings, and, if its peak
    would sit above the master's ceiling once brought to the event's loudness, round off
    only the first instant of that attack (a fast look-ahead limiter with a 15 ms
    release), so the master's slower limiter has nothing to squeeze."""
    ev = EVENT_BY_ID[event]
    y = A.highpass(x, hp, 2) if hp else x - float(np.mean(x))
    nmax = _n(ev.max_seconds - 0.015)
    if len(y) > nmax:
        y = _tail(y[:nmax], 0.02)
    allowed = -1.0 - margin_db - ev.loudness_db       # the largest crest the master leaves alone
    for _ in range(6):
        pk = 20 * math.log10(float(np.max(np.abs(y))) + 1e-12)
        crest = pk - _loud_db(y)
        if crest <= allowed:
            break
        thr = 10 ** ((pk - (crest - allowed) - 0.3) / 20.0)
        y = A.limit(y / thr, 0.0, lookahead=0.0012, release=0.015) * thr
    return y


# ----------------------------------------------------------------------------- struck objects
def _strike(width: float) -> np.ndarray:
    """A Hann pulse ``width`` seconds wide with unit area: what strikes the object (its
    spectrum falls away above about 1 / width)."""
    k = _n(width)
    if k < 3:
        return np.array([1.0])
    w = np.hanning(k + 2)[1:-1]
    return w / w.sum()


def _reson(x: np.ndarray, f: float, t60: float) -> np.ndarray:
    """A two-pole resonator at ``f`` ringing for ``t60`` seconds (to -60 dB); an impulse
    gives a unit-amplitude damped sine."""
    w = 2 * np.pi * f / SR
    r = 10 ** (-3.0 / (max(t60, 1e-4) * SR))
    return signal.lfilter([math.sin(w)], [1.0, -2 * r * math.cos(w), r * r], x)


def _modal(dur: float, modes, width: float, hits=((0.0, 1.0),)) -> np.ndarray:
    """An object with modes [(freq, t60, gain), ...] struck at ``hits`` [(seconds, amp)]."""
    n = _n(dur)
    exc = np.zeros(n)
    for at, amp in hits:
        i = _n(at)
        if i < n:
            exc[i] += amp
    exc = np.convolve(exc, _strike(width))[:n]
    y = np.zeros(n)
    for f, t60, g in modes:
        if f < SR * 0.45:
            y += g * _reson(exc, f, t60)
    return y


def _click(dur: float, lo: float, hi: float, tau: float, seed: int) -> np.ndarray:
    """The contact noise of an impact: a breath of band-passed noise."""
    n = _n(dur)
    return _band(_noise(n, seed) * _env(n, tau, 0.0002), lo, hi)


# (ratio to the lowest mode, share of the ring time, gain): a thin free disc
_COIN = ((1.0, 1.0, 1.0), (1.73, 0.8, 0.8), (2.33, 0.65, 0.65), (3.91, 0.4, 0.3), (4.11, 0.35, 0.25))


def _coin(dur: float, hits, f1: float, t60: float, seed: int, width: float = 0.00012,
          fmax: float = 7800.0, split: float = 0.0022, hi_gain: float = 1.0) -> np.ndarray:
    """A coin whose lowest mode is ``f1``, struck at ``hits`` [(seconds, amp)]."""
    n = _n(dur)
    rng = np.random.default_rng(seed)
    k = _strike(width)
    y = np.zeros(n)
    for j, (ratio, ts, g) in enumerate(_COIN):
        f = f1 * ratio
        if f > fmax:
            continue
        if j >= 3:
            g *= hi_gain
        d = f * split * rng.uniform(0.5, 1.0)
        for ff in (f - d / 2, f + d / 2):
            exc = np.zeros(n)
            for at, amp in hits:
                i = _n(at)
                if i < n:
                    exc[i] += amp * rng.uniform(0.3, 1.0)
            y += g * _reson(np.convolve(exc, k)[:n], ff, t60 * ts)
    return y


# ----------------------------------------------------------------------------- strings, filters
def _pluck(freq: float, dur: float, t60: float = 1.0, bright: float = 0.5, seed: int = 0,
           pick: float = 0.2) -> np.ndarray:
    """Karplus-Strong: a noise burst (low-passed by ``bright``, comb-filtered by where the
    string is plucked) circulating in a delay line with a two-point average, a loss for
    the ring time and a first-order all-pass that makes up the fractional delay."""
    n = _n(dur)
    P = SR / freq
    N = int(P - 0.6)
    d = P - 0.5 - N                        # the all-pass's share of the delay, 0.1..1.1
    C = (1 - d) / (1 + d)
    g = 10 ** (-3.0 * P / (max(t60, 0.02) * SR))
    rng = np.random.default_rng(seed)
    burst = A.lowpass(rng.uniform(-1, 1, N), 300 + 7000 * bright, 1)
    m = max(1, int(N * pick))
    burst = burst - np.concatenate([np.zeros(m), burst[:-m]])
    burst = (burst - burst.mean()) * _rise(N, 0.0008)
    x = np.zeros(n)
    x[:min(N, n)] = burst[:n]
    xs = x.tolist()
    y = [0.0] * n
    lp = 0.0
    ax = 0.0
    ay = 0.0
    for i in range(n):
        v = y[i - N] if i >= N else 0.0
        w = 0.5 * (v + lp)
        lp = v
        a = C * w + ax - C * ay
        ax = w
        ay = a
        y[i] = xs[i] + g * a
    return np.asarray(y)


def _svf_bp(x: np.ndarray, fc, q: float = 1.0) -> np.ndarray:
    """A band-pass (state-variable, unity gain at the centre) whose centre ``fc`` may move
    sample by sample."""
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


def _partials(f: float, dur: float, parts, attack: float = 0.001, phase_seed: int = 0) -> np.ndarray:
    """A sum of decaying sines [(ratio, gain, t60), ...] above ``f``, each after a short
    rise; anything above 7.8 kHz is left out."""
    n = _n(dur)
    t = _t(n)
    rng = np.random.default_rng(phase_seed)
    y = np.zeros(n)
    for ratio, gain, t60 in parts:
        ff = f * ratio
        if ff > 7800.0:
            continue
        y += gain * np.sin(2 * np.pi * ff * t + rng.uniform(0, 0.4)) * np.exp(-6.9078 * t / t60)
    return y * _rise(n, attack)


# ----------------------------------------------------------------------------- 8-bit
def _chip(frames, duty: float = 0.5, smooth: float = 0.001, after: float = 0.02) -> np.ndarray:
    """A console pulse channel: ``frames`` is [(hz, volume 0..15), ...], one per 1/60 s.
    The pitch carries on through silent frames so the phase never jumps."""
    nf = len(frames)
    nb = _n(nf * FRAME)
    n = nb + _n(after)
    f = np.array([fr[0] for fr in frames], float)
    v = np.array([fr[1] for fr in frames], float) / 15.0
    for i in range(1, nf):
        if f[i] <= 0:
            f[i] = f[i - 1]
    f[f <= 0] = f[f > 0][0]
    idx = np.minimum((np.arange(n) / (FRAME * SR)).astype(int), nf - 1)
    freq = f[idx]
    vol = v[idx]
    vol[nb:] = 0.0
    a = math.exp(-1.0 / (smooth * SR))
    vol = signal.lfilter([1 - a], [1, -a], vol)
    dur = n / SR
    if abs(duty - 0.5) < 1e-6:
        wave = A.osc("square", freq, dur)
    else:
        wave = 0.5 * (A.osc("saw", freq, dur) - A.osc("saw", freq, dur, 2 * np.pi * duty))
    return wave * vol


def _lfsr(n: int, clock: float, seed: int = 1) -> np.ndarray:
    """A console noise channel: a 15-bit shift register clocked ``clock`` times a second."""
    reg = (seed * 7919) & 0x7FFF or 1
    steps = int(n * clock / SR) + 2
    out = np.empty(steps)
    for i in range(steps):
        fb = (reg ^ (reg >> 1)) & 1
        reg = (reg >> 1) | (fb << 14)
        out[i] = 1.0 if reg & 1 else -1.0
    return out[(np.arange(n) * clock / SR).astype(int)]


# ============================================================================= button
def _btn_felt() -> np.ndarray:
    """A fingertip on the felt-covered table: a soft, damped knock of the board under the
    cloth (190-660 Hz) and the muffled pat of skin on felt."""
    dur = 0.075
    n = _n(dur)
    body = _modal(dur, [(190.0, 0.07, 0.6), (_hz("F#4"), 0.05, 1.0), (660.0, 0.03, 0.45),
                        (1180.0, 0.018, 0.12)], 0.0024)
    pat = _band(_noise(n, 11), 300, 1800) * _env(n, 0.0045, 0.0003)
    y = _en(body) + 0.5 * _en(pat)
    return _tail(A.lowpass(y, 3200, 1), 0.02)


def _btn_wood() -> np.ndarray:
    """A small wooden block tapped with a fingernail: a bar's modes (1, 2.76, 5.4) on D5,
    the table's D4 below, and the nail's tiny click."""
    dur = 0.09
    n = _n(dur)
    f = _hz("D5")
    body = _modal(dur, [(f, 0.075, 1.0), (f * 2.76, 0.04, 0.4), (f * 5.4, 0.02, 0.12),
                        (_hz("D4"), 0.055, 0.3)], 0.0008)
    click = _band(_noise(n, 12), 1500, 4500) * _env(n, 0.0008, 0.0002)
    return _tail(_en(body) + 0.25 * _en(click), 0.025)


def _btn_drop() -> np.ndarray:
    """A water drop: a sine whose pitch springs up (the bubble shrinking) to F#6."""
    dur = 0.075
    n = _n(dur)
    t = _t(n)
    f0, f1 = 820.0, _hz("F#6")
    f = f0 * (f1 / f0) ** np.clip(t / 0.02, 0.0, 1.0)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.013, 0.0006)
    return _tail(y, 0.015)


def _btn_crystal() -> np.ndarray:
    """A fingernail on a small crystal glass: glass modes (1, 2.32, 4.25) on D6."""
    dur = 0.14
    n = _n(dur)
    f = _hz("D6")
    ring = _modal(dur, [(f, 0.12, 1.0), (f * 2.32, 0.07, 0.3), (f * 4.25, 0.035, 0.1)], 0.0003)
    tick = _band(_noise(n, 14), 3000, 7000) * _env(n, 0.0006, 0.0001)
    return _tail(_en(ring) + 0.15 * _en(tick), 0.03)


def _btn_chip() -> np.ndarray:
    """An 8-bit blip: one frame of A5, then D6 stepping down in volume."""
    frames = [(_hz("A5"), 9), (_hz("D6"), 8), (_hz("D6"), 5), (_hz("D6"), 2)]
    return A.lowpass(_chip(frames, duty=0.25), 4500, 2)


# ============================================================================= popup
def _pop_flip() -> np.ndarray:
    """A card flipped over onto the felt: the thumb lets the edge go (a flick and the
    card's own brief ring), the card turns in the air (a band of noise that rises and
    falls), then lands flat (a paper slap and a soft low thump) and settles."""
    dur = 0.36
    nf = _n(0.03)
    flick = _band(_noise(nf, 21), 2200, 6500) * _env(nf, 0.0025, 0.0002)
    card = _modal(0.04, [(2950.0, 0.03, 1.0), (1720.0, 0.04, 0.7)], 0.0003)
    m = _n(0.14)
    tt = np.linspace(0.0, 1.0, m)
    fc = 700.0 * (1700.0 / 700.0) ** np.sin(np.pi * tt * 0.85)
    grain = 0.65 + 0.35 * A.lowpass(np.random.default_rng(22).uniform(-1, 1, m), 150, 1) * 2.5
    air = _svf_bp(_noise(m, 22), fc, 1.4) * np.sin(np.pi * tt) ** 1.3 * np.clip(grain, 0.2, 1.2)
    ns = _n(0.06)
    slap = _band(_noise(ns, 23), 450, 4000) * _env(ns, 0.006, 0.0004)
    thump = _modal(0.15, [(165.0, 0.12, 0.8), (_hz("F#4"), 0.07, 1.0), (720.0, 0.04, 0.3)], 0.002)
    nst = _n(0.05)
    settle = A.paper(0.05, 1500, 6000, seed=24, grain=0.7) * _curve(nst, [(0, 0), (0.004, 1), (0.05, 0)])
    land = 0.13
    y = _place([(_en(flick), 0.0, 0.55), (_en(card), 0.0, 0.18), (_en(air), 0.004, 0.75),
                (_en(slap), land, 0.8), (_en(thump), land, 0.6), (_en(settle), land + 0.012, 0.2)], dur)
    return _tail(y, 0.06)


def _pop_swish() -> np.ndarray:
    """A soft airy swish rising in pitch (pink noise through a moving band) with a light
    two-note glass tone, A5 then D6, each a slightly detuned pair that shimmers."""
    dur = 0.62
    m = _n(0.3)
    tt = _t(m)
    fc = 450.0 * (2600.0 / 450.0) ** np.clip(tt / 0.26, 0.0, 1.0)
    sw = _svf_bp(A.noise(0.3, "pink", 31), fc, 1.3)
    env = _curve(m, [(0, 0.35), (0.06, 1.0), (0.14, 0.55), (0.29, 0.0), (0.3, 0.0)])
    env = A.lowpass(env, 40, 1) * _rise(m, 0.002)
    sw = sw * env

    def tone(f: float) -> np.ndarray:
        nt = _n(0.58)
        t = _t(nt)
        y = np.sin(2 * np.pi * (f - 1.2) * t) + np.sin(2 * np.pi * (f + 1.2) * t + 0.7)
        y += 0.12 * np.sin(2 * np.pi * 2 * f * t)
        return y * np.exp(-6.9078 * t / 0.5) * _rise(nt, 0.003)

    y = _place([(_en(sw), 0.0, 1.0), (_en(tone(_hz("A5"))), 0.0, 0.7), (_en(tone(_hz("D6"))), 0.05, 0.6)],
               dur)
    return _tail(y, 0.12)


def _pop_parchment() -> np.ndarray:
    """A sheet of parchment unrolled on the table (a grainy rustle, the crackle of its
    fibres and a soft flump as it settles), over a soft lute strum of A4 and D5."""
    dur = 0.66
    rng = np.random.default_rng(41)
    m = _n(0.3)
    bed = A.paper(0.3, 1100, 5500, seed=42, grain=0.85)
    bed = bed * _curve(m, [(0, 0.0), (0.003, 0.8), (0.12, 1.0), (0.22, 0.5), (0.3, 0.0)])
    imp = np.zeros(m)
    t = 0.002
    while t < 0.26:
        imp[_n(t)] += rng.uniform(0.3, 1.0) * rng.choice([-1.0, 1.0])
        t += rng.exponential(0.006 + 0.04 * t)
    crack = _band(imp, 1500, 6000)
    nfl = _n(0.12)
    flump = _en(_modal(0.12, [(160.0, 0.08, 1.0), (330.0, 0.05, 0.6)], 0.003)) + \
        0.5 * _en(A.lowpass(_noise(nfl, 43), 1200, 2) * _env(nfl, 0.018, 0.002))
    lute = _place([(_pluck(_hz("A4"), 0.62, 0.55, 0.35, seed=44), 0.0, 1.0),
                   (_pluck(_hz("D5"), 0.6, 0.6, 0.35, seed=45), 0.022, 0.9)], 0.64)
    lute = A.peak_eq(lute, 260, 3, 1.0)
    y = _place([(_en(bed), 0.0, 0.75), (_en(crack), 0.0, 0.45), (_en(flump), 0.2, 0.35),
                (_en(lute), 0.0, 0.8)], dur)
    return _tail(y, 0.12)


def _pop_fairy() -> np.ndarray:
    """Tiny glass bells rising D6, F#6, A6, D7 with a few high glints and an airy breath,
    in a small room."""
    dur = 0.56
    bells = []
    for k, (nm, amp) in enumerate([("D6", 0.75), ("F#6", 0.8), ("A6", 0.9), ("D7", 1.0)]):
        f = _hz(nm)
        b = _partials(f, 0.5, [(1.0 - 0.0012, 0.55, 0.42), (1.0 + 0.0012, 0.55, 0.42),
                               (2.32, 0.16, 0.18), (4.25, 0.05, 0.08)], 0.0008, 50 + k)
        bells.append((_en(b), 0.048 * k, amp))
    rng = np.random.default_rng(51)
    glints = []
    for k in range(9):
        f = _hz(str(rng.choice(["D7", "E7", "F#7", "A7"])))
        ng = _n(0.06)
        g = np.sin(2 * np.pi * f * _t(ng)) * _env(ng, 0.012, 0.0005)
        glints.append((_en(g), 0.03 + rng.uniform(0, 0.3), 0.12 * rng.uniform(0.5, 1.0)))
    na = _n(0.35)
    air = _band(_noise(na, 52), 2500, 6500) * _curve(na, [(0, 0.2), (0.12, 1.0), (0.35, 0.0)])
    y = _place(bells + glints + [(_en(air), 0.0, 0.12)], dur - 0.15)
    y = A.reverb(y, room=0.3, wet=0.2, damping=0.6, tail=0.15)
    return _tail(y[:_n(dur)], 0.14)


def _pop_pixel() -> np.ndarray:
    """An 8-bit menu window sliding open: a pitch sweep up from A4 (with a puff of the
    noise channel), then a little chime of D6 over A5 that fades in steps."""
    sweep = [440.0 * 2 ** (k / 5.0) for k in range(6)]          # A4 up to A5 in six frames
    ding = [15, 13, 11, 10, 9, 8, 7, 6, 5, 5, 4, 3, 3, 2, 2, 1, 1]
    ch1 = [(f, 10) for f in sweep] + [(_hz("D6"), v) for v in ding]
    ch2 = [(0.0, 0)] * 6 + [(_hz("A5"), max(0, v // 2)) for v in ding]
    y = _chip(ch1, duty=0.5) + 0.8 * _chip(ch2, duty=0.25)
    nn = _n(4 * FRAME)
    nz = A.lowpass(_lfsr(nn, 9000.0, 3), 6000, 2) * np.repeat([0.25, 0.18, 0.1, 0.05], _n(FRAME) + 1)[:nn]
    nz = A.lowpass(nz, 6000, 1)
    y = _place([(y, 0.0, 1.0), (nz, 0.0, 1.0)], len(y) / SR)
    return A.lowpass(y, 5500, 2)


# ============================================================================= coin
def _coin_single() -> np.ndarray:
    """One gold coin dropped on the wooden table: it strikes, bounces ever faster, wobbles
    flat with a quickening chatter and is left ringing, damped by the table."""
    dur = 1.12
    n = _n(dur)
    hits = [(0.0, 1.0)]
    t, T, a = 0.0, 0.12, 1.0
    for _ in range(6):
        t += T
        T *= 0.6
        a *= 0.62
        hits.append((t, a))
    gap = 0.034
    a = 0.3
    for _ in range(10):
        t += gap
        gap *= 0.84
        a *= 0.86
        hits.append((t, a))
    flat = t
    ring = _coin(dur, hits, _hz("A6"), 0.9, seed=61)
    # once flat on the table, the wood damps the ring
    tt = _t(n)
    damp = np.exp(-np.clip(tt - flat, 0.0, None) / 0.16)
    ring = ring * damp
    tock = _modal(dur, [(430.0, 0.03, 1.0), (980.0, 0.02, 0.5)], 0.0004, hits)
    clicks = np.zeros(n)
    for k, (at, amp) in enumerate(hits):
        clicks = A.mix_at(clicks, _click(0.01, 2000, 7000, 0.0005, 70 + k), at, amp)
    clicks = clicks[:n]
    y = _en(ring) + 0.12 * _en(tock) + 0.06 * _en(clicks)
    return _tail(y, 0.08)


def _coin_purse() -> np.ndarray:
    """A leather purse of coins set down: a soft heavy thud and a crunch of leather, while
    the coins inside clink against each other and settle (muffled a little)."""
    dur = 0.9
    rng = np.random.default_rng(81)
    thud = _modal(0.3, [(110.0, 0.14, 0.8), (230.0, 0.09, 1.0), (480.0, 0.045, 0.4)], 0.004)
    nc = _n(0.14)
    crunch = A.paper(0.14, 250, 2200, seed=82, grain=0.9) * _env(nc, 0.03, 0.001)
    sizes = [_hz("F#6"), _hz("A6"), _hz("B6"), _hz("D7")]
    clinks = []
    t = 0.001
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
    coins = A.lowpass(_place(clinks, dur), 5000, 1)
    y = _place([(_en(thud), 0.0, 0.5), (_en(crunch), 0.0, 0.4), (_en(coins), 0.0, 1.0)], dur)
    return _tail(y, 0.15)


def _coin_count() -> np.ndarray:
    """Three coins counted onto the tavern table, one after another: each lands with a
    knock of the wooden board and a short clink, the second and third onto the first."""
    dur = 0.82
    times = [0.0, 0.19, 0.37]
    parts = []
    for k, at in enumerate(times):
        knock = _modal(0.12, [(260.0, 0.07, 1.0), (590.0, 0.045, 0.6), (1130.0, 0.025, 0.3)], 0.0006)
        if k == 0:
            clink = _coin(0.42, [(0.0, 1.0)], _hz("B6"), 0.3, seed=91)
        else:      # onto the coins already there: two coins ring, a little brighter
            clink = _coin(0.42, [(0.0, 1.0)], _hz("B6") * (1 + 0.004 * k), 0.26, seed=91 + k) + \
                0.6 * _coin(0.42, [(0.0, 1.0)], _hz("B6"), 0.2, seed=95 + k)
        cl = _click(0.01, 1500, 6000, 0.0006, 97 + k)
        g = [0.9, 0.95, 1.0][k]
        parts += [(_en(knock), at, 0.55 * g), (_en(clink), at, 0.9 * g), (_en(cl), at, 0.08 * g)]
    return _tail(_place(parts, dur), 0.12)


def _coin_sparkle() -> np.ndarray:
    """A bright magic "ching" (A6 and D7 together), then a shower of small bells falling
    through D major pentatonic, like coins of light."""
    dur = 1.12
    chime = [(1.0 - 0.001, 0.5, 0.6), (1.0 + 0.001, 0.5, 0.6), (2.0, 0.12, 0.3), (2.76, 0.06, 0.15)]
    notes = [(0.0, "A6", 1.0), (0.0, "D7", 0.9), (0.075, "B6", 0.55), (0.13, "F#6", 0.5),
             (0.18, "A6", 0.45), (0.235, "E6", 0.4), (0.28, "D6", 0.36), (0.33, "F#6", 0.3),
             (0.385, "E6", 0.25), (0.44, "D6", 0.22)]
    parts = []
    for k, (at, nm, amp) in enumerate(notes):
        b = _partials(_hz(nm), 0.75, chime, 0.0006, 300 + k)
        parts.append((_en(b), at, amp))
    rng = np.random.default_rng(311)
    for k in range(10):
        f = _hz(str(rng.choice(["D7", "E7", "F#7", "A7"])))
        ng = _n(0.05)
        g = np.sin(2 * np.pi * f * _t(ng)) * _env(ng, 0.01, 0.0004)
        parts.append((_en(g), rng.uniform(0.02, 0.45), 0.1 * rng.uniform(0.5, 1.0)))
    y = _place(parts, dur - 0.2)
    y = A.reverb(y, room=0.35, wet=0.18, damping=0.55, tail=0.2)
    return _tail(y[:_n(dur)], 0.2)


def _coin_pixel() -> np.ndarray:
    """An 8-bit coin: a short A5, then a long D6 that fades in console volume steps."""
    frames = [(_hz("A5"), 13)] * 4 + [(_hz("D6"), max(0, 14 - k // 2)) for k in range(28)]
    return A.lowpass(_chip(frames, duty=0.25, after=0.03), 6000, 2)


# ============================================================================= error
def _hum_note(f: float, dur: float, droop: float = 0.0) -> np.ndarray:
    n = _n(dur)
    t = _t(n)
    freq = f * (1.0 - droop * np.clip((t - dur * 0.4) / (dur * 0.6), 0.0, 1.0))
    ph = 2 * np.pi * np.cumsum(freq) / SR
    y = sum(h * np.sin(k * ph) for k, h in enumerate([1.0, 0.55, 0.3, 0.16, 0.08, 0.04], start=1))
    rel = _n(0.07)
    env = _rise(n, 0.004)
    env[-rel:] *= 0.5 + 0.5 * np.cos(np.pi * np.linspace(0.0, 1.0, rel))
    return y * env


def _err_hum() -> np.ndarray:
    """A soft hummed "mm-mm": A3 then F#3 (a falling minor third), warm and closed."""
    y = _place([(_hum_note(_hz("A3"), 0.15), 0.0, 1.0),
                (_hum_note(_hz("F#3"), 0.25, droop=0.012), 0.19, 0.95)], 0.48)
    y = A.peak_eq(y, 280, 3, 1.0)
    return A.lowpass(y, 1500, 2)


def _err_knock() -> np.ndarray:
    """Two knuckle knocks on a hollow wooden box, the second deeper: the box's air
    (A3, then E3) and its wooden walls."""
    def knock(f0: float, seed: int) -> np.ndarray:
        body = _modal(0.4, [(f0, 0.17, 1.0), (f0 * 2.42, 0.08, 0.55), (f0 * 4.1, 0.05, 0.3),
                            (f0 * 6.3, 0.03, 0.15)], 0.0013)
        return _place([(_en(body), 0.0, 1.0), (_en(_click(0.02, 700, 3000, 0.002, seed)), 0.0, 0.18)], 0.4)

    y = _place([(knock(_hz("A3"), 121), 0.0, 1.0), (knock(_hz("E3"), 122), 0.17, 1.0)], 0.56)
    return _tail(y, 0.08)


def _err_lute() -> np.ndarray:
    """Two low lute notes muted by the palm, F3 then D3: a shrugging "nuh-uh"."""
    def note(f: float, seed: int) -> np.ndarray:
        s = _pluck(f, 0.42, 0.22, 0.28, seed=seed, pick=0.22)
        s = A.peak_eq(s, 220, 4, 1.2)
        n = len(s)
        thumb = A.lowpass(_noise(n, seed + 7), 1200, 2) * _env(n, 0.003, 0.0003)
        return _en(s) + 0.12 * _en(thumb)

    y = _place([(note(_hz("F3"), 131), 0.0, 1.0), (note(_hz("D3"), 132), 0.17, 1.05)], 0.58)
    return _tail(A.lowpass(y, 2500, 1), 0.1)


def _err_chime() -> np.ndarray:
    """Two soft, dark bells, D5 then B4 (with a bell's hum, minor-third and fifth tones),
    and the faint fading hiss of a spell that did not take."""
    bell = [(0.5, 0.35, 0.7), (1.0, 1.0, 0.5), (1.0 + 0.002, 0.5, 0.5), (2 ** (3 / 12), 0.3, 0.35),
            (1.5, 0.12, 0.25), (2.0, 0.15, 0.2)]
    b1 = _partials(_hz("D5"), 0.42, bell, 0.002, 141)
    b2 = _partials(_hz("B4"), 0.44, bell, 0.002, 142)
    m = _n(0.2)
    tt = _t(m)
    fz = _svf_bp(_noise(m, 143), 2400.0 * (600.0 / 2400.0) ** (tt / 0.2), 2.0)
    fz = fz * _curve(m, [(0, 0.0), (0.01, 1.0), (0.2, 0.0)])
    y = _place([(_en(b1), 0.0, 1.0), (_en(b2), 0.16, 1.0), (_en(fz), 0.17, 0.18)], 0.6)
    return _tail(A.lowpass(y, 4000, 1), 0.1)


def _err_pixel() -> np.ndarray:
    """An 8-bit "uh-uh": two low square notes, A3 then D3, softened."""
    frames = [(_hz("A3"), v) for v in (11, 11, 10, 9, 8, 7)] + [(_hz("A3"), 0)] * 2 + \
        [(_hz("D3"), v) for v in (11, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1)]
    return A.lowpass(_chip(frames, duty=0.5), 1400, 2)


# ============================================================================= candidates
def _fx(event: str, fn, hp: float = 25.0):
    return lambda: _fit(fn(), event, hp)


CANDIDATES = [
    Candidate("button", "felt_tap", "Felt tap", "A muffled fingertip tap on the felt table.",
              _fx("button", _btn_felt), ["realistic", "soft"]),
    Candidate("button", "wood_tick", "Wood tick", "A tiny dry knock on a small wooden block.",
              _fx("button", _btn_wood), ["wooden", "tavern"]),
    Candidate("button", "droplet", "Droplet", "A single round water-drop plip.",
              _fx("button", _btn_drop), ["soft", "round"]),
    Candidate("button", "crystal_tap", "Crystal tap", "A tiny tap on a crystal glass, quickly hushed.",
              _fx("button", _btn_crystal), ["magical", "chime"]),
    Candidate("button", "pixel_blip", "Pixel blip", "A short, soft 8-bit beep, like an old handheld.",
              _fx("button", _btn_chip, hp=0), ["retro", "8-bit"]),

    Candidate("popup", "card_flip", "Card flip", "A card flipped over and landing softly on the felt.",
              _fx("popup", _pop_flip), ["realistic", "paper"]),
    Candidate("popup", "soft_swish", "Soft swish", "A gentle airy swish with a light glassy two-note tone.",
              _fx("popup", _pop_swish), ["soft", "airy"]),
    Candidate("popup", "parchment", "Parchment", "A sheet of parchment unrolls over a soft lute strum.",
              _fx("popup", _pop_parchment), ["tavern", "paper"]),
    Candidate("popup", "fairy_reveal", "Fairy reveal", "Tiny bells rise in a sparkle, like magic revealing a card.",
              _fx("popup", _pop_fairy), ["magical", "chime"]),
    Candidate("popup", "pixel_window", "Pixel window", "An 8-bit menu window slides open with a little chime.",
              _fx("popup", _pop_pixel, hp=0), ["retro", "8-bit"]),

    Candidate("coin", "gold_coin", "Gold coin", "One gold coin dropped on the table: it rings, bounces and settles.",
              _fx("coin", _coin_single), ["realistic", "metal"]),
    Candidate("coin", "coin_purse", "Coin purse", "A leather purse of coins set down with a heavy jingle.",
              _fx("coin", _coin_purse), ["realistic", "purse"]),
    Candidate("coin", "counting", "Counting coins", "Three coins counted onto the tavern table: clink, clink, clink.",
              _fx("coin", _coin_count), ["tavern", "wooden"]),
    Candidate("coin", "gold_sparkle", "Gold sparkle", "A bright magic ching and a shower of little bells.",
              _fx("coin", _coin_sparkle), ["magical", "chime"]),
    Candidate("coin", "pixel_coin", "Pixel coin", "A cheerful 8-bit coin pickup: a quick two-note ping.",
              _fx("coin", _coin_pixel, hp=0), ["retro", "8-bit"]),

    Candidate("error", "low_hum", "Low hum", "A gentle low two-note hum, like a polite 'mm-mm'.",
              _fx("error", _err_hum), ["soft"]),
    Candidate("error", "hollow_knock", "Hollow knock", "Two knocks on a hollow wooden box, the second deeper.",
              _fx("error", _err_knock), ["wooden", "realistic"]),
    Candidate("error", "muted_lute", "Muted lute", "Two muted low lute notes stepping down, like a shrug.",
              _fx("error", _err_lute), ["tavern", "string"]),
    Candidate("error", "dim_bells", "Dim bells", "Two soft, dark bells falling, like a spell that fizzles.",
              _fx("error", _err_chime), ["magical", "bell"]),
    Candidate("error", "pixel_no", "Pixel no", "A low, soft 8-bit 'uh-uh': two square notes going down.",
              _fx("error", _err_pixel, hp=0), ["retro", "8-bit"]),
]
