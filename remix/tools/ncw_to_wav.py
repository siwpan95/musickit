#!/usr/bin/env python
"""NCW -> WAV decoder (pure Python + numpy), ported from monomadic/ncw (Rust, MIT/Apache).

Format summary (from ncw/src/reader.rs):
  - 120-byte file header: magic u64 BE in {0x01A89ED631010000, 0x01A89ED630010000},
    channels u16 LE, bits_per_sample u16 LE, sample_rate u32 LE, num_samples u32 LE
    (frames per channel), blocks_offset u32, data_offset u32, data_size u32.
  - block offset table: num_blocks u32 LE entries between blocks_offset..data_offset;
    entry i is the offset of block i relative to data_offset; the final entry is
    an EOF sentinel (never used). The decoder iterates num_blocks-1 blocks.
  - each block, per channel: 16-byte block header (magic u32 BE 0x160C9A3E,
    base_value i32 LE, bits i16 LE, flags u16 LE) followed by abs(bits)*64 data bytes.
    bits > 0  -> DPCM: LSB-first bitstream of `bits`-wide signed deltas;
                 samples[i] = running base (starts at base_value, adds deltas).
    bits < 0  -> bit truncation: unsigned abs(bits)-wide values, used as-is.
    bits == 0 -> uncompressed: 512 samples of bits_per_sample/8 bytes each (rare).
  - each block yields exactly 512 samples per channel; final block keeps only
    overflow = (num_samples*channels % 512) // channels samples per channel.

Usage:
    python ncw_to_wav.py <in.ncw> <out.wav>
    python ncw_to_wav.py --verify <dir-with-tests-data>   # compare vs reference wavs
"""
import struct
import sys

import numpy as np

HEADER_SIZE = 120
BLOCK_HEADER_SIZE = 16
BLOCK_SAMPLES = 512
MAGIC_FILE = (0x01A89ED631010000, 0x01A89ED630010000)
MAGIC_BLOCK = 0x160C9A3E


class NcwError(Exception):
    pass


def _unpack_lsb(data: bytes, p: int, signed: bool) -> np.ndarray:
    """Unpack LSB-first bitstream into p-bit values (vectorized)."""
    if p <= 0 or p > 32:
        raise NcwError(f"unsupported precision {p} bits")
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8), bitorder="little")
    n = (bits.size // p) * p
    b = bits[:n].reshape(-1, p).astype(np.int64)
    w = (np.int64(1) << np.arange(p, dtype=np.int64))
    vals = b @ w
    if signed:
        half = np.int64(1) << (p - 1)
        full = np.int64(1) << p
        vals = np.where(vals >= half, vals - full, vals)
    return vals


def _decode_block(hdr: tuple, data: bytes, bits_per_sample: int) -> np.ndarray:
    base_value, nb, flags = hdr
    p = abs(nb)
    if nb > 0:
        deltas = _unpack_lsb(data, p, signed=True)
        out = np.empty(len(deltas), dtype=np.int64)
        out[0] = base_value
        np.cumsum(deltas[:-1], out=out[1:])
        out[1:] += base_value
        return out
    if nb < 0:
        # Bit truncation: each value holds the TOP p bits of a bps-bit sample
        # (verified against ncw-master reference wavs: values need sign
        # extension to p bits, then a left shift of (bits_per_sample - p)).
        vals = _unpack_lsb(data, p, signed=False)
        half = np.int64(1) << (p - 1)
        full = np.int64(1) << p
        vals = np.where(vals >= half, vals - full, vals)
        shift = bits_per_sample - p
        if shift > 0:
            vals = vals << shift
        return vals
    # nb == 0: uncompressed fallback (data is empty per rust impl; read 512*bps
    # bytes directly from stream instead - handled by caller)
    raise NcwError("uncompressed block must be handled by caller")


def decode_ncw(path: str) -> dict:
    """Return dict with channels, sample_rate, bits_per_sample, num_samples, samples (int32, interleaved)."""
    with open(path, "rb") as f:
        buf = f.read()

    if len(buf) < HEADER_SIZE:
        raise NcwError("file too small")
    magic = struct.unpack_from(">Q", buf, 0)[0]
    if magic not in MAGIC_FILE:
        raise NcwError(f"bad file magic 0x{magic:016X}")
    (channels, bits_per_sample, sample_rate, num_samples,
     blocks_offset, data_offset, data_size) = struct.unpack_from(
        "<HHIIIII", buf, 8)

    num_blocks = (data_offset - blocks_offset) // 4
    # entries 0..num_blocks-2 are offsets of blocks 0..num_blocks-2; the final
    # table entry is an EOF sentinel and is never used (mirrors rust `1..num_blocks`)
    offsets = struct.unpack_from(f"<{num_blocks - 1}I", buf, blocks_offset)

    total = num_samples * channels
    overflow = (total % BLOCK_SAMPLES) // channels
    # Kontakt 32-bit NCW files are IEEE float32; treat bps==32 as float
    is_float = bits_per_sample == 32

    chans = [np.empty(0, dtype=np.int64)] * channels
    chans = [list() for _ in range(channels)]
    pos = data_offset  # running read position

    def blocks():
        nonlocal pos
        for i, off in enumerate(offsets):
            yield i == len(offsets) - 1, data_offset + off

    # NOTE: rust reads (num_blocks-1) offsets and iterates that many blocks.
    is_float = False
    for is_final, block_pos in blocks():
        pos = block_pos
        block_ch = []
        ch_flags = []
        for c in range(channels):
            m = struct.unpack_from(">I", buf, pos)[0]
            if m != MAGIC_BLOCK:
                raise NcwError(f"bad block magic 0x{m:08X} at {pos}")
            base_value, nb = struct.unpack_from("<ih", buf, pos + 4)
            ch_flags.append(struct.unpack_from("<H", buf, pos + 6)[0])
            pos += BLOCK_HEADER_SIZE
            if nb == 0:
                bps = bits_per_sample // 8
                need = BLOCK_SAMPLES * bps
                raw = buf[pos:pos + need]
                pos += need
                if len(raw) < need:
                    raw = raw + b"\x00" * (need - len(raw))
                samples = np.frombuffer(raw, dtype="<i4" if bps == 4 else None)
                if bps == 2:
                    samples = np.frombuffer(raw, dtype="<i2").astype(np.int64)
                elif bps == 3:
                    u8 = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
                    samples = (u8[:, 0].astype(np.int64)
                               | (u8[:, 1].astype(np.int64) << 8)
                               | (u8[:, 2].astype(np.int64).astype(np.int64) << 16))
                    samples = np.where(samples >= (1 << 23), samples - (1 << 24), samples)
                elif bps == 4:
                    samples = np.frombuffer(raw, dtype="<i4").astype(np.int64)
            else:
                p = abs(nb)
                data = buf[pos:pos + p * 64]
                pos += p * 64
                samples = _decode_block((base_value, nb, 0), data, bits_per_sample)
            keep = overflow if is_final else len(samples)
            block_ch.append(samples[:keep])
        # MidSide stereo: only when BOTH channel headers carry bit0 and the
        # value is not the 0xFFFF placeholder seen in plain L/R files
        ms = (channels == 2
              and all(f & 0x0001 for f in ch_flags)
              and all(f != 0xFFFF for f in ch_flags))
        if ms:
            mid, side = block_ch[0], block_ch[1]
            n = min(len(mid), len(side))
            block_ch = [mid[:n] + side[:n], mid[:n] - side[:n]]
        for c in range(channels):
            chans[c].extend(block_ch[c].tolist())

    # interleave
    frames = [None] * channels
    out = np.empty(num_samples * channels, dtype=np.int64)
    for c in range(channels):
        ch = np.array(chans[c], dtype=np.int64)
        if ch.size < num_samples:
            ch = np.pad(ch, (0, num_samples - ch.size))
        out[c::channels] = ch[:num_samples]

    return {
        "channels": channels,
        "sample_rate": sample_rate,
        "bits_per_sample": bits_per_sample,
        "num_samples": num_samples,
        "float": is_float,
        "samples": out,
    }


def write_wav(path: str, info: dict):
    ch = info["channels"]
    sr = info["sample_rate"]
    bps = info["bits_per_sample"]
    s = info["samples"]

    if bps == 32:
        if info.get("float"):
            fmt, data = 3, s.astype("<i4").view("<f4").tobytes()
        else:
            fmt, data = 1, s.astype("<i4").tobytes()
        bits_out = 32
    elif bps == 24:
        u8 = s.astype("<i4").view(np.uint8).reshape(-1, 4)[:, :3]
        fmt, data = 1, u8.tobytes()
        bits_out = 24
    elif bps == 16:
        fmt, data = 1, s.astype("<i2").tobytes()
        bits_out = 16
    else:
        raise NcwError(f"unsupported bits_per_sample {bps}")

    byte_rate = sr * ch * bits_out // 8
    block_align = ch * bits_out // 8
    hdr = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
    hdr += b"fmt " + struct.pack("<IHHIIHH", 16, fmt, ch, sr, byte_rate, block_align, bits_out)
    hdr += b"data" + struct.pack("<I", len(data))
    with open(path, "wb") as f:
        f.write(hdr)
        f.write(data)


def _read_ref_wav(path: str):
    with open(path, "rb") as f:
        buf = f.read()
    assert buf[:4] == b"RIFF" and buf[8:12] == b"WAVE"
    pos = 12
    fmt = None
    data = None
    while pos + 8 <= len(buf):
        cid = buf[pos:pos + 4]
        (csz,) = struct.unpack_from("<I", buf, pos + 4)
        body = buf[pos + 8:pos + 8 + csz]
        if cid == b"fmt ":
            fmt = struct.unpack_from("<HHIIHH", body)
        elif cid == b"data":
            data = body
        pos += 8 + csz + (csz & 1)
    audio_fmt, ch, sr, _, _, bits = fmt
    if audio_fmt == 3:
        # keep bit patterns (not value-truncated floats) for exact comparison
        arr = np.frombuffer(data, dtype="<f4").view("<i4").astype(np.int64)
    elif bits == 16:
        arr = np.frombuffer(data, dtype="<i2").astype(np.int64)
    elif bits == 24:
        u8 = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3)
        arr = (u8[:, 0].astype(np.int64) | (u8[:, 1].astype(np.int64) << 8)
               | (u8[:, 2].astype(np.int64) << 16))
        arr = np.where(arr >= (1 << 23), arr - (1 << 24), arr)
    elif bits == 32:
        arr = np.frombuffer(data, dtype="<i4").astype(np.int64)
    else:
        raise NcwError(f"ref wav bits {bits}")
    return ch, sr, arr


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--verify":
        import os
        d = sys.argv[2] if len(sys.argv) > 2 else "."
        n_ok = n_bad = 0
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".ncw"):
                continue
            ncw_path = os.path.join(d, fn)
            ref = os.path.join(d, fn[:-4] + ".wav")
            if not os.path.exists(ref):
                continue
            try:
                info = decode_ncw(ncw_path)
                rch, rsr, rarr = _read_ref_wav(ref)
                n = min(info["samples"].size, rarr.size)
                # reference wavs may keep the full final block (untrimmed);
                # compare over the common prefix and require close sizes
                ok = (info["channels"] == rch and info["sample_rate"] == rsr
                      and abs(info["samples"].size - rarr.size) < 512
                      and np.array_equal(info["samples"][:n], rarr[:n]))
                print(f"{'OK ' if ok else 'BAD'} {fn}  ({info['channels']}ch {info['sample_rate']}Hz "
                      f"{info['bits_per_sample']}bit {info['num_samples']} frames)")
                n_ok += ok
                n_bad += not ok
            except Exception as e:
                print(f"ERR {fn}: {e}")
                n_bad += 1
        print(f"\nverify: ok={n_ok} bad={n_bad}")
        sys.exit(0 if n_bad == 0 else 1)

    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    info = decode_ncw(sys.argv[1])
    write_wav(sys.argv[2], info)
    print(f"{sys.argv[2]}: {info['channels']}ch {info['sample_rate']}Hz "
          f"{info['bits_per_sample']}bit {info['num_samples']} frames")


if __name__ == "__main__":
    main()
