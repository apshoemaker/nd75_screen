# ND75 USB HID Protocol

## Device Identification

- **VID:** 0x36B5 (SONiX)
- **PID:** 0x2BA7
- **Interface 3** (usage_page=0xFF13): Command channel — 64-byte feature reports
- **Interface 2** (usage_page=0xFF68): Data channel — 4096-byte output reports

## Feature Report Format

All commands are 64-byte feature reports with prefix byte `0x04`:

```
[0x04, CMD_BYTE, payload..., 0x00 padding to 64 bytes]
```

### Allowed Commands

| Byte | Name | Purpose |
|------|------|---------|
| `0x18` | Start Session | Initialize communication |
| `0x72` | Initiate LCD Transfer | Begin image upload, includes chunk count |
| `0x28` | Time Sync | Set keyboard RTC clock |
| `0x02` | Finalize | Complete transfer, response byte[3]==1 = success |

All other command bytes are rejected by the software whitelist to prevent accidental firmware/config writes.

## Upload Flow

1. **Start session:** Send `[0x04, 0x18, 0x00*62]` on command channel
2. **Initiate LCD transfer:** Send `[0x04, 0x72, 0x02, 0, 0, 0, 0, 0, chunk_count_lo, chunk_count_hi, 0x00*54]`
3. **Stream data:** Write 4096-byte chunks on data channel (prepend `0x00` report ID)
   - Wait for ACK (input report read with 5s timeout) between each chunk
4. **Finalize:** Send `[0x04, 0x02, 0x00*62]`, verify response byte[3]==1

## Time Sync Flow

Reverse-engineered from the [web configurator](https://nd75.chilkey.com/) JS (`set0428` function).

1. **Start session:** `[0x04, 0x18, 0x00*62]`
2. **Initiate time command:** `[0x04, 0x28, 0, 0, 0, 0, 0, 0, 0x01, 0x00*55]` (byte[8]=1 = one data packet)
3. **Send time payload** (64 data bytes, sent with report ID 0x00 — see hidapi caveat below):

```
byte[0]  = 0x00
byte[1]  = 0x01
byte[2]  = 0x5A  (marker for time set)
byte[3]  = year % 100  (e.g. 26 for 2026)
byte[4]  = month        (1-12)
byte[5]  = day          (1-31)
byte[6]  = hours        (0-23)
byte[7]  = minutes      (0-59)
byte[8]  = seconds      (0-59)
byte[9]  = 0x00
byte[10] = day_of_week  (0=Sunday, 1=Monday, ... 6=Saturday)
byte[11..61] = 0x00
byte[62] = 0xAA
byte[63] = 0x55
```

4. **Read ACK** (get_feature_report)
5. **Finalize:** `[0x04, 0x02, 0x00*62]`

5ms delays between each send/receive pair; 20ms delay after reading the time payload ACK.

**IMPORTANT — hidapi report ID caveat (macOS):** The time payload uses report ID `0x00`, unlike commands which use `0x04`. On macOS, hidapi's `send_feature_report()` strips `data[0]` when it equals `0x00` (treating it as "no report ID"). This means you must send a **65-byte** buffer: `[0x00, <64 bytes of payload>]`. hidapi strips the leading `0x00` and sends the remaining 64 bytes to the device. If you send only 64 bytes starting with `0x00`, the payload arrives shifted by one byte and the time sync silently fails. See `hid.py:sync_time()` for the working implementation.

## Safety Considerations

- Only the LCD image transfer path is used — firmware flash uses a different VID/PID
- The LCD (likely ST7789 SPI TFT) is a passive display; worst case of a bad transfer is a garbled image
- ACK timeout (5s) prevents hanging on unresponsive device
- Device paths change on reconnect — always re-enumerate
