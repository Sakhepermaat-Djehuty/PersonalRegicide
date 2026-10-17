"""Atmospheric music loops: a misty ambient keep, a music-box lullaby and a tense royal court.

Every track is written out note by note in a small text notation (each bar is checked to
add up), played by instruments built here, mixed through one shared synthetic hall and
folded into a loop with no seam.

Instruments, all private to this file (exactly in tune: the shared synth.pluck runs 7-15
cents flat from A4 up, and synth.sweep_lowpass switches filters block by block, which
clicks, so neither is used):
  _harp      a plucked gut string as a sum of its partials: levels from where it is plucked,
             the highs dying sooner than the fundamental, a whisker of stiffness, a soft
             finger noise.
  _celesta   a soft glass-and-metal bar struck by a felt hammer: a strong fundamental (the
             resonator), the bar's inharmonic modes (2.76x, 5.40x) dying fast, a twin a hair
             sharp so the long tail shimmers slowly.
  _tine      a music-box comb tooth plucked by a pin: a pure fundamental ringing for seconds,
             the tooth's second bending mode (about 5.9x) as a short bright "ting", a little
             2nd and 3rd harmonic, a tiny pin click; a tooth re-struck while ringing is
             damped first (choke), as the pin does on a real comb.
  _pad_note  a slow pad: detuned saws per ear through a dark and a brighter low-pass, the two
             blended so each chord glows brighter in its middle and darkens as it fades.
  _soft_pad  a rounder pad of detuned triangles and a sine (for the music box).
  _strings   an ensemble of bowed voices, each with its own vibrato, pitch drift and place in
             the stereo field, through a string-body EQ; optional bowed tremolo.
  _horn      a pair of horns: a saw that scoops into pitch and brightens as it swells.
  _pizz      plucked low strings (pizzicato) for the ostinato.
  _timp      a felt-mallet timpani: the drum's nearly harmonic modes (1, 1.5, 2, 2.44 ...),
             a short dull membrane mode, the pitch settling after the hit, a soft thud.
  _soft_bass a round, bowed-like bass for the ambient middle section.
  beds       a drone and a "mist" (faint airy noise) made exactly periodic over the loop
             (every frequency an exact number of cycles per loop; the noise built in the
             frequency domain), so they never seam.
  _hall_ir   a hall as a synthetic impulse response: early reflections, then a diffuse tail
             whose highs die sooner than its lows, different in each ear.

Tuning: all in D. The menu tracks use D major without C# (D E F# G A B: the pentatonic of the
sound effects plus G), so they never clash with the effects; the court uses D dorian
(D E F G A B C), the minor colour the brief allows. Everything is seeded.
"""
from __future__ import annotations

import math
from typing import Callable, Optional, Sequence, Tuple

import numpy as np
from scipy import signal

import synth as A
from catalog import Candidate

SR = A.SR
TAU = 2 * math.pi


# ----------------------------------------------------------------------------- basics
def _n(t: float) -> int:
    return int(round(t * SR))


def _mhz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12.0)


def _m(name: str) -> int:
    return A.midi(name)


def _smooth(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def _drift(n: int, rate_hz: float, rng: np.random.Generator) -> np.ndarray:
    """A smooth random wander in about -1..1, changing about ``rate_hz`` times a second."""
    k = max(4, int(n / SR * rate_hz) + 4)
    pts = rng.uniform(-1, 1, k)
    xs = np.linspace(0, n, k)
    return np.interp(np.arange(n), xs, pts)


def _note_env(n: int, attack: float, rel_start: float, release: float) -> np.ndarray:
    """Raised-cosine attack, hold, raised-cosine release starting at ``rel_start`` s."""
    t = np.arange(n) / SR
    up = _smooth(t / max(attack, 1e-4))
    down = 1.0 - _smooth((t - rel_start) / max(release, 1e-4))
    return up * down


def _additive(n: int, parts: Sequence[Tuple[float, float, float]], phases=None) -> np.ndarray:
    """Sum of decaying sines: (freq, amp, t60); each is computed only while audible."""
    t = np.arange(n) / SR
    y = np.zeros(n)
    for k, (f, a, t60) in enumerate(parts):
        if a == 0 or f >= SR * 0.45:
            continue
        m = min(n, _n(t60 * 1.35) + 1)
        ph = 0.0 if phases is None else phases[k]
        y[:m] += a * np.sin(TAU * f * t[:m] + ph) * np.exp(-6.9078 * t[:m] / t60)
    return y


def _to_db(x: np.ndarray, target_db: float) -> np.ndarray:
    cur = A._rms_db(x)
    return x * 10 ** ((target_db - cur) / 20.0)


def _st(x: np.ndarray, p: float) -> np.ndarray:
    """Mono -> panned stereo; a stereo note keeps its own spread and is balanced towards p."""
    if x.ndim == 1:
        return A.pan(x, p)
    a = (p + 1) * math.pi / 4
    return x * np.array([math.cos(a), math.sin(a)]) * math.sqrt(2)


def _circ(x: np.ndarray, fn: Callable[[np.ndarray], np.ndarray], warm: float = 2.0) -> np.ndarray:
    """Filter a periodic signal as if it had always been playing (no start transient)."""
    m = min(len(x), _n(warm))
    return fn(np.concatenate([x[-m:], x]))[m:]


# ----------------------------------------------------------------------------- notation
def _line(text: str, bar: float, start: float = 0.0, vel: float = 0.8) -> list:
    """'F#5:2 A5:1 | E5:3 | r:3' -> [(beat, length, midi, velocity)]. '|' is a bar line and
    every bar must add up to ``bar`` beats. A trailing '!' accents a note, '_' softens it."""
    out = []
    pos = start
    bar_start = start
    for tok in text.split():
        if tok == "|":
            if abs((pos - bar_start) - bar) > 1e-9:
                raise ValueError("bar of %.3f beats near beat %.2f in %r" % (pos - bar_start, pos, text[:40]))
            bar_start = pos
            continue
        v = vel
        while tok[-1] in "!_":
            v *= 1.15 if tok[-1] == "!" else 0.75
            tok = tok[:-1]
        p, l = tok.split(":")
        length = float(l)
        if p != "r":
            out.append((pos, length, _m(p), v))
        pos += length
    if abs((pos - bar_start) - bar) > 1e-9:
        raise ValueError("last bar of %.3f beats in %r" % (pos - bar_start, text[:40]))
    return out


def _hits(spec: Sequence[Tuple[float, str, float]], start: float = 0.0, length: float = 1.0) -> list:
    """[(beat, pitch, vel)] -> notes."""
    return [(start + b, length, _m(p), v) for b, p, v in spec]


# ----------------------------------------------------------------------------- room
def _hall_ir(seconds: float, t60_lo: float, t60_hi: float, seed: int, predelay: float = 0.02,
             lp: float = 7000.0, early: int = 10) -> np.ndarray:
    """A stereo hall: sparse early reflections, then a diffuse tail (noise) decaying band by
    band, the lows lasting ``t60_lo`` and the highs ``t60_hi``; unit energy per ear."""
    n = _n(seconds)
    t = np.arange(n) / SR
    edges = [0, 250, 800, 2500, 6000, None]
    t60s = np.geomspace(t60_lo, t60_hi, 5)
    chans = []
    for ch in range(2):
        rng = np.random.default_rng(seed * 31 + ch)
        w = rng.standard_normal(n)
        y = np.zeros(n)
        for b in range(5):
            lo, hi = edges[b], edges[b + 1]
            if lo == 0:
                band = A.lowpass(w, hi, 4)
            elif hi is None:
                band = A.highpass(w, lo, 4)
            else:
                band = A.bandpass(w, lo, hi, 3)
            y += band * np.exp(-6.9078 * t / t60s[b])
        y *= 1 - np.exp(-t / 0.018)
        for _ in range(early):
            d = rng.uniform(0.006, 0.075)
            k = _n(d)
            y[k] += rng.choice([-1, 1]) * 2.2 * math.exp(-d / 0.06) * np.sqrt(np.mean(y[:_n(0.2)] ** 2)) * 6
        y = A.lowpass(y, lp, 2)
        chans.append(np.concatenate([np.zeros(_n(predelay)), y]))
    ir = np.stack(chans, axis=1)
    return ir / np.sqrt(np.mean(np.sum(ir ** 2, axis=0)))


def _wobble(x: np.ndarray, T: float, depth_ms: float, rates: Sequence[float], seed: int) -> np.ndarray:
    """A slowly swaying delay (a few cents of chorus) on what enters the hall. A noise-built
    hall, like a real one, answers some pitches several dB louder than others; a held, nearly
    pure tone (a bell, a music-box tooth) swept gently across them comes out even. The sway
    repeats a whole number of times per loop, so the loop stays seamless."""
    n = len(x)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    out = np.empty_like(x)
    for ch in range(x.shape[1]):
        d = 0.012 + sum(depth_ms / 1000.0 / len(rates) *
                        np.sin(TAU * max(1, round(r * T)) / T * t + rng.uniform(0, TAU)) for r in rates)
        out[:, ch] = np.interp(np.arange(n) - d * SR, np.arange(n), x[:, ch], left=0.0)
    return out


def _convolve(send: np.ndarray, ir: np.ndarray, cross: float = 0.25) -> np.ndarray:
    l = (1 - cross) * send[:, 0] + cross * send[:, 1]
    r = (1 - cross) * send[:, 1] + cross * send[:, 0]
    wl = signal.oaconvolve(l, ir[:, 0])
    wr = signal.oaconvolve(r, ir[:, 1])
    return np.stack([wl, wr], axis=1)


# ----------------------------------------------------------------------------- the mixer
class _Mix:
    """Stems of notes placed on a beat grid, each brought to a level (gated RMS, dB), panned
    and sent to the shared hall; periodic beds added as they are. ``render`` folds whatever
    rings past the loop back onto its start, so the result loops seamlessly."""

    def __init__(self, bpm: float, beats: float, seed: int):
        self.bpm = float(bpm)
        self.beat = 60.0 / self.bpm
        self.n = _n(beats * self.beat)
        self.T = self.n / SR
        self.seed = seed
        self.dry = np.zeros((self.n, 2))
        self.send = np.zeros((self.n, 2))
        self.levels = {}

    @staticmethod
    def _add(buf: np.ndarray, x: np.ndarray, i: int) -> np.ndarray:
        end = i + len(x)
        if end > len(buf):
            buf = np.concatenate([buf, np.zeros((end - len(buf),) + buf.shape[1:])])
        buf[i:end] += x
        return buf

    def _grow(self, k: int):
        if k > len(self.dry):
            pad = np.zeros((k - len(self.dry), 2))
            self.dry = np.concatenate([self.dry, pad])
            self.send = np.concatenate([self.send, pad.copy()])

    def stem(self, name: str, inst: Callable, notes: list, level_db: float, pan=0.0, send: float = 0.3,
             jitter: float = 0.0, vel_jit: float = 0.0, choke: bool = False, hp: Optional[float] = None,
             lp: Optional[float] = None) -> np.ndarray:
        """``inst(hz, seconds, velocity, rng)`` returns a mono or stereo note; ``pan`` is a
        number or a function of (midi, index)."""
        rng = np.random.default_rng([self.seed, len(self.levels), 7])
        placed = []
        for i, (b, length, p, v) in enumerate(notes):
            t0 = b * self.beat + (rng.uniform(-1, 1) * jitter if jitter else 0.0)
            if t0 < 0:
                t0 += self.T
            vv = v * (1 + rng.uniform(-vel_jit, vel_jit)) if vel_jit else v
            placed.append((t0, length, p, vv, i))
        buf = np.zeros((self.n, 2))
        for t0, length, p, vv, i in placed:
            x = inst(_mhz(p), length * self.beat, vv, np.random.default_rng([self.seed, len(self.levels), i]))
            if choke:
                later = [q[0] for q in placed if q[2] == p and q[0] > t0 + 1e-6]
                nxt = min(later) if later else min(q[0] for q in placed if q[2] == p) + self.T
                cut = _n(nxt - t0 + 0.01)
                if cut < len(x):
                    fade = _n(0.03)
                    x = x[:cut + fade].copy()
                    x[cut:] *= np.linspace(1, 0, len(x) - cut) if x.ndim == 1 else np.linspace(1, 0, len(x) - cut)[:, None]
            pp = pan(p, i) if callable(pan) else pan
            buf = self._add(buf, _st(x, pp), _n(t0))
        if hp:
            buf = A.highpass(buf, hp, 2)
        if lp:
            buf = A.lowpass(buf, lp, 2)
        buf = _to_db(buf, level_db)
        self.levels[name] = level_db
        self._grow(len(buf))
        self.dry[:len(buf)] += buf
        self.send[:len(buf)] += send * buf
        return buf

    def bed(self, name: str, x: np.ndarray, level_db: float, send: float = 0.3) -> None:
        """A periodic layer exactly one loop long (it already loops by itself)."""
        assert len(x) == self.n, (name, len(x), self.n)
        x = _to_db(x, level_db)
        self.levels[name] = level_db
        self.dry[:self.n] += x
        self.send[:self.n] += send * x

    def render(self, ir: np.ndarray, hp: float = 32.0, eq: Optional[Callable] = None,
               wobble_ms: float = 2.0) -> np.ndarray:
        send = _wobble(self.send, self.T, wobble_ms, (0.23, 0.37), self.seed) if wobble_ms else self.send
        wet = _convolve(send, ir)
        total = np.zeros((max(len(wet), len(self.dry)), 2))
        total[:len(self.dry)] += self.dry
        total[:len(wet)] += wet
        total = A.highpass(total, hp, 2)
        if eq:
            total = eq(total)
        return A.loop_seamless(total[:self.n], total[self.n:])


# ----------------------------------------------------------------------------- periodic beds
def _section_env(n: int, points: Sequence[Tuple[float, float]]) -> np.ndarray:
    """A smooth gain curve through (seconds, value) points, eased between them; the first
    point must be at 0 and its value is repeated at the loop's end so the curve loops."""
    T = n / SR
    pts = list(points) + [(T, points[0][1])]
    t = np.arange(n) / SR
    out = np.empty(n)
    for (t0, v0), (t1, v1) in zip(pts[:-1], pts[1:]):
        m = (t >= t0) & (t < t1)
        out[m] = v0 + (v1 - v0) * _smooth((t[m] - t0) / max(t1 - t0, 1e-6))
    return out


def _drone_bed(n: int, notes: Sequence[Tuple[float, float]], seed: int, harmonics: int = 9, tilt: float = 1.35,
               fmax: float = 1800.0, swirl: float = 0.55, beat_hz: float = 0.13) -> np.ndarray:
    """A sustained drone exactly periodic over the loop: each harmonic of each note turns an
    exact number of cycles per loop and swells slowly (a few times per loop, differently in
    each ear), so the timbre keeps drifting; a twin a hair sharp beats gently."""
    T = n / SR
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    out = np.zeros((n, 2))
    for f0, g0 in notes:
        for h in range(1, harmonics + 1):
            fh = h * f0
            if fh > fmax:
                break
            a = g0 / h ** tilt
            layers = [(fh, 1.0)] + ([(fh + beat_hz * h, 0.4)] if h <= 2 else [])
            for f, g in layers:
                fq = round(f * T) / T
                s = np.sin(TAU * fq * t + rng.uniform(0, TAU))
                for ch in range(2):
                    c = int(rng.integers(1, 6))
                    am = 1 + swirl * np.sin(TAU * c * t / T + rng.uniform(0, TAU))
                    out[:, ch] += a * g * am * s
    return out


def _loop_noise(n: int, lo: float, hi: float, seed: int, slope: float = -0.5) -> np.ndarray:
    """Band-limited noise that is exactly periodic over n samples (made in the frequency
    domain), with a soft roll-off below ``lo`` and above ``hi``; ``slope`` tilts it (pink
    is -0.5 in amplitude)."""
    rng = np.random.default_rng(seed)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    f[0] = 1.0
    mag = (f / 1000.0) ** slope / np.sqrt(1 + (lo / f) ** 4) / np.sqrt(1 + (f / hi) ** 4)
    mag[0] = 0.0
    spec = mag * np.exp(1j * rng.uniform(0, TAU, len(f)))
    y = np.fft.irfft(spec, n)
    return y / (np.max(np.abs(y)) or 1.0)


def _slow_lfo(n: int, cycles: Sequence[int], seed: int, depth: float = 0.5) -> np.ndarray:
    """1 + a sum of slow sines, each an exact number of cycles per loop."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / n
    y = np.zeros(n)
    for c in cycles:
        y += np.sin(TAU * c * t + rng.uniform(0, TAU))
    return 1 + depth * y / max(1, len(cycles))


# ----------------------------------------------------------------------------- instruments
def _harp(f: float, dur: float, vel: float, rng: np.random.Generator, ring: float = 1.0,
          beta: float = 0.27, fmax: float = 6000.0) -> np.ndarray:
    """A gut-strung harp: partials of a string plucked at ``beta`` of its length, the
    highs dying first; softer plucks are darker."""
    t60 = float(np.clip(6.5 * (110.0 / f) ** 0.5, 1.8, 7.0)) * ring
    n = _n(t60 * 1.2)
    b = beta + rng.uniform(-0.03, 0.03)
    parts = []
    for k in range(1, 40):
        fk = k * f * math.sqrt(1 + 0.00006 * k * k)
        if fk > fmax:
            break
        a = abs(math.sin(math.pi * k * b)) / k ** 1.3 * (0.72 + 0.28 * vel) ** (k - 1)
        tk = t60 / (1 + 0.45 * (k - 1)) * min(1.0, (900.0 / fk) ** 0.35)
        parts.append((fk, a, max(0.08, tk)))
    y = _additive(n, parts)
    y *= _smooth(np.arange(n) / max(1, _n(0.004)))
    nz = A.bandpass(rng.standard_normal(_n(0.02)), 300, 2500) * np.exp(-np.arange(_n(0.02)) / _n(0.004))
    y[:len(nz)] += 0.04 * nz
    return y * vel


def _celesta(f: float, dur: float, vel: float, rng: np.random.Generator, ring: float = 1.0) -> np.ndarray:
    """A felt hammer on a small glass-and-metal bar over a tuned resonator."""
    t60 = float(np.clip(3.6 * (600.0 / f) ** 0.55, 1.4, 5.5)) * ring
    n = _n(t60 * 1.2)
    parts = [(f, 1.0, t60), (f * 1.0016, 0.32, t60 * 0.9), (f * 2.0, 0.10, t60 * 0.4),
             (f * 2.756, 0.14 * vel, t60 * 0.18), (f * 5.404, 0.04 * vel, t60 * 0.06)]
    parts = [p for p in parts if p[0] < 7500]
    y = _additive(n, parts, phases=rng.uniform(0, 0.3, len(parts)))
    y *= _smooth(np.arange(n) / max(1, _n(0.0025)))
    tok = A.lowpass(rng.standard_normal(_n(0.012)), 2500, 2) * np.exp(-np.arange(_n(0.012)) / _n(0.002))
    y[:len(tok)] += 0.03 * tok
    return y * vel


def _tine(f: float, dur: float, vel: float, rng: np.random.Generator) -> np.ndarray:
    """A music-box tooth plucked by a pin."""
    t60 = float(np.clip(2.9 * (880.0 / f) ** 0.5, 1.5, 4.8))
    n = _n(t60 * 1.2)
    r2 = 5.93 * (1 + rng.uniform(-0.03, 0.03))
    parts = [(f, 1.0, t60), (f * 1.0011, 0.2, t60 * 1.1), (f * 2.0, 0.11, t60 * 0.3),
             (f * 3.0, 0.04, t60 * 0.16), (f * r2, 0.16 + 0.16 * vel, 0.24), (f * r2 * 2.96, 0.03 * vel, 0.06)]
    parts = [p if p[0] < 7600 else (p[0], 0.0, p[2]) for p in parts]
    y = _additive(n, parts)
    y *= _smooth(np.arange(n) / max(1, _n(0.0008)))
    clk = A.bandpass(rng.standard_normal(_n(0.006)), 1500, 4500) * np.exp(-np.arange(_n(0.006)) / _n(0.0009))
    y[:len(clk)] += 0.03 * clk
    return y * vel


def _pad_note(f: float, dur: float, vel: float, rng: np.random.Generator, attack: float = 3.0,
              release: float = 4.0, dark: float = 650.0, bright: float = 1700.0, glow: float = 0.55) -> np.ndarray:
    """Detuned saws per ear, a dark and a brighter filter blended over the note (brighter in
    its middle), a slow raised-cosine swell in and out."""
    total = dur + release
    n = _n(total)
    out = np.zeros((n, 2))
    for ch in range(2):
        for c in (-7.0, 0.0, 7.0):
            cents = c + rng.uniform(-1.5, 1.5) + 2.0 * _drift(n, 0.15, rng)
            fv = f * 2 ** (cents / 1200.0)
            out[:, ch] += A.osc("saw", fv, total, phase=rng.uniform(0, TAU))
    out /= 3.0
    lo = A.lowpass(out, dark, 4)
    hi = A.lowpass(out, bright, 4)
    t = np.arange(n) / SR
    m = glow * np.sin(np.pi * np.clip(t / total, 0, 1)) ** 2
    y = lo * (1 - m[:, None]) + hi * m[:, None]
    return y * _note_env(n, attack, dur, release)[:, None] * vel


def _soft_pad(f: float, dur: float, vel: float, rng: np.random.Generator, attack: float = 1.2,
              release: float = 2.2, cutoff: float = 1000.0) -> np.ndarray:
    total = dur + release
    n = _n(total)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for ch in range(2):
        for c in (-5.0, 5.0):
            fv = f * 2 ** ((c + rng.uniform(-1.5, 1.5)) / 1200.0)
            out[:, ch] += 0.5 * A.osc("tri", fv, total, phase=rng.uniform(0, TAU))
        out[:, ch] += 0.6 * np.sin(TAU * f * t + rng.uniform(0, TAU))
    out = A.lowpass(out, cutoff, 2)
    return out * _note_env(n, attack, dur, release)[:, None] * vel


def _soft_bass(f: float, dur: float, vel: float, rng: np.random.Generator) -> np.ndarray:
    total = dur + 2.5
    n = _n(total)
    ph = TAU * np.cumsum(f * (1 + 0.0015 * _drift(n, 0.3, rng))) / SR
    y = np.sin(ph) + 0.28 * np.sin(2 * ph + 0.4) + 0.09 * np.sin(3 * ph + 1.1) + 0.04 * np.sin(4 * ph)
    y = A.lowpass(y, 500, 2)
    return y * _note_env(n, 1.4, dur, 2.5) * vel


def _strings(f: float, dur: float, vel: float, rng: np.random.Generator, voices: int = 4, bright: float = 0.35,
             attack: float = 0.8, release: float = 1.2, vib: float = 0.0035, trem: float = 0.0,
             spread: float = 0.5, swell: float = 0.0) -> np.ndarray:
    """A section of bowed strings."""
    total = dur + release
    n = _n(total)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for v in range(voices):
        cents = rng.uniform(-7, 7) + 3.0 * _drift(n, 0.25, rng)
        rate = rng.uniform(4.7, 5.8)
        vib_env = _smooth((t - 0.3) / 0.7)
        fv = f * 2 ** (cents / 1200.0) * (1 + vib * vib_env * np.sin(TAU * rate * t + rng.uniform(0, TAU)))
        s = A.osc("saw", fv, total, phase=rng.uniform(0, TAU))
        if trem:
            tr = rng.uniform(8.5, 10.5)
            s = s * (1 - trem * (0.5 + 0.5 * np.sin(TAU * tr * t + rng.uniform(0, TAU))))
        p = spread * (2 * v / (voices - 1) - 1) if voices > 1 else 0.0
        out += A.pan(s, p)
    out /= math.sqrt(voices)
    cutoff = float(np.clip(f * 7, 900, 2800)) * (0.6 + 0.8 * bright)
    out = A.lowpass(out, cutoff, 4)
    out = A.peak_eq(out, 300, 2.5, 1.0)
    out = A.peak_eq(out, 1100, 2.0, 1.2)
    env = _note_env(n, attack, dur, release)
    if swell:
        env = env * (1 - swell + swell * np.sin(np.pi * np.clip(t / max(dur, 1e-3), 0, 1)))
    return out * env[:, None] * vel


def _horn(f: float, dur: float, vel: float, rng: np.random.Generator) -> np.ndarray:
    """Two horns in unison: a saw that scoops up into pitch and grows brighter as it swells."""
    rel = 0.5
    total = dur + rel
    n = _n(total)
    t = np.arange(n) / SR
    src = np.zeros(n)
    for c in (-3.0, 3.5):
        scoop = -0.010 * np.exp(-t / 0.06)
        vibr = 0.003 * _smooth((t - 0.45) / 0.5) * np.sin(TAU * rng.uniform(4.6, 5.3) * t + rng.uniform(0, TAU))
        fv = f * 2 ** ((c + 2 * _drift(n, 0.3, rng)) / 1200.0) * (1 + scoop + vibr)
        src += 0.5 * A.osc("saw", fv, total, phase=rng.uniform(0, TAU))
    env = _note_env(n, 0.16, dur, rel)
    env = env * (0.85 + 0.15 * np.sin(np.pi * np.clip(t / max(dur, 1e-3), 0, 1)))
    dark = A.lowpass(src, float(np.clip(f * 2.2, 260, 900)), 2)
    brt = A.lowpass(src, float(np.clip(f * 5.0, 800, 2400)), 2)
    b = np.clip(0.25 + 0.7 * vel * env ** 1.5, 0, 1)
    y = (dark * (1 - b) + brt * b) * env
    y = A.peak_eq(y, 520, 3.0, 0.9)
    return y * vel


def _pizz(f: float, dur: float, vel: float, rng: np.random.Generator) -> np.ndarray:
    t60 = float(np.clip(1.4 * (110.0 / f) ** 0.3, 0.6, 1.6))
    n = _n(t60 * 1.15)
    b = 0.22 + rng.uniform(-0.02, 0.02)
    parts = []
    for k in range(1, 40):
        fk = k * f
        if fk > 3200:
            break
        parts.append((fk, abs(math.sin(math.pi * k * b)) / k ** 1.4, max(0.05, t60 / (1 + 0.5 * (k - 1)))))
    y = _additive(n, parts)
    y *= _smooth(np.arange(n) / max(1, _n(0.002)))
    th = A.lowpass(rng.standard_normal(_n(0.03)), 600, 2) * np.exp(-np.arange(_n(0.03)) / _n(0.006))
    y[:len(th)] += 0.12 * th
    y = A.peak_eq(y, 250, 2.5, 1.0)
    return y * vel


def _timp(f: float, dur: float, vel: float, rng: np.random.Generator) -> np.ndarray:
    """A felt-mallet timpani: its nearly harmonic modes, a short dull mode below, the
    pitch settling as the hit dies, a soft thud."""
    n = _n(2.6)
    t = np.arange(n) / SR
    settle = 1 + 0.018 * np.exp(-t / 0.09)
    modes = [(0.66, 0.35, 0.22), (1.0, 1.0, 2.4), (1.504, 0.42 * vel, 1.6), (1.98, 0.25 * vel, 1.1),
             (2.44, 0.13 * vel, 0.8), (2.90, 0.07 * vel, 0.6)]
    y = np.zeros(n)
    for r, a, t60 in modes:
        ph = TAU * np.cumsum(f * r * settle) / SR
        y += a * np.sin(ph) * np.exp(-6.9078 * t / t60)
    y *= _smooth(t / 0.003)
    th = A.lowpass(rng.standard_normal(_n(0.08)), 280, 2) * np.exp(-np.arange(_n(0.08)) / _n(0.02))
    y[:len(th)] += 0.5 * th
    return A.lowpass(y, 1500, 2) * vel


# ----------------------------------------------------------------------------- 1. Misty keep
def _misty_keep() -> np.ndarray:
    """D major without C#, 60 bpm, 24 bars of 4/4 (96 s): A (bars 1-8) harp over a drone and
    slow pads; B (9-16) the drone recedes, a soft bass walks G-E-B-A and celesta bells sing;
    A' (17-24) the harp returns with a bell counter-line."""
    bpm, beats = 60, 96
    mix = _Mix(bpm, beats, seed=11)
    n = mix.n
    bar = 4

    # pads: (bar, bars, voicing)
    chords = [
        (0, 2, "D3 A3 E4 F#4"), (2, 2, "D3 A3 B3 F#4"), (4, 2, "D3 G3 B3 F#4"), (6, 2, "E3 A3 D4 E4"),
        (8, 2, "G3 B3 F#4 A4"), (10, 2, "G3 B3 D4 F#4"), (12, 2, "F#3 A3 D4 E4"), (14, 1, "E3 A3 D4 E4"),
        (15, 1, "E3 A3 B3 E4"),
        (16, 2, "D3 A3 E4 F#4"), (18, 2, "D3 G3 B3 F#4"), (20, 2, "D3 A3 B3 F#4"), (22, 1, "E3 A3 D4 E4"),
        (23, 1, "E3 A3 B3 E4"),
    ]
    pad_notes = []
    for b0, nb, voicing in chords:
        sect_vel = 0.95 if 8 <= b0 < 16 else 0.85
        for k, p in enumerate(voicing.split()):
            pad_notes.append((b0 * bar, nb * bar + 0.5, _m(p), sect_vel * (1.0 - 0.06 * k)))
    pad = lambda f, d, v, r: _pad_note(f, d, v, r, attack=3.0, release=4.0, dark=650, bright=2000, glow=0.6)
    mix.stem("pad", pad, pad_notes, -12.0, pan=0.0, send=0.35)

    # the low drone on D (and A), strong in A and A', receding in B
    sect = _section_env(n, [(0, 1.0), (28, 1.0), (38, 0.32), (58, 0.32), (68, 1.0)])
    drone = _drone_bed(n, [(_mhz(_m("D2")), 1.0), (_mhz(_m("A2")), 0.55), (_mhz(_m("D3")), 0.5)], seed=5,
                       harmonics=8, tilt=1.5, fmax=1200)
    drone = _circ(drone, lambda x: A.lowpass(x, 900, 2)) * sect[:, None]
    mix.bed("drone", drone, -16.0, send=0.25)

    # mist: faint, slowly breathing air
    mist = np.stack([_loop_noise(n, 280, 1400, 101), _loop_noise(n, 280, 1400, 202)], axis=1)
    mist *= (_slow_lfo(n, [2, 3, 5], 9, 0.8) ** 2)[:, None]
    mix.bed("mist", mist, -32.0, send=0.5)

    # bass in B
    bass = _line("G2:8 | E2:8 | B2:8 | A2:8", 8, start=32, vel=0.8)
    mix.stem("bass", _soft_bass, bass, -17.0, pan=0.0, send=0.2)

    # harp: arpeggios with a melody in their top notes
    H = []
    harp_bars = {
        0: [(0, "D4", .55), (1, "A4", .55), (2, "E5", .6), (3, "F#5", .72)],
        1: [(1.5, "A5", .75), (3, "E5", .6)],
        2: [(0, "B3", .55), (1, "F#4", .55), (2, "D5", .6), (3, "E5", .7)],
        3: [(1.5, "F#5", .72), (3, "D5", .58)],
        4: [(0, "G3", .55), (1, "D4", .55), (2, "B4", .6), (3, "F#5", .7)],
        5: [(1.5, "A5", .78), (3, "B5", .74)],
        6: [(0, "A3", .55), (1, "E4", .55), (2, "A4", .58), (3, "D5", .64)],
        7: [(1.5, "E5", .66)],
        8: [(0, "G2", .34), (1.5, "D3", .28)],
        10: [(0, "E3", .32), (1.5, "B3", .27)],
        12: [(0, "B2", .32), (1.5, "F#3", .27)],
        14: [(0, "A2", .32), (1.5, "E3", .27)],
        16: [(0, "D4", .55), (1, "A4", .55), (2, "E5", .6), (3, "F#5", .7)],
        17: [(1.5, "D5", .62), (3, "A4", .55)],
        18: [(0, "G3", .55), (1, "D4", .55), (2, "B4", .58), (3, "D5", .62)],
        19: [(1.5, "F#5", .66), (3, "B4", .55)],
        20: [(0, "B3", .55), (1, "F#4", .55), (2, "A4", .58), (3, "D5", .62)],
        21: [(1.5, "E5", .64), (3, "B4", .52)],
        22: [(0, "A3", .52), (1, "D4", .5), (2, "E4", .52), (3, "A4", .55)],
        23: [(1.5, "B4", .55)],
    }
    for b0, hits in harp_bars.items():
        H += _hits(hits, start=b0 * bar)
    harp_pan = lambda m, i: float(np.clip(0.4 * (m - 66) / 17.0, -0.4, 0.4))
    mix.stem("harp", lambda f, d, v, r: _harp(f, d, v, r, ring=1.0), H, -11.0, pan=harp_pan, send=0.42,
             jitter=0.012, vel_jit=0.06)

    # celesta: the melody in B, a counter-line in A'
    bells = _line("B4:2 D5:2 | F#5:3 E5:1 | D5:1.5 E5:0.5 B4:2 | E5:4 | "
                  "F#5:2 A5:2 | B5:3 A5:1 | E5:2 F#5:1 E5:1 | D5:1 E5:3", bar, start=32, vel=0.78)
    bells += _line("r:4 | r:1 A5:2 F#5:1 | r:2 B5:2 | A5:3 r:1 | r:2 F#5:2 | E5:2 D5:2 | E5:4 | r:4",
                   bar, start=64, vel=0.6)
    mix.stem("bells", _celesta, bells, -13.0, pan=lambda m, i: -0.22 + 0.12 * math.sin(i * 1.7), send=0.45,
             jitter=0.01, vel_jit=0.05)

    ir = _hall_ir(4.6, 4.2, 1.8, seed=3, predelay=0.02, lp=6500)
    return mix.render(ir, wobble_ms=2.5)


# ----------------------------------------------------------------------------- 2. Music box
_MB = {  # chord: (bass, dyad, arpeggio of six eighths, pad voicing)
    "D": ("D3", ("F#4", "A4"), "D3 A3 D4 F#4 A4 F#4", "D3 A3 F#4"),
    "G": ("G3", ("G4", "B4"), "G3 D4 G4 B4 G4 D4", "D3 G3 B3"),
    "Bm": ("B2", ("F#4", "B4"), "B2 F#3 B3 D4 F#4 D4", "D3 F#3 B3"),
    "Em": ("E3", ("G4", "B4"), "E3 B3 E4 G4 B4 G4", "E3 G3 B3"),
    "Asus4": ("A2", ("D4", "A4"), "A2 E3 A3 D4 E4 D4", "E3 A3 D4"),
    "Asus2": ("A2", ("B3", "E4"), "A2 E3 A3 B3 E4 B3", "E3 A3 B3"),
    "D/F#": ("F#3", ("A4", "D5"), "F#3 A3 D4 F#4 A4 F#4", "F#3 A3 D4"),
}


def _music_box() -> np.ndarray:
    """D major without C#, 3/4 at 88 bpm, 40 bars (81.8 s): the theme (16 bars, oom-pah-pah),
    a quieter middle in B minor (8 bars, broken chords, the pad comes forward), then the
    theme's variation (16 bars: ornamented melody reaching higher, flowing arpeggios)."""
    bpm, bar = 88, 3
    theme_chords = ["D", "D", "G", "D", "Bm", "G", "Em", "Asus4", "D", "D", "G", "D/F#", "G", "Em", "Asus4", "D"]
    mid_chords = ["Bm", "G", "Em", "Asus4", "Bm", "G", "Em", "Asus2"]
    chords = theme_chords + mid_chords + theme_chords
    beats = bar * len(chords)
    mix = _Mix(bpm, beats, seed=23)

    theme = ("A5:2 F#5:1 | E5:1 F#5:1 A5:1 | B5:2 A5:1 | F#5:3 | D5:1 F#5:1 B5:1 | D6:2 B5:1 | A5:1 G5:1 E5:1 | "
             "E5:3 | A5:2 F#5:1 | E5:1 F#5:1 A5:1 | B5:1 D6:1 B5:1 | A5:3 | B5:1.5 A5:0.5 G5:1 | G5:1 F#5:1 E5:1 | "
             "D5:1 E5:2 | D5:3")
    middle = ("D6:2 B5:1 | B5:2 G5:1 | G5:2 E5:1 | E5:1 D5:1 E5:1 | F#5:2 B5:1 | D6:2 B5:1 | B5:1.5 A5:0.5 G5:1 | "
              "E5:1 F#5:1 G5:1")
    variation = ("A5:1 B5:0.5 A5:0.5 F#5:1 | E5:0.5 D5:0.5 E5:0.5 F#5:0.5 A5:1 | B5:1 D6:1 B5:0.5 A5:0.5 | "
                 "F#5:2 E5:0.5 F#5:0.5 | D5:0.5 F#5:0.5 B5:1 A5:0.5 B5:0.5 | D6:2 B5:1 | A5:0.5 B5:0.5 G5:1 E5:1 | "
                 "E5:3 | A5:1 B5:0.5 A5:0.5 F#5:1 | E5:0.5 F#5:0.5 A5:1 D6:1 | E6:1 D6:1 B5:1 | A5:2 F#5:1 | "
                 "B5:1 A5:0.5 G5:0.5 F#5:1 | G5:1 F#5:0.5 E5:0.5 D5:1 | E5:1.5 F#5:0.5 E5:1 | D5:3")
    mel = _line(theme, bar, 0, 0.8) + _line(middle, bar, 48, 0.68) + _line(variation, bar, 72, 0.76)
    # phrase shaping: a little louder towards each phrase's peak, softer on the long last notes
    mel = [(b, l, p, v * (0.92 + 0.1 * (p - 74) / 12.0) * (0.9 if l >= 3 else 1.0)) for b, l, p, v in mel]
    mix.stem("melody", _tine, mel, -8.0, pan=0.12, send=0.32, jitter=0.004, vel_jit=0.05, choke=True)

    acc = []
    for k, c in enumerate(chords):
        bass, dyad, arp, _ = _MB[c]
        b0 = k * bar
        if k < 16:                      # theme: oom-pah-pah
            acc.append((b0, 1, _m(bass), 0.6))
            if k != 15:
                acc += [(b0 + 1, 1, _m(dyad[0]), 0.36), (b0 + 1, 1, _m(dyad[1]), 0.34),
                        (b0 + 2, 1, _m(dyad[0]), 0.3), (b0 + 2, 1, _m(dyad[1]), 0.28)]
            else:
                acc += [(b0 + 1, 1, _m(dyad[0]), 0.3), (b0 + 1, 1, _m(dyad[1]), 0.28)]
        elif k < 24:                    # middle: a bass and a slow broken chord
            acc += [(b0, 1, _m(bass), 0.52), (b0 + 1, 1, _m(dyad[0]), 0.3), (b0 + 2, 1, _m(dyad[1]), 0.27)]
        else:                           # variation: flowing eighths
            for j, p in enumerate(arp.split()):
                acc.append((b0 + 0.5 * j, 0.5, _m(p), 0.55 if j == 0 else 0.3 - 0.02 * (j % 2)))
    mix.stem("accomp", _tine, acc, -13.0, pan=-0.14, send=0.32, jitter=0.004, vel_jit=0.06, choke=True)

    # soft pad: one note per chord change, held while the chord holds
    pad_notes = []
    k = 0
    while k < len(chords):
        j = k
        while j + 1 < len(chords) and chords[j + 1] == chords[k]:
            j += 1
        mid = 16 <= k < 24
        for i, p in enumerate(_MB[chords[k]][3].split()):
            pad_notes.append((k * bar, (j - k + 1) * bar, _m(p), (0.95 if mid else 0.6) * (1 - 0.08 * i)))
        k = j + 1
    mix.stem("pad", lambda f, d, v, r: _soft_pad(f, d, v, r, 1.0, 2.0, 900), pad_notes, -17.0, pan=0.0,
             send=0.3)

    ir = _hall_ir(3.2, 2.6, 1.1, seed=8, predelay=0.008, lp=7000)
    return mix.render(ir, hp=60.0, eq=lambda x: A.lowpass(x, 9000, 2), wobble_ms=2.0)


# ----------------------------------------------------------------------------- 3. The Kings' court
def _kings_court() -> np.ndarray:
    """D dorian (D minor with B natural), 66 bpm, 24 bars of 4/4 (87.3 s). A (bars 1-8):
    low strings drone, a slow pizzicato ostinato, a distant timpani heartbeat, high violins
    creeping in; B (9-16): the bass climbs F-G-A under a noble horn theme, violins above;
    A' (17-24): the drone returns with a cello lament and trembling violins."""
    bpm, bar = 66, 4
    harm = (["Dm", "Dm", "Dm7", "Dm", "Dm", "C/D", "G/B", "Am"] +
            ["F", "G", "Am", "Dm", "F", "G", "Em", "Am"] +
            ["Dm", "Dm", "Dm7", "Dm", "Dm", "C/D", "G/B", "Am"])
    beats = bar * len(harm)
    mix = _Mix(bpm, beats, seed=31)

    ost = {
        "Dm": "D3 A3 F3 A3 E3 A3 F3 A3", "Dm7": "D3 A3 F3 A3 C4 A3 F3 A3",
        "C/D": "C3 G3 E3 G3 D3 G3 E3 G3", "G/B": "B2 G3 D3 G3 B2 G3 D3 G3",
        "Am": "A2 E3 C3 E3 B2 E3 C3 E3", "F": "F2 C3 A2 C3 G2 C3 A2 C3",
        "G": "G2 D3 B2 D3 A2 D3 B2 D3", "Em": "E3 B3 G3 B3 A3 B3 G3 B3",
    }
    O = []
    for k, c in enumerate(harm):
        sect_v = 0.7 if 8 <= k < 16 else 0.62
        for j, p in enumerate(ost[c].split()):
            accent = 1.0 if j == 0 else (0.8 if j == 4 else 0.66)
            O.append((k * bar + 0.5 * j, 0.5, _m(p), sect_v * accent))
    mix.stem("ostinato", _pizz, O, -13.5, pan=lambda m, i: -0.12 if i % 2 == 0 else 0.08, send=0.35,
             jitter=0.008, vel_jit=0.07, hp=90)

    # low strings: a drone on D (with the fifth), then the bass line of B
    low = [(0, 24, "D2", 0.65), (0, 24, "A2", 0.6), (0, 24, "D3", 0.5), (24, 4, "G2", 0.75), (24, 4, "D3", 0.55),
           (28, 4, "A2", 0.75), (28, 4, "E3", 0.55)]
    for k, (r, f5) in enumerate([("F2", "C3"), ("G2", "D3"), ("A2", "E3"), ("D2", "A2"), ("F2", "C3"),
                                  ("G2", "D3"), ("E2", "B2"), ("A2", "E3")]):
        low += [(32 + 4 * k, 4, r, 0.8), (32 + 4 * k, 4, f5, 0.6)]
    low += [(64 + b, l, p, v) for b, l, p, v in low[:7]]
    low = [(b, l, _m(p), v) for b, l, p, v in low]
    lowstr = lambda f, d, v, r: _strings(f, d + 0.3, v, r, voices=4, bright=0.15, attack=1.4, release=1.6,
                                         vib=0.0025, spread=0.35, swell=0.25)
    mix.stem("low strings", lowstr, low, -12.0, pan=-0.1, send=0.3, hp=105)

    # timpani heartbeat, far away
    TP = []
    for k, c in enumerate(harm):
        b0 = k * bar
        v = 0.8 if 8 <= k < 16 else 0.7
        drum = _m("A2") if c in ("F", "Am") else _m("D2")     # two drums, D and A
        TP += [(b0, 1, drum, v), (b0 + 0.32, 1, drum, v * 0.6),
               (b0 + 2, 1, drum, v * 0.72), (b0 + 2.32, 1, drum, v * 0.45)]
        if k in (7, 15):                # a soft roll that swells into the next section
            for j in range(10):
                TP.append((b0 + 3 + 0.1 * j, 1, _m("A2"), 0.2 + 0.05 * j))
    mix.stem("timpani", _timp, TP, -22.0, pan=0.0, send=0.75, jitter=0.006, vel_jit=0.05, hp=55, lp=1200)

    # high violins: sustained, quiet tension
    vl = [(8, 12, _m("A4"), 0.55), (20, 8, _m("G4"), 0.55), (28, 4, _m("E4"), 0.5)]
    vl += [(32 + 4 * k, 4.2, _m(p), 0.55) for k, p in enumerate(["A4", "B4", "C5", "A4", "A4", "B4", "B4", "C5"])]
    vl += [(64, 20, _m("D5"), 0.55), (84, 4, _m("C5"), 0.55), (88, 4, _m("B4"), 0.52), (92, 4, _m("C5"), 0.4)]
    vio = lambda f, d, v, r: _strings(f, d, v, r, voices=4, bright=0.3, attack=2.0, release=2.0, vib=0.004,
                                      trem=0.0, spread=0.5)
    vio_trem = lambda f, d, v, r: _strings(f, d, v, r, voices=4, bright=0.3, attack=1.5, release=2.0, vib=0.003,
                                           trem=0.55, spread=0.5)
    mix.stem("violins", vio, [x for x in vl if x[0] < 64], -18.0, pan=0.32, send=0.45, hp=200)
    mix.stem("violins trem", vio_trem, [x for x in vl if x[0] >= 64], -19.0, pan=0.32, send=0.45, hp=200)

    # horns: the noble theme of B
    horn = _line("F3:1.5 A3:0.5 C4:2 | D4:3 B3:1 | C4:1.5 B3:0.5 A3:2 | D4:4 | "
                 "F3:1.5 A3:0.5 C4:1 F4:1 | G4:3 F4:1 | E4:2 D4:1 B3:1 | C4:1 B3:1 A3:2", bar, 32, 0.7)
    horn = [(b, l + 0.15, p, v) for b, l, p, v in horn]
    mix.stem("horns", _horn, horn, -10.0, pan=0.18, send=0.5, jitter=0.01, vel_jit=0.04, hp=90)

    # cello lament in A'
    cello = _line("D4:3 E4:1 | F4:2 E4:1 D4:1 | C4:2 A3:2 | D4:4 | F4:2 G4:1 A4:1 | G4:2 E4:1 C4:1 | "
                  "D4:2 B3:2 | C4:1 B3:1 A3:2", bar, 64, 0.65)
    cello = [(b, l + 0.1, p, v * (0.82 if b >= 92 else 1.0)) for b, l, p, v in cello]
    vc = lambda f, d, v, r: _strings(f, d, v, r, voices=2, bright=0.6, attack=0.35, release=0.8, vib=0.0055,
                                     spread=0.15, swell=0.3)
    mix.stem("cello", vc, cello, -10.5, pan=-0.22, send=0.4, jitter=0.01, hp=90)

    ir = _hall_ir(4.2, 3.6, 1.5, seed=17, predelay=0.025, lp=6000)
    return mix.render(ir, hp=35.0, eq=lambda x: A.peak_eq(A.peak_eq(x, 90, -3.0, 0.8), 2600, 2.0, 0.8))


# ----------------------------------------------------------------------------- the list
def _loop_len(bpm: float, beats: float) -> float:
    return _n(beats * 60.0 / bpm) / SR


CANDIDATES = [
    Candidate("music", "misty_keep", "Misty keep",
              "Slow, misty pads over a low drone, with a harp and soft bells now and then; very calm.",
              _misty_keep, tags=["menu"], loop_seconds=_loop_len(60, 96), bpm=60),
    Candidate("music", "music_box", "Music box",
              "A gentle music-box lullaby over a soft pad, then a fancier second take on the tune.",
              _music_box, tags=["menu"], loop_seconds=_loop_len(88, 120), bpm=88),
    Candidate("music", "kings_court", "The Kings' court",
              "Dark and regal: low strings, a slow plucked pattern, a far-off drum heartbeat and horns.",
              _kings_court, tags=["boss"], loop_seconds=_loop_len(66, 96), bpm=66),
]
