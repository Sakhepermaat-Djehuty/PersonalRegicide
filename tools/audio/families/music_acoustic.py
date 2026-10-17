"""Acoustic medieval music loops: a tavern jig, a bard's ballad and a harp hall.

Each track is written out note by note (a small text notation, checked bar by bar), played
by instruments built here, mixed in one shared room and folded into a loop with no seam.

Instruments, all private to this file:
  _pluck     a plucked string as a sum of its partials (exactly in tune: the shared
             synth.pluck runs 7-15 cents flat from A4 up, which would clash with a recorder
             or a fiddle). Each partial's level comes from where the string is plucked and
             how hard; its ring time shortens with frequency (the highs die first, as on gut
             or nylon); a small stretch of the upper partials (string stiffness); a quick
             first decay into a longer one (the two ways a string swings). A lute's courses
             are pairs of strings a hair apart (they beat gently); its bass courses carry an
             octave string. A touch of finger or quill noise at the start.
  _voice     a wind or bowed line rendered phrase by phrase, so notes join as on the real
             instrument: one continuous tone whose pitch moves note to note (a quick finger
             change, or a fiddler's slide on a leap), with tonguing or bow changes as short
             dips, a chiff of breath at each tongued note, delayed vibrato on long notes,
             a slow wander of pitch and breath. The recorder is nearly pure (a weak 2nd and
             3rd harmonic plus breath); the fiddle is a bowed sawtooth whose harmonics move
             through a fixed body resonance as the vibrato swings (the real violin shimmer).
  _bowed     soft ensemble strings for a pad: detuned bowed voices, each with its own
             vibrato, slow bow, dark filter.
  _drone     a hurdy-gurdy-like drone on D and A, breathing slowly.
  _drum      a frame drum (bodhran) as a circular membrane: its inharmonic modes
             (1, 1.59, 2.14, 2.30 ...), a strike in the middle (low and round) or near the
             rim (higher, papery), the skin's pitch settling as the hit dies, a soft tipper
             tap.
  _ir        a room as a synthetic impulse response (early reflections, then a diffuse
             tail whose highs die sooner than its lows, different in each ear), shared by
             every instrument of a track, applied by convolution.

Every track loops seamlessly: whatever rings past the loop's end (notes, the room) is
folded back onto its start, exactly as it would sound the second time round; slow tempo
breathing (rubato) is periodic within each phrase, so the loop keeps its exact length.
All tonal material is in D: the jig and the harp hall in D major (the harp hall's middle in
A mixolydian, the same notes), the ballad in D dorian. Everything is seeded.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import signal

import synth as A
from catalog import Candidate

SR = A.SR


# ----------------------------------------------------------------------------- basics
def _n(t: float) -> int:
    return int(round(t * SR))


def _mhz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12.0)


def _smoothstep(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def _slow_noise(n: int, rate_hz: float, seed: int) -> np.ndarray:
    """Smooth random wander in about -1..1, changing about ``rate_hz`` times a second."""
    rng = np.random.default_rng(seed)
    k = max(4, int(n / SR * rate_hz) + 4)
    pts = rng.uniform(-1, 1, k)
    xp = np.linspace(0, n, k)
    y = np.interp(np.arange(n), xp, pts)
    return A.lowpass(y, max(rate_hz, 0.05), 1) * 1.6 if n > 8 else y


def _loud(x: np.ndarray) -> float:
    return A._rms_db(x)


def _to_db(x: np.ndarray, target_db: float) -> np.ndarray:
    """Scale a stem to a gated-RMS level, so each part's share of the mix is set in dB."""
    cur = _loud(x)
    return x * 10 ** ((target_db - cur) / 20.0)


# ----------------------------------------------------------------------------- notation
SCALE_D_MAJOR = {2, 4, 6, 7, 9, 11, 1}       # pitch classes D E F# G A B C#
SCALE_D_DORIAN = {2, 4, 5, 7, 9, 11, 0}      # D E F G A B C


def _parse(text: str, bar: float, start: float = 0.0) -> Tuple[list, float]:
    """'F#5:3 E5:1 | r:2 ...' -> [(start, length, midi, flags)] in units, and the end.
    '|' marks a bar line: every bar must add up to ``bar`` units (a typo shows at once).
    A trailing '^' on a note asks for a cut (a flick of the next scale note above, as
    pipers and whistlers ornament), '~' for a slur into the note."""
    out = []
    pos = start
    bar_start = start
    for tok in text.split():
        if tok == "|":
            if abs((pos - bar_start) - bar) > 1e-9:
                raise ValueError("bar of %.3f units before %r at %.1f" % (pos - bar_start, text[:30], pos))
            bar_start = pos
            continue
        flags = set()
        while tok[-1] in "^~":
            flags.add(tok[-1])
            tok = tok[:-1]
        p, l = tok.split(":")
        length = float(l)
        if p != "r":
            out.append((pos, length, A.midi(p), flags))
        pos += length
    if abs((pos - bar_start) - bar) > 1e-9:
        raise ValueError("last bar of %.3f units in %r" % (pos - bar_start, text[:30]))
    return out, pos


def _scale_up(m: int, scale: set) -> int:
    k = m + 1
    while k % 12 not in scale:
        k += 1
    return k


class Clock:
    """Units (eighth notes) to seconds: a steady pulse, an optional jig lilt (the first
    of each three eighths a little long) and optional rubato, a gentle push and pull that
    repeats every phrase (its average is the steady tempo, so the loop's length is exact)."""

    def __init__(self, unit_s: float, lilt: Sequence[float] = (), rubato: float = 0.0,
                 phrase_units: float = 24.0, peak_at: float = 0.9):
        self.u = unit_s
        self.lilt = list(lilt)
        self.rub = rubato
        self.P = phrase_units
        self.peak = peak_at

    def __call__(self, units: float) -> float:
        u = float(units)
        if self.lilt:
            g = math.floor(u / 3.0)
            j = u - 3 * g
            xs = [0.0, 1.0, 2.0, 3.0]
            ys = [0.0, 1.0 + self.lilt[0], 2.0 + self.lilt[1], 3.0]
            u = 3 * g + float(np.interp(j, xs, ys))
        if self.rub:
            # d(time)/d(unit) = 1 + r cos(2 pi (u/P - peak)): slowest near the phrase end
            w = 2 * math.pi / self.P
            u = u + self.rub / w * (math.sin(w * u - 2 * math.pi * self.peak) + math.sin(2 * math.pi * self.peak))
        return u * self.u


# ----------------------------------------------------------------------------- instruments
_CACHE: Dict[tuple, np.ndarray] = {}

LUTE = dict(pos=0.14, floor=0.12, tilt=1.0, bright=2300.0, t1=1.3, tpow=0.45, hf=0.75, B=2.0e-5,
            q=0.35, fmax=6500.0, att=0.0012, rel=0.14, course=1.6, octave_below=52,
            noise=0.035, nlo=1200.0, nhi=5000.0, ndecay=0.006)
HARP = dict(pos=0.33, floor=0.18, tilt=1.25, bright=3600.0, t1=3.0, tpow=0.5, hf=0.32, B=3.5e-5,
            q=0.3, fmax=7500.0, att=0.0025, rel=0.45, course=0.0, octave_below=0,
            noise=0.02, nlo=600.0, nhi=3500.0, ndecay=0.008)


def _pluck(f: float, ring: float, vel: float, seed: int, P: dict) -> np.ndarray:
    """A plucked string (see the module notes). Sounds for ``ring`` seconds, then is damped
    over P['rel'] (a finger resting on it)."""
    vq = max(0.05, round(vel * 20) / 20.0)
    ring = max(0.05, round(ring * 20) / 20.0)
    key = ("pluck", id(P), round(f, 3), ring, vq, seed % 5)
    if key in _CACHE:
        return _CACHE[key] * (vel / vq)
    vel_out, vel = vel, vq
    rel = P["rel"]
    n = _n(ring + rel)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    y = np.zeros(n)
    fc = P["bright"] * (0.5 + 0.9 * vel)
    tau1 = P["t1"] * (220.0 / f) ** P["tpow"]
    B = P["B"]
    strings = [(f, 1.0)]
    if P["course"]:
        strings.append((f * 2 ** (P["course"] / 1200.0), 0.72))
    if P["octave_below"] and 69 + 12 * math.log2(f / 440.0) < P["octave_below"]:
        strings.append((2 * f * 2 ** (-0.9 / 1200.0), 0.42))
    for s_i, (fs, amp) in enumerate(strings):
        for k in range(1, 200):
            fk = k * fs * math.sqrt((1 + B * k * k) / (1 + B))
            if fk > P["fmax"]:
                break
            shape = abs(math.sin(math.pi * k * P["pos"])) * (1 - P["floor"]) + P["floor"]
            a = amp * shape / k ** P["tilt"] / (1 + (fk / fc) ** 2)
            if a < 1e-4:
                continue
            tau = 1.0 / (1.0 / tau1 + P["hf"] * (fk / 1000.0) ** 2)
            L = min(n, _n(tau * 7.0))
            tl = t[:L]
            env = (1 - P["q"]) * np.exp(-tl / tau) + P["q"] * np.exp(-tl / (tau * 0.22))
            ph = rng.uniform(-0.3, 0.3)
            y[:L] += a * env * np.sin(2 * np.pi * fk * tl + ph)
    # the finger or quill
    if P["noise"]:
        m = min(n, _n(0.03))
        nz = A.bandpass(rng.standard_normal(m), P["nlo"], P["nhi"], 2)
        nz *= np.exp(-t[:m] / P["ndecay"])
        y[:m] += P["noise"] * vel * nz
    # attack (a raised-cosine rise) and the damping at the end
    k = max(2, _n(P["att"]))
    y[:k] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(k) / k)
    r0 = _n(ring)
    if r0 < n:
        x = (t[r0:] - ring) / rel
        y[r0:] *= np.exp(-4.0 * x) * (0.5 + 0.5 * np.cos(np.pi * np.clip(x, 0, 1)))
    y *= vel
    _CACHE[key] = y
    return y * (vel_out / vq)


def _drum(kind: str, vel: float, seed: int, pitch: float = 110.0) -> np.ndarray:
    """A frame drum. 'down': a full stroke near the middle (low, round); 'up': the tipper's
    lighter return stroke (a little higher, less body); 'tap': a touch near the rim
    (mostly the high modes and the skin's papery slap)."""
    key = ("drum", kind, round(vel, 2), seed % 6, round(pitch, 2))
    if key in _CACHE:
        return _CACHE[key]
    rng = np.random.default_rng(seed)
    dur = 0.6
    n = _n(dur)
    t = np.arange(n) / SR
    ratios = [1.0, 1.594, 2.136, 2.296, 2.653, 2.918, 3.156, 3.501, 3.600, 4.060]
    if kind == "down":
        amps = [0.8, 0.4, 0.45, 0.15, 0.25, 0.12, 0.12, 0.06, 0.05, 0.04]
        tau1, f0, slap = 0.13, pitch, 0.35
    elif kind == "up":
        amps = [0.55, 0.45, 0.45, 0.25, 0.25, 0.15, 0.15, 0.08, 0.06, 0.05]
        tau1, f0, slap = 0.12, pitch * 1.06, 0.35
    else:
        amps = [0.12, 0.25, 0.35, 0.40, 0.40, 0.35, 0.30, 0.28, 0.25, 0.2]
        tau1, f0, slap = 0.07, pitch * 1.12, 0.8
    # the skin's pitch is a little higher at the moment of the hit and settles
    bend = 1.0 + (0.05 + 0.05 * vel) * np.exp(-t / 0.025)
    y = np.zeros(n)
    for i, (r, a) in enumerate(zip(ratios, amps)):
        tau = tau1 / (1 + 0.45 * i)
        ph = 2 * np.pi * np.cumsum(f0 * r * bend) / SR
        y += a * (1 + rng.uniform(-0.1, 0.1)) * np.sin(ph) * np.exp(-t / tau)
    # the tipper on goatskin: a short soft slap
    m = _n(0.05)
    nz = A.bandpass(rng.standard_normal(m), 350, 2800, 2) * np.exp(-t[:m] / 0.010)
    y[:m] += slap * 0.5 * nz
    k = _n(0.0015)
    y[:k] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(k) / k)
    y = A.highpass(y, 70, 2) * vel
    _CACHE[key] = y
    return y


def _bowed(f: float, dur: float, vel: float, seed: int, voices: int = 2, cutoff: float = 1700.0,
           att: float = 0.9, rel: float = 1.2, detune_c: float = 5.0) -> np.ndarray:
    """Soft section strings on one chord tone: ``voices`` bows a few cents apart, each
    with its own vibrato, a slow bow in and out, a dark tone."""
    key = ("bowed", round(f, 3), round(dur, 2), round(vel, 2), seed % 4, voices, cutoff, att, rel)
    if key in _CACHE:
        return _CACHE[key]
    rng = np.random.default_rng(seed)
    total = dur + rel
    n = _n(total)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for v in range(voices):
        det = (v - (voices - 1) / 2) * detune_c * 2 / max(1, voices - 1) if voices > 1 else 0.0
        rate = rng.uniform(4.6, 5.6)
        depth = rng.uniform(0.0016, 0.0026)
        vib_on = np.clip((t - rng.uniform(0.25, 0.5)) / 0.6, 0, 1)
        fr = f * 2 ** (det / 1200.0) * (1 + depth * vib_on * np.sin(2 * np.pi * rate * t + rng.uniform(0, 6.28)))
        fr = fr * (1 + 0.0008 * _slow_noise(n, 0.7, seed * 7 + v))
        y += A.osc("saw", fr, total, phase=rng.uniform(0, 6.28))
    y = A.lowpass(y / voices, cutoff, 2)
    env = A.adsr(total, att, 0.2, 0.92, rel, curve=2.5)
    env = env * (1 + 0.06 * _slow_noise(n, 0.4, seed + 11))
    y = y * env * vel
    _CACHE[key] = y
    return y


def _drone(freqs: Sequence[float], dur: float, seed: int, cutoff: float = 1100.0, fade: float = 2.0) -> np.ndarray:
    """A hurdy-gurdy-like drone: a bowed (saw) tone per string, a slightly nasal body,
    breathing slowly; fades in and out over ``fade`` seconds (equal power)."""
    n = _n(dur)
    y = np.zeros(n)
    rng = np.random.default_rng(seed)
    for i, f in enumerate(freqs):
        fr = f * (1 + 0.0007 * _slow_noise(n, 0.5, seed + i))
        y += (0.9 if i == 0 else 0.6) * A.osc("saw", fr, dur, phase=rng.uniform(0, 6.28))
    y = A.lowpass(y, cutoff, 2)
    y = A.peak_eq(y, 700, 3, 1.2)
    y = y * (1 + 0.12 * _slow_noise(n, 0.15, seed + 5))
    k = _n(fade)
    w = np.ones(n)
    w[:k] = np.sin(0.5 * np.pi * np.arange(k) / k)
    w[-k:] = np.cos(0.5 * np.pi * np.arange(k) / k)
    return y * w


RECORDER = dict(kind="recorder", att=0.02, rel=0.07, glide=0.012, glide_leap=0.016, gap=0.022, floor=0.06,
                rise=0.014, vib_min=0.45, vib_delay=0.22, vib_depth=6.0, vib_rate=5.2, drift=3.0,
                harm=[1.0, 0.13, 0.09, 0.035, 0.02, 0.01], chiff=0.07, breath=0.02, smooth=0.004,
                swell=0.12, cut=0.032)
FIDDLE = dict(kind="fiddle", att=0.16, rel=0.28, glide=0.045, glide_leap=0.08, gap=0.06, floor=0.55,
              rise=0.07, vib_min=0.35, vib_delay=0.16, vib_depth=13.0, vib_rate=5.3, drift=4.0,
              tilt=1.12, fmax=6000.0, chiff=0.0, breath=0.012, smooth=0.012, swell=0.22, cut=0.04)


def _voice(notes: list, P: dict, seed: int) -> np.ndarray:
    """One phrase of a wind or bowed line as one continuous tone (see the module notes).
    ``notes``: (t, d, midi, vel, articulate, cut_midi) with t in seconds from the phrase's
    start; ``articulate`` True is a tongued note or a bow change, False a slur."""
    rng = np.random.default_rng(seed)
    end = notes[-1][0] + notes[-1][1]
    n = _n(end + P["rel"] * 4 + 0.02)
    starts = [_n(x[0]) for x in notes]
    ends = starts[1:] + [_n(end)]
    pitch = np.zeros(n)
    level = np.zeros(n)
    vdepth = np.zeros(n)
    for i, (t0, d, m, v, art, cut) in enumerate(notes):
        s, e = starts[i], ends[i]
        pitch[s:e] = m
        x = np.linspace(0, 1, max(1, e - s))
        sw = 1 - P["swell"] + P["swell"] * np.sin(np.pi * x) if d > 0.5 else np.ones(e - s)
        level[s:e] = v * sw
        if d >= P["vib_min"]:
            on = (np.arange(e - s) / SR - P["vib_delay"]) / 0.35
            vdepth[s:e] = np.clip(on, 0, 1) * P["vib_depth"] * min(1.0, d / 1.2 + 0.3)
    pitch[ends[-1]:] = notes[-1][2]
    # pitch changes: a quick finger change, slower on big leaps (a fiddler's slide)
    for i in range(1, len(notes)):
        p0, p1 = notes[i - 1][2], notes[i][2]
        if p0 == p1:
            continue
        g = P["glide_leap"] if abs(p1 - p0) >= 5 and not notes[i][4] else P["glide"]
        if notes[i][4]:
            g = min(g, 0.008)
        w = max(2, _n(g))
        a = max(0, starts[i] - int(0.7 * w))
        b = min(n, a + w)
        pitch[a:b] = p0 + (p1 - p0) * _smoothstep(np.linspace(0, 1, b - a))
    # cuts: the next note up flicked in for an instant at the start of the note
    for i, (t0, d, m, v, art, cut) in enumerate(notes):
        if cut:
            s = starts[i]
            c = _n(P["cut"])
            pitch[s:s + c] = cut
    # level: the phrase's attack and release, dips for tongue strokes or bow changes
    art_env = np.ones(n)
    a0 = _n(P["att"])
    art_env[:a0] = (1 - np.exp(-4.0 * np.arange(a0) / a0)) / (1 - math.exp(-4.0))
    e0 = ends[-1]
    rel = np.arange(n - e0) / SR
    level[e0:] = level[e0 - 1] if e0 > 0 else 0.0
    art_env[e0:] = np.exp(-rel / (P["rel"] / 3.0)) * (0.5 + 0.5 * np.cos(np.pi * np.clip(rel / (P["rel"] * 3.5), 0, 1)))
    onset = np.zeros(n)
    for i in range(len(notes)):
        art = notes[i][4]
        s = starts[i]
        if i > 0 and art:
            g = _n(P["gap"])
            r = _n(P["rise"])
            a = max(0, s - g)
            art_env[a:s] *= 1 - (1 - P["floor"]) * _smoothstep(np.linspace(0, 1, s - a))
            b = min(n, s + r)
            art_env[s:b] *= P["floor"] + (1 - P["floor"]) * (1 - np.exp(-4.0 * np.linspace(0, 1, b - s))) / (1 - math.exp(-4.0))
        if art or i == 0:
            m = min(n - s, _n(0.08))
            onset[s:s + m] += notes[i][3] * np.exp(-np.arange(m) / SR / 0.012)
    # smooth the level (no steps), then vibrato, wander and the tone itself
    lvl = signal.lfilter([1 - math.exp(-1 / (P["smooth"] * SR))], [1, -math.exp(-1 / (P["smooth"] * SR))], level)
    env = lvl * art_env * (1 + 0.025 * _slow_noise(n, 3.0, seed + 3))
    vd = A.lowpass(vdepth, 3.0, 1)
    rate = P["vib_rate"] * (1 + 0.05 * _slow_noise(n, 0.6, seed + 4))
    lfo = np.sin(2 * np.pi * np.cumsum(rate) / SR + rng.uniform(0, 6.28))
    cents = vd * lfo + P["drift"] * _slow_noise(n, 0.4, seed + 5)
    freq = 440.0 * 2 ** ((pitch + cents / 100.0 - 69) / 12.0)
    ph = 2 * np.pi * np.cumsum(freq) / SR
    if P["kind"] == "recorder":
        y = np.zeros(n)
        on = np.clip(onset, 0, 1)
        for k, h in enumerate(P["harm"], start=1):
            boost = 1 + (2.5 if k in (2, 3) else 0.0) * on
            y += h * boost * np.sin(k * ph + rng.uniform(0, 6.28) * (k > 1))
        y *= env
        nz = rng.standard_normal(n)
        breath = A.lowpass(A.bandpass(nz, 900, 4500, 2), 6000, 2) * env * P["breath"]
        chiff = A.lowpass(A.bandpass(nz, 1800, 6000, 2), 7000, 2) * on * P["chiff"] * 3
        y = y + breath + chiff
    else:
        y = np.zeros(n)
        for k in range(1, 60):
            roll = np.clip((P["fmax"] - k * freq) / 700.0, 0, 1)
            if not roll.any():
                break
            # louder bowing brings out the upper harmonics; each one wavers a little
            bright = (0.35 + 0.65 * np.clip(env / max(1e-6, env.max()), 0, 1)) ** (0.18 * (k - 1))
            jit = 1 + 0.08 * _slow_noise(n, 9.0, seed * 31 + k)
            y += (roll * bright * jit / k ** P["tilt"]) * np.sin(k * ph + rng.uniform(0, 6.28))
        y *= env
        bow = A.lowpass(A.bandpass(rng.standard_normal(n), 1800, 6000, 2), 7000, 2) * env * P["breath"]
        y = y + bow
    return y


# ----------------------------------------------------------------------------- room and mix
def _ir(rt60: float, seed: int, predelay: float = 0.014, length: Optional[float] = None,
        hi_rt: float = 0.5, lo_rt: float = 1.15) -> np.ndarray:
    """A stereo room: early reflections, then a diffuse tail (highs die first), unit energy
    per ear."""
    length = length or min(4.5, rt60 * 1.3)
    n = _n(length)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    out = []
    for ch in range(2):
        w = rng.standard_normal(n)
        lo = A.lowpass(w, 500, 2)
        hi = A.highpass(w, 3500, 2)
        mid = A.bandpass(w, 500, 3500, 1)
        env = lambda r: np.exp(-6.9078 * t / r)
        late = lo * env(rt60 * lo_rt) + mid * env(rt60) + hi * env(rt60 * hi_rt)
        late *= 1 - np.exp(-t / 0.03)
        pd = _n(predelay)
        late = np.concatenate([np.zeros(pd), late])[:n]
        er = np.zeros(n)
        for _ in range(14):
            d = predelay * 0.4 + rng.uniform(0.003, 0.075)
            er[_n(d)] += rng.choice([-1.0, 1.0]) * rng.uniform(0.3, 1.0) * math.exp(-d / 0.04)
        er = A.lowpass(er, 4500, 1)
        late /= math.sqrt(np.sum(late ** 2))
        er /= math.sqrt(np.sum(er ** 2))
        out.append(0.85 * late + 0.45 * er)
    ir = np.stack(out, axis=1)
    ir = A.highpass(ir, 170, 2)
    ir = A.lowpass(ir, 7000, 2)
    ir[-_n(0.05):] *= np.linspace(1, 0, _n(0.05))[:, None]
    return ir / math.sqrt(np.sum(ir ** 2) / 2)


class Mix:
    """Stems (mono, starting at the loop's start, any length) into one stereo loop."""

    def __init__(self, loop_s: float, tail_s: float = 6.0):
        self.n = _n(loop_s)
        self.L = self.n + _n(tail_s)
        self.parts = []

    def buffer(self) -> np.ndarray:
        return np.zeros(self.L)

    def add_note(self, buf: np.ndarray, x: np.ndarray, t: float) -> None:
        """Add a sound at ``t`` seconds; a time before the start wraps to the loop's end."""
        i = _n(t)
        if i < 0:
            i += self.n
        i %= self.n
        e = min(self.L, i + len(x))
        buf[i:e] += x[:e - i]

    def part(self, stem: np.ndarray, level_db: float, pan: float = 0.0, send: float = 0.3) -> None:
        self.parts.append((stem, level_db, pan, send))

    def render(self, ir: np.ndarray, master_eq: Optional[Callable] = None) -> np.ndarray:
        dry = np.zeros((self.L, 2))
        snd = np.zeros((self.L, 2))
        for stem, level_db, pan, send in self.parts:
            x = _to_db(stem, level_db)
            st = A.pan(x, pan)
            dry += st
            snd += st * send
        wet = np.stack([signal.fftconvolve(snd[:, c], ir[:, c]) for c in range(2)], axis=1)
        full = np.zeros((max(self.L, len(wet)), 2))
        full[:self.L] += dry
        full[:len(wet)] += wet
        full = A.highpass(full, 35, 2)
        if master_eq:
            full = master_eq(full)
        return A.loop_seamless(full[:self.n], full[self.n:])


# ----------------------------------------------------------------------------- helpers to place parts
def _phrases(notes: list, join: float = 0.02) -> List[list]:
    """Split (t, d, ...) notes into phrases wherever there is a rest."""
    out: List[list] = []
    for nt in sorted(notes, key=lambda x: x[0]):
        if out and nt[0] - (out[-1][-1][0] + out[-1][-1][1]) < join:
            out[-1].append(nt)
        else:
            out.append([nt])
    return out


def _render_voice(mix: Mix, notes: list, P: dict, seed: int, jitter: float = 0.0) -> np.ndarray:
    """``notes``: (t, d, midi, vel, articulate, cut) in seconds; rendered phrase by phrase."""
    buf = mix.buffer()
    rng = np.random.default_rng(seed)
    for k, ph in enumerate(_phrases(notes)):
        t0 = ph[0][0]
        rel = []
        for (t, d, m, v, art, cut) in ph:
            j = rng.normal(0, jitter) if jitter else 0.0
            rel.append((max(0.0, t - t0 + j) if t > t0 else 0.0, d, m, v, art, cut))
        # keep the order and lengths consistent after the jitter
        fixed = []
        for i, x in enumerate(rel):
            nxt = rel[i + 1][0] if i + 1 < len(rel) else x[0] + x[1]
            fixed.append((x[0], max(0.03, nxt - x[0]) if i + 1 < len(rel) else x[1], *x[2:]))
        y = _voice(fixed, P, seed * 101 + k)
        mix.add_note(buf, y, t0 + (rng.normal(0, jitter) if jitter else 0.0))
    return buf


# ============================================================================= 1. Tavern jig
JIG_A_BARS = [
    "A4:1 D5:1 F#5:1 A5:2 F#5:1", "G5:1 F#5:1 G5:1 B5:2 G5:1", "F#5:1 E5:1 D5:1 A4:1 D5:1 F#5:1",
    "E5:2 D5:1 C#5:1 B4:1 A4:1", "A4:1 D5:1 F#5:1 A5:3", "B5:1 A5:1 G5:1 E5:2 G5:1",
    "F#5:1 E5:1 D5:1 E5:1 C#5:1 A4:1",
]
JIG_A_END1 = "D5:2 F#5:1 D5:3"
JIG_A_END2 = "D5:2 E5:1 F#5:1 G5:1 A5:1"
JIG_B_BARS = [
    "B5:2 A5:1 G5:1 A5:1 B5:1", "A5:2 F#5:1 D5:1 E5:1 F#5:1", "G5:2 E5:1 B4:1 E5:1 G5:1",
    "A5:2 E5:1 C#5:1 D5:1 E5:1", "B5:2 A5:1 G5:1 B5:1 D6:1", "A5:1 F#5:1 A5:1 D6:2 A5:1",
    "G5:1 F#5:1 E5:1 A5:1 E5:1 C#5:1",
]
JIG_B_END1 = "D5:2 F#5:1 A5:3"
JIG_B_END2 = "D5:2 A4:1 D5:3"
# chords per half bar
JIG_A_CH = [("D", "D"), ("G", "G"), ("D", "D"), ("A", "A"), ("D", "D"), ("G", "Em"), ("D", "A"), ("D", "D")]
JIG_B_CH = [("G", "G"), ("D", "D"), ("Em", "Em"), ("A", "A"), ("G", "G"), ("D", "D"), ("Em", "A"), ("D", "D")]
JIG_VOICING = {  # (root bass, fifth bass, upper chord tones)
    "D": ("D3", "A2", ("A3", "D4", "F#4")),
    "G": ("G2", "D3", ("B3", "D4", "G4")),
    "A": ("A2", "E3", ("A3", "C#4", "E4")),
    "Em": ("E3", "B2", ("B3", "E4", "G4")),
}


def _jig_tune(part: str, ending: int, ornaments: bool, start_bar: int, transpose: int = 0) -> list:
    bars = JIG_A_BARS if part == "A" else JIG_B_BARS
    end = (JIG_A_END1, JIG_A_END2)[ending - 1] if part == "A" else (JIG_B_END1, JIG_B_END2)[ending - 1]
    text = " | ".join(bars + [end])
    notes, _ = _parse(text, 6, start_bar * 6)
    out = []
    for i, (u, l, m, fl) in enumerate(notes):
        cut = None
        if ornaments and l >= 2 and (i % 3 != 2):
            cut = _scale_up(m, SCALE_D_MAJOR)
        out.append((u, l, m + transpose, fl, cut))
    return out


def _tavern_jig() -> np.ndarray:
    _CACHE.clear()
    bars = 64
    clock = Clock(0.2, lilt=(0.07, 0.035))
    loop_s = bars * 6 * 0.2
    mix = Mix(loop_s, tail_s=6.0)
    rng = np.random.default_rng(1207)

    # ---- the tune: recorder (bars 1-32 and 49-64), lute melody (33-48), recorder descant (41-48)
    rec_units = []
    plan = [("A", 1, False, 0), ("A", 2, True, 8), ("B", 1, False, 16), ("B", 2, True, 24),
            ("B", 1, True, 48), ("B", 2, False, 56)]
    for part, ending, orn, b0 in plan:
        rec_units += _jig_tune(part, ending, orn, b0)
    rec = []
    for (u, l, m, fl, cut) in rec_units:
        in_bar = u % 6
        group_start = abs(in_bar % 3) < 1e-9
        prev = rec[-1] if rec else None
        art = group_start or l >= 2 or (prev is not None and prev[2] == m)
        accent = 1.0 if in_bar == 0 else (0.9 if abs(in_bar - 3) < 1e-9 else 0.8)
        t = clock(u)
        d = clock(u + l) - t
        if abs((u + l) % 24) < 1e-9:
            d -= min(0.13, 0.4 * d)          # a breath at the end of every four bars
        rec.append((t, d * 0.97, m, 0.8 * accent, art, cut))
    # descant over the lute's melody, bars 41-48: long notes on chord tones
    desc, _ = _parse("F#5:6 | G5:6 | F#5:6 | E5:6 | A5:6 | B5:3 G5:3 | A5:3 E5:3 | F#5:5 r:1", 6, 40 * 6)
    for (u, l, m, fl) in desc:
        t = clock(u)
        rec.append((t, clock(u + l) - t, m, 0.6, True, None))
    rec_stem = _render_voice(mix, rec, RECORDER, seed=31, jitter=0.004)

    # ---- lute: chords (bars 1-32, 49-64), melody an octave down (33-48), bass (41-48)
    chord_buf = mix.buffer()          # the accompanying lute
    mel_buf = mix.buffer()            # the lute's turn at the tune, mixed on its own
    count = [0]

    def pl(buf, m, ring, vel, t):
        count[0] += 1
        x = _pluck(_mhz(m), ring, float(np.clip(vel * (1 + rng.uniform(-0.07, 0.07)), 0.05, 1.0)), count[0], LUTE)
        mix.add_note(buf, x, t + rng.normal(0, 0.005))

    def chords(b0, chs, busy):
        for b, (c1, c2) in enumerate(chs):
            for half, c in enumerate((c1, c2)):
                root, fifth, upper = JIG_VOICING[c]
                u0 = (b0 + b) * 6 + half * 3
                same = half == 1 and c1 == c2
                bass = fifth if same else root
                pl(chord_buf, A.midi(bass), clock(u0 + 2.6) - clock(u0), 0.75 if half == 0 else 0.62, clock(u0))
                hits = [(1, 0.24), (2, 0.36)] if busy else [(2, 0.36)]
                for (h, v) in hits:
                    tu = clock(u0 + h)
                    ring = clock(u0 + 3) - tu - 0.02
                    for j, nm in enumerate(upper):
                        pl(chord_buf, A.midi(nm), ring, v * (0.9 + 0.1 * j), tu + j * 0.011)

    chords(0, JIG_A_CH, False)
    chords(8, JIG_A_CH, False)
    chords(16, JIG_B_CH, True)
    chords(24, JIG_B_CH, True)
    chords(48, JIG_B_CH, True)
    chords(56, JIG_B_CH, True)
    lute_mel = _jig_tune("A", 1, False, 32, -12) + _jig_tune("A", 2, False, 40, -12)
    for (u, l, m, fl, cut) in lute_mel:
        in_bar = u % 6
        v = 0.82 if in_bar in (0, 3) else 0.62
        t = clock(u)
        pl(mel_buf, m, clock(u + l) - t + 0.08, v, t)
    for b in range(40, 48):
        c1, c2 = JIG_A_CH[b - 40]
        for half, c in enumerate((c1, c2)):
            u0 = b * 6 + half * 3
            root, fifth, upper = JIG_VOICING[c]
            pl(chord_buf, A.midi(root if half == 0 or c1 != c2 else fifth), clock(u0 + 2.7) - clock(u0), 0.55,
               clock(u0))

    # ---- frame drum
    drum = mix.buffer()
    P_A = [(0, "down", 0.8), (2, "up", 0.3), (3, "down", 0.55), (5, "up", 0.34)]
    P_B = [(0, "down", 0.85), (1, "tap", 0.22), (2, "up", 0.36), (3, "down", 0.6), (4, "tap", 0.22), (5, "up", 0.42)]
    P_S = [(0, "down", 0.6), (3, "up", 0.32), (5, "tap", 0.2)]
    FILL = [(0, "down", 0.8), (1, "up", 0.34), (2, "up", 0.42), (3, "down", 0.7), (4, "up", 0.5), (5, "up", 0.6)]
    for b in range(bars):
        if b < 16 or 40 <= b < 48:
            pat = P_A
        elif b < 32 or b >= 48:
            pat = P_B
        else:
            pat = P_S
        if b in (31, 63):
            pat = FILL
        for (u, kind, v) in pat:
            uu = b * 6 + u
            mix.add_note(drum, _drum(kind, v * (1 + rng.uniform(-0.08, 0.08)), int(uu)), clock(uu) + rng.normal(0, 0.003))

    # ---- drone: D and A, the whole loop, folded seamlessly through its own fades
    drone = _drone([_mhz(A.midi("D3")), _mhz(A.midi("A3"))], loop_s + 2.0, seed=77, fade=2.0)
    dstem = mix.buffer()
    dstem[:len(drone)] += drone

    def lute_body(x):
        x = A.highpass(x, 75, 2)
        x = A.peak_eq(x, 260, 3.0, 1.4)
        return A.peak_eq(x, 520, 1.5, 1.2)

    rec_stem = A.lowpass(A.highpass(rec_stem, 200, 2), 7000, 2)
    mix.part(rec_stem, -18.0, pan=0.22, send=0.32)
    mix.part(lute_body(chord_buf), -21.0, pan=-0.28, send=0.28)
    mix.part(lute_body(mel_buf), -19.5, pan=-0.18, send=0.3)
    mix.part(drum, -28.0, pan=0.05, send=0.18)
    mix.part(dstem, -31.0, pan=0.0, send=0.35)
    ir = _ir(1.1, seed=5, predelay=0.010)
    return mix.render(ir)


# ============================================================================= 2. Bard's ballad
BAL_MEL_A = ("A4:4 D5:2 | B4:3 C5:1 D5:2 | F5:3 E5:1 D5:2 | E5:5 r:1 | "
             "A5:4 G5:1 F5:1 | G5:3 F5:1 E5:1 D5:1 | C5:4 B4:1 C5:1 | A4:5 r:1 | "
             "F5:4 E5:1 F5:1 | G5:4 E5:2 | D5:4 B4:2 | C5:3 B4:1 A4:2 | "
             "D5:3 E5:1 F5:2 | A5:4 G5:2 | E5:3 D5:1 C5:2 | D5:5 r:1")
BAL_MEL_B = ("A4:3 G4:1 F4:2 | G4:4 E4:2 | D4:2 G4:2 B4:2 | A4:5 r:1 | "
             "C5:4 F5:2 | E5:3 D5:1 C5:2 | D5:2 G5:2 A5:2 | B5:5 r:1 | "
             "C6:4 B5:1 A5:1 | A5:3 G5:1 F5:2 | G5:3 F5:1 E5:1 D5:1 | E5:4 G5:2 | "
             "A5:3 G5:1 F5:2 | D5:4 B4:2 | C5:3 D5:1 E5:2 | E5:5 r:1")
BAL_CH_A = ["Dm", "G", "Dm", "C", "Dm", "G", "Am", "Am", "F", "C", "G", "Am", "Dm", "G", "C", "Dm"]
BAL_CH_B = ["F", "C", "G", "Dm", "F", "C", "G", "G", "Am", "Dm", "G", "C", "F", "G", "Am", "Am"]
BAL_VOICING = {
    "Dm": ("D3", ("A3", "D4", "F4")),
    "G": ("G2", ("B3", "D4", "G4")),
    "C": ("C3", ("G3", "C4", "E4")),
    "Am": ("A2", ("A3", "C4", "E4")),
    "F": ("F2", ("A3", "C4", "F4")),
}


def _bards_ballad() -> np.ndarray:
    _CACHE.clear()
    bars = 32
    unit = 60.0 / 69.0 / 2.0
    clock = Clock(unit, rubato=0.05, phrase_units=24.0, peak_at=0.9)
    loop_s = bars * 6 * unit
    mix = Mix(loop_s, tail_s=7.0)
    rng = np.random.default_rng(4401)

    # ---- fiddle melody: a bow per bar (slurs inside), separate bows on repeated notes
    mel_a, _ = _parse(BAL_MEL_A, 6, 0)
    mel_b, _ = _parse(BAL_MEL_B, 6, 96)
    mel = mel_a + mel_b
    fid = []
    for i, (u, l, m, fl) in enumerate(mel):
        bar_i = int(u // 6)
        phrase_pos = (u % 24) / 24.0
        v = 0.62 + 0.22 * math.sin(math.pi * min(1.0, phrase_pos + 0.1))
        if 96 + 6 * 7 <= u < 96 + 6 * 11:      # the climb to the high C
            v += 0.08
        if u < 96 + 24 and u >= 96:            # the low answering phrase, softer
            v -= 0.08
        prev = mel[i - 1] if i else None
        new_bow = prev is None or int(prev[0] // 6) != bar_i or prev[2] == m or (prev[0] + prev[1] < u - 1e-9)
        t = clock(u)
        d = clock(u + l) - t
        fid.append((t, d, m, v, new_bow, None))
    fid_stem = _render_voice(mix, fid, FIDDLE, seed=12, jitter=0.006)

    # ---- lute arpeggios: up and down in the A section, rolling upward in B
    lute = mix.buffer()
    cnt = [0]

    def pl(m, ring, vel, t):
        cnt[0] += 1
        x = _pluck(_mhz(m), ring, float(np.clip(vel * (1 + rng.uniform(-0.06, 0.06)), 0.05, 1.0)), cnt[0], LUTE)
        mix.add_note(lute, x, t + rng.normal(0, 0.007))

    for b in range(bars):
        ch = (BAL_CH_A + BAL_CH_B)[b]
        bass, up = BAL_VOICING[ch]
        u = [A.midi(x) for x in up]
        u0 = b * 6
        if b < 16:
            seq = [u[0], u[1], u[2], u[1], u[0]]
        else:
            seq = [u[0], u[1], u[2], u[0], u[1]]
        lift = 1.08 if 20 <= b <= 26 else 1.0
        t_bar_end = clock(u0 + 6)
        pl(A.midi(bass), t_bar_end - clock(u0) + 0.25, 0.7 * lift, clock(u0))
        for j, m in enumerate(seq, start=1):
            t = clock(u0 + j)
            vel = (0.42, 0.46, 0.5, 0.44, 0.4)[j - 1] * lift
            pl(m, t_bar_end - t + 0.3, vel, t)

    lute_stem = A.highpass(lute, 65, 2)
    lute_stem = A.peak_eq(lute_stem, 115, 2.0, 1.8)
    lute_stem = A.peak_eq(lute_stem, 260, 3.0, 1.4)
    lute_stem = A.peak_eq(lute_stem, 520, 1.5, 1.2)
    fid_stem = A.highpass(fid_stem, 180, 2)
    for f, g, q in ((285, 5.0, 3.0), (470, 4.0, 2.5), (560, 3.0, 3.0), (1100, 1.5, 2.0), (1650, -4.0, 1.4),
                    (2700, 2.0, 1.6), (4200, -4.0, 1.0)):
        fid_stem = A.peak_eq(fid_stem, f, g, q)
    fid_stem = A.lowpass(fid_stem, 6500, 2)
    mix.part(fid_stem, -18.0, pan=0.18, send=0.38)
    mix.part(lute_stem, -21.0, pan=-0.22, send=0.3)
    ir = _ir(1.9, seed=9, predelay=0.018)
    return mix.render(ir)


# ============================================================================= 3. Harp hall
HARP_MEL_A = ("F#5:3 E5:1 F#5:2 A5:2 | E5:6 F#5:1 E5:1 | D5:3 C#5:1 D5:2 F#5:2 | C#5:6 D5:1 C#5:1 | "
              "B4:3 A4:1 B4:2 D5:2 | A4:4 D5:2 F#5:2 | B5:4 A5:2 G5:2 | F#5:2 E5:6")
HARP_MEL_B = ("E5:4 C#5:2 E5:2 | D5:4 B4:2 D5:2 | A4:2 D5:2 F#5:2 A5:2 | G5:6 E5:2 | "
              "E5:4 G5:2 B5:2 | D6:4 B5:2 G5:2 | A5:4 G5:2 F#5:2 | E5:8")
HARP_CH_A = ["D", "A/C#", "Bm", "F#m/A", "G", "D/F#", "Em", "A"]
HARP_CH_B = ["A", "G", "D", "A7", "Em", "G", "Asus4", "A"]
HARP_VOICING = {  # bass, arpeggio (three notes), strings (three notes)
    "D": ("D3", ("A3", "D4", "F#4"), ("A3", "D4", "F#4")),
    "A/C#": ("C#3", ("A3", "C#4", "E4"), ("A3", "C#4", "E4")),
    "Bm": ("B2", ("B3", "D4", "F#4"), ("B3", "D4", "F#4")),
    "F#m/A": ("A2", ("A3", "C#4", "F#4"), ("A3", "C#4", "F#4")),
    "G": ("G2", ("B3", "D4", "G4"), ("B3", "D4", "G4")),
    "D/F#": ("F#2", ("A3", "D4", "F#4"), ("A3", "D4", "F#4")),
    "Em": ("E2", ("B3", "E4", "G4"), ("B3", "E4", "G4")),
    "A": ("A2", ("A3", "C#4", "E4"), ("A3", "C#4", "E4")),
    "A7": ("A2", ("G3", "C#4", "E4"), ("G3", "C#4", "E4")),
    "Asus4": ("A2", ("A3", "D4", "E4"), ("A3", "D4", "E4")),
}


def _harp_hall() -> np.ndarray:
    _CACHE.clear()
    bars = 24
    unit = 60.0 / 72.0 / 2.0
    clock = Clock(unit, rubato=0.04, phrase_units=32.0, peak_at=0.92)
    loop_s = bars * 8 * unit
    mix = Mix(loop_s, tail_s=7.0)
    rng = np.random.default_rng(9090)
    cnt = [0]
    stems_by_pan: Dict[int, np.ndarray] = {}  # harp notes panned by pitch, low left, high right

    def pl(m, ring, vel, t):
        cnt[0] += 1
        x = _pluck(_mhz(m), ring, float(np.clip(vel * (1 + rng.uniform(-0.06, 0.06)), 0.05, 1.0)), cnt[0], HARP)
        zone = int(np.clip((m - 50) // 8, 0, 4))      # five pan zones
        if zone not in stems_by_pan:
            stems_by_pan[zone] = mix.buffer()
        mix.add_note(stems_by_pan[zone], x, t + rng.normal(0, 0.006))

    chords = HARP_CH_A + HARP_CH_B + HARP_CH_A
    for b in range(bars):
        bass, arp, _ = HARP_VOICING[chords[b]]
        a = [A.midi(x) for x in arp]
        u0 = b * 8
        t_end = clock(u0 + 8)
        if 8 <= b < 16:
            # B: rolled chords on beats 1 and 3, the bass on 1
            pl(A.midi(bass), t_end - clock(u0) + 0.3, 0.46, clock(u0))
            for beat, v in ((0, 0.36), (4, 0.28)):
                t = clock(u0 + beat)
                for j, m in enumerate(a):
                    pl(m, t_end - t + 0.6, v, t + 0.045 + j * 0.04)
        else:
            pl(A.midi(bass), t_end - clock(u0) + 0.3, 0.46, clock(u0))
            seq = [a[0], a[1], a[2], a[1], a[0], a[1], a[2]]
            for j, m in enumerate(seq, start=1):
                t = clock(u0 + j)
                pl(m, t_end - t + 0.5, (0.34, 0.3, 0.36, 0.3, 0.32, 0.29, 0.34)[j - 1], t)
    mel_a, _ = _parse(HARP_MEL_A, 8, 0)
    mel_b, _ = _parse(HARP_MEL_B, 8, 64)
    mel_a2, _ = _parse(HARP_MEL_A, 8, 128)
    for (u, l, m, fl) in mel_a + mel_b + mel_a2:
        t = clock(u)
        strong = (u % 8) in (0, 4)
        v = 0.78 if strong else 0.66
        ring = min(3.2, clock(u + l) - t + 1.0)
        pl(m, ring, v, t)
        if u >= 128 and strong and l >= 2:
            # the last section: the melody doubled by a chord tone a third to a sixth below
            bass, arp, _ = HARP_VOICING[chords[int(u // 8)]]
            pcs = {A.midi(x) % 12 for x in arp + (bass,)}
            below = [k for k in range(m - 9, m - 2) if k % 12 in pcs]
            if below:
                pl(max(below), ring, v * 0.5, t + 0.012)

    # ---- strings: a soft held chord per bar (fuller in the middle section)
    # each of the three string voices holds a note across bar lines when the next chord
    # keeps it (no re-bowing of common tones), so the pad does not swell at every bar
    sides = [mix.buffer(), mix.buffer()]
    for j in range(3):
        held = []                                  # [first bar, last bar, pitch]
        for b in range(bars):
            m = A.midi(HARP_VOICING[chords[b]][2][j])
            if held and held[-1][2] == m and held[-1][1] == b - 1:
                held[-1][1] = b
            else:
                held.append([b, b, m])
        for (b0, b1, m) in held:
            t = clock(b0 * 8)
            d = clock(b1 * 8 + 8) - t + 0.35
            vel = 0.68 if 8 <= b0 < 16 else 0.55
            for side in (0, 1):
                f = _mhz(m) * 2 ** ((3.5 if side else -3.5) / 1200.0)
                x = _bowed(f, d, vel, b0 * 7 + j * 2 + side, voices=1, cutoff=1500.0, att=0.9, rel=1.4)
                mix.add_note(sides[side], x, t - 0.15 + 0.012 * side)
    for side in (0, 1):
        sides[side] = A.peak_eq(A.highpass(sides[side], 140, 2), 400, 2.0, 1.0)

    pans = {0: -0.4, 1: -0.2, 2: 0.0, 3: 0.2, 4: 0.4}
    for z, st in stems_by_pan.items():
        st = A.highpass(st, 70, 2)
        st = A.peak_eq(st, 240, 2.0, 1.2)
        stems_by_pan[z] = st
    total = sum(stems_by_pan.values())
    harp_db = _loud(total)
    # centre the harp: shift every zone so the energy-weighted pan is zero
    energy = {z: float(np.sum(st ** 2)) for z, st in stems_by_pan.items()}
    centre = sum(energy[z] * pans[z] for z in energy) / sum(energy.values())
    for z, st in stems_by_pan.items():
        rel_db = _loud(st) - harp_db if np.any(st) else -120
        mix.part(st, -18.0 + rel_db, pan=float(np.clip(pans[z] - centre, -0.6, 0.6)), send=0.42)
    mix.part(sides[0], -28.0, pan=-0.55, send=0.5)
    mix.part(sides[1], -28.0, pan=0.55, send=0.5)
    ir = _ir(2.5, seed=21, predelay=0.022)
    return mix.render(ir)


# ----------------------------------------------------------------------------- candidates
JIG_BPM = 100.0          # dotted quarters a minute (six-eight: 300 eighth notes)
BALLAD_BPM = 69.0
HARP_BPM = 72.0

CANDIDATES = [
    Candidate("music", "tavern_jig", "Tavern jig",
              "A lively, light jig: a recorder and a lute trade the tune over a soft frame drum "
              "and a quiet drone, like musicians in the corner of an inn.",
              _tavern_jig, tags=["table"], loop_seconds=64 * 6 * 0.2, bpm=JIG_BPM),
    Candidate("music", "bards_ballad", "Bard's ballad",
              "A slow, wistful song: a bowed fiddle sings over a gently rolling lute.",
              _bards_ballad, tags=["menu"], loop_seconds=32 * 6 * (60.0 / 69.0 / 2.0), bpm=BALLAD_BPM),
    Candidate("music", "harp_hall", "Harp hall",
              "A calm harp melody over soft held strings, like a quiet great hall.",
              _harp_hall, tags=["menu", "table"], loop_seconds=24 * 8 * (60.0 / 72.0 / 2.0), bpm=HARP_BPM),
]
