# Lessons Learned

## hidapi Python API

The `hidapi` package uses `hid.device()` (lowercase) + `.open_path(path)`, not `hid.Device(path=...)`. Available methods: `write`, `read`, `send_feature_report`, `get_feature_report`, `close`. Mock at `hid.enumerate` and `hid.device` level in tests.

## Daemon do-while pattern

`while not stop_event.is_set()` skips the body if event is pre-set (e.g. `--once`). Use `while True` + `if stop_event.wait(timeout): break` at the end to guarantee at least one iteration.

## RGB565 byte order — confirmed on hardware

Little-endian: red (255,0,0) = 0xF800 -> bytes `[0x00, 0xF8]`. Verified with solid color uploads — no byte swapping needed.

## Multi-frame animation

The LCD firmware natively animates multi-frame uploads. Header byte[0] = frame count, pixel data packed sequentially. 8 frames = ~127 chunks. See [rendering.md](rendering.md) for chunk math.

## macOS quirks

- `timeout` command not available by default (use `sleep` + `kill` instead)
- HID device paths look like `b'DevSrvsID:4295283928'` (not /dev paths)
- Device paths change on USB reconnect — always re-enumerate
- May need Input Monitoring permission in System Settings for HID access

## hidapi report ID 0x00 gotcha (macOS)

On macOS, hidapi's `send_feature_report(data)` checks `data[0]`: if it's `0x00`, it strips that byte before sending (treating it as "no report ID"), so the device receives `data[1:]`. Commands use `data[0]=0x04` and are unaffected. The time sync payload uses report ID `0x00`, so you must send a **65-byte** buffer (`[0x00, ...64 data bytes...]`) to compensate for the stripped byte. This caused silent time sync failures until diagnosed — the payload arrived one byte short and shifted. See `hid.py:sync_time()` and `docs/protocol.md` for details.

## Adding a new widget

1. Create `nd75_screen/widgets/your_widget.py` with `render_*_frames(data) -> list[Image]`
2. Create `tests/test_your_widget.py` with mocked external calls
3. Wire into `daemon.py` and `__main__.py` with a CLI flag
4. Pipeline: `render_frames_to_chunks(frames)` -> `device.upload_image(chunks)`
5. For static widgets, `render_to_chunks(single_image)` still works
