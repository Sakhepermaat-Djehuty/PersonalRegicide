"""Three more music loops with their own characters: a hurdy-gurdy dance, a chiptune quest
and a candlelit minuet.

Every loop is built as a circle: each part is a mono buffer exactly one loop long, and a
note that rings past the loop's end wraps round onto its start (as it would sound the
second time round). Filters run in their steady state (warmed up on the loop's own end)
and the room is a circular convolution, so the loop has no seam by construction. Tempo
breathing (rubato) and swing average out inside each phrase, so the loop keeps its exact
length. Everything is seeded.

Instruments, all private to this file:
  _pluck      a plucked string as a sum of its partials, exactly in tune: each partial's
              level comes from where the string is plucked (the quill of a harpsichord
              near the end of the string: bright and nasal; a cittern's plectrum a little
              further in), its ring time shortens with frequency, two choirs or a course
              of two strings a hair apart beat gently; a quill or plectrum click at the
              start and the damper (or a finger) stopping it at the end.
  _bow_phrase a bowed string line rendered phrase by phrase so notes join as on the real
              instrument (one tone whose pitch moves note to note, bow changes as small
              dips, delayed vibrato, a slow bow in and out); a sawtooth through a fixed
              body resonance, so the vibrato makes the harmonics shimmer.
  _hg_line    a hurdy-gurdy melody: the wheel never stops, so the tune is one unbroken,
              buzzy tone (two unison strings a few cents apart) whose pitch jumps
              instantly as the keys (tangents) change; it swells a little with every turn
              of the crank. A nasal, vowel-like body (formant peaks) makes it a hurdy-gurdy
              rather than a fiddle.
  _coup       the trompette's buzz: the loose bridge (the "dog") rattling against the
              soundboard once per string cycle when the player jerks the crank.
  _drum       a frame drum as a circular membrane (its inharmonic modes).
  _chip_*     8-bit voices: pulse waves (50% and 25%), the stepped 4-bit triangle and a
              shift-register noise channel, each band-limited (no aliasing, no glare),
              with volume envelopes that step at 60 frames a second like the old chips.
  _room_ir    a room as a synthetic stereo impulse response (highs die first).

Keys: the hurdy-gurdy dance is in D dorian over a D-A drone, the chiptune and the minuet
in D major (the minuet's trio in B minor, the same notes).
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import signal

import synth as A
from catalog import Candidate

SR = A.SR
_DEBUG: Optional[dict] = None     # set to {} to collect each track's stems (for checking)


# ----------------------------------------------------------------------------- basics
def _n(t: float) -> int:
    return int(round(t * SR))


def _mhz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12.0)


def _smoothstep(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def _wander(n: int, rate_hz: float, seed: int) -> np.ndarray:
    """A smooth random wander in -1..1 that changes about ``rate_hz`` times a second and
    is periodic over its own length (whole cycles only), so it loops."""
    rng = np.random.default_rng(seed)
    m = max(8, int(math.ceil(n / 64.0)))          # a control rate of about 690 Hz
    m += m % 2
    kmax = max(1, int(rate_hz * n / SR))
    spec = np.zeros(m // 2 + 1, dtype=complex)
    k = min(kmax, len(spec) - 2)
    spec[1:k + 1] = rng.standard_normal(k) + 1j * rng.standard_normal(k)
    ctl = np.fft.irfft(spec, m)
    y = np.interp(np.arange(n), np.arange(m) * (n / m), ctl, period=n)
    return y / (np.max(np.abs(y)) + 1e-12)


def _to_db(x: np.ndarray, target_db: float) -> np.ndarray:
    """Scale a part to a gated-RMS level (its level while it plays)."""
    if not np.any(x):
        return x
    return x * 10 ** ((target_db - A._rms_db(x)) / 20.0)


def _cfilt(x: np.ndarray, fn: Callable[[np.ndarray], np.ndarray], warm: float = 2.0) -> np.ndarray:
    """Run a filter over a looping signal in its steady state: it is warmed up on the
    loop's own last ``warm`` seconds, so the start joins the end."""
    n = len(x)
    w = min(n, _n(warm))
    y = fn(np.concatenate([x[n - w:], x], axis=0))
    return y[w:]


def _aac_aligned(seconds: float) -> float:
    """The nearest loop length that is a whole number of AAC frames (1024 samples): the
    phone's .m4a then needs no padding at its end, which would otherwise leave a tiny gap
    each time the loop comes round. (It moves the tempo by a hundredth of a beat or less.)"""
    return round(seconds * SR / 1024.0) * 1024.0 / SR


def _cconv(x: np.ndarray, ir: np.ndarray) -> np.ndarray:
    """Circular convolution: the room's ring past the loop's end lands on its start."""
    n = len(x)
    return np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(ir, n), n)


# ----------------------------------------------------------------------------- notation
def _parse(text: str, bar: float, start: float = 0.0) -> List[tuple]:
    """'F#5:3 E5:1 | r:2 ...' -> [(start, length, midi, flags)] in units (eighth notes
    here). '|' marks a bar line and every bar must add up to ``bar`` units, so a typo shows
    at once. Flags are letters after the length, for ``_ornament``: 'm' a mordent, 't' a
    trill, 'g' a grace note from above."""
    out = []
    pos = start
    bar_start = start
    for tok in text.split():
        if tok == "|":
            if abs((pos - bar_start) - bar) > 1e-9:
                raise ValueError("bar of %.3f units before %r (at unit %.1f)" % (pos - bar_start, tok, pos))
            bar_start = pos
            continue
        p, rest = tok.split(":")
        i = 0
        while i < len(rest) and (rest[i].isdigit() or rest[i] == "."):
            i += 1
        length = float(rest[:i])
        flags = rest[i:]
        if p != "r":
            out.append((pos, length, A.midi(p), flags))
        pos += length
    if abs((pos - bar_start) - bar) > 1e-9:
        raise ValueError("last bar of %.3f units in %r" % (pos - bar_start, text[:40]))
    return out


# pitch classes of the chords used here (root first)
_PC = {"C": 0, "C#": 1, "D": 2, "E": 4, "F": 5, "F#": 6, "G": 7, "A": 9, "B": 11}


def _chord_pcs(name: str) -> Tuple[List[int], int]:
    """'F#m' -> ([6, 9, 1], bass pc); 'D/F#' -> D major over F#; '7', 'sus4', 'm7'."""
    body, _, bass = name.partition("/")
    root = body[:2] if len(body) > 1 and body[1] == "#" else body[:1]
    kind = body[len(root):]
    r = _PC[root]
    shapes = {"": [0, 4, 7], "m": [0, 3, 7], "7": [0, 4, 7, 10], "m7": [0, 3, 7, 10], "sus4": [0, 5, 7],
              "sus2": [0, 2, 7], "maj7": [0, 4, 7, 11], "5": [0, 7]}
    pcs = [(r + s) % 12 for s in shapes[kind]]
    return pcs, (_PC[bass] if bass else r)


def _voicings(chords: Sequence[str], lo: int, hi: int, voices: int = 3, start: Optional[List[int]] = None
              ) -> List[List[int]]:
    """Close voicings for ``voices`` upper parts between MIDI ``lo`` and ``hi``, each
    chord chosen to move the parts as little as possible from the last (good voice
    leading): every note of a triad; root, third and seventh of a seventh chord."""
    import itertools
    out = []
    prev = start
    for ch in chords:
        pcs, _ = _chord_pcs(ch)
        cand = [m for m in range(lo, hi + 1) if m % 12 in pcs]
        must = set(pcs) if len(pcs) <= voices else {pcs[0], pcs[1], pcs[3]}
        best, best_cost = None, 1e9
        for combo in itertools.combinations(cand, voices):
            if not must <= {m % 12 for m in combo}:
                continue
            if combo[-1] - combo[0] > 12:
                continue
            cost = 0.0 if prev is None else sum(abs(a - b) for a, b in zip(combo, prev))
            cost += 0.01 * abs(sum(combo) / voices - (lo + hi) / 2)
            if cost < best_cost:
                best, best_cost = list(combo), cost
        if best is None:
            raise ValueError("no voicing for %s in %d..%d" % (ch, lo, hi))
        out.append(best)
        prev = best
    return out


class _Clock:
    """Units (eighth notes) to seconds: a steady pulse, an optional swing (each off-beat
    eighth a little late) and an optional rubato, a gentle push and pull repeating every
    phrase whose average is the steady tempo (so the loop keeps its exact length)."""

    def __init__(self, unit_s: float, swing: float = 0.0, rubato: float = 0.0, phrase_units: float = 48.0,
                 peak_at: float = 0.92):
        self.u = unit_s
        self.swing = swing
        self.rub = rubato
        self.P = phrase_units
        self.peak = peak_at

    def __call__(self, units: float) -> float:
        u = float(units)
        if self.swing:
            b = math.floor(u / 2.0)
            j = u - 2.0 * b
            u = 2.0 * b + float(np.interp(j, [0.0, 1.0, 2.0], [0.0, 1.0 + self.swing, 2.0]))
        if self.rub:
            w = 2 * math.pi / self.P
            u = u + self.rub / w * (math.sin(w * u - 2 * math.pi * self.peak) + math.sin(2 * math.pi * self.peak))
        return u * self.u


# ----------------------------------------------------------------------------- the loop and the room
class _Loop:
    """Mono parts as circular buffers exactly one loop long, mixed into a stereo loop."""

    def __init__(self, seconds: float, name: str = ""):
        self.n = _n(seconds)
        self.name = name
        self.parts: List[tuple] = []

    def stem(self) -> np.ndarray:
        return np.zeros(self.n)

    def add(self, buf: np.ndarray, x: np.ndarray, t: float, gain: float = 1.0) -> None:
        """Add a sound at ``t`` seconds; whatever runs past the end wraps to the start (and a
        time before the start wraps to the end)."""
        i = _n(t) % self.n
        pos = 0
        while pos < len(x):
            k = min(len(x) - pos, self.n - i)
            buf[i:i + k] += gain * x[pos:pos + k]
            pos += k
            i = 0

    def part(self, name: str, stem: np.ndarray, level_db: float, pan: float = 0.0, send: float = 0.25) -> None:
        self.parts.append((name, stem, level_db, pan, send))

    def render(self, ir: np.ndarray, master: Optional[Callable[[np.ndarray], np.ndarray]] = None) -> np.ndarray:
        dry = np.zeros((self.n, 2))
        snd = np.zeros((self.n, 2))
        for name, stem, level_db, pan, send in self.parts:
            x = _to_db(stem, level_db)
            st = A.pan(x, pan)
            dry += st
            snd += st * send
            if _DEBUG is not None:
                _DEBUG.setdefault(self.name, {})[name] = (x, pan, send)
        wet = np.stack([_cconv(snd[:, c], ir[:, c]) for c in range(2)], axis=1)
        out = dry + wet
        out = _cfilt(out, lambda y: A.highpass(y, 32, 2))
        if master:
            out = _cfilt(out, master)
        return out


def _room_ir(rt60: float, seed: int, predelay: float = 0.012, length: Optional[float] = None,
             hi_rt: float = 0.45, lo_rt: float = 1.1, hp: float = 180.0, lp: float = 7000.0) -> np.ndarray:
    """A stereo room: a few early reflections, then a diffuse tail whose highs die sooner
    than its lows, different in each ear; unit energy per ear."""
    length = length or min(4.0, rt60 * 1.25)
    n = _n(length)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    chans = []
    for ch in range(2):
        w = rng.standard_normal(n)
        lo = A.lowpass(w, 450, 2)
        hi = A.highpass(w, 3000, 2)
        mid = A.bandpass(w, 450, 3000, 1)

        def env(r):
            return np.exp(-6.9078 * t / max(0.05, r))

        late = lo * env(rt60 * lo_rt) + mid * env(rt60) + hi * env(rt60 * hi_rt)
        late *= 1 - np.exp(-t / 0.025)
        pd = _n(predelay)
        late = np.concatenate([np.zeros(pd), late])[:n]
        er = np.zeros(n)
        for _ in range(12):
            d = predelay * 0.5 + rng.uniform(0.002, 0.06)
            er[_n(d)] += rng.choice([-1.0, 1.0]) * rng.uniform(0.3, 1.0) * math.exp(-d / 0.035)
        er = A.lowpass(er, 5000, 1)
        late /= math.sqrt(np.sum(late ** 2))
        er /= math.sqrt(np.sum(er ** 2))
        chans.append(0.88 * late + 0.4 * er)
    ir = np.stack(chans, axis=1)
    ir = A.highpass(ir, hp, 2)
    ir = A.lowpass(ir, lp, 2)
    k = _n(0.08)
    ir[-k:] *= np.linspace(1, 0, k)[:, None]
    return ir / math.sqrt(np.sum(ir ** 2) / 2)


# ----------------------------------------------------------------------------- plucked strings
_CACHE: Dict[tuple, np.ndarray] = {}

HARPSICHORD = dict(name="harpsichord", choirs=((0.0, 1.0, 0.118), (1.4, 0.8, 0.086)), tilt=1.0,
                   fmax=7000.0, ftaper=3400.0, tau=1.5, tpow=0.6, hf=0.24, B=1.2e-5, q=0.35, qtau=0.18,
                   att=0.0007, rel=0.10, noise=0.030, nlo=1800.0, nhi=5500.0, ndecay=0.0035,
                   thud=0.012, variants=3)
CITTERN = dict(name="cittern", choirs=((0.0, 1.0, 0.16), (2.6, 0.8, 0.155)), tilt=1.1, fmax=6500.0,
               ftaper=3800.0, tau=1.0, tpow=0.5, hf=0.45, B=3.5e-5, q=0.4, qtau=0.2, att=0.0010, rel=0.12,
               noise=0.045, nlo=1500.0, nhi=5000.0, ndecay=0.005, thud=0.0, variants=4)


def _pluck(f: float, ring: float, vel: float, seed: int, P: dict) -> np.ndarray:
    """A plucked string (see the module notes): rings for ``ring`` seconds, then a damper
    or a finger stops it over P['rel']."""
    ring = max(0.05, round(ring * 20) / 20.0)
    var = seed % P["variants"]
    key = (P["name"], round(f, 3), ring, var)
    if key not in _CACHE:
        rel = P["rel"]
        n = _n(ring + rel + 0.01)
        t = np.arange(n) / SR
        rng = np.random.default_rng(int(f * 10) * 7 + var)
        y = np.zeros(n)
        tau1 = P["tau"] * (220.0 / f) ** P["tpow"]
        for cents, gain, pos in P["choirs"]:
            fs = f * 2 ** (cents / 1200.0)
            for k in range(1, 400):
                fk = k * fs * math.sqrt(1 + P["B"] * k * k)
                if fk > P["fmax"]:
                    break
                a = gain * abs(math.sin(math.pi * k * pos)) / k ** P["tilt"]
                if fk > P["ftaper"]:
                    a *= 0.5 + 0.5 * math.cos(math.pi * (fk - P["ftaper"]) / (P["fmax"] - P["ftaper"]))
                if a < 2e-4:
                    continue
                tau = 1.0 / (1.0 / tau1 + P["hf"] * (fk / 1000.0) ** 2)
                L = min(n, _n(tau * 7.0))
                tl = t[:L]
                env = (1 - P["q"]) * np.exp(-tl / tau) + P["q"] * np.exp(-tl / (tau * P["qtau"]))
                y[:L] += a * env * np.sin(2 * np.pi * fk * tl + rng.uniform(-0.4, 0.4))
        # the quill or plectrum leaving the string
        m = min(n, _n(0.03))
        nz = A.bandpass(rng.standard_normal(m), P["nlo"], P["nhi"], 2) * np.exp(-t[:m] / P["ndecay"])
        y[:m] += P["noise"] * nz * (1.0 + 0.5 * (f < 200))
        k = max(2, _n(P["att"]))
        y[:k] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(k) / k)
        # the damper: a quick fall with a soft felt thud
        r0 = _n(ring)
        if r0 < n:
            x = (t[r0:] - ring) / rel
            y[r0:] *= np.exp(-5.0 * x) * (0.5 + 0.5 * np.cos(np.pi * np.clip(x, 0, 1)))
            if P["thud"]:
                mm = min(n - r0, _n(0.025))
                th = A.bandpass(rng.standard_normal(mm), 250, 1400, 2) * np.exp(-np.arange(mm) / SR / 0.006)
                y[r0:r0 + mm] += P["thud"] * th
        _CACHE[key] = y
    return _CACHE[key] * vel


def _ornament(notes: list, clock: _Clock, scale_pcs: set, speed: float = 0.07, trill: float = 0.75) -> List[tuple]:
    """Expand flags into the notes a player adds: 'm' a mordent (note, the scale step
    below, note), 't' a trill from the step above, 'g' a quick grace note from above.
    ``notes`` are (unit, length, midi, flags); returns (seconds, seconds, midi, accent)."""

    def step(m, d):
        k = m + d
        while k % 12 not in scale_pcs:
            k += d
        return k

    out = []
    for (u, l, m, fl) in notes:
        t0 = clock(u)
        dur = clock(u + l) - t0
        if "m" in fl and dur > 3 * speed:
            out += [(t0, speed * 0.8, m, 1.0), (t0 + speed * 0.8, speed * 0.8, step(m, -1), 0.8),
                    (t0 + speed * 1.6, dur - speed * 1.6, m, 0.9)]
        elif "t" in fl and dur > 4 * speed:
            up = step(m, +1)
            k = int((dur * trill) / speed)
            k -= k % 2
            tt = t0
            for i in range(k):
                out.append((tt, speed, up if i % 2 == 0 else m, 0.95 if i == 0 else 0.75))
                tt += speed
            out.append((tt, t0 + dur - tt, m, 0.85))
        elif "g" in fl:
            out += [(t0 - speed * 0.7, speed * 0.7, step(m, +1), 0.7), (t0, dur, m, 1.0)]
        else:
            out.append((t0, dur, m, 1.0))
    return out


# ----------------------------------------------------------------------------- bowed strings
VIOLINS = dict(att=0.20, rel=0.40, glide=0.035, glide_bow=0.015, dip=0.55, dip_t=0.07, vib_rate=5.3,
               vib_depth=13.0, vib_delay=0.28, drift=3.0, noise=0.012, swell=0.18)
SECTION = dict(att=0.45, rel=0.70, glide=0.08, glide_bow=0.03, dip=0.75, dip_t=0.12, vib_rate=5.0,
               vib_depth=9.0, vib_delay=0.4, drift=3.0, noise=0.008, swell=0.12)


def _bow_phrase(notes: list, P: dict, seed: int, cents: float = 0.0) -> np.ndarray:
    """One phrase of a bowed line as one continuous tone (see the module notes).
    ``notes``: (t, d, midi, vel, new_bow) with t in seconds from the phrase's start."""
    rng = np.random.default_rng(seed)
    t_end = notes[-1][0] + notes[-1][1]
    n = _n(t_end + P["rel"] * 3.0 + 0.02)
    starts = [_n(x[0]) for x in notes]
    ends = starts[1:] + [_n(t_end)]
    pitch = np.zeros(n)
    lvl = np.zeros(n)
    vd = np.zeros(n)
    for i, (t0, d, m, v, nb) in enumerate(notes):
        s, e = starts[i], ends[i]
        L = max(1, e - s)
        pitch[s:e] = m
        x = np.linspace(0, 1, L)
        sw = (1 - P["swell"] + P["swell"] * np.sin(np.pi * x) ** 0.8) if d > 0.7 else np.ones(L)
        lvl[s:e] = v * sw[:e - s]
        on = np.clip((np.arange(L) / SR - P["vib_delay"]) / 0.45, 0, 1)
        vd[s:e] = (on * P["vib_depth"] * min(1.0, 0.45 + d / 1.2))[:e - s]
    e0 = ends[-1]
    pitch[e0:] = notes[-1][2]
    lvl[e0:] = lvl[e0 - 1]
    vd[e0:] = vd[e0 - 1]
    for i in range(1, len(notes)):
        p0, p1 = notes[i - 1][2], notes[i][2]
        if p0 == p1:
            continue
        w = max(2, _n(P["glide_bow"] if notes[i][4] else P["glide"]))
        a = max(0, starts[i] - w // 2)
        b = min(n, a + w)
        pitch[a:b] = p0 + (p1 - p0) * _smoothstep(np.linspace(0, 1, b - a))
    env = np.ones(n)
    for i in range(1, len(notes)):
        if notes[i][4]:
            s = starts[i]
            w = _n(P["dip_t"])
            a, b = max(0, s - w // 2), min(n, s + w // 2)
            x = np.linspace(-1, 1, b - a)
            env[a:b] *= 1 - (1 - P["dip"]) * (0.5 + 0.5 * np.cos(np.pi * x))
    a0 = _n(P["att"])
    env[:a0] *= _smoothstep(np.linspace(0, 1, a0)) ** 0.8
    rel = np.arange(n - e0) / SR
    env[e0:] *= np.exp(-rel / (P["rel"] / 2.5)) * (0.5 + 0.5 * np.cos(np.pi * np.clip(rel / (P["rel"] * 3.0), 0, 1)))
    a1 = 1 - math.exp(-1 / (0.02 * SR))
    lvl = signal.lfilter([a1], [1, -(1 - a1)], lvl, zi=[lvl[0] * (1 - a1)])[0]
    rate = P["vib_rate"] * (1 + 0.04 * _wander(n, 0.5, seed + 1))
    lfo = np.sin(2 * np.pi * np.cumsum(rate) / SR + rng.uniform(0, 6.28))
    cnt = vd * lfo + P["drift"] * _wander(n, 0.35, seed + 2) + cents
    f = 440.0 * 2 ** ((pitch + cnt / 100.0 - 69) / 12.0)
    y = A.osc("saw", f, n / SR, phase=rng.uniform(0, 6.28))[:n]
    amp = env * lvl * (1 + 0.04 * _wander(n, 2.0, seed + 3))
    bow = A.bandpass(rng.standard_normal(n), 1800, 5500, 2) * P["noise"]
    return (y + bow) * amp


def _phrases(notes: list, join: float = 0.03) -> List[list]:
    """Split (t, d, ...) notes into phrases wherever there is a rest."""
    out: List[list] = []
    for nt in sorted(notes, key=lambda x: x[0]):
        if out and nt[0] - (out[-1][-1][0] + out[-1][-1][1]) < join:
            out[-1].append(nt)
        else:
            out.append([nt])
    return out


def _bowed_part(loop: _Loop, notes: list, P: dict, seed: int, cents: float = 0.0, delay: float = 0.0,
                jitter: float = 0.0) -> np.ndarray:
    """``notes``: (t, d, midi, vel, new_bow) in seconds, rendered phrase by phrase."""
    buf = loop.stem()
    rng = np.random.default_rng(seed)
    for k, ph in enumerate(_phrases(notes)):
        t0 = ph[0][0]
        rel = [(x[0] - t0 + (rng.normal(0, jitter) if (jitter and i) else 0.0),) + tuple(x[1:])
               for i, x in enumerate(ph)]
        fixed = []
        for i, x in enumerate(rel):
            nxt = rel[i + 1][0] if i + 1 < len(rel) else x[0] + x[1]
            fixed.append((max(0.0, x[0]), max(0.04, nxt - x[0]) if i + 1 < len(rel) else x[1]) + tuple(x[2:]))
        y = _bow_phrase(fixed, P, seed * 131 + k, cents)
        loop.add(buf, y, t0 + delay)
    return buf


# ----------------------------------------------------------------------------- hurdy-gurdy
def _periodic(f: np.ndarray) -> np.ndarray:
    """Nudge a frequency curve (by far less than a cent) so it makes a whole number of
    cycles over its length: the tone then joins itself at the loop's seam."""
    cyc = float(np.sum(f)) / SR
    return f * (max(1, round(cyc)) / cyc)


def _hg_line(events: Sequence[Tuple[float, float]], n: int, seed: int, detune_c: float = 3.5,
             beat_s: float = 0.6, crank: float = 0.05, rosin: float = 0.07, drift_c: float = 1.5,
             pair: float = 0.55) -> np.ndarray:
    """A hurdy-gurdy string pair sounding the whole loop (see the module notes).
    ``events``: (t, midi) note starts in seconds; each note lasts until the next, and the
    last one until the first comes round again. ``pair`` is the level of the second string
    of the pair (0: a single string); kept below the first so their beating never empties
    the tone."""
    rng = np.random.default_rng(seed)
    ev = sorted((_n(t) % n, m) for t, m in events)
    pitch = np.empty(n)
    for i, (s, m) in enumerate(ev):
        e = ev[i + 1][0] if i + 1 < len(ev) else n
        pitch[s:e] = m
    pitch[:ev[0][0]] = ev[-1][1]
    art = np.ones(n)
    for i in range(len(ev)):
        if ev[i][1] == ev[i - 1][1] and len(ev) > 1:      # a repeated note: the key let go for an instant
            s = ev[i][0]
            w = _n(0.03)
            idx = (np.arange(-w, w) + s) % n
            art[idx] *= 1 - 0.35 * (0.5 + 0.5 * np.cos(np.pi * np.arange(-w, w) / w))
    # the tangent's quick change (a few ms), in the loop's steady state
    pitch = _cfilt(pitch, lambda p: A.lowpass(p, 45.0, 1), warm=0.3)
    t = np.arange(n) / SR
    drift = drift_c * _wander(n, 0.3, seed + 1)
    y = np.zeros(n)
    ph = None
    for k, (c, g) in enumerate(((-detune_c / 2, 1.0), (detune_c / 2, pair))):
        if not g:
            continue
        f = 440.0 * 2 ** ((pitch + (c + drift * (1.0 if k == 0 else -0.6)) / 100.0 - 69) / 12.0)
        f = _periodic(f)
        y += g * A.osc("saw", f, n / SR, phase=rng.uniform(0, 6.28))[:n]
        if ph is None:
            ph = np.cumsum(f) / SR
    # rosin on the wheel: a grain of noise at each slip of the string
    nz = _cfilt(rng.standard_normal(n), lambda x: A.bandpass(x, 1500, 5000, 2), warm=0.05)
    y = y + rosin * nz * np.exp(-(ph % 1.0) / 0.12)
    # the crank: one turn a beat, a little stronger as the hand pulls
    am = 1 + crank * np.cos(2 * np.pi * t / beat_s - 0.6) + 0.02 * _wander(n, 1.5, seed + 2)
    return y * am * art


def _hg_body(x: np.ndarray, dark: float = 6500.0) -> np.ndarray:
    """The hurdy-gurdy's nasal, vowel-like body: formant peaks near 700 Hz, 1.25 kHz and
    2.5 kHz over a small box."""
    x = A.highpass(x, 170, 2)
    x = A.peak_eq(x, 700, 5.0, 1.8)
    x = A.peak_eq(x, 1250, 6.0, 2.2)
    x = A.peak_eq(x, 2500, 4.5, 2.5)
    x = A.peak_eq(x, 3900, -5.0, 1.0)
    return A.lowpass(x, dark, 2)


def _coup(f: float, dur: float, vel: float, seed: int) -> np.ndarray:
    """The trompette's buzz (see the module notes): a knock at the start of every string
    cycle with a little randomness, coloured by the soundboard; rendered 4x oversampled
    so the sharp knocks do not alias."""
    os_ = 4
    sr = SR * os_
    n = int(round((dur + 0.07) * sr))
    t = np.arange(n) / sr
    rng = np.random.default_rng(seed)
    fr = f * (1 + 0.004 * np.exp(-t / 0.03))
    ph = np.cumsum(fr) / sr
    frac = ph % 1.0
    knock = np.exp(-frac / 0.05)
    cyc = np.floor(ph).astype(int)
    amp = np.clip(1 + 0.35 * rng.standard_normal(cyc.max() + 2), 0.2, 2.0)
    y = (knock - 0.05) * amp[cyc]
    y = signal.resample_poly(y, 1, os_)
    m = len(y)
    tt = np.arange(m) / SR
    y = A.bandpass(y, 500, 4800, 2)
    y = A.peak_eq(y, 1900, 6.0, 2.0)
    hold = dur * 0.55
    env = (1 - np.exp(-tt / 0.006)) * np.where(tt < hold, 1.0, np.exp(-(tt - hold) / 0.028))
    return y * env * vel


def _drum(kind: str, vel: float, seed: int, pitch: float = 105.0) -> np.ndarray:
    """A frame drum as a circular membrane: 'down' a full stroke near the middle (low,
    round), 'up' the lighter return stroke, 'tap' a touch near the rim (high and papery)."""
    key = ("drum", kind, seed % 5, round(pitch, 1))
    if key not in _CACHE:
        rng = np.random.default_rng(seed % 5 + 11)
        n = _n(0.55)
        t = np.arange(n) / SR
        ratios = [1.0, 1.594, 2.136, 2.296, 2.653, 2.918, 3.156, 3.501]
        if kind == "down":
            amps, tau1, f0, slap = [0.9, 0.35, 0.4, 0.12, 0.2, 0.1, 0.08, 0.05], 0.12, pitch, 0.25
        elif kind == "up":
            amps, tau1, f0, slap = [0.5, 0.45, 0.42, 0.22, 0.22, 0.14, 0.12, 0.07], 0.10, pitch * 1.06, 0.3
        else:
            amps, tau1, f0, slap = [0.1, 0.2, 0.3, 0.35, 0.35, 0.3, 0.25, 0.22], 0.06, pitch * 1.1, 0.7
        bend = 1.0 + 0.07 * np.exp(-t / 0.02)
        y = np.zeros(n)
        for i, (r, a) in enumerate(zip(ratios, amps)):
            ph = 2 * np.pi * np.cumsum(f0 * r * bend) / SR
            env = np.exp(-t / (tau1 / (1 + 0.4 * i)))
            y += a * (1 + rng.uniform(-0.1, 0.1)) * np.sin(ph + rng.uniform(0, 6.28)) * env
        m = _n(0.04)
        y[:m] += slap * 0.5 * A.bandpass(rng.standard_normal(m), 350, 3000, 2) * np.exp(-t[:m] / 0.009)
        k = _n(0.0015)
        y[:k] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(k) / k)
        _CACHE[key] = A.highpass(y, 65, 2)
    return _CACHE[key] * vel


# ============================================================================= 1. Hurdy-gurdy dance
# 4/4 at 100 crotchets a minute, eighth notes as units (8 to a bar), D dorian over a D-A
# drone. A tune in two strains, each played twice: A A' B B' (32 bars).
HG_A = ("D5:2 A4:1 D5:1 F5:2 E5:1 D5:1 | E5:2 C5:1 E5:1 G5:2 F5:1 E5:1 | F5:1 E5:1 D5:1 E5:1 F5:1 G5:1 A5:2 | "
        "B5:2 G5:1 B5:1 A5:4 | D5:2 A4:1 D5:1 F5:2 E5:1 D5:1 | E5:2 C5:1 E5:1 G5:2 F5:1 E5:1 | "
        "D5:1 B4:1 G4:1 B4:1 C5:1 E5:1 G5:1 E5:1 | D5:5 A4:1 B4:1 C5:1")
HG_A2 = ("D5:2g A4:1 D5:1 F5:2 E5:1 D5:1 | E5:2g C5:1 E5:1 G5:2 F5:1 E5:1 | F5:1 E5:1 D5:1 E5:1 F5:1 G5:1 A5:2g | "
         "B5:2 G5:1 B5:1 A5:4t | D5:2g A4:1 D5:1 F5:2 E5:1 D5:1 | E5:2g C5:1 E5:1 G5:2 F5:1 E5:1 | "
         "D5:1 B4:1 G4:1 B4:1 C5:1 E5:1 G5:1 E5:1 | D5:5t E5:1 F5:1 G5:1")
HG_B = ("A5:3 G5:1 F5:2 A5:2 | G5:3 F5:1 E5:2 G5:2 | F5:2 A5:2 D6:2 C6:1 A5:1 | C6:2 B5:1 A5:1 E5:4 | "
        "A5:3 G5:1 F5:2 A5:2 | G5:3 F5:1 E5:2 G5:2 | E5:2 A5:1 G5:1 F5:1 E5:1 D5:1 C5:1 | D5:5 E5:1 F5:1 G5:1")
HG_B2 = ("A5:3g G5:1 F5:2 A5:2 | G5:3g F5:1 E5:2 G5:2 | F5:2 A5:2 D6:2g C6:1 A5:1 | C6:2 B5:1 A5:1 E5:4t | "
         "A5:3g G5:1 F5:2 A5:2 | G5:3g F5:1 E5:2 G5:2 | E5:2 A5:1 G5:1 F5:1 E5:1 D5:1 C5:1 | D5:5t A4:1 B4:1 C5:1")
HG_CH_A = ["Dm", "Dm", "C", "C", "Dm", "Dm", "G", "Am", "Dm", "Dm", "C", "C", "G", "C", "Dm", "Dm"]
HG_CH_B = ["F", "F", "C", "C", "Dm", "Dm", "Am", "Am", "F", "F", "C", "C", "Am", "G", "Dm", "Dm"]
HG_CH = HG_CH_A + HG_CH_A + HG_CH_B + HG_CH_B          # one chord per half bar
D_DORIAN = {2, 4, 5, 7, 9, 11, 0}
HG_BPM = 100.0
HG_BARS = 32
HG_SECONDS = _aac_aligned(HG_BARS * 8 * 60.0 / HG_BPM / 2.0)
HG_UNIT = HG_SECONDS / (HG_BARS * 8)


def _harmonize(mel: list, chords: Sequence[str], upc: float, scale: set, lo: int) -> list:
    """A second voice under the tune: a third below, except on a beat where the third
    would clash with the chord; there it takes the chord tone a third to a sixth below
    that lies nearest its last note (a fourth counts as a little further); off the beat,
    a third or a sixth below, whichever is nearer. So the line moves smoothly."""

    def down(m, steps):
        k, c = m, 0
        while c < steps:
            k -= 1
            if k % 12 in scale:
                c += 1
        return k

    out = []
    prev = None
    for (u, l, m, fl) in mel:
        pcs, _ = _chord_pcs(chords[int(u // upc) % len(chords)])
        ref = prev if prev is not None else m - 8
        h = down(m, 2)
        if abs(u / 2 - round(u / 2)) < 1e-9:
            if h % 12 not in pcs:
                cands = [k for k in range(m - 9, m - 2) if k % 12 in pcs and k >= lo]
                if not cands:
                    cands = [k for k in range(m - 9, m - 2) if k % 12 in pcs]
                h = min(cands, key=lambda k: abs(k - ref) + (1.5 if m - k == 5 else 0))
        else:
            h = min((down(m, 2), down(m, 5)), key=lambda k: abs(k - ref) + (0 if k >= lo else 12))
        while h < lo:
            h += 12
        out.append((u, l, h, fl.replace("t", "").replace("g", "")))
        prev = h
    return out


def _hurdy_score() -> dict:
    mel = _parse(HG_A, 8, 0) + _parse(HG_A2, 8, 64) + _parse(HG_B, 8, 128) + _parse(HG_B2, 8, 192)
    harm = _harmonize(_parse(HG_B2, 8, 192)[:-3], HG_CH, 4, D_DORIAN, 62)
    bass = []
    for i, ch in enumerate(HG_CH):
        pcs, bpc = _chord_pcs(ch)
        root = min(m for m in range(41, 53) if m % 12 == bpc)
        prev = HG_CH[i - 1] if i % 2 else None
        note = root if prev != ch else (root + 7 if root + 7 <= 52 else root - 5)
        bass.append((i * 4.0, 2.0, note, ""))
    return dict(mel=mel, harm=harm, bass=bass, chords=HG_CH)


def _hurdy_gurdy_dance() -> np.ndarray:
    _CACHE.clear()
    sc = _hurdy_score()
    clock = _Clock(HG_UNIT, swing=0.08)
    beat = 2 * HG_UNIT
    loop = _Loop(HG_SECONDS, "hurdy")
    n = loop.n
    rng = np.random.default_rng(2718)

    # ---- the melody strings: one unbroken line round the whole loop
    ev = [(t, m) for (t, d, m, a) in _ornament(sc["mel"], clock, D_DORIAN, speed=0.065, trill=0.55)]
    mel = _hg_line(ev, n, seed=5, detune_c=2.2, beat_s=beat, drift_c=1.0, pair=0.5)
    # ---- a second hurdy-gurdy joins a third below for the last strain (bars 25-32)
    hev = [(clock(u), m) for (u, l, m, fl) in sc["harm"]]
    hev = [(clock(20 * 8), sc["harm"][0][2])] + hev          # waits on its first note, silent
    harm = _hg_line(hev, n, seed=8, detune_c=2.0, beat_s=beat, rosin=0.05, drift_c=1.0, pair=0.45)
    gate = np.zeros(n)
    a, b = _n(clock(24 * 8) - 0.04), _n(clock(31 * 8 + 4))
    fade_in, fade_out = _n(0.08), _n(0.35)
    gate[a:b] = 1.0
    gate[a:a + fade_in] = _smoothstep(np.linspace(0, 1, fade_in))
    gate[b:b + fade_out] = 1 - _smoothstep(np.linspace(0, 1, fade_out))
    harm = harm * gate
    # ---- the drones: D3 and A3, and the trompette string on D4 (soft between its buzzes)
    drone = (_hg_line([(0.0, 50)], n, seed=21, detune_c=0.0, beat_s=beat, rosin=0.05, drift_c=1.0, pair=0.0)
             + 0.85 * _hg_line([(0.0, 57)], n, seed=22, detune_c=0.0, beat_s=beat, rosin=0.05, drift_c=1.0,
                               pair=0.0))
    trompette = _hg_line([(0.0, 62)], n, seed=23, detune_c=0.0, beat_s=beat, rosin=0.08, drift_c=1.0, pair=0.0)

    # ---- coups (the trompette buzz) and the frame drum, by strain
    buzz = loop.stem()
    drum = loop.stem()
    for bar in range(HG_BARS):
        strain = "A" if bar < 8 else ("A2" if bar < 16 else ("B" if bar < 24 else "B2"))
        coups = {"A": [(2, 0.8), (6, 0.85)], "A2": [(2, 0.8), (6, 0.85), (7, 0.55)],
                 "B": [(6, 0.6)], "B2": [(2, 0.8), (6, 0.85), (7, 0.5)]}[strain]
        hits = {"A": [(0, "down", 0.8), (4, "down", 0.55), (7, "up", 0.32)],
                "A2": [(0, "down", 0.85), (3, "tap", 0.22), (4, "down", 0.6), (7, "up", 0.36)],
                "B": [(0, "down", 0.6), (4, "tap", 0.25)],
                "B2": [(0, "down", 0.85), (3, "tap", 0.22), (4, "down", 0.6), (6, "tap", 0.2), (7, "up", 0.38)]}[strain]
        if bar in (15, 31):
            hits = hits + [(5, "up", 0.3), (6, "up", 0.36)]
        for (u, v) in coups:
            uu = bar * 8 + u
            loop.add(buzz, _coup(_mhz(62), 0.15, v * (1 + rng.uniform(-0.08, 0.08)), int(uu)),
                     clock(uu) + rng.normal(0, 0.004))
        for (u, kind, v) in hits:
            uu = bar * 8 + u
            loop.add(drum, _drum(kind, v * (1 + rng.uniform(-0.08, 0.08)), int(uu)), clock(uu) + rng.normal(0, 0.004))

    # ---- the cittern: a bass and a strum ("boom-chick") in A, A' and B'; broken chords in B
    cit_b, cit_c = loop.stem(), loop.stem()
    voic = _voicings(HG_CH, 59, 72, 3, start=[62, 65, 69])
    cnt = [0]

    def pl(buf, m, t, ring, v):
        cnt[0] += 1
        loop.add(buf, _pluck(_mhz(m), ring, v * (1 + rng.uniform(-0.06, 0.06)), cnt[0], CITTERN),
                 t + rng.normal(0, 0.005))

    for i, ch in enumerate(HG_CH):
        bar, half = divmod(i, 2)
        u0 = bar * 8 + half * 4
        bass = sc["bass"][i][2]
        vc = voic[i]
        if 16 <= bar < 24:
            seq = [bass, vc[0], vc[1], vc[2]]
            for j, m in enumerate(seq):
                t = clock(u0 + j)
                pl(cit_c if j else cit_b, m, t, clock(u0 + 4) - t + 0.1, (0.8, 0.5, 0.55, 0.6)[j])
        else:
            t = clock(u0)
            pl(cit_b, bass, t, clock(u0 + 2) - t + 0.05, 0.85 if half == 0 else 0.7)
            ts = clock(u0 + 2)
            for j, m in enumerate(vc):
                pl(cit_c, m, ts + 0.012 * j, 0.2, 0.5 - 0.04 * j)
            if bar >= 24 or (8 <= bar < 16):
                tq = clock(u0 + 3)
                for j, m in enumerate(vc[::-1]):
                    pl(cit_c, m, tq + 0.01 * j, 0.12, 0.3)

    # ---- body colour and the mix
    def cittern_eq(x, lo=80.0):
        x = A.highpass(x, lo, 2)
        x = A.peak_eq(x, 240, 2.5, 1.2)
        x = A.peak_eq(x, 2400, 1.5, 1.5)
        return A.lowpass(x, 6500, 2)

    loop.part("hg_melody", _cfilt(mel, _hg_body), -18.0, pan=0.08, send=0.25)
    loop.part("hg_harmony", _cfilt(harm, _hg_body), -22.0, pan=-0.3, send=0.28)
    loop.part("drone", _cfilt(drone, lambda x: _hg_body(x, 2600.0)), -25.0, pan=0.0, send=0.3)
    loop.part("trompette", _cfilt(trompette, lambda x: _hg_body(x, 3500.0)), -34.0, pan=0.05, send=0.3)
    loop.part("coups", buzz, -29.0, pan=0.05, send=0.22)
    loop.part("cittern_bass", _cfilt(cit_b, cittern_eq), -23.0, pan=-0.22, send=0.25)
    loop.part("cittern_chords", _cfilt(cit_c, lambda x: cittern_eq(x, 150.0)), -26.0, pan=-0.3, send=0.28)
    loop.part("frame_drum", drum, -27.0, pan=0.18, send=0.2)
    ir = _room_ir(1.2, seed=31, predelay=0.012)
    return loop.render(ir)


# ----------------------------------------------------------------------------- 8-bit voices
_TABLES: Dict[tuple, np.ndarray] = {}
_FRAME = 1.0 / 60.0          # the old consoles stepped their volume once per video frame


def _raw_wave(kind: str, size: int = 4096) -> np.ndarray:
    x = np.arange(size) / size
    if kind == "p50":
        return np.where(x < 0.5, 1.0, -1.0)
    if kind == "p25":
        return np.where(x < 0.25, 1.0, -1.0)
    if kind == "p125":
        return np.where(x < 0.125, 1.0, -1.0)
    if kind == "tri":                       # the 4-bit, 32-step triangle
        step = np.floor(x * 32).astype(int)
        v = np.where(step < 16, 15 - step, step - 16)
        return v / 7.5 - 1.0
    raise ValueError(kind)


def _wave_table(kind: str, f: float, soft: float = 2600.0, top: float = 8000.0, size: int = 2048) -> np.ndarray:
    """One period of ``kind`` for a note of ``f`` Hz, band-limited: harmonics fade out
    between ``soft`` and ``top`` Hz (no aliasing, and no glare up high), no DC."""
    key = (kind, round(f, 1), soft, top)
    if key not in _TABLES:
        spec = np.fft.rfft(_raw_wave(kind))
        k = np.arange(len(spec))
        fk = k * f
        w = np.where(fk <= soft, 1.0, 0.5 + 0.5 * np.cos(np.pi * np.clip((fk - soft) / (top - soft), 0, 1)))
        w[0] = 0.0
        w[k > size // 2 - 1] = 0.0
        spec = spec * w
        tab = np.fft.irfft(spec[:size // 2 + 1], size) * (size / 4096.0)
        _TABLES[key] = tab / (np.max(np.abs(np.fft.irfft(np.fft.rfft(_raw_wave(kind)) * (k > 0), 4096))) + 1e-12)
    return _TABLES[key]


def _osc_table(tab: np.ndarray, freq: np.ndarray, phase0: float = 0.0) -> np.ndarray:
    size = len(tab)
    ph = (phase0 + np.cumsum(freq) / SR) % 1.0
    pos = ph * size
    i0 = pos.astype(int) % size
    fr = pos - np.floor(pos)
    return tab[i0] * (1 - fr) + tab[(i0 + 1) % size] * fr


def _frames_env(levels: np.ndarray, n: int, smooth: float = 0.0025) -> np.ndarray:
    """Per-frame volume levels (60 a second) as a sample envelope, each step softened by a
    couple of milliseconds so it never clicks."""
    per = SR * _FRAME
    idx = np.minimum((np.arange(n) / per).astype(int), len(levels) - 1)
    env = levels[idx]
    a = 1 - math.exp(-1 / (smooth * SR))
    return signal.lfilter([a], [1, -(1 - a)], env, zi=[env[0] * (1 - a)])[0]


def _chip_note(kind: str, m: float, dur: float, vel: float, env: str = "lead", vib: float = 0.0,
               slide: bool = False, soft: float = 2600.0) -> np.ndarray:
    """One 8-bit note: a band-limited ``kind`` wave with a stepped volume envelope.
    'lead' (a quick fall to a held level), 'pluck' (falls away, for arpeggios), 'pad' (soft
    rise and fall) or 'gate' (on and off, the triangle has no volume control)."""
    f0 = _mhz(m)
    rel = {"lead": 0.07, "pluck": 0.03, "pad": 0.12, "gate": 0.012}[env]
    n = _n(dur + rel)
    t = np.arange(n) / SR
    freq = np.full(n, f0)
    if vib:
        on = np.clip((t - 0.22) / 0.25, 0, 1)
        lfo = 2 * np.abs(2 * ((t * 5.6) % 1.0) - 1) - 1          # a triangle LFO, as the drivers had
        freq *= 2 ** (vib * on * lfo / 1200.0)
    if slide:
        k = min(n, _n(0.05))
        freq[:k] *= 2 ** (-(1 - _smoothstep(np.linspace(0, 1, k))) / 12.0)
    tab = _wave_table(kind, f0, soft=soft)
    y = _osc_table(tab, freq)
    fr = np.arange(int(math.ceil(n / (SR * _FRAME))) + 1)
    on_frames = dur / _FRAME
    if env == "lead":
        lv = np.maximum(0.72, 1.0 - 0.05 * fr)
    elif env == "pluck":
        lv = np.maximum(0.12, 1.0 - 0.075 * fr)
    elif env == "pad":
        lv = np.minimum(1.0, 0.35 + 0.08 * fr)
    else:
        lv = np.ones(len(fr))
    lv = np.round(lv * 15) / 15.0                                  # sixteen volume steps
    off = fr >= on_frames
    if env == "gate":
        lv = np.where(off, 0.0, lv)
        e = _frames_env(lv, n, smooth=0.003)
    else:
        rel_fr = fr - on_frames
        lv = np.where(off, lv * np.clip(1 - rel_fr / (rel / _FRAME), 0, 1), lv)
        lv = np.round(lv * 15) / 15.0
        e = _frames_env(lv, n)
    k = _n(0.0015)
    e[:k] *= np.linspace(0, 1, k)
    e[-_n(0.004):] *= np.linspace(1, 0, _n(0.004))
    return y * e * vel


_LFSR: Dict[bool, np.ndarray] = {}


def _lfsr(short: bool = False) -> np.ndarray:
    """The noise channel's 15-bit shift register (long mode: hiss; short mode: metallic)."""
    if short not in _LFSR:
        s, tap = 1, (6 if short else 1)
        out = np.empty(32767)
        for i in range(32767):
            fb = (s ^ (s >> tap)) & 1
            s = (s >> 1) | (fb << 14)
            out[i] = 1.0 if s & 1 else -1.0
        _LFSR[short] = out
    return _LFSR[short]


def _chip_drum(kind: str, vel: float, seed: int) -> np.ndarray:
    """'kick' (the triangle swept down plus a dark noise tick), 'snare' (mid noise and a
    short tone), 'hat' (bright, short noise), each with frame-stepped decays."""
    bits = _lfsr()
    rng = np.random.default_rng(seed)
    off = int(rng.integers(0, len(bits)))

    def noise(n, rate):
        i = (off + (np.arange(n) * rate / SR).astype(int)) % len(bits)
        return bits[i]

    if kind == "kick":
        n = _n(0.2)
        t = np.arange(n) / SR
        f = 55.0 + 150.0 * np.exp(-t / 0.025)
        y = _osc_table(_wave_table("tri", 80.0, soft=1500.0, top=4000.0), f) * np.exp(-t / 0.07)
        y += 0.25 * noise(n, 4000.0) * np.exp(-t / 0.008)
        y = A.lowpass(y, 3000, 2)
    elif kind == "snare":
        n = _n(0.22)
        t = np.arange(n) / SR
        lv = np.round(np.maximum(0.0, 1.0 - 0.09 * np.arange(20)) * 15) / 15.0
        y = noise(n, 11186.0) * _frames_env(lv, n) * 0.8
        y += 0.5 * np.sin(2 * np.pi * np.cumsum(170 + 60 * np.exp(-t / 0.02)) / SR) * np.exp(-t / 0.04)
        y = A.lowpass(A.highpass(y, 150, 2), 7000, 2)
    else:
        n = _n(0.08)
        lv = np.round(np.maximum(0.0, 1.0 - 0.3 * np.arange(10)) * 15) / 15.0
        y = noise(n, 27965.0) * _frames_env(lv, n, smooth=0.002)
        y = A.lowpass(A.highpass(y, 4500, 2), 8000, 4)
    k = _n(0.001)
    y[:k] *= np.linspace(0, 1, k)
    y[-_n(0.003):] *= np.linspace(1, 0, _n(0.003))
    return y * vel


# ============================================================================= 2. Chiptune quest
# 4/4 at 120, eighth notes as units (8 to a bar), D major. A (1-8), A' (9-16), B (17-24,
# more tension), C (25-32, a quiet bridge: the triangle sings), A'' (33-40, the tune in
# thirds) and round again.
CH_LEAD_A = ("D5:3 A4:1 D5:1 E5:1 F#5:2 | F#5:3 E5:1 D5:2 B4:2 | G5:3 F#5:1 G5:1 A5:1 B5:2 | A5:6 r:2 | "
             "D5:3 A4:1 D5:1 E5:1 F#5:2 | B5:3 A5:1 F#5:2 B5:2 | D6:2 B5:2 C#6:2 A5:2 | D6:4 r:2 A4:1 C#5:1")
CH_LEAD_A2 = ("D5:3 A4:1 D5:1 E5:1 F#5:1 A5:1 | F#5:3 E5:1 D5:2 B4:1 D5:1 | G5:3 F#5:1 G5:1 A5:1 B5:1 D6:1 | "
              "C#6:4 A5:2 E5:2 | F#5:3 E5:1 F#5:1 A5:1 D6:2 | B5:3 A5:1 F#5:2 D5:2 | G5:2 B5:2 A5:2 C#6:2 | "
              "A5:4 E5:2 C#5:2")
CH_LEAD_B = ("B4:2 D5:1 F#5:2 E5:1 D5:2 | B4:2 D5:1 G5:2 F#5:1 D5:2 | F#5:2 A5:1 D6:2 C#6:1 A5:2 | "
             "E5:2 A5:1 C#6:2 B5:1 A5:2 | B4:2 D5:1 F#5:2 E5:1 D5:2 | B4:2 D5:1 G5:2 F#5:1 D5:2 | "
             "E5:2 G5:1 B5:2 A5:1 G5:2 | C#5:2 E5:2 A5:4")
CH_LEAD_C = "r:8 | r:8 | r:8 | r:8 | r:8 | r:8 | r:8 | r:6 A4:1 C#5:1"
CH_TRI_C = ("B4:3 D5:1 G5:4 | A5:3 G5:1 E5:4 | F#5:3 A5:1 C#6:4 | B5:3 A5:1 F#5:4 | G5:3 A5:1 B5:4 | "
            "A5:3 B5:1 C#6:4 | D6:3 C#6:1 B5:2 G5:2 | A5:8")
CH_CHORDS = (["D", "D", "Bm", "Bm", "G", "G", "A", "A", "D", "D", "Bm", "Bm", "G", "A", "D", "A"]
             + ["D", "D", "Bm", "Bm", "G", "G", "A", "A", "D", "D", "Bm", "Bm", "G", "A", "A", "A"]
             + ["Bm", "Bm", "G", "G", "D", "D", "A", "A", "Bm", "Bm", "G", "G", "Em", "Em", "A", "A"]
             + ["G", "G", "A", "A", "F#m", "F#m", "Bm", "Bm", "Em", "Em", "F#m", "F#m", "G", "G", "A", "A"]
             + ["D", "D", "Bm", "Bm", "G", "G", "A", "A", "D", "D", "Bm", "Bm", "G", "A", "D", "A"])
CHIP_BPM = 120.0
CHIP_BARS = 40
CHIP_SECONDS = _aac_aligned(CHIP_BARS * 8 * 60.0 / CHIP_BPM / 2.0)
CHIP_UNIT = CHIP_SECONDS / (CHIP_BARS * 8)


def _chip_score() -> dict:
    lead = (_parse(CH_LEAD_A, 8, 0) + _parse(CH_LEAD_A2, 8, 64) + _parse(CH_LEAD_B, 8, 128)
            + _parse(CH_LEAD_C, 8, 192) + _parse(CH_LEAD_A, 8, 256))
    tri_lead = _parse(CH_TRI_C, 8, 192)
    harm = _harmonize([x for x in _parse(CH_LEAD_A, 8, 256) if x[0] < 256 + 62], CH_CHORDS, 4, D_MAJOR, 59)
    bass = []
    for i, ch in enumerate(CH_CHORDS):
        _, bpc = _chord_pcs(ch)
        root = min(m for m in range(38, 50) if m % 12 == bpc)
        bass.append((i * 4.0, 4.0, root, ""))
    return dict(lead=lead, tri_lead=tri_lead, harm=harm, bass=bass, chords=CH_CHORDS)


def _chiptune_quest() -> np.ndarray:
    _TABLES.clear()
    sc = _chip_score()
    U = CHIP_UNIT
    loop = _Loop(CHIP_SECONDS, "chip")
    rng = np.random.default_rng(1985)

    def sect(bar):
        return "A" if bar < 8 else "A2" if bar < 16 else "B" if bar < 24 else "C" if bar < 32 else "D"

    # ---- lead (pulse: 50% for the tune, 25% for the tenser B strain) and its echo
    lead = loop.stem()
    for (u, l, m, fl) in sc["lead"]:
        s = sect(int(u // 8))
        kind = "p25" if s == "B" else "p50"
        d = l * U * (0.92 if l <= 1 else 0.96)
        long_ = l >= 3
        x = _chip_note(kind, m, d, 0.95 if u % 2 == 0 else 0.85, "lead", vib=(22.0 if long_ else 0.0),
                       slide=(long_ and s in ("A2", "D") and (u % 8) == 0), soft=2400.0)
        loop.add(lead, x, u * U + rng.normal(0, 0.002))
    echo = np.roll(lead, _n(3 * U / 2))                         # three sixteenths later
    # ---- harmony a third below in the last section (the second pulse)
    harm = loop.stem()
    for (u, l, m, fl) in sc["harm"]:
        d = l * U * (0.92 if l <= 1 else 0.96)
        loop.add(harm, _chip_note("p25", m, d, 0.8, "lead", vib=(18.0 if l >= 3 else 0.0), soft=2200.0), u * U)
    # ---- the bridge's tune on the triangle
    tri_lead = loop.stem()
    for (u, l, m, fl) in sc["tri_lead"]:
        loop.add(tri_lead, _chip_note("tri", m, l * U * 0.97, 1.0, "gate", vib=15.0 if l >= 3 else 0.0), u * U)
    # ---- arpeggios (the second pulse): broken chords, faster as the tune builds
    arp = loop.stem()
    voic = _voicings(CH_CHORDS, 57, 71, 3, start=[62, 66, 69])
    for i, ch in enumerate(CH_CHORDS):
        bar = i // 2
        s = sect(bar)
        vc = voic[i]
        notes = vc + [vc[0] + 12]
        u0 = i * 4.0
        if s == "C":
            # a soft chord shimmer: the three notes in turn every two frames (the old trick)
            seq = vc * 40
            dt = 2 * _FRAME
            k = int(4 * U / dt)
            for j in range(k):
                v = 0.55 * (0.45 + 0.55 * (1 - j / k))
                loop.add(arp, _chip_note("p50", seq[j], dt, v, "gate", soft=1800.0), u0 * U + j * dt)
            continue
        if s == "A":
            pat, step = [0, 1, 2, 3], 1.0
        elif s == "B":
            pat, step = [0, 2, 1, 3, 2, 1, 3, 2], 0.5
        else:
            pat, step = [0, 1, 2, 3, 2, 1, 2, 3], 0.5
        for j, p in enumerate(pat):
            uu = u0 + j * step
            loop.add(arp, _chip_note("p25", notes[p], step * U * 0.9, 0.75 if j % 2 == 0 else 0.6, "pluck",
                                     soft=2000.0), uu * U)
    # ---- the triangle bass
    bass = loop.stem()
    for i, (u0, l, root, fl) in enumerate(sc["bass"]):
        bar = i // 2
        s = sect(bar)
        if s == "C":
            pat = [(0, 4, root)]
        elif s == "B":
            pat = [(0, 1.5, root), (1.5, 0.5, root), (2, 1, root + 12), (3, 1, root + 7 if root + 7 < 52 else root - 5)]
        else:
            pat = [(j, 1, root + (12 if j % 2 else 0)) for j in range(4)]
        for (du, dl, m) in pat:
            loop.add(bass, _chip_note("tri", m, dl * U * 0.9, 1.0, "gate", soft=1800.0), (u0 + du) * U)
    # ---- drums on the noise channel (and the triangle's kick)
    drums = loop.stem()
    hats = loop.stem()
    for bar in range(CHIP_BARS):
        s = sect(bar)
        if s == "C":
            hits = [(0, "kick", 0.6), (2, "hat", 0.5), (6, "hat", 0.5)]
            if bar == 31:
                hits += [(4, "snare", 0.5), (5, "snare", 0.6), (6, "snare", 0.7), (7, "snare", 0.85)]
        else:
            hits = [(0, "kick", 1.0), (2, "snare", 0.8), (4, "kick", 0.85), (6, "snare", 0.8)]
            if s in ("A2", "B", "D"):
                hits.append((5, "kick", 0.55))
            hits += [(j, "hat", 0.75 if j % 2 else 0.5) for j in range(8)]
            if bar in (15, 23, 39):
                hits = [h for h in hits if h[0] < 4] + [(4, "snare", 0.6), (5, "snare", 0.7), (6, "snare", 0.8),
                                                        (7, "snare", 0.95)]
        for (u, kind, v) in hits:
            uu = bar * 8 + u
            buf = hats if kind == "hat" else drums
            loop.add(buf, _chip_drum(kind, v * (1 + rng.uniform(-0.06, 0.06)), int(uu * 7 + 3)), uu * U)

    def soft_top(x, f=6500.0):
        return A.lowpass(x, f, 2)

    loop.part("lead", _cfilt(lead, soft_top), -19.0, pan=0.06, send=0.16)
    loop.part("echo", _cfilt(echo, lambda x: A.lowpass(x, 3500, 2)), -30.0, pan=-0.45, send=0.2)
    loop.part("harmony", _cfilt(harm, soft_top), -24.0, pan=-0.2, send=0.16)
    loop.part("tri_lead", _cfilt(tri_lead, soft_top), -20.0, pan=0.05, send=0.22)
    loop.part("arps", _cfilt(arp, lambda x: A.lowpass(x, 5000, 2)), -27.0, pan=-0.25, send=0.2)
    loop.part("bass", _cfilt(bass, lambda x: A.highpass(x, 55, 2)), -26.5, pan=0.0, send=0.05)
    loop.part("drums", _cfilt(drums, soft_top), -26.0, pan=0.05, send=0.1)
    loop.part("hats", hats, -35.0, pan=0.2, send=0.08)
    ir = _room_ir(0.9, seed=44, predelay=0.01)
    return loop.render(ir, master=lambda x: A.lowpass(x, 11000, 2))


# ============================================================================= 3. Candlelit minuet
# 3/4, eighth notes as units (6 to a bar). Minuet (bars 1-24) and trio in B minor (25-40);
# the loop's return to bar 1 is the minuet's da capo.
MIN_A1 = ("A5:2 F#5:1 G5:1 A5:2 | G5:2 E5:1 F#5:1 G5:2 | F#5:2 D5:1 E5:1 F#5:1 A5:1 | G5:2 E5:2 C#5:2 | "
          "D5:2 F#5:2 A5:2 | B5:2 D6:2 B5:1 G5:1 | A5:2 G5:1 F#5:1 E5:2 | C#5:4 r:2")
MIN_A2 = ("A5:2m F#5:1 G5:1 A5:2 | G5:2m E5:1 F#5:1 G5:2 | F#5:2m D5:1 E5:1 F#5:1 A5:1 | B5:2 D6:2 B5:2 | "
          "A5:2m F#5:1 G5:1 A5:2 | G5:2m E5:1 F#5:1 G5:2 | F#5:4 E5:2t | D5:4 r:2")
MIN_B = ("B5:1 C#6:1 D6:1 C#6:1 B5:1 F#5:1 | E5:1 F#5:1 G5:1 F#5:1 E5:1 G5:1 | A5:1 B5:1 C#6:1 B5:1 A5:1 E5:1 | "
         "D5:1 E5:1 F#5:1 G5:1 A5:2 | B5:2m G5:1 A5:1 B5:2 | A5:2m F#5:1 G5:1 A5:2 | F#5:4 E5:2t | D5:4 r:2")
TRIO_STR = ("B4:2 D5:2 F#5:2 | G5:4 F#5:1 E5:1 | C#5:4 D5:1 E5:1 | F#5:6 | B5:4 A5:1 G5:1 | A5:2 F#5:2 D5:2 | "
            "G5:3 F#5:1 E5:2 | C#5:6")
TRIO_HPS = ("B4:1 C#5:1 D5:1 E5:1 F#5:2 | G5:4m F#5:1 E5:1 | C#5:4 D5:1 E5:1 | F#5:2 A5:2 F#5:2 | B5:4m A5:1 G5:1 | "
            "G5:2 E5:1 F#5:1 G5:2 | D5:4 C#5:2 | E5:2 G5:2 F#5:1 G5:1")
MIN_LH_A1 = ("D3:4 F#3:2 | C#3:4 A2:2 | D3:4 A2:2 | E3:4 A2:2 | D3:4 F#2:2 | G2:4 B2:2 | E3:2 D3:2 C#3:2 | "
             "A2:2 C#3:2 E3:2")
MIN_LH_A2 = ("D3:4 F#3:2 | C#3:4 A2:2 | D3:4 A2:2 | G2:2 A2:2 B2:2 | D3:4 F#3:2 | E3:2 G3:2 E3:2 | A2:4 A2:2 | "
             "D3:2 A2:2 F#2:2")
MIN_LH_B = "B2:4 D3:2 | G2:4 B2:2 | A2:4 C#3:2 | D3:4 F#2:2 | G2:4 B2:2 | F#2:4 D3:2 | A2:4 A2:2 | D3:4 F#2:2"
MIN_LH_T2 = "B2:4 D3:2 | G2:4 B2:2 | A2:4 C#3:2 | D3:4 F#3:2 | G2:4 B2:2 | E3:2 G3:2 E3:2 | A2:4 A2:2 | A2:2 C#3:2 E3:2"
# the harmony, one chord per beat ("x" repeats the last), for the strings and the checks
MIN_CH = (["D"] * 3 + ["A7/C#"] * 3 + ["D"] * 3 + ["Em", "Em", "A"] + ["D"] * 3 + ["G"] * 3 + ["Em", "Em", "A/C#"]
          + ["A"] * 3
          + ["D"] * 3 + ["A7/C#"] * 3 + ["D"] * 3 + ["G"] * 3 + ["D"] * 3 + ["Em"] * 3 + ["D/A", "D/A", "A7"]
          + ["D"] * 3
          + ["Bm"] * 3 + ["Em/G"] * 3 + ["A"] * 3 + ["D", "D", "D/F#"] + ["G"] * 3 + ["D/F#"] * 3
          + ["D/A", "D/A", "A7"] + ["D"] * 3
          + ["Bm"] * 3 + ["Em/G"] * 3 + ["A"] * 3 + ["D"] * 3 + ["G"] * 3 + ["D/F#"] * 3 + ["Em"] * 3 + ["F#m"] * 3
          + ["Bm"] * 3 + ["Em/G"] * 3 + ["A"] * 3 + ["D"] * 3 + ["G"] * 3 + ["Em"] * 3 + ["Asus4", "Asus4", "A"]
          + ["A7"] * 3)
D_MAJOR = {2, 4, 6, 7, 9, 11, 1}
MIN_BPM = 96.0
MIN_BARS = 40
MIN_SECONDS = _aac_aligned(MIN_BARS * 6 * 60.0 / MIN_BPM / 2.0)
MIN_UNIT = MIN_SECONDS / (MIN_BARS * 6)


def _minuet_score() -> dict:
    """The minuet's notes in units, by part (also used by the checks)."""
    rh = (_parse(MIN_A1, 6, 0) + _parse(MIN_A2, 6, 48) + _parse(MIN_B, 6, 96) + _parse(TRIO_HPS, 6, 192))
    lh = (_parse(MIN_LH_A1, 6, 0) + _parse(MIN_LH_A2, 6, 48) + _parse(MIN_LH_B, 6, 96)
          + _parse(MIN_LH_T2, 6, 192))
    strings_mel = _parse(TRIO_STR, 6, 144)
    return dict(rh=rh, lh=lh, vln=strings_mel, chords=MIN_CH)


def _candlelit_minuet() -> np.ndarray:
    _CACHE.clear()
    sc = _minuet_score()
    clock = _Clock(MIN_UNIT, rubato=0.035, phrase_units=48.0, peak_at=0.93)
    loop = _Loop(MIN_SECONDS, "minuet")
    rng = np.random.default_rng(3141)
    cnt = [0]
    rh_buf, lh_buf, arp_buf = loop.stem(), loop.stem(), loop.stem()

    def hp(buf, m, start, ring, vel=1.0):
        cnt[0] += 1
        v = vel * (1 + rng.uniform(-0.04, 0.04))
        x = _pluck(_mhz(m), ring, v, cnt[0], HARPSICHORD)
        loop.add(buf, x, start + rng.normal(0, 0.005))

    # ---- harpsichord, right hand: the tune with its ornaments (not in bars 25-32)
    for (t, d, m, acc) in _ornament(sc["rh"], clock, D_MAJOR, speed=0.068):
        hp(rh_buf, m, t, d + 0.03, acc)
    # ---- harpsichord, left hand: the bass line (bars 1-24 and 33-40)
    for (u, l, m, fl) in sc["lh"]:
        t = clock(u)
        hp(lh_buf, m, t + 0.008, clock(u + l) - t + 0.06, 0.92)
    # ---- harpsichord in the trio's first half: broken chords under the strings, each note
    # left ringing to the bar's end (as a lutenist or a harpsichordist would)
    trio_ch = ["Bm", "Em/G", "A", "D", "G", "D/F#", "Em", "F#m"]
    for b, ch in enumerate(trio_ch):
        pcs, bass_pc = _chord_pcs(ch)
        bass = min(m for m in range(40, 52) if m % 12 == bass_pc)        # E2..D#3
        ups = [m for m in range(bass + 5, bass + 22) if m % 12 in pcs][:4]
        seq = [bass, ups[0], ups[1], ups[2], ups[1], ups[0]] if len(ups) >= 3 else [bass] + ups
        u0 = (24 + b) * 6
        t_end = clock(u0 + 6)
        for j, m in enumerate(seq):
            t = clock(u0 + j)
            hp(arp_buf, m, t, t_end - t + 0.15, (0.95, 0.7, 0.75, 0.8, 0.7, 0.68)[j])

    # ---- strings
    # chords per bar for the sustained parts: bars 9-24 and 33-40 (one per beat in MIN_CH)
    def bar_chords(b):
        return MIN_CH[b * 3:(b + 1) * 3]

    pad_bars = list(range(8, 24)) + list(range(24, 40))
    # one chord per change (beat resolution), voiced smoothly for three upper parts
    events = []          # (unit start, unit length, chord)
    for b in pad_bars:
        for k, ch in enumerate(bar_chords(b)):
            u = b * 6 + 2 * k
            if events and events[-1][2] == ch and abs(events[-1][0] + events[-1][1] - u) < 1e-9:
                events[-1] = (events[-1][0], events[-1][1] + 2, ch)
            else:
                events.append((u, 2, ch))
    voic = _voicings([e[2] for e in events], 57, 74, 3, start=[62, 66, 69])
    upper = [[], [], []]
    cello = []
    for (u, l, ch), vc in zip(events, voic):
        bar = int(u // 6)
        soft = 0.55 if bar >= 32 else (0.62 if bar < 16 else 0.7)
        if 24 <= bar < 32:
            soft = 0.5           # under the trio's melody
        for j in range(3):
            upper[j].append((u, l, vc[j], soft))
        _, bpc = _chord_pcs(ch)
        cm = min(m for m in range(40, 52) if m % 12 == bpc)
        cello.append((u, l, cm, soft))

    def legato(notes):
        """merge repeated pitches into held notes; mark a new bow on each change of note
        and every bar or so on a long held note"""
        out = []
        for (u, l, m, v) in notes:
            if out and out[-1][2] == m and abs(out[-1][0] + out[-1][1] - u) < 1e-9 and out[-1][1] < 12:
                out[-1] = (out[-1][0], out[-1][1] + l, m, max(out[-1][3], v))
            else:
                out.append((u, l, m, v))
        res = []
        for i, (u, l, m, v) in enumerate(out):
            t = clock(u)
            res.append((t, clock(u + l) - t, m, v, True))
        return res

    sec_bufs = []
    for j in range(3):
        notes = legato(upper[j])
        for side in (0, 1):
            sec_bufs.append(_bowed_part(loop, notes, SECTION, seed=40 + j * 2 + side,
                                        cents=(-4.0 if side else 4.0), delay=0.012 * side, jitter=0.01))
    cel = legato(cello)
    cello_buf = _bowed_part(loop, cel, SECTION, seed=71, cents=0.0, jitter=0.008)
    # the trio's melody: two first violins
    vnotes = []
    for i, (u, l, m, fl) in enumerate(sc["vln"]):
        t = clock(u)
        bar_pos = (u % 6)
        v = 0.85 if bar_pos == 0 else 0.75
        prev = sc["vln"][i - 1] if i else None
        new_bow = bar_pos == 0 or prev is None or prev[2] == m or prev[1] >= 4
        vnotes.append((t, clock(u + l) - t, m, v, new_bow))
    vln = [_bowed_part(loop, vnotes, VIOLINS, seed=91 + s, cents=(-3.0 if s else 3.0), delay=0.01 * s,
                       jitter=0.006) for s in (0, 1)]

    # ---- body colour and the mix
    def harps_eq(x):
        x = A.highpass(x, 70, 2)
        x = A.peak_eq(x, 420, 1.5, 1.0)
        x = A.peak_eq(x, 2800, -3.0, 0.9)
        return A.lowpass(x, 6500, 2)

    def violin_eq(x):
        x = A.highpass(x, 180, 2)
        for f, g, q in ((290, 4.0, 2.5), (480, 3.0, 2.0), (1050, 2.0, 1.6), (1700, -3.0, 1.2), (2900, 2.0, 1.8)):
            x = A.peak_eq(x, f, g, q)
        return A.lowpass(x, 4200, 4)

    def section_eq(x, lo=150):
        x = A.highpass(x, lo, 2)
        x = A.peak_eq(x, 400, 2.0, 1.0)
        x = A.peak_eq(x, 1800, -3.0, 1.0)
        return A.lowpass(x, 3000, 4)

    rh = _cfilt(rh_buf, harps_eq)
    lh = _cfilt(lh_buf, harps_eq)
    arp = _cfilt(arp_buf, harps_eq)
    loop.part("harpsichord_rh", rh, -18.0, pan=0.12, send=0.30)
    loop.part("harpsichord_lh", lh, -22.5, pan=-0.12, send=0.30)
    loop.part("harpsichord_arp", arp, -23.0, pan=-0.05, send=0.32)
    pans = [-0.45, -0.25, 0.1, 0.3, 0.45, 0.6]
    for k, b in enumerate(sec_bufs):
        loop.part("strings_%d" % k, _cfilt(b, section_eq), -32.5, pan=pans[k], send=0.45)
    loop.part("cello", _cfilt(cello_buf, lambda x: section_eq(x, 70)), -29.0, pan=0.3, send=0.4)
    loop.part("violin_a", _cfilt(vln[0], violin_eq), -21.5, pan=-0.35, send=0.4)
    loop.part("violin_b", _cfilt(vln[1], violin_eq), -23.0, pan=-0.15, send=0.4)
    ir = _room_ir(1.7, seed=12, predelay=0.016)
    return loop.render(ir)


# ----------------------------------------------------------------------------- candidates
CANDIDATES = [
    Candidate("music", "hurdy_gurdy_dance", "Hurdy-gurdy dance",
              "A rustic country dance: a buzzing hurdy-gurdy plays the tune over its own droning strings, "
              "with a strummed cittern and a soft frame drum, like a village fair.",
              _hurdy_gurdy_dance, tags=["table"], loop_seconds=HG_SECONDS, bpm=HG_BPM),
    Candidate("music", "chiptune_quest", "Chiptune quest",
              "A cheerful 8-bit adventure tune like an old video game, with bubbly arpeggios, a bouncy "
              "bass, soft drums and a calmer middle part.",
              _chiptune_quest, tags=["table", "boss"], loop_seconds=CHIP_SECONDS, bpm=CHIP_BPM),
    Candidate("music", "candlelit_minuet", "Candlelit minuet",
              "An unhurried, graceful old-fashioned dance: a harpsichord plays the tune, soft strings "
              "join in and sing a wistful middle part, like music in a candlelit salon.",
              _candlelit_minuet, tags=["menu"], loop_seconds=MIN_SECONDS, bpm=MIN_BPM),
]
