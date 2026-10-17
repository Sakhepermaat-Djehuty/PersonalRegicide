"""Sound building blocks for the game's effects and music (desktop only: numpy, scipy and
pedalboard; the phone only plays the files these make).

Everything is mono float64 at ``SR`` unless a function says stereo (shape (n, 2)). A sound
is made from the pieces below, then ``master`` brings it to a loudness target and writes
nothing; ``write_wav`` / ``write_mp3`` save it. Every random choice takes a seed, so a
sound comes out the same each time it is rebuilt.

Pieces:
  time / tone        seconds(), osc(), sine(), glide(), note_hz()
  noise              noise() white / pink / brown
  envelopes          adsr(), decay(), ar()
  filters            lowpass(), highpass(), bandpass(), peak_eq()
  instruments        pluck() (Karplus-Strong string), bell() (FM), flute(), bowed(), pad(),
                     kick(), frame_drum(), snare(), shaker(), tick(), paper()
  mixing             mix_at(), pan(), stereo()
  effects            reverb(), delay(), chorus(), compress()
  finishing          fade(), master(), loop_seamless(), stats()
  files              write_wav(), write_mp3(), write_m4a(), spectrogram_png()
"""
from __future__ import annotations

import math
import os
import subprocess
import wave
from typing import Callable, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np
from scipy import signal

SR = 44100
Num = Union[float, np.ndarray]


# ----------------------------------------------------------------------------- time and tone
def seconds(dur: float) -> np.ndarray:
    """Sample times for ``dur`` seconds."""
    return np.arange(int(round(dur * SR))) / SR


def n_of(dur: float) -> int:
    return int(round(dur * SR))


def note_hz(name: Union[str, int]) -> float:
    """'A4' -> 440, 'C#3', 'Eb5'; or a MIDI number."""
    if isinstance(name, (int, np.integer)):
        return 440.0 * 2 ** ((int(name) - 69) / 12.0)
    names = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    s = name.strip()
    k = names[s[0].upper()]
    i = 1
    while i < len(s) and s[i] in "#b":
        k += 1 if s[i] == "#" else -1
        i += 1
    octave = int(s[i:])
    return 440.0 * 2 ** ((k + 12 * (octave + 1) - 69) / 12.0)


def midi(name: str) -> int:
    return int(round(69 + 12 * math.log2(note_hz(name) / 440.0)))


def _phase(freq: Num, n: int) -> np.ndarray:
    f = np.broadcast_to(np.asarray(freq, dtype=float), (n,))
    return 2 * np.pi * np.cumsum(f) / SR


def osc(kind: str, freq: Num, dur: float, phase: float = 0.0) -> np.ndarray:
    """'sine', 'tri', 'saw', 'square' (band-limited enough for our use: PolyBLEP saw and
    square). ``freq`` may be an array (a glide) of the sound's length."""
    n = n_of(dur)
    ph = _phase(freq, n) + phase
    if kind == "sine":
        return np.sin(ph)
    f = np.broadcast_to(np.asarray(freq, dtype=float), (n,))
    dt = np.clip(f / SR, 1e-9, 0.5)
    t = (ph / (2 * np.pi)) % 1.0
    if kind == "saw":
        return (2 * t - 1) - _polyblep(t, dt)
    if kind == "square":
        sq = np.where(t < 0.5, 1.0, -1.0)
        return sq + _polyblep(t, dt) - _polyblep((t + 0.5) % 1.0, dt)
    if kind == "tri":
        return 2 * np.abs(2 * t - 1) - 1
    raise ValueError(kind)


def _polyblep(t: np.ndarray, dt: np.ndarray) -> np.ndarray:
    out = np.zeros_like(t)
    a = t < dt
    x = t[a] / dt[a]
    out[a] = x + x - x * x - 1
    b = t > 1 - dt
    x = (t[b] - 1) / dt[b]
    out[b] = x * x + x + x + 1
    return out


def sine(freq: Num, dur: float, phase: float = 0.0) -> np.ndarray:
    return osc("sine", freq, dur, phase)


def glide(f0: float, f1: float, dur: float, curve: str = "exp") -> np.ndarray:
    """A frequency ramp from f0 to f1 (exponential by default, as pitch is heard)."""
    n = n_of(dur)
    x = np.linspace(0, 1, n)
    if curve == "exp":
        return f0 * (f1 / f0) ** x
    return f0 + (f1 - f0) * x


# ----------------------------------------------------------------------------- noise
def noise(dur: float, color: str = "white", seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = n_of(dur)
    w = rng.standard_normal(n)
    if color == "white":
        out = w
    elif color == "pink":
        # Voss-McCartney-ish via a 1/f filter (Paul Kellet's coefficients)
        b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
        a = [1, -2.494956002, 2.017265875, -0.522189400]
        out = signal.lfilter(b, a, w)
    elif color == "brown":
        out = np.cumsum(w)
        out = highpass(out, 20)
    else:
        raise ValueError(color)
    peak = np.max(np.abs(out)) or 1.0
    return out / peak


# ----------------------------------------------------------------------------- envelopes
def adsr(dur: float, a: float, d: float, s: float, r: float, curve: float = 3.0) -> np.ndarray:
    """Attack, decay to sustain level ``s``, hold, release; exponential-ish segments."""
    n = n_of(dur)
    na, nd, nr = n_of(a), n_of(d), n_of(r)
    ns = max(0, n - na - nd - nr)
    att = (1 - np.exp(-curve * np.linspace(0, 1, na))) / (1 - math.exp(-curve)) if na else np.zeros(0)
    dec = s + (1 - s) * np.exp(-curve * np.linspace(0, 1, nd)) if nd else np.zeros(0)
    sus = np.full(ns, s)
    rel = s * np.exp(-curve * np.linspace(0, 1, nr)) if nr else np.zeros(0)
    env = np.concatenate([att, dec, sus, rel])
    if len(env) < n:
        env = np.concatenate([env, np.zeros(n - len(env))])
    return env[:n]


def decay(dur: float, t60: float, attack: float = 0.002) -> np.ndarray:
    """A fast attack, then an exponential fall reaching -60 dB after ``t60`` seconds."""
    t = seconds(dur)
    env = np.exp(-6.9078 * t / max(t60, 1e-4))
    na = n_of(attack)
    if na:
        env[:na] *= np.linspace(0, 1, na)
    return env


def ar(dur: float, attack: float, release: float) -> np.ndarray:
    return adsr(dur, attack, 0.0, 1.0, release)


# ----------------------------------------------------------------------------- filters
def _sos(kind: str, freq, order: int):
    nyq = SR / 2.0
    if isinstance(freq, (tuple, list)):
        wn = [min(max(f / nyq, 1e-5), 0.999) for f in freq]
    else:
        wn = min(max(freq / nyq, 1e-5), 0.999)
    return signal.butter(order, wn, btype=kind, output="sos")


def lowpass(x: np.ndarray, freq: float, order: int = 2) -> np.ndarray:
    return signal.sosfilt(_sos("lowpass", freq, order), x, axis=0)


def highpass(x: np.ndarray, freq: float, order: int = 2) -> np.ndarray:
    return signal.sosfilt(_sos("highpass", freq, order), x, axis=0)


def bandpass(x: np.ndarray, lo: float, hi: float, order: int = 2) -> np.ndarray:
    return signal.sosfilt(_sos("bandpass", (lo, hi), order), x, axis=0)


def peak_eq(x: np.ndarray, freq: float, gain_db: float, q: float = 1.0) -> np.ndarray:
    """A bell-shaped boost or cut (RBJ biquad)."""
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * math.pi * freq / SR
    alpha = math.sin(w0) / (2 * q)
    b = [1 + alpha * A, -2 * math.cos(w0), 1 - alpha * A]
    a = [1 + alpha / A, -2 * math.cos(w0), 1 - alpha / A]
    return signal.lfilter(b, a, x, axis=0)


def sweep_lowpass(x: np.ndarray, f_start: float, f_end: float, steps: int = 32) -> np.ndarray:
    """A low-pass whose cutoff moves from f_start to f_end (block-wise, crossfaded)."""
    n = len(x)
    out = np.zeros_like(x)
    edges = np.linspace(0, n, steps + 1).astype(int)
    freqs = f_start * (f_end / f_start) ** np.linspace(0, 1, steps)
    for i in range(steps):
        y = lowpass(x, freqs[i])
        a, b = edges[i], edges[i + 1]
        out[a:b] = y[a:b]
    return out


# ----------------------------------------------------------------------------- instruments
def pluck(freq: float, dur: float, brightness: float = 0.5, t60: float = 1.5, seed: int = 0,
          body: bool = True) -> np.ndarray:
    """A plucked string (Karplus-Strong), computed one period at a time. ``brightness``
    0..1 shapes the pick (darker to brighter); ``t60`` is the ring time."""
    n = n_of(dur)
    period = SR / freq
    N = max(2, int(period))
    frac = period - N
    rng = np.random.default_rng(seed)
    burst = rng.uniform(-1, 1, N)
    burst = lowpass(burst, 600 + 9000 * brightness, 1) if N > 8 else burst
    # loss per period for the requested ring time
    g = 10 ** (-3.0 * (N / SR) / max(t60, 0.05))
    out = np.zeros(n + N + 1)
    out[:N] = burst
    i = N
    prev = out[:N].copy()
    while i < n:
        seg = np.empty(N)
        # averaging filter with fractional delay smoothing
        last = out[i - N - 1] if i - N - 1 >= 0 else 0.0
        shifted = np.concatenate([[last], prev[:-1]])
        seg = g * ((1 - 0.5 - frac * 0.5) * prev + (0.5 + frac * 0.5) * shifted)
        out[i:i + N] = seg
        prev = seg
        i += N
    y = out[:n]
    if body:
        y = peak_eq(y, 220, 4, 1.2)
        y = peak_eq(y, 2800, 2, 1.5)
    return y * decay(dur, t60 * 1.6, 0.001)


def bell(freq: float, dur: float, ratio: float = 3.5, index: float = 2.5, t60: float = 2.0,
         partials: Sequence[Tuple[float, float]] = ()) -> np.ndarray:
    """An FM bell or chime: carrier at ``freq``, modulator at ``ratio`` x; the index falls
    with the sound; extra (ratio, gain) partials for inharmonic shimmer."""
    t = seconds(dur)
    env = decay(dur, t60, 0.001)
    ienv = decay(dur, t60 * 0.6, 0.001) * index
    y = np.sin(2 * np.pi * freq * t + ienv * np.sin(2 * np.pi * freq * ratio * t))
    for r, gain in partials:
        y = y + gain * np.sin(2 * np.pi * freq * r * t) * decay(dur, t60 * 0.7, 0.001)
    return y * env


def flute(freq: float, dur: float, vibrato: float = 5.0, depth: float = 0.006, breath: float = 0.08,
          seed: int = 0) -> np.ndarray:
    """A soft wooden flute or recorder: sine with a little 2nd and 3rd harmonic, delayed
    vibrato and band-passed breath noise."""
    t = seconds(dur)
    vib_env = np.clip((t - 0.15) / 0.3, 0, 1)
    f = freq * (1 + depth * vib_env * np.sin(2 * np.pi * vibrato * t))
    ph = _phase(f, len(t))
    tone = np.sin(ph) + 0.18 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph)
    br = bandpass(noise(dur, "white", seed), freq * 0.8, min(freq * 4, 15000)) * breath
    env = adsr(dur, 0.06, 0.08, 0.85, min(0.12, dur * 0.4))
    return (tone + br) * env


def bowed(freq: float, dur: float, bright: float = 0.4, vibrato: float = 5.5, seed: int = 0) -> np.ndarray:
    """A bowed string or fiddle: a band-limited saw, slow attack, vibrato, body filter."""
    t = seconds(dur)
    vib_env = np.clip((t - 0.2) / 0.4, 0, 1)
    f = freq * (1 + 0.005 * vib_env * np.sin(2 * np.pi * vibrato * t))
    y = osc("saw", f, dur)
    y = lowpass(y, 900 + 4000 * bright, 2)
    y = peak_eq(y, 450, 5, 1.0)
    y = peak_eq(y, 1800, 3, 1.4)
    y = y + 0.02 * bandpass(noise(dur, "white", seed), 2000, 6000)
    env = adsr(dur, 0.12, 0.1, 0.9, min(0.25, dur * 0.4))
    return y * env


def pad(freqs: Sequence[float], dur: float, detune: float = 0.006, cutoff: float = 1400.0,
        attack: float = 1.2, release: float = 1.5) -> np.ndarray:
    """A soft chord pad: detuned saws per note through a gentle low-pass."""
    y = np.zeros(n_of(dur))
    for k, f in enumerate(freqs):
        for d in (-detune, 0.0, detune):
            y += osc("saw", f * (1 + d), dur, phase=k * 1.3 + d * 100)
    y = lowpass(y / max(1, 3 * len(freqs)), cutoff, 2)
    return y * adsr(dur, attack, 0.3, 0.9, release)


def kick(dur: float = 0.5, f0: float = 120.0, f1: float = 45.0, t60: float = 0.35) -> np.ndarray:
    y = sine(glide(f0, f1, dur), dur)
    return y * decay(dur, t60, 0.001)


def frame_drum(dur: float = 0.6, pitch: float = 90.0, t60: float = 0.45, slap: float = 0.3,
               seed: int = 0) -> np.ndarray:
    """A hand drum (bodhran / tar): a pitched thump plus a short skin noise."""
    drop = min(0.08, dur)
    f = np.concatenate([glide(pitch * 1.5, pitch, drop), np.full(n_of(dur) - n_of(drop), pitch)])
    body = sine(f, dur)
    skin = bandpass(noise(dur, "white", seed), 400, 3000) * decay(dur, 0.06, 0.0005) * slap
    return body * decay(dur, t60, 0.001) + skin


def snare(dur: float = 0.3, t60: float = 0.18, tone: float = 190.0, seed: int = 0) -> np.ndarray:
    n = noise(dur, "white", seed)
    n = bandpass(n, 1500, 9000)
    body = sine(tone, dur) * decay(dur, 0.08, 0.001)
    return 0.8 * n * decay(dur, t60, 0.0005) + 0.5 * body


def shaker(dur: float = 0.12, seed: int = 0, bright: float = 7000.0) -> np.ndarray:
    n = highpass(noise(dur, "white", seed), bright)
    return n * adsr(dur, 0.01, 0.03, 0.3, dur * 0.6)


def tick(freq: float = 3000.0, dur: float = 0.03, q_noise: float = 0.3, seed: int = 0) -> np.ndarray:
    """A short click: a damped resonance plus a breath of noise."""
    t = seconds(dur)
    y = np.sin(2 * np.pi * freq * t) * np.exp(-t * 220)
    y += q_noise * bandpass(noise(dur, "white", seed), freq * 0.5, min(freq * 2.5, 18000)) * np.exp(-t * 400)
    return y


def paper(dur: float = 0.12, lo: float = 1200.0, hi: float = 9000.0, seed: int = 0,
          grain: float = 0.6) -> np.ndarray:
    """Card or paper friction: band-passed noise with a rough, grainy amplitude."""
    rng = np.random.default_rng(seed + 991)
    n = bandpass(noise(dur, "white", seed), lo, hi)
    m = n_of(dur)
    k = max(4, m // 220)
    grains = np.repeat(rng.uniform(1 - grain, 1, k), int(math.ceil(m / k)))[:m]
    grains = lowpass(grains, 400, 1)
    return n * grains


# ----------------------------------------------------------------------------- mixing
def mix_at(buffer: np.ndarray, sound: np.ndarray, at: float, gain: float = 1.0) -> np.ndarray:
    """Add ``sound`` into ``buffer`` starting at ``at`` seconds (grows the buffer if
    needed); works for mono and stereo alike. Returns the buffer."""
    i = n_of(at)
    end = i + len(sound)
    if end > len(buffer):
        pad_shape = (end - len(buffer),) + buffer.shape[1:]
        buffer = np.concatenate([buffer, np.zeros(pad_shape)])
    if sound.ndim == 1 and buffer.ndim == 2:
        sound = stereo(sound)
    buffer[i:end] += gain * sound
    return buffer


def pan(x: np.ndarray, p: float) -> np.ndarray:
    """Mono -> stereo, p in -1 (left) .. 1 (right), equal power."""
    a = (p + 1) * math.pi / 4
    return np.stack([x * math.cos(a), x * math.sin(a)], axis=1)


def stereo(x: np.ndarray) -> np.ndarray:
    """Mono -> stereo in the centre (the same equal-power level as pan(x, 0))."""
    return x if x.ndim == 2 else pan(x, 0.0)


def silence(dur: float, channels: int = 1) -> np.ndarray:
    n = n_of(dur)
    return np.zeros(n) if channels == 1 else np.zeros((n, channels))


# ----------------------------------------------------------------------------- effects
def _pb(x: np.ndarray, plugins) -> np.ndarray:
    from pedalboard import Pedalboard
    board = Pedalboard(list(plugins))
    arr = x.T.astype(np.float32) if x.ndim == 2 else x[None, :].astype(np.float32)
    y = board(arr, SR)
    y = y.astype(np.float64)
    return y.T if x.ndim == 2 else y[0]


def reverb(x: np.ndarray, room: float = 0.4, wet: float = 0.25, damping: float = 0.5, width: float = 1.0,
           tail: float = 1.5) -> np.ndarray:
    """Room reverb (pedalboard's Freeverb). ``tail`` seconds of silence are added first
    so the reverb can ring out."""
    from pedalboard import Reverb
    pad_ = np.zeros((n_of(tail),) + x.shape[1:])
    x = np.concatenate([x, pad_])
    return _pb(x, [Reverb(room_size=room, wet_level=wet, dry_level=1.0 - wet * 0.5, damping=damping,
                          width=width)])


def delay(x: np.ndarray, seconds_: float = 0.25, feedback: float = 0.3, mix: float = 0.25,
          tail: float = 1.0) -> np.ndarray:
    from pedalboard import Delay
    pad_ = np.zeros((n_of(tail),) + x.shape[1:])
    return _pb(np.concatenate([x, pad_]), [Delay(delay_seconds=seconds_, feedback=feedback, mix=mix)])


def chorus(x: np.ndarray, rate: float = 0.8, depth: float = 0.2, mix: float = 0.35) -> np.ndarray:
    from pedalboard import Chorus
    return _pb(x, [Chorus(rate_hz=rate, depth=depth, mix=mix, centre_delay_ms=7.0)])


def compress(x: np.ndarray, threshold_db: float = -18.0, ratio: float = 3.0, attack_ms: float = 5.0,
             release_ms: float = 120.0) -> np.ndarray:
    from pedalboard import Compressor
    return _pb(x, [Compressor(threshold_db=threshold_db, ratio=ratio, attack_ms=attack_ms,
                              release_ms=release_ms)])


# ----------------------------------------------------------------------------- finishing
def fade(x: np.ndarray, fade_in: float = 0.0, fade_out: float = 0.0) -> np.ndarray:
    y = x.copy()
    ni, no = n_of(fade_in), n_of(fade_out)
    if ni:
        r = np.linspace(0, 1, ni)
        y[:ni] *= r if y.ndim == 1 else r[:, None]
    if no:
        r = np.linspace(1, 0, no) ** 2
        y[-no:] *= r if y.ndim == 1 else r[:, None]
    return y


def trim(x: np.ndarray, floor_db: float = -60.0, keep_tail: float = 0.02) -> np.ndarray:
    """Cut leading silence (nothing before the first sample above the floor) and the tail
    once everything stays below it."""
    mono = np.abs(x) if x.ndim == 1 else np.max(np.abs(x), axis=1)
    peak = np.max(mono) or 1.0
    thr = peak * 10 ** (floor_db / 20.0)
    idx = np.nonzero(mono > thr)[0]
    if not len(idx):
        return x[:1]
    a, b = idx[0], min(len(x), idx[-1] + n_of(keep_tail))
    return x[a:b]


def _rms_db(x: np.ndarray, gate_db: float = -45.0) -> float:
    """Loudness as gated RMS in dBFS: the mean power of 50 ms blocks louder than the gate
    (relative to the loudest block), K-weighting approximated by a 100 Hz high-pass."""
    y = x if x.ndim == 1 else x.mean(axis=1)
    y = highpass(y, 100, 1)
    blk = n_of(0.05)
    if len(y) < blk:
        p = np.mean(y ** 2)
        return 10 * math.log10(p + 1e-20)
    k = len(y) // blk
    powers = np.mean(y[:k * blk].reshape(k, blk) ** 2, axis=1)
    top = np.max(powers)
    keep = powers[powers > top * 10 ** (gate_db / 10.0)]
    return 10 * math.log10(np.mean(keep) + 1e-20)


def master(x: np.ndarray, loudness_db: float = -18.0, ceiling_db: float = -1.0,
           fade_out: float = 0.01) -> np.ndarray:
    """Bring a finished sound to a gated-RMS loudness, then keep its peaks under the
    ceiling with a soft limiter; a short fade at the end avoids a click. Removes DC."""
    y = x - (np.mean(x, axis=0) if len(x) else 0)
    cur = _rms_db(y)
    y = y * 10 ** ((loudness_db - cur) / 20.0)
    y = limit(y, ceiling_db)
    return fade(y, 0.0, fade_out)


def limit(x: np.ndarray, ceiling_db: float = -1.0, lookahead: float = 0.004, release: float = 0.08) -> np.ndarray:
    """A look-ahead peak limiter that only ever turns the sound down: the gain follows
    ceiling / peak, taken over a short window ahead, and recovers smoothly."""
    from scipy.ndimage import maximum_filter1d
    ceil = 10 ** (ceiling_db / 20.0)
    mag = np.abs(x) if x.ndim == 1 else np.max(np.abs(x), axis=1)
    if not len(mag) or np.max(mag) <= ceil:
        return x
    w = max(1, n_of(lookahead))
    ahead = maximum_filter1d(mag, size=2 * w + 1)
    want = np.minimum(1.0, ceil / np.maximum(ahead, 1e-12))
    # recover slowly (a one-pole release), never letting the gain rise above what is needed
    alpha = math.exp(-1.0 / max(1, n_of(release)))
    g = signal.lfilter([1 - alpha], [1, -alpha], want - 1.0, zi=[0.0])[0] + 1.0
    g = np.minimum(g, want)
    g = np.minimum(g, maximum_filter1d(g, size=w))
    y = x * (g if x.ndim == 1 else g[:, None])
    peak = np.max(np.abs(y))
    return y * (ceil / peak) if peak > ceil else y


def loop_seamless(body: np.ndarray, tail: np.ndarray) -> np.ndarray:
    """A loop that repeats without a seam: ``body`` is exactly one loop long, ``tail`` is
    what rings on past its end (reverb, notes still sounding); the tail is folded back
    onto the loop's start, as it would sound on the second time round."""
    out = body.copy()
    t = tail
    while len(t):
        k = min(len(t), len(out))
        out[:k] += t[:k]
        t = t[k:]
    return out


def render_loop(fn: Callable[[], np.ndarray], loop_seconds: float) -> np.ndarray:
    """Call ``fn`` for a rendering that runs past the loop's length (its tail) and fold
    the tail back: the result is exactly ``loop_seconds`` long and loops seamlessly."""
    full = fn()
    n = n_of(loop_seconds)
    if len(full) < n:
        pad_shape = (n - len(full),) + full.shape[1:]
        full = np.concatenate([full, np.zeros(pad_shape)])
    return loop_seamless(full[:n], full[n:])


def stats(x: np.ndarray) -> dict:
    mono = x if x.ndim == 1 else x.mean(axis=1)
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    return {
        "seconds": round(len(x) / SR, 3),
        "channels": 1 if x.ndim == 1 else x.shape[1],
        "peak_db": round(20 * math.log10(peak + 1e-12), 2),
        "loudness_db": round(_rms_db(x), 2) if len(x) else -120.0,
        "dc": round(float(np.mean(mono)), 5) if len(x) else 0.0,
        "clipped": int(np.sum(np.abs(x) >= 0.999)),
        "start_db": round(20 * math.log10(float(np.max(np.abs(x[:64]))) + 1e-12), 1) if len(x) else -120.0,
        "end_db": round(20 * math.log10(float(np.max(np.abs(x[-64:]))) + 1e-12), 1) if len(x) else -120.0,
    }


# ----------------------------------------------------------------------------- files
def _pcm16(x: np.ndarray) -> np.ndarray:
    return (np.clip(x, -1, 1) * 32767).astype("<i2")


def write_wav(path: str, x: np.ndarray, sr: int = SR) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1 if x.ndim == 1 else x.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(_pcm16(x).tobytes())
    return path


def _ffmpeg(src: str, dst: str, args: List[str]) -> str:
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src] + args + [dst], check=True)
    return dst


def write_mp3(path: str, x: np.ndarray, kbps: int = 128) -> str:
    """For the picker page (Safari plays MP3 everywhere)."""
    tmp = path + ".tmp.wav"
    write_wav(tmp, x)
    try:
        return _ffmpeg(tmp, path, ["-codec:a", "libmp3lame", "-b:a", "%dk" % kbps])
    finally:
        os.remove(tmp)


def write_m4a(path: str, x: np.ndarray, kbps: int = 96) -> str:
    """AAC for music on the phone (small; AVAudioPlayer loops it)."""
    tmp = path + ".tmp.wav"
    write_wav(tmp, x)
    try:
        return _ffmpeg(tmp, path, ["-codec:a", "aac", "-b:a", "%dk" % kbps, "-movflags", "+faststart"])
    finally:
        os.remove(tmp)


def spectrogram_png(path: str, x: np.ndarray, width: int = 900, height: int = 300,
                    fmax: float = 12000.0) -> str:
    """A log-magnitude spectrogram (time left to right, pitch bottom to top, dark = quiet)
    with the waveform's envelope along the bottom: a way to look at a sound."""
    from PIL import Image, ImageDraw
    mono = x if x.ndim == 1 else x.mean(axis=1)
    nper = 1024
    f, t, z = signal.stft(mono, SR, nperseg=nper, noverlap=nper * 3 // 4)
    mag = 20 * np.log10(np.abs(z) + 1e-9)
    keep = f <= fmax
    mag = mag[keep]
    top = mag.max()
    img = np.clip((mag - (top - 80)) / 80.0, 0, 1)
    img = (255 * img[::-1]).astype(np.uint8)
    im = Image.fromarray(img, "L").resize((width, height - 60)).convert("RGB")
    canvas = Image.new("RGB", (width, height), (16, 18, 24))
    canvas.paste(im, (0, 0))
    d = ImageDraw.Draw(canvas)
    if len(mono):
        k = max(1, len(mono) // width)
        env = np.abs(mono[:k * width]).reshape(-1, k).max(axis=1) if len(mono) >= width else np.abs(mono)
        for i, v in enumerate(env[:width]):
            h = int(min(1.0, v) * 56)
            d.line([(i, height - 2), (i, height - 2 - h)], fill=(120, 200, 255))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    canvas.save(path)
    return path
