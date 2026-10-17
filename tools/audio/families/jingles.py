"""Jingles: victory, loss and mission start (five candidates each).

The five candidates of each event come from five matching instrument sets, so the owner
can pick one set for all three events (or mix freely):

  royal       brass (trumpets, French horns, trombones, a tuba), kettle drums, a field drum
  tavern      a lute (paired strings, as real lutes have), a recorder and a frame drum
  enchanted   a harp, glockenspiel bells, a low chime and a music box
  orchestral  a string section (violins, violas, cellos, basses; legato, marcato, tremolo)
  8-bit       an old console: two pulse channels, a stepped triangle bass and a noise drum

All in D: victory and mission start in D major (cadences IV-V-I, 2-7-1 and a plain
V-I), loss in D dorian or D minor (a dorian amen, a folk bVII-i close, v-i, and a
string lament with the minor sixth sighing onto the fifth). Every loss is slow and soft,
never a "wah-wah" joke.

How the instruments are made (all additive or physical, so they behave like the real ones):
  brass     a sum of harmonics whose upper partials grow faster than the fundamental as
            the note gets louder (Risset's trumpet rule: soft is dark, loud is brassy),
            with a mouthpiece scoop into the pitch, a little "bite" on the attack, a
            formant per instrument (trumpet bright, horn dark), delayed vibrato and two
            slightly detuned players per part
  timpani   the membrane's modes (1, 1.50, 1.98, 2.44, 2.94 x) with a pitch that sags as
            the head relaxes after a hit, plus the felt mallet's thud; rolls are many
            soft strokes that build up the ring
  strings   three detuned, independently vibrating saws per section part, a body filter
            and a hint of bow noise; tremolo is a fast re-bowing of the amplitude
  plucks    additive plucked strings (exactly in tune; synth.pluck's loop runs 2-15 cents
            flat depending on the note, which would sour chords and glissandos): the
            pluck point sets the tone (lute near the bridge, harp near the middle), high
            harmonics die first, two polarisations give the quick-then-long decay; the
            lute doubles every string as lute courses do (bass courses with an octave)
  bells     inharmonic bar modes (glockenspiel 1, 2.76, 5.40 x; music box tine 1, 6.27 x
            with a second tooth tuned a hair apart for its gentle shimmer)
  8-bit     band-limited pulse waves, a 4-bit stepped triangle and a 15-bit LFSR noise
            channel, with volumes and pitches that change once per 1/60 s frame
Every part is mixed by loudness (gated RMS, as the build measures it), lightly
reverberated, kept below ~7.5 kHz (no hiss or harsh sizzle) and faded naturally to
silence before the event's length limit. Everything is seeded, so each rebuild is
identical.
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Callable, List, Sequence, Tuple, Union

import numpy as np
from scipy import signal

import synth as A
from catalog import EVENT_BY_ID, Candidate

SR = A.SR
FRAME = 1.0 / 60.0
Pitch = Union[str, float, int]


# ----------------------------------------------------------------------------- basics
def _n(s: float) -> int:
    return int(round(s * SR))


def _t(n: int) -> np.ndarray:
    return np.arange(n) / SR


def _hz(p: Pitch) -> float:
    if isinstance(p, str):
        return A.note_hz(p)
    if isinstance(p, (int, np.integer)):
        return A.note_hz(int(p))
    return float(p)


def _peak(x: np.ndarray) -> float:
    return float(np.max(np.abs(x))) if len(x) else 0.0


def _norm(x: np.ndarray, peak: float = 1.0) -> np.ndarray:
    p = _peak(x)
    return x * (peak / p) if p > 0 else x


def _endfade(x: np.ndarray, sec: float) -> np.ndarray:
    """A raised-cosine fade over the last ``sec`` seconds, so a buffer always ends at 0."""
    k = min(len(x), _n(sec))
    if k < 2:
        return x
    y = x.copy()
    y[-k:] *= 0.5 + 0.5 * np.cos(np.pi * np.linspace(0.0, 1.0, k))
    return y


def _ramp(x: np.ndarray, sec: float = 0.0008) -> np.ndarray:
    """A very short raised-cosine rise (starts at exactly 0, no click)."""
    k = min(len(x), max(2, _n(sec)))
    y = x.copy()
    y[:k] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(k) / k)
    return y


def _place(buf: np.ndarray, x: np.ndarray, at: float, gain: float = 1.0) -> np.ndarray:
    return A.mix_at(buf, x, max(0.0, at), gain)


def _np_zeros() -> np.ndarray:
    return np.zeros(1)


def _mix(*parts: Tuple[np.ndarray, float]) -> np.ndarray:
    n = max(len(x) for x, _ in parts)
    out = np.zeros(n)
    for x, g in parts:
        out[:len(x)] += g * x
    return out


def _loud(x: np.ndarray) -> float:
    """The build's loudness measure (gated RMS of 50 ms blocks)."""
    return A._rms_db(x)


def _at(x: np.ndarray, db: float) -> np.ndarray:
    """Scale a part to a loudness, so parts are balanced by how loud they sound."""
    return x * 10 ** ((db - _loud(x)) / 20.0)


def _verb(x: np.ndarray, room: float, wet: float, damping: float = 0.5, tail: float = 2.0) -> np.ndarray:
    return A.reverb(x, room=room, wet=wet, damping=damping, width=1.0, tail=tail)


def _glue(x: np.ndarray, crest_db: float = 14.0, release: float = 0.05) -> np.ndarray:
    """Hold the peaks to ``crest_db`` above the loudness with a smooth, look-ahead gain
    (only the tallest transients move), so the master's limiter barely has to act."""
    thr = 10 ** ((_loud(x) + crest_db) / 20.0)
    if _peak(x) <= thr:
        return x
    return A.limit(x / thr, 0.0, lookahead=0.004, release=release) * thr


def _finish(x: np.ndarray, event: str, max_s: float, fade: float = 0.6, hp: float = 70.0,
            lp: float = 7500.0, crest_db: float = 14.0) -> np.ndarray:
    """Remove sub-bass, keep the top below ``lp``, cut at ``max_s`` (well inside the
    event's limit) with a long fade so the tail dies away naturally, and glue the peaks."""
    ev = EVENT_BY_ID[event]
    max_s = min(max_s, ev.max_seconds - 0.05)
    y = A.highpass(x, hp, 2)
    if lp:
        y = A.lowpass(y, lp, 2)
    n = _n(max_s)
    if len(y) > n:
        y = y[:n]
    y = _endfade(y, min(fade, len(y) / SR * 0.5))
    return _glue(y, crest_db)


Note = Tuple[float, float, Pitch, float]          # (beat, length in beats, pitch, velocity)


def _seq(notes: Sequence[Note], beat: float, fn: Callable[..., np.ndarray], players: int = 1,
         seed: int = 0, spread_c: float = 5.0, spread_t: float = 0.012, offset: float = 0.0,
         **kw) -> np.ndarray:
    """Play ``notes`` on instrument ``fn(hz, seconds, vel, seed=, cents=, **kw)``; with
    ``players`` > 1 each note is doubled by players a few cents and milliseconds apart
    (a section, not a single synth voice). The first player is always on time."""
    rng = np.random.default_rng(seed + 17)
    buf = np.zeros(1)
    for i, (b, L, p, v) in enumerate(notes):
        for pl in range(players):
            c = 0.0 if players == 1 else spread_c * (2.0 * pl / (players - 1) - 1.0) + rng.uniform(-1, 1)
            dt = 0.0 if pl == 0 else rng.uniform(0.002, spread_t)
            x = fn(_hz(p), L * beat, v, seed=seed * 7919 + i * 31 + pl, cents=c, **kw)
            buf = _place(buf, x, offset + b * beat + dt, 1.0 / math.sqrt(players))
    return buf


def _chord(pitches: Sequence[Pitch], b: float, L: float, v: float) -> List[Note]:
    return [(b, L, p, v) for p in pitches]


# ----------------------------------------------------------------------------- brass
#            attack  release  growth  tilt   formant (Hz, gain, width oct)  roll-off
_BRASS = {
    "trumpet": (0.028, 0.16, 0.55, 0.70, (1300.0, 2.2, 0.75), 5200.0),
    "horn": (0.055, 0.30, 1.00, 1.05, (480.0, 2.5, 0.90), 2200.0),
    "trombone": (0.045, 0.24, 0.80, 0.85, (620.0, 2.0, 0.90), 3200.0),
    "tuba": (0.065, 0.30, 1.15, 1.10, (300.0, 2.0, 1.00), 1500.0),
}


def _brass(f: float, dur: float, vel: float = 0.8, seed: int = 0, cents: float = 0.0,
           kind: str = "trumpet", swell: Tuple[float, float] = (1.0, 1.0), vib: float = 0.0035,
           rel: float = None) -> np.ndarray:
    """One brass note, additive: harmonic k has amplitude k^-tilt x formant x level^(1 +
    growth (k - 1)), so the sound brightens as it gets louder (the attack 'blat', a
    forte that turns brassy, a piano that stays round)."""
    att, rel0, growth, tilt, (ff, fg, fw), lp = _BRASS[kind]
    rel = rel0 if rel is None else rel
    rng = np.random.default_rng(seed)
    total = dur + rel
    n = _n(total)
    t = _t(n)
    x = np.clip(t / att, 0.0, 1.0)
    rise = np.sin(0.5 * np.pi * x) ** 2
    g = np.where(t < att, (t / att) ** 2, np.exp(-(t - att) / 0.08))
    bite = 1.0 + 0.22 * vel * g
    s0, s1 = swell
    shape = s0 + (s1 - s0) * np.clip(t / max(dur, 1e-3), 0.0, 1.0)
    rel_env = np.where(t < dur, 1.0, np.exp(-np.maximum(t - dur, 0.0) * 5.5 / rel))
    lv = np.clip(vel * rise * bite * shape * rel_env, 0.0, 1.4)
    scoop = -26.0 * np.exp(-t / 0.03)
    vib_env = np.clip((t - 0.25) / 0.35, 0.0, 1.0)
    rate = 5.0 + rng.uniform(-0.3, 0.3)
    fi = f * 2 ** ((cents + scoop) / 1200.0) * (1 + vib * vib_env * np.sin(2 * np.pi * rate * t + rng.uniform(0, 6.28)))
    ph = 2 * np.pi * np.cumsum(fi) / SR
    loglv = np.log(np.maximum(lv, 1e-7))
    y = np.zeros(n)
    kmax = max(1, int(min(7200.0, lp * 2.5) / f))
    for k in range(1, kmax + 1):
        fk = k * f
        form = 1.0 + fg * math.exp(-(math.log2(fk / ff)) ** 2 / (2 * fw * fw))
        roll = 1.0 / (1.0 + (fk / lp) ** 4)
        ak = k ** (-tilt) * form * roll
        y += ak * np.exp((1.0 + growth * (k - 1)) * loglv) * np.sin(k * ph)
    # breath at the start of the note (the lips opening)
    br = A.lowpass(A.bandpass(rng.standard_normal(n), 900, 3500, 2), 4000, 2) * np.exp(-t / 0.035) * x
    breath = {"trumpet": 0.03, "horn": 0.012, "trombone": 0.018, "tuba": 0.01}[kind]
    y += breath * vel * br * (np.std(y) / (np.std(br) + 1e-9))
    return _endfade(y, rel * 0.35)


# ----------------------------------------------------------------------------- drums
def _timp(f: float, vel: float = 0.8, seed: int = 0, t60: float = 2.2, dur: float = None,
          mallet: float = 0.5) -> np.ndarray:
    """A kettle drum stroke: the membrane's modes, a pitch that sags back after the hit,
    and the felt mallet's soft thud. Louder strokes bring out the upper modes."""
    dur = dur or t60 * 1.15
    rng = np.random.default_rng(seed)
    n = _n(dur)
    t = _t(n)
    sag = 1.0 + 0.018 * vel * np.exp(-t / 0.06)
    ph = 2 * np.pi * np.cumsum(f * sag) / SR
    modes = [(1.0, 1.0, 1.0), (1.50, 0.55, 0.62), (1.98, 0.38, 0.50), (2.44, 0.22, 0.40),
             (2.94, 0.13, 0.32), (3.43, 0.07, 0.26)]
    y = np.zeros(n)
    for r, gain, tr in modes:
        gk = gain * (0.35 + 0.65 * vel) ** (r - 1.0) * (0.5 + mallet) ** (r - 1.0)
        y += gk * np.sin(r * ph + rng.uniform(0, 6.28)) * np.exp(-6.9 * t / (t60 * tr))
    thud = A.lowpass(rng.standard_normal(n), 250 + 900 * mallet, 2) * np.exp(-t / 0.012)
    y += 0.9 * thud * (np.std(y[:_n(0.05)]) / (np.std(thud[:_n(0.05)]) + 1e-9))
    return _endfade(_ramp(y * vel, 0.0015), dur * 0.3)


def _timp_roll(f: float, start: float, end: float, v0: float, v1: float, seed: int = 0,
               rate: float = 16.0, t60: float = 2.2) -> np.ndarray:
    """A roll: soft single strokes from alternate hands, ``rate`` per second, swelling
    from v0 to v1 (velocity), each slightly early or late as real hands are."""
    rng = np.random.default_rng(seed)
    buf = np.zeros(1)
    times = np.arange(start, end, 1.0 / rate)
    for i, tt in enumerate(times):
        fr = (tt - start) / max(end - start, 1e-3)
        v = (v0 + (v1 - v0) * fr) * (0.92 if i % 2 else 1.0) * rng.uniform(0.9, 1.05)
        jit = 0.0 if i == 0 else rng.uniform(-0.006, 0.006)
        buf = _place(buf, _timp(f, v, seed + i, t60=t60, mallet=0.3), tt + jit, 0.45)
    return buf


def _snare(vel: float = 0.8, seed: int = 0, dur: float = 0.32, wires: float = 1.0) -> np.ndarray:
    """A field drum: the stick's tick, the shell's low ring and the snare wires' buzz,
    kept below 7 kHz (warm, not hissy)."""
    rng = np.random.default_rng(seed)
    n = _n(dur)
    t = _t(n)
    w = A.lowpass(A.bandpass(rng.standard_normal(n), 1500, 6000, 2), 6500, 2)
    w = _norm(w) * np.exp(-t / 0.06) * wires
    shell = 0.8 * np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.03) + 0.35 * np.sin(2 * np.pi * 330 * t) * np.exp(-t / 0.018)
    stick = 0.5 * _norm(A.bandpass(rng.standard_normal(n), 2000, 5000, 2)) * np.exp(-t / 0.0015)
    return _endfade(_ramp((0.7 * w + shell + stick) * vel, 0.0005), dur * 0.4)


def _snare_roll(start: float, end: float, v0: float, v1: float, seed: int = 0, rate: float = 24.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    buf = np.zeros(1)
    for i, tt in enumerate(np.arange(start, end, 1.0 / rate)):
        fr = (tt - start) / max(end - start, 1e-3)
        v = (v0 + (v1 - v0) * fr) * (0.85 if i % 2 else 1.0) * rng.uniform(0.9, 1.05)
        jit = 0.0 if i == 0 else rng.uniform(-0.004, 0.004)
        buf = _place(buf, _snare(v, seed + i, 0.2), tt + jit, 0.5)
    return buf


def _bodhran(vel: float = 0.8, seed: int = 0, tap: bool = False) -> np.ndarray:
    """A frame drum: a low pitched thump in the middle of the skin, or a lighter tap
    near the rim (higher, more skin slap)."""
    if tap:
        y = A.frame_drum(0.25, 150.0, 0.12, 0.6, seed)
    else:
        y = A.frame_drum(0.6, 82.0, 0.40, 0.35, seed)
    y = A.lowpass(y, 5000, 2)
    return _endfade(_ramp(y * vel, 0.0008), 0.08)


# ----------------------------------------------------------------------------- strings
def _strings(f: float, dur: float, vel: float = 0.7, seed: int = 0, cents: float = 0.0,
             att: float = 0.12, rel: float = 0.3, bright: float = 0.5, voices: int = 3,
             vib: float = 0.0045, trem: float = 0.0, swell: Tuple[float, float] = (1.0, 1.0),
             bite: float = 0.0) -> np.ndarray:
    """A section part: ``voices`` players, each a saw a few cents apart with its own
    vibrato and a few ms late; a body filter (wood resonances near 300 Hz and 1.8 kHz);
    louder is brighter. ``trem`` is a measured tremolo (re-bowings per second)."""
    rng = np.random.default_rng(seed)
    total = dur + rel
    n = _n(total)
    t = _t(n)
    y = np.zeros(n)
    for v in range(voices):
        det = cents + (v - (voices - 1) / 2.0) * 6.0 + rng.uniform(-1.5, 1.5)
        d = 0.0 if v == 0 else rng.uniform(0.002, 0.014)
        rate = rng.uniform(4.8, 6.0)
        vib_env = np.clip((t - 0.12 - d) / 0.3, 0.0, 1.0)
        fi = f * 2 ** (det / 1200.0) * (1 + vib * vib_env * np.sin(2 * np.pi * rate * t + rng.uniform(0, 6.28)))
        s = A.osc("saw", fi, total, phase=rng.uniform(0, 6.28))
        on = np.clip((t - d) / att, 0.0, 1.0)
        env = np.sin(0.5 * np.pi * on) ** 2
        if trem:
            ph0 = rng.uniform(0, 6.28)
            env = env * (0.55 + 0.45 * (0.5 + 0.5 * np.cos(2 * np.pi * trem * t + ph0)))
        y += s * env
    y /= voices
    s0, s1 = swell
    shape = s0 + (s1 - s0) * np.clip(t / max(dur, 1e-3), 0.0, 1.0)
    shape *= 1.0 + bite * np.exp(-t / 0.07)
    rel_env = np.where(t < dur, 1.0, np.exp(-np.maximum(t - dur, 0.0) * 5.0 / rel))
    y *= shape * rel_env * vel
    cutoff = min(1200.0 + 4200.0 * bright * (0.55 + 0.45 * vel), 6500.0)
    y = A.lowpass(y, cutoff, 4)
    y = A.peak_eq(y, 300, 2.5, 1.0)
    y = A.peak_eq(y, 1800, 2.5, 1.4)
    bow = A.lowpass(A.bandpass(rng.standard_normal(n), 1800, 4500, 2), 5000, 2)
    y += 0.012 * vel * bow * shape * rel_env * (np.std(y) / (np.std(bow) + 1e-9))
    return _endfade(y, rel * 0.4)


# ----------------------------------------------------------------------------- plucked
def _pstring(f: float, vel: float = 0.7, seed: int = 0, t60: float = 1.5, beta: float = 0.15,
             soft: float = 2500.0, hf: float = 1500.0, power: float = 1.3, inharm: float = 8e-5,
             pick: float = 0.08, pick_band: Tuple[float, float] = (700.0, 3000.0), dur: float = None,
             maxf: float = 7000.0) -> np.ndarray:
    """A plucked string, additive (exactly in tune, unlike a Karplus-Strong loop whose
    delay is rounded): harmonic k has the plucked-string amplitude |sin(k pi beta)| /
    k^power (beta is where the string is plucked: near the bridge is bright and nasal,
    near the middle round and hollow), softened above ``soft`` by the fingertip, a ring
    that shortens with frequency (``hf``), the string's slight stiffness, and two
    polarisations: a quick first fall, then a longer, gently beating ring. A short
    breath of noise is the finger leaving the string."""
    rng = np.random.default_rng(seed)
    dur = dur or min(t60 * 1.15, 4.5)
    n = _n(dur)
    y = np.zeros(n)
    k = 1
    while True:
        fk = k * f * math.sqrt(1.0 + inharm * k * k)
        if fk > maxf:
            break
        a = abs(math.sin(k * math.pi * beta)) / k ** power / (1.0 + (fk / soft) ** 2)
        if a > 2e-4:
            tk = t60 / (1.0 + (fk / hf) ** 1.5)
            L = min(n, _n(tk * 1.15 + 0.01))
            tt = _t(L)
            ph = rng.uniform(-0.3, 0.3)
            fast = np.sin(2 * np.pi * fk * tt + ph) * np.exp(-6.91 * tt / (tk * 0.35))
            slow = np.sin(2 * np.pi * fk * (1.0 + 0.0006) * tt + ph) * np.exp(-6.91 * tt / tk)
            y[:L] += a * (0.55 * fast + 0.45 * slow)
        k += 1
    t = _t(n)
    nz = A.bandpass(rng.standard_normal(n), pick_band[0], pick_band[1], 2)
    y += pick * _peak(y) * _norm(nz) * np.exp(-t / 0.004)
    return _endfade(_ramp(_norm(y) * vel, 0.0006), dur * 0.25)


def _lute_body(x: np.ndarray) -> np.ndarray:
    """The lute's bowl: an air resonance low down, a wooden one near 280 Hz and a
    little nasal presence; nothing bright."""
    y = A.peak_eq(x, 130, 3.0, 1.2)
    y = A.peak_eq(y, 280, 4.0, 1.3)
    y = A.peak_eq(y, 1100, 1.5, 1.5)
    return A.lowpass(y, 6000, 2)


def _lute(f: float, dur: float, vel: float = 0.7, seed: int = 0, cents: float = 0.0,
          ring: float = None) -> np.ndarray:
    """A lute course: two gut strings plucked together a hair apart in tune, near the
    bridge; the bass courses pair a string with its octave (the lute's shimmer). Pass
    the finished part through ``_lute_body``."""
    t60 = ring or float(np.clip(1.6 * (147.0 / f) ** 0.3, 0.7, 2.0))
    f = f * 2 ** (cents / 1200)
    kw = dict(t60=t60, beta=0.13, soft=3600.0, hf=2200.0, power=1.2)
    y = _pstring(f * 2 ** (2.5 / 1200), 1.0, seed, **kw) + 0.8 * _pstring(f * 2 ** (-2.5 / 1200), 1.0, seed + 101,
                                                                          **dict(kw, beta=0.14))
    if f < 225.0:
        y = _mix((y, 1.0), (_pstring(2 * f, 1.0, seed + 202, **dict(kw, t60=t60 * 0.8)), 0.4))
    return _norm(y) * vel


def _harp(f: float, dur: float, vel: float = 0.7, seed: int = 0, cents: float = 0.0,
          ring: float = None) -> np.ndarray:
    """A harp string: plucked near its middle with the soft of the finger, long and
    round; low strings ring for seconds, high ones briefly."""
    t60 = ring or float(np.clip(3.0 * (196.0 / f) ** 0.4, 0.9, 4.0))
    y = _pstring(f * 2 ** (cents / 1200), 1.0, seed, t60=t60, beta=0.42, soft=1500.0 + 900.0 * vel,
                 hf=1400.0, power=1.45, pick=0.05, pick_band=(500.0, 2500.0))
    y = A.peak_eq(y, 240, 2.0, 0.9)
    return _norm(y) * vel


def _pizz(f: float, dur: float, vel: float = 0.7, seed: int = 0, cents: float = 0.0) -> np.ndarray:
    y = _pstring(f * 2 ** (cents / 1200), 1.0, seed, t60=0.5, beta=0.25, soft=1200.0, hf=700.0, power=1.4,
                 pick=0.04)
    return _norm(y) * vel


def _recorder(f: float, dur: float, vel: float = 0.7, seed: int = 0, cents: float = 0.0,
              vib: float = 0.004, breath: float = 0.05, swell: Tuple[float, float] = (1.0, 1.0)) -> np.ndarray:
    """A recorder: the flute voice with a tongued 'chiff' (a breath of noise at the
    start of each note)."""
    f = f * 2 ** (cents / 1200)
    rng = np.random.default_rng(seed)
    d = dur + 0.06
    y = A.flute(f, d, vibrato=5.3, depth=vib, breath=breath, seed=seed)
    n = len(y)
    t = _t(n)
    chiff = A.bandpass(rng.standard_normal(n), min(f * 2.0, 6000), min(f * 5.0, 7000), 2)
    y = y + 0.35 * _norm(chiff) * np.exp(-t / 0.015) * np.clip(t / 0.003, 0, 1)
    s0, s1 = swell
    y *= s0 + (s1 - s0) * np.clip(t / d, 0.0, 1.0)
    y = A.lowpass(y, 7000, 2)
    return _endfade(_ramp(y * vel, 0.002), min(0.05, d * 0.3))


# ----------------------------------------------------------------------------- bells
def _bars(f: float, vel: float, seed: int, partials: Sequence[Tuple[float, float, float]],
          t60: float, strike: float, strike_band: Tuple[float, float]) -> np.ndarray:
    rng = np.random.default_rng(seed)
    d = min(t60 * 1.1, 4.5)
    n = _n(d)
    t = _t(n)
    y = np.zeros(n)
    for r, g, tr in partials:
        fr = f * r
        if fr > 7600:
            continue
        y += g * np.sin(2 * np.pi * fr * t + rng.uniform(0, 6.28)) * np.exp(-6.9 * t / (t60 * tr))
    if strike:
        k = A.bandpass(rng.standard_normal(n), strike_band[0], strike_band[1], 2)
        y += strike * _norm(k) * np.exp(-t / 0.0015)
    return _endfade(_ramp(y * vel, 0.0005), d * 0.3)


def _glock(f: float, dur: float = 0.0, vel: float = 0.7, seed: int = 0, cents: float = 0.0) -> np.ndarray:
    """A glockenspiel bar struck with a soft mallet."""
    f = f * 2 ** (cents / 1200)
    t60 = float(np.clip(2.6 * (900.0 / f) ** 0.4, 1.0, 3.5))
    return _bars(f, vel, seed, [(1.0, 1.0, 1.0), (2.76, 0.28, 0.28), (5.40, 0.10, 0.14), (8.93, 0.035, 0.07)],
                 t60, 0.06, (1500, 5000))


def _chime(f: float, dur: float = 0.0, vel: float = 0.7, seed: int = 0, cents: float = 0.0,
           t60: float = 3.6) -> np.ndarray:
    """A low tubular chime: a round fundamental with a few weaker, slightly stretched
    overtones that fade first."""
    f = f * 2 ** (cents / 1200)
    return _bars(f, vel, seed, [(1.0, 1.0, 1.0), (2.0, 0.45, 0.7), (3.0, 0.22, 0.5), (4.18, 0.10, 0.32),
                                (5.43, 0.05, 0.22)], t60, 0.04, (600, 2500))


def _mbox(f: float, dur: float = 0.0, vel: float = 0.7, seed: int = 0, cents: float = 0.0) -> np.ndarray:
    """A music box tine: the pin's tiny click, the tine's pure tone (with its 6.27 x
    bending mode, quickly gone) and a second tooth a hair sharp, which makes the slow
    shimmer music boxes have."""
    f = f * 2 ** (cents / 1200)
    t60 = float(np.clip(2.6 * (600.0 / f) ** 0.5, 1.0, 3.2))
    beat = 1.1 / f
    return _bars(f, vel, seed, [(1.0, 1.0, 1.0), (1.0 + beat, 0.32, 0.9), (2.0, 0.04, 0.4), (6.27, 0.16, 0.06)],
                 t60, 0.09, (2500, 6000))


# ----------------------------------------------------------------------------- 8-bit console
@lru_cache(maxsize=2)
def _lfsr_bits(short: bool = False) -> np.ndarray:
    reg = 1
    tap = 6 if short else 1
    out = np.empty(32767)
    for i in range(32767):
        out[i] = 1.0 if reg & 1 else -1.0
        fb = (reg & 1) ^ ((reg >> tap) & 1)
        reg = (reg >> 1) | (fb << 14)
    return out


def _blep(t: np.ndarray, dt: np.ndarray) -> np.ndarray:
    out = np.zeros_like(t)
    a = t < dt
    x = t[a] / dt[a]
    out[a] = x + x - x * x - 1
    b = t > 1 - dt
    x = (t[b] - 1) / dt[b]
    out[b] = x * x + x + x + 1
    return out


def _smooth(x: np.ndarray, ms: float = 1.2) -> np.ndarray:
    a = 1.0 - math.exp(-1.0 / max(1.0, ms * 1e-3 * SR))
    return signal.lfilter([a], [1, -(1 - a)], x)


def _chip(notes: Sequence[dict], total: float, wave: str = "pulse") -> np.ndarray:
    """One console channel (monophonic: a new note takes over the channel). A note is a
    dict: t (s), d (s), p (a pitch, or a list for a fast arpeggio), v (volume 0..15),
    duty (pulse width), dec (volume steps lost per frame), rel (frames of release),
    vib (vibrato depth), vdel (frames before vibrato), arp (frames per arpeggio step).
    Volume and pitch change once per frame, like the real thing; the volume steps are
    smoothed over ~1 ms so they do not click."""
    n = _n(total)
    freq = np.zeros(n)
    amp = np.zeros(n)
    duty = np.full(n, 0.5)
    for nt in notes:
        ps = nt["p"] if isinstance(nt["p"], (list, tuple)) else [nt["p"]]
        hzs = [_hz(p) for p in ps]
        v0 = float(nt.get("v", 12))
        dec = float(nt.get("dec", 0.0))
        rel = int(nt.get("rel", 0))
        vib = float(nt.get("vib", 0.0))
        vdel = int(nt.get("vdel", 12))
        arpf = int(nt.get("arp", 2))
        on = max(1, int(round(nt["d"] * 60)))
        i0 = _n(nt["t"])
        for k in range(on + rel):
            if k < on:
                v = v0 - dec * k
            else:
                v = (v0 - dec * on) * (1.0 - (k - on + 1) / (rel + 1.0))
            v = max(0.0, math.floor(v + 1e-9)) / 15.0
            fk = hzs[(k // arpf) % len(hzs)]
            if vib and k >= vdel:
                fk *= 1 + vib * math.sin(2 * math.pi * 5.6 * (k - vdel) / 60.0)
            a = i0 + _n(k * FRAME)
            b = min(n, i0 + _n((k + 1) * FRAME))
            if a >= n:
                break
            freq[a:b] = fk
            amp[a:b] = v
            duty[a:b] = nt.get("duty", 0.5)
    amp = _smooth(amp, 1.0)
    cyc = np.cumsum(freq) / SR
    ph = cyc % 1.0
    dt = np.clip(freq / SR, 1e-9, 0.5)
    if wave == "pulse":
        s1 = 2 * ph - 1 - _blep(ph, dt)
        p2 = (ph + duty) % 1.0
        s2 = 2 * p2 - 1 - _blep(p2, dt)
        y = 0.5 * (s1 - s2)
    elif wave == "tri":
        tri = 2 * np.abs(2 * ph - 1) - 1
        y = np.floor((tri + 1) * 7.999) / 7.5 - 1.0
        y = A.lowpass(y, 5000, 2)
    else:
        raise ValueError(wave)
    return y * amp


def _chip_noise(hits: Sequence[dict], total: float) -> np.ndarray:
    """The noise channel: t, d, rate (the LFSR's clock in Hz: low is a rumble, high a
    hiss), v, dec, short (the metallic 93-step mode)."""
    n = _n(total)
    amp = np.zeros(n)
    y = np.zeros(n)
    for h in hits:
        bits = _lfsr_bits(bool(h.get("short", False)))
        on = max(1, int(round(h["d"] * 60)))
        i0 = _n(h["t"])
        dec = float(h.get("dec", 1.0))
        for k in range(on):
            a = i0 + _n(k * FRAME)
            b = min(n, i0 + _n((k + 1) * FRAME))
            if a >= n:
                break
            amp[a:b] = max(0.0, math.floor(h.get("v", 10) - dec * k + 1e-9)) / 15.0
        a, b = i0, min(n, i0 + _n(on * FRAME))
        idx = (np.arange(b - a) / SR * h.get("rate", 12000)).astype(int) % len(bits)
        y[a:b] = bits[idx]
    return y * _smooth(amp, 1.0)


def _console(total: float, p1=(), p2=(), tri=(), noise=(), g=(0.32, 0.22, 0.42, 0.16)) -> np.ndarray:
    y = (g[0] * _chip(p1, total) + g[1] * _chip(p2, total) + g[2] * _chip(tri, total, "tri")
         + g[3] * A.lowpass(_chip_noise(noise, total), 7000, 2))
    y = A.highpass(y, 60, 1)            # the console's output coupling
    return A.lowpass(y, 6500, 2)        # a small TV speaker: no fizz


def _echo_of(notes: Sequence[dict], delay: float, vol_scale: float, duty: float = None) -> List[dict]:
    out = []
    for nt in notes:
        e = dict(nt)
        e["t"] = nt["t"] + delay
        e["v"] = max(1, int(round(nt.get("v", 12) * vol_scale)))
        if duty is not None:
            e["duty"] = duty
        out.append(e)
    return out


# ============================================================================= VICTORY
def _victory_royal() -> np.ndarray:
    """Trumpets call (a triplet pickup, the tonic, then IV and V rising into a long D
    major chord); horns and trombones fill the chords; timpani roll in, mark the
    harmony, roll under the last chord and close it with one stroke."""
    b = 0.42
    T = 1.0 / 3.0
    s = 0.82                                   # short notes are detached
    rhythm = [(0, T * s), (T, T * s), (2 * T, T * s), (1, 0.92), (2, 0.46), (2.5, 0.46),
              (3, T * 0.9), (3 + T, T * 0.9), (3 + 2 * T, T * 0.9), (4, 2.6)]
    top = ["A4", "A4", "A4", "D5", "B4", "D5", "E5", "F#5", "G5", "A5"]
    sec = ["F#4", "F#4", "F#4", "A4", "G4", "B4", "C#5", "D5", "E5", "F#5"]
    vel = [0.8, 0.74, 0.86, 1.0, 0.84, 0.9, 0.84, 0.9, 0.96, 1.0]
    tp1 = [(bb, L, p, v) for (bb, L), p, v in zip(rhythm, top, vel)]
    tp2 = [(bb, L, p, v * 0.92) for (bb, L), p, v in zip(rhythm, sec, vel)]
    fin = dict(swell=(1.0, 1.12))
    t1 = _seq(tp1[:-1], b, _brass, players=2, seed=1, kind="trumpet")
    t1 = _mix((t1, 1.0), (_seq(tp1[-1:], b, _brass, players=2, seed=2, kind="trumpet", **fin), 1.0))
    t2 = _seq(tp2[:-1], b, _brass, players=2, seed=3, kind="trumpet")
    t2 = _mix((t2, 1.0), (_seq(tp2[-1:], b, _brass, players=2, seed=4, kind="trumpet", **fin), 1.0))
    hn = (_chord(["A3", "D4"], 0, 0.95, 0.6) + _chord(["D4", "F#4"], 1, 0.95, 0.72)
          + _chord(["B3", "D4"], 2, 0.95, 0.72) + _chord(["C#4", "E4"], 3, 0.95, 0.76)
          + _chord(["D4", "A4"], 4, 2.6, 0.88))
    horns = _seq(hn, b, _brass, players=2, seed=5, kind="horn")
    tb = (_chord(["D3"], 0, 0.95, 0.55) + _chord(["D3", "A3"], 1, 0.95, 0.7) + _chord(["G2", "G3"], 2, 0.95, 0.7)
          + _chord(["A2", "A3"], 3, 0.95, 0.74) + _chord(["D3", "A3"], 4, 2.6, 0.85))
    bones = _seq(tb, b, _brass, players=2, seed=6, kind="trombone")
    tuba = _seq([(1, 0.95, "D2", 0.6), (2, 0.95, "G2", 0.6), (3, 0.95, "A2", 0.65), (4, 2.6, "D2", 0.75)],
                b, _brass, seed=7, kind="tuba")
    timp = _timp_roll(_hz("A2"), 0.0, 0.93 * b, 0.25, 0.65, seed=10)
    timp = _place(timp, _timp(_hz("D3"), 0.95, 11), 1 * b)
    timp = _place(timp, _timp(_hz("A2"), 0.7, 12), 3 * b)
    timp = _place(timp, _timp(_hz("D3"), 1.0, 13), 4 * b)
    timp = _mix((timp, 1.0), (_timp_roll(_hz("D3"), 4.25 * b, 6.45 * b, 0.35, 0.55, seed=14), 1.0))
    timp = _place(timp, _timp(_hz("D3"), 0.9, 15), 6.6 * b)
    timp = A.lowpass(timp, 2500, 2)                     # felt mallets: no click on top
    x = _mix((_at(t1, -18), 1.0), (_at(t2, -21.5), 1.0), (_at(horns, -22), 1.0), (_at(bones, -23), 1.0),
             (_at(tuba, -28), 1.0), (_at(timp, -22), 1.0))
    x = _verb(x, room=0.78, wet=0.2, damping=0.45, tail=2.5)
    return _finish(x, "victory", 4.9, fade=1.0)


def _victory_tavern() -> np.ndarray:
    """A jig in 6/8: the recorder climbs the D chord and comes home through G and A; the
    lute plays bass and chord ('oom-pa'); a frame drum keeps the lilt; a rolled D chord
    ends it."""
    e = 0.15
    rec = [(0, 1, "D5", 0.8), (1, 1, "F#5", 0.8), (2, 1, "A5", 0.85), (3, 2, "D6", 0.9), (5, 1, "A5", 0.78),
           (6, 2, "B5", 0.88), (8, 1, "G5", 0.78), (9, 1, "E5", 0.8), (10, 1, "F#5", 0.8), (11, 1, "G5", 0.82),
           (12, 1, "A5", 0.86), (13, 1, "G5", 0.78), (14, 1, "E5", 0.8), (15, 2, "C#5", 0.84), (17, 1, "E5", 0.8)]
    rec = [(bb, L * 0.86, p, v) for bb, L, p, v in rec]
    recorder = _seq(rec, e, _recorder, seed=21)
    recorder = _mix((recorder, 1.0), (_seq([(18, 7, "D5", 0.9)], e, _recorder, seed=22, vib=0.006,
                                           swell=(1.0, 0.55)), 1.0))
    lute = []
    for bar, (bass, ch) in enumerate([("D3", ["F#3", "A3", "D4"]), ("G2", ["G3", "B3", "D4"]),
                                       ("A2", ["G3", "C#4", "E4"])]):
        lute.append((bar * 6, 3, bass, 0.85))
        for j, p in enumerate(ch):
            lute.append((bar * 6 + 3 + j * 0.1, 3, p, 0.6))
    for j, p in enumerate(["D2", "D3", "A3", "D4", "F#4", "A4"]):
        lute.append((18 + j * 0.2, 6, p, 0.85 - 0.04 * j))
    lute_x = _lute_body(_seq(lute, e, _lute, seed=23))
    drum = _np_zeros()
    for k in range(0, 18):
        pos = k % 6
        if pos in (0, 3):
            drum = _place(drum, _bodhran(0.9 if pos == 0 else 0.6, 30 + k), k * e)
        elif pos in (2, 5):
            drum = _place(drum, _bodhran(0.35, 30 + k, tap=True), k * e)
    drum = _place(drum, _bodhran(1.0, 60), 18 * e)
    x = _mix((_at(recorder, -18), 1.0), (_at(lute_x, -21), 1.0), (_at(drum, -25), 1.0))
    x = _verb(x, room=0.38, wet=0.13, damping=0.55, tail=1.5)
    return _finish(x, "victory", 4.4, fade=0.7)


def _victory_bells() -> np.ndarray:
    """A harp sweeps up the pentatonic scale; bells answer with a D chord arpeggio and a
    2-7-1 turn (E, C#, D) over A then D chords on the harp; a low chime and two high
    twinkles ring out."""
    harp = _np_zeros()
    gl = ["D3", "E3", "F#3", "A3", "B3", "D4", "E4", "F#4", "A4", "B4", "D5", "E5", "F#5"]
    for i, p in enumerate(gl):
        harp = _place(harp, _harp(_hz(p), 0, 0.45 + 0.03 * i, seed=40 + i, ring=1.6), i * 0.034)
    for i, p in enumerate(["A2", "E3", "A3", "C#4", "E4"]):
        harp = _place(harp, _harp(_hz(p), 0, 0.6, seed=60 + i, ring=1.4), 1.05 + i * 0.025)
    for i, p in enumerate(["D2", "A2", "D3", "F#3", "A3", "D4", "F#4", "A4"]):
        harp = _place(harp, _harp(_hz(p), 0, 0.8 - 0.02 * i, seed=70 + i), 1.5 + i * 0.03)
    bells = _np_zeros()
    for tt, p, v in [(0.47, "F#5", 0.7), (0.62, "A5", 0.75), (0.77, "D6", 0.85), (1.07, "E6", 0.78),
                     (1.25, "C#6", 0.72), (1.50, "D6", 1.0), (1.50, "A5", 0.5), (1.78, "A6", 0.28),
                     (1.95, "D7", 0.22)]:
        bells = _place(bells, _glock(_hz(p), 0, v, seed=int(tt * 100)), tt)
    chime = _chime(_hz("D4"), 0, 0.8, seed=80)
    chime = _place(_np_zeros(), chime, 1.5)
    x = _mix((_at(harp, -21), 1.0), (_at(bells, -19), 1.0), (_at(chime, -27), 1.0))
    x = _verb(x, room=0.8, wet=0.26, damping=0.5, tail=2.5)
    return _finish(x, "victory", 4.6, fade=1.2)


def _victory_strings() -> np.ndarray:
    """The violins rush up a scale into three bowed chords, IV, V and a long I that
    swells and is let go, with the cellos and basses underneath."""
    run = [(0.0, "D5"), (0.07, "E5"), (0.14, "F#5"), (0.21, "G5"), (0.28, "A5")]
    vln = _np_zeros()
    for i, (tt, p) in enumerate(run):
        v = 0.55 + 0.06 * i
        vln = _place(vln, _strings(_hz(p), 0.1, v, seed=90 + i, att=0.012, rel=0.08, bright=0.6), tt)
        vln = _place(vln, _strings(_hz(p) / 2, 0.1, v * 0.7, seed=95 + i, att=0.012, rel=0.08, bright=0.5), tt)
    chords = [(0.35, 0.3, ["G2", "G3", "D4", "B4", "G5", "B5"]),
              (0.75, 0.3, ["A2", "A3", "E4", "C#5", "A5", "C#6"]),
              (1.15, 2.0, ["D2", "D3", "A3", "F#4", "D5", "A5", "D6"])]
    body = _np_zeros()
    for ci, (tt, L, ps) in enumerate(chords):
        last = ci == 2
        for j, p in enumerate(ps):
            hi = _hz(p) > 500
            x = _strings(_hz(p), L, 0.85 if last else 0.78, seed=100 + ci * 10 + j, att=0.02,
                         rel=0.55 if last else 0.12, bright=0.6 if hi else 0.45, bite=0.45,
                         swell=(1.0, 1.12) if last else (1.0, 0.85),
                         trem=7.5 if (last and p in ("F#4", "A3")) else 0.0)
            body = _place(body, x, tt, 1.0 if hi else 0.8)
    x = _mix((_at(vln, -20), 1.0), (_at(body, -18), 1.0))
    x = _verb(x, room=0.75, wet=0.24, damping=0.5, tail=2.0)
    return _finish(x, "victory", 4.4, fade=0.9)


def _victory_8bit() -> np.ndarray:
    """A console fanfare: a quick D arpeggio up to a high D, then G and A answers and a
    long held high D with vibrato, while the second channel ripples the chord and the
    triangle walks D, G, A, D."""
    lead = [dict(t=0.000, d=0.07, p="D5", v=12, duty=0.25, dec=0.3),
            dict(t=0.075, d=0.07, p="F#5", v=12, duty=0.25, dec=0.3),
            dict(t=0.150, d=0.07, p="A5", v=12, duty=0.25, dec=0.3),
            dict(t=0.225, d=0.19, p="D6", v=13, duty=0.25, dec=0.3, rel=2),
            dict(t=0.450, d=0.12, p="B5", v=12, duty=0.25, dec=0.5, rel=2),
            dict(t=0.600, d=0.12, p="G5", v=11, duty=0.25, dec=0.5, rel=2),
            dict(t=0.750, d=0.12, p="C#6", v=12, duty=0.25, dec=0.5, rel=2),
            dict(t=0.900, d=0.12, p="A5", v=11, duty=0.25, dec=0.5, rel=2),
            dict(t=1.050, d=1.25, p="D6", v=13, duty=0.25, dec=0.13, rel=12, vib=0.006, vdel=14)]
    p2 = _echo_of(lead[:4], 0.0375, 0.45, 0.5)
    p2 += [dict(t=0.450, d=0.12, p="G5", v=8, duty=0.5, dec=0.4, rel=2),
           dict(t=0.600, d=0.12, p="D5", v=7, duty=0.5, dec=0.4, rel=2),
           dict(t=0.750, d=0.12, p="A5", v=8, duty=0.5, dec=0.4, rel=2),
           dict(t=0.900, d=0.12, p="E5", v=7, duty=0.5, dec=0.4, rel=2),
           dict(t=1.050, d=1.2, p=["A5", "F#5", "D5"], v=8, duty=0.5, dec=0.09, rel=10, arp=2)]
    tri = [dict(t=0.0, d=0.4, p="D3", v=15), dict(t=0.45, d=0.27, p="G3", v=15), dict(t=0.75, d=0.27, p="A3", v=15),
           dict(t=1.05, d=0.45, p="D4", v=15), dict(t=1.5, d=0.75, p="D3", v=15, dec=0.25, rel=8)]
    noi = [dict(t=0.45, d=0.1, rate=18000, v=10, dec=1.6), dict(t=0.75, d=0.1, rate=18000, v=10, dec=1.6),
           dict(t=0.6, d=0.05, rate=40000, v=5, dec=1.5), dict(t=0.9, d=0.05, rate=40000, v=5, dec=1.5),
           dict(t=1.05, d=0.4, rate=7000, v=10, dec=0.5)]
    x = _console(2.8, lead, p2, tri, noi)
    return _finish(x, "victory", 2.5, fade=0.7, crest_db=13.0)


# ============================================================================= LOSS
def _loss_royal() -> np.ndarray:
    """A soft horn chorale: D minor, C, G (the dorian major IV), back to D minor, the top
    horn holding its G over the last chord and sighing down to F; a muffled kettle
    drum rolls quietly underneath."""
    b = 0.58
    sop = [(0, 1.5, "A4", 0.66), (1.5, 2.5, "G4", 0.66), (4.0, 2.4, "F4", 0.62)]
    alt = [(0, 1.5, "F4", 0.6), (1.5, 1.0, "E4", 0.6), (2.5, 1.0, "D4", 0.6), (3.5, 2.9, "D4", 0.58)]
    ten = [(0, 1.5, "D4", 0.6), (1.5, 1.0, "C4", 0.6), (2.5, 1.0, "B3", 0.6), (3.5, 2.9, "A3", 0.58)]
    bas = [(0, 1.5, "D3", 0.58), (1.5, 1.0, "C3", 0.58), (2.5, 1.0, "G2", 0.58), (3.5, 2.9, "D3", 0.58)]
    fade = dict(swell=(1.0, 0.6))
    horns = _mix((_seq(sop[:2], b, _brass, players=2, seed=201, kind="horn"), 1.0),
                 (_seq(sop[2:], b, _brass, players=2, seed=202, kind="horn", **fade), 1.0),
                 (_seq(alt[:3], b, _brass, players=2, seed=203, kind="horn"), 0.9),
                 (_seq(alt[3:], b, _brass, players=2, seed=204, kind="horn", **fade), 0.9),
                 (_seq(ten[:3], b, _brass, players=2, seed=205, kind="horn"), 0.9),
                 (_seq(ten[3:], b, _brass, players=2, seed=206, kind="horn", **fade), 0.9))
    bones = _mix((_seq(bas[:3], b, _brass, players=2, seed=207, kind="trombone"), 1.0),
                 (_seq(bas[3:], b, _brass, players=2, seed=208, kind="trombone", **fade), 1.0),
                 (_seq([(3.5, 2.9, "D2", 0.45)], b, _brass, seed=209, kind="tuba", **fade), 0.7))
    timp = _timp_roll(_hz("D3"), 3.5 * b, 5.6 * b, 0.35, 0.12, seed=210, rate=13.0, t60=2.4)
    timp = _place(timp, _timp(_hz("D3"), 0.5, 211, mallet=0.2), 3.5 * b)
    timp = A.lowpass(timp, 1200, 2)                     # muffled, far away
    x = _mix((_at(horns, -19), 1.0), (_at(bones, -23), 1.0), (_at(timp, -28), 1.0))
    x = _verb(x, room=0.85, wet=0.25, damping=0.55, tail=2.5)
    return _finish(x, "loss", 4.9, fade=1.1)


def _loss_tavern() -> np.ndarray:
    """A lone lute picks a D minor chord, then C, and the recorder sings A, D, F, sighs
    down through E and C and comes to rest on D over a slow rolled D minor chord."""
    e = 0.28
    lute = [(0, 4, "D3", 0.75), (1, 3, "A3", 0.6), (2, 2, "D4", 0.6), (3, 1.2, "F4", 0.55),
            (4, 4, "C3", 0.72), (5, 3, "G3", 0.58), (6, 2, "C4", 0.58), (7, 1.2, "E4", 0.52)]
    for j, p in enumerate(["D2", "A2", "D3", "A3", "D4", "F4"]):
        lute.append((8 + j * 0.16, 6, p, 0.72 - 0.04 * j))
    lute_x = _lute_body(_seq(lute, e, _lute, seed=221))
    rec = [(0, 0.9, "A4", 0.6), (1, 0.9, "D5", 0.66), (2, 1.9, "F5", 0.72), (4, 1.4, "E5", 0.66),
           (5.5, 0.45, "D5", 0.6), (6, 1.9, "C5", 0.62)]
    recorder = _mix((_seq(rec, e, _recorder, seed=222, vib=0.005, breath=0.07), 1.0),
                    (_seq([(8, 6.5, "D5", 0.66)], e, _recorder, seed=223, vib=0.006, breath=0.07,
                          swell=(1.0, 0.25)), 1.0))
    x = _mix((_at(recorder, -19), 1.0), (_at(lute_x, -21), 1.0))
    x = _verb(x, room=0.55, wet=0.18, damping=0.55, tail=2.0)
    return _finish(x, "loss", 4.8, fade=1.0)


def _loss_mbox() -> np.ndarray:
    """A music box plays a little D minor lullaby and slows down as its spring runs out:
    D, F, A, G, F, E (over C), C, E (over A minor) and a last, late D."""
    seq = [("D5", ["D4"]), ("F5", []), ("A5", ["A3"]), ("G5", []), ("F5", ["C4"]), ("E5", []),
           ("C5", ["A3"]), ("E5", []), ("D5", ["D4", "A4"])]
    x = _np_zeros()
    tt = 0.0
    step = 0.24
    for i, (mel, bass) in enumerate(seq):
        last = i == len(seq) - 1
        x = _place(x, _mbox(_hz(mel), 0, 0.85 if not last else 0.8, seed=230 + i), tt)
        for j, p in enumerate(bass):
            x = _place(x, _mbox(_hz(p), 0, 0.5, seed=250 + i * 3 + j), tt + 0.004 * (j + 1))
        tt += step
        step *= 1.1 if i < 6 else 1.22
    x = _verb(x, room=0.4, wet=0.16, damping=0.5, tail=2.0)
    return _finish(x, "loss", 5.0, fade=1.2, crest_db=15.0)


def _loss_strings() -> np.ndarray:
    """A string lament in D minor: D minor, B flat, G minor, A minor, D minor; the violins
    lean on B flat over A and on F over E (the minor sixth sighing down), then fall
    to D while the lower strings fade."""
    b = 0.6
    mel = [(0, 1.0, "A5", 0.6), (1, 0.5, "Bb5", 0.66), (1.5, 0.5, "A5", 0.58), (2, 1.0, "G5", 0.6),
           (3, 0.5, "F5", 0.64), (3.5, 0.5, "E5", 0.56)]
    v1 = _mix((_seq(mel[:1], b, _strings, seed=260, att=0.035, rel=0.12, bright=0.45, vib=0.006), 1.0),
              (_seq(mel[1:], b, _strings, seed=261, att=0.09, rel=0.12, bright=0.45, vib=0.006), 1.0))
    v1 = _mix((v1, 1.0), (_seq([(4, 2.2, "D5", 0.6)], b, _strings, seed=262, att=0.09, rel=0.8, bright=0.4,
                               vib=0.006, swell=(1.0, 0.45)), 1.0))
    ch = [(0, 1.0, ["D4", "F4", "A4"], "D3"), (1, 1.0, ["D4", "F4", "Bb4"], "Bb2"),
          (2, 1.0, ["D4", "G4", "Bb4"], "G2"), (3, 1.0, ["C4", "E4", "A4"], "A2")]
    pad = _np_zeros()
    for i, (bb, L, ps, bass) in enumerate(ch):
        for j, p in enumerate(ps + [bass]):
            pad = _place(pad, _strings(_hz(p), L * b, 0.5, seed=270 + i * 10 + j, att=0.15, rel=0.15,
                                       bright=0.3, vib=0.004), bb * b)
    for j, p in enumerate(["D2", "D3", "A3", "D4", "F4"]):
        pad = _place(pad, _strings(_hz(p), 2.2 * b, 0.5, seed=300 + j, att=0.15, rel=0.9, bright=0.28,
                                   vib=0.004, swell=(1.0, 0.35)), 4 * b)
    x = _mix((_at(v1, -19), 1.0), (_at(pad, -22), 1.0))
    x = _verb(x, room=0.85, wet=0.28, damping=0.55, tail=2.5)
    return _finish(x, "loss", 5.0, fade=1.1)


def _loss_8bit() -> np.ndarray:
    """A gentle console farewell: slow falling arpeggios of D minor, C and A minor in a
    soft hollow square tone, an echo behind it, a triangle bass, and a long last D that
    fades away step by step."""
    e = 0.2
    pat = [("A5", 1), ("F5", 1), ("D5", 2), ("G5", 1), ("E5", 1), ("C5", 2), ("E5", 1), ("C5", 1), ("A4", 2)]
    lead = []
    pos = 0
    for p, L in pat:
        lead.append(dict(t=pos * e, d=L * e * 0.9, p=p, v=9, duty=0.5, dec=0.08, rel=3))
        pos += L
    lead.append(dict(t=pos * e, d=1.45, p="D5", v=9, duty=0.5, dec=0.085, rel=10, vib=0.007, vdel=18))
    p2 = _echo_of(lead, 0.1, 0.45, 0.25)
    tri = [dict(t=0.0, d=0.76, p="D4", v=12, rel=3), dict(t=0.8, d=0.76, p="C4", v=12, rel=3),
           dict(t=1.6, d=0.76, p="A3", v=12, rel=3), dict(t=2.4, d=1.3, p="D4", v=12, dec=0.12, rel=8)]
    x = _console(4.3, lead, p2, tri, (), g=(0.34, 0.2, 0.32, 0.0))
    return _finish(x, "loss", 4.0, fade=1.0, crest_db=13.0)


# ============================================================================= MISSION START
def _mission_royal() -> np.ndarray:
    """A horn call over a kettle drum and a field drum: 'D — A, A —, F# A, D!' climbing
    the D chord, the trombones holding D underneath and a drum roll driving into the
    last note."""
    b = 0.36
    call = [(0, 0.7, "D4", 0.8), (0.75, 0.22, "A4", 0.8), (1, 0.92, "A4", 0.9), (2, 0.45, "F#4", 0.8),
            (2.5, 0.45, "A4", 0.85), (3, 2.0, "D5", 1.0)]
    second = [(0, 0.7, "D4", 0.7), (0.75, 0.22, "F#4", 0.7), (1, 0.92, "F#4", 0.8), (2, 0.45, "D4", 0.7),
              (2.5, 0.45, "F#4", 0.75), (3, 2.0, "A4", 0.9)]
    h1 = _mix((_seq(call[:-1], b, _brass, players=2, seed=401, kind="horn"), 1.0),
              (_seq(call[-1:], b, _brass, players=2, seed=402, kind="horn", swell=(1.0, 1.1)), 1.0))
    h2 = _mix((_seq(second[:-1], b, _brass, players=2, seed=403, kind="horn"), 1.0),
              (_seq(second[-1:], b, _brass, players=2, seed=404, kind="horn", swell=(1.0, 1.1)), 1.0))
    tp = _seq([(3, 2.0, "F#5", 0.75), (3, 2.0, "D5", 0.7)], b, _brass, players=2, seed=405, kind="trumpet")
    bones = _seq([(0, 2.95, "D3", 0.6), (3, 2.0, "D3", 0.8), (3, 2.0, "A3", 0.75)], b, _brass, players=2,
                 seed=406, kind="trombone")
    timp = _place(_np_zeros(), _timp(_hz("D3"), 0.95, 410), 0.0)
    timp = _place(timp, _timp(_hz("A2"), 0.65, 411), 1 * b)
    timp = _place(timp, _timp(_hz("A2"), 0.55, 412), 2 * b)
    timp = _place(timp, _timp(_hz("D3"), 1.0, 413), 3 * b)
    timp = A.lowpass(timp, 2500, 2)
    sn = _place(_np_zeros(), _snare(0.8, 420), 0.0)
    sn = _place(sn, _snare(0.5, 421), 0.75 * b)
    sn = _place(sn, _snare(0.65, 422), 1 * b)
    sn = _mix((sn, 1.0), (_snare_roll(2 * b, 2.95 * b, 0.3, 0.75, seed=430), 1.0))
    sn = _place(sn, _snare(0.9, 440), 3 * b)
    x = _mix((_at(h1, -18.5), 1.0), (_at(h2, -21.5), 1.0), (_at(tp, -24), 1.0), (_at(bones, -24), 1.0),
             (_at(timp, -22), 1.0), (_at(sn, -27.5), 1.0))
    x = _verb(x, room=0.75, wet=0.2, damping=0.5, tail=2.0)
    return _finish(x, "mission_start", 3.6, fade=0.9)


def _mission_tavern() -> np.ndarray:
    """A marching tune to set off on: the frame drum and lute strum on every beat, the
    recorder skips up the D chord, through G and A, and lands home on D."""
    b = 0.28
    rec = [(0, 0.45, "D5", 0.78), (0.5, 0.45, "F#5", 0.78), (1, 0.45, "A5", 0.84), (1.5, 0.45, "F#5", 0.76),
           (2, 0.45, "G5", 0.8), (2.5, 0.45, "B5", 0.84), (3, 0.45, "A5", 0.82), (3.5, 0.22, "F#5", 0.76),
           (3.75, 0.22, "E5", 0.74)]
    recorder = _mix((_seq(rec, b, _recorder, seed=451), 1.0),
                    (_seq([(4, 3.2, "D5", 0.85)], b, _recorder, seed=452, vib=0.006, swell=(1.0, 0.5)), 1.0))
    chords = [["D3", "A3", "D4", "F#4"], ["D3", "A3", "D4", "F#4"], ["G2", "D3", "G3", "B3"], ["A2", "E3", "A3", "C#4"]]
    lute = []
    for i, ch in enumerate(chords):
        for j, p in enumerate(ch):
            lute.append((i + j * 0.045, 1.0, p, 0.7 - 0.05 * j))
        for j, p in enumerate(reversed(ch[1:])):            # a light up-strum on the off-beat
            lute.append((i + 0.5 + j * 0.035, 0.5, p, 0.35))
    for j, p in enumerate(["D3", "A3", "D4", "F#4", "A4"]):
        lute.append((4 + j * 0.06, 4, p, 0.78 - 0.03 * j))
    lute_x = _lute_body(_seq(lute, b, _lute, seed=453))
    drum = _np_zeros()
    for k, (bb, tap, v) in enumerate([(0, False, 0.95), (0.5, True, 0.4), (0.75, True, 0.35), (1, False, 0.8),
                                      (1.5, True, 0.4), (2, False, 0.85), (2.5, True, 0.4), (2.75, True, 0.35),
                                      (3, False, 0.8), (3.5, True, 0.45), (3.75, True, 0.5), (4, False, 1.0)]):
        drum = _place(drum, _bodhran(v, 460 + k, tap=tap), bb * b)
    x = _mix((_at(recorder, -18.5), 1.0), (_at(lute_x, -21), 1.0), (_at(drum, -23.5), 1.0))
    x = _verb(x, room=0.38, wet=0.13, damping=0.55, tail=1.5)
    return _finish(x, "mission_start", 3.0, fade=0.8)


def _mission_bells() -> np.ndarray:
    """Bells ask a question (A, D, E, rising), a harp sweeps up to meet them and opens
    into a ringing D-A-E chord (open, like a road ahead), with a low chime and a
    trail of sparkles."""
    bells = _np_zeros()
    for tt, p, v in [(0.0, "A5", 0.8), (0.16, "D6", 0.85), (0.32, "E6", 0.95), (0.72, "D6", 0.5),
                     (1.0, "A6", 0.28), (1.16, "E6", 0.24), (1.34, "A5", 0.22)]:
        bells = _place(bells, _glock(_hz(p), 0, v, seed=500 + int(tt * 100)), tt)
    harp = _np_zeros()
    for i, p in enumerate(["D4", "E4", "F#4", "A4", "B4", "D5", "E5", "F#5", "A5"]):
        harp = _place(harp, _harp(_hz(p), 0, 0.4 + 0.035 * i, seed=520 + i, ring=1.4), 0.36 + i * 0.03)
    for i, p in enumerate(["D2", "A2", "D3", "A3", "E4", "A4", "D5"]):
        harp = _place(harp, _harp(_hz(p), 0, 0.75 - 0.03 * i, seed=540 + i), 0.72 + i * 0.03)
    chime = _place(_np_zeros(), _chime(_hz("D4"), 0, 0.8, seed=560, t60=3.0), 0.72)
    x = _mix((_at(bells, -19), 1.0), (_at(harp, -21), 1.0), (_at(chime, -27), 1.0))
    x = _verb(x, room=0.8, wet=0.26, damping=0.5, tail=2.5)
    return _finish(x, "mission_start", 3.6, fade=1.1)


def _mission_strings() -> np.ndarray:
    """Low strings shiver on D and swell; the violins call out in octaves, D up to A,
    a quick B-A-F# and a leap to the high D on a full D major chord."""
    trem = _np_zeros()
    for j, p in enumerate(["D2", "D3", "A3", "D4"]):
        trem = _place(trem, _strings(_hz(p), 0.62, 0.7, seed=600 + j, att=0.012, rel=0.08, bright=0.45,
                                     trem=9.0, swell=(0.3, 1.0), bite=1.3), 0.0)
    call = [(0.62, 0.16, "D5", 0.85), (0.78, 0.4, "A5", 0.9), (1.18, 0.13, "B5", 0.82), (1.31, 0.13, "A5", 0.8),
            (1.44, 0.26, "F#5", 0.84)]
    vln = _np_zeros()
    for i, (tt, L, p, v) in enumerate(call):
        for k, f in enumerate((_hz(p), _hz(p) / 2)):
            vln = _place(vln, _strings(f, L, v * (1.0 if k == 0 else 0.8), seed=610 + i * 2 + k, att=0.018,
                                       rel=0.07, bright=0.6, bite=0.5), tt)
    low = _np_zeros()
    for j, p in enumerate(["D2", "D3", "A3"]):
        low = _place(low, _strings(_hz(p), 1.1, 0.6, seed=630 + j, att=0.03, rel=0.1, bright=0.4,
                                   trem=9.0), 0.62)
    fin = _np_zeros()
    for j, p in enumerate(["D2", "D3", "A3", "D4", "F#4", "A4", "D5", "F#5", "D6"]):
        fin = _place(fin, _strings(_hz(p), 1.05, 0.85, seed=650 + j, att=0.02, rel=0.55,
                                   bright=0.6 if _hz(p) > 500 else 0.45, bite=0.5, swell=(1.0, 1.1)), 1.70)
    x = _mix((_at(trem, -23), 1.0), (_at(vln, -19), 1.0), (_at(low, -25), 1.0), (_at(fin, -18), 1.0))
    x = _verb(x, room=0.72, wet=0.22, damping=0.5, tail=2.0)
    return _finish(x, "mission_start", 3.7, fade=0.9)


def _mission_8bit() -> np.ndarray:
    """A console 'ready, set, go': two A blips, then a quick D arpeggio up to a held high
    D with a drum splash, the second channel holding A under it."""
    lead = [dict(t=0.0, d=0.13, p="A4", v=11, duty=0.25, dec=0.4, rel=4),
            dict(t=0.4, d=0.13, p="A4", v=11, duty=0.25, dec=0.4, rel=4),
            dict(t=0.80, d=0.05, p="D5", v=12, duty=0.25),
            dict(t=0.85, d=0.05, p="F#5", v=12, duty=0.25),
            dict(t=0.90, d=0.05, p="A5", v=12, duty=0.25),
            dict(t=0.95, d=0.75, p="D6", v=13, duty=0.25, dec=0.14, rel=10, vib=0.006, vdel=12)]
    p2 = [dict(t=0.0, d=0.13, p="A3", v=6, duty=0.5, dec=0.3, rel=2),
          dict(t=0.4, d=0.13, p="A3", v=6, duty=0.5, dec=0.3, rel=2),
          dict(t=0.95, d=0.75, p=["A5", "F#5"], v=8, duty=0.5, dec=0.1, rel=8, arp=3)]
    tri = [dict(t=0.0, d=0.12, p="A3", v=15, rel=3), dict(t=0.4, d=0.12, p="A3", v=15, rel=3),
           dict(t=0.8, d=0.9, p="D3", v=15, dec=0.18, rel=8)]
    noi = [dict(t=0.0, d=0.05, rate=30000, v=6, dec=2), dict(t=0.4, d=0.05, rate=30000, v=6, dec=2),
           dict(t=0.8, d=0.4, rate=7000, v=11, dec=0.55)]
    x = _console(2.0, lead, p2, tri, noi)
    return _finish(x, "mission_start", 1.85, fade=0.5, crest_db=13.0)


# ============================================================================= the list
_SETS = {"royal": ["brass", "royal"], "tavern": ["tavern", "lute"], "enchanted": ["bells", "harp", "magic"],
         "orchestral": ["strings", "orchestral"], "8bit": ["8-bit", "retro"]}

CANDIDATES = [
    Candidate("victory", "royal_fanfare", "Royal fanfare",
              "Trumpets, horns and kettle drums ring out a proud fanfare that ends on a long, rolling chord.",
              _victory_royal, _SETS["royal"]),
    Candidate("victory", "tavern_jig", "Tavern jig",
              "A lute, a recorder and a frame drum dance a quick, merry jig, like the whole inn cheering.",
              _victory_tavern, _SETS["tavern"]),
    Candidate("victory", "golden_bells", "Golden bells",
              "A harp sweeps up and bright bells chime a little winning tune that sparkles as it fades.",
              _victory_bells, _SETS["enchanted"]),
    Candidate("victory", "string_triumph", "String triumph",
              "Violins rush upwards into three big bowed chords, the last one swelling like a film's happy end.",
              _victory_strings, _SETS["orchestral"]),
    Candidate("victory", "pixel_fanfare", "Pixel fanfare",
              "A cheerful old-console victory tune with a quick arpeggio and a long wobbly high note.",
              _victory_8bit, _SETS["8bit"]),

    Candidate("loss", "fallen_banner", "Fallen banner",
              "Soft French horns play a slow, solemn hymn over a quiet drum roll: dignified, not mocking.",
              _loss_royal, _SETS["royal"]),
    Candidate("loss", "lonely_lute", "Lonely lute",
              "A lute picks a quiet minor chord while a recorder sings a short, wistful phrase and comes to rest.",
              _loss_tavern, _SETS["tavern"]),
    Candidate("loss", "music_box", "Music box",
              "A little music box plays a sad lullaby and slows down as its spring runs out.",
              _loss_mbox, _SETS["enchanted"]),
    Candidate("loss", "rainy_strings", "Rainy strings",
              "Strings play a short, tender lament that sighs downwards and fades away.",
              _loss_strings, _SETS["orchestral"]),
    Candidate("loss", "pixel_farewell", "Pixel farewell",
              "A gentle old-console tune that falls slowly and fades out step by step, like a game-over screen.",
              _loss_8bit, _SETS["8bit"]),

    Candidate("mission_start", "horn_call", "Horn call",
              "Horns sound a rising call over kettle drums and a snare roll: time to ride out.",
              _mission_royal, _SETS["royal"]),
    Candidate("mission_start", "road_song", "Road song",
              "A frame drum, a strummed lute and a skipping recorder strike up a marching tune for the road.",
              _mission_tavern, _SETS["tavern"]),
    Candidate("mission_start", "starlit_path", "Starlit path",
              "Bells ask a rising question and a harp sweeps up into a shimmering, open chord.",
              _mission_bells, _SETS["enchanted"]),
    Candidate("mission_start", "rising_quest", "Rising quest",
              "Low strings shiver and swell, then the violins call out a bold motif onto a big chord.",
              _mission_strings, _SETS["orchestral"]),
    Candidate("mission_start", "ready_go", "Ready, go!",
              "An old-console start signal: two short beeps, then a quick climb to a bright held note.",
              _mission_8bit, _SETS["8bit"]),
]
