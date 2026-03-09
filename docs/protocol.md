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
| `0x02` | Finalize | Complete transfer, response byte[3]==1 = success |

All other command bytes are rejected by the software whitelist to prevent accidental firmware/config writes.

## Upload Flow

1. **Start session:** Send `[0x04, 0x18, 0x00*62]` on command channel
2. **Initiate LCD transfer:** Send `[0x04, 0x72, 0x02, 0, 0, 0, 0, 0, chunk_count_lo, chunk_count_hi, 0x00*54]`
3. **Stream data:** Write 4096-byte chunks on data channel (prepend `0x00` report ID)
   - Wait for ACK (input report read with 5s timeout) between each chunk
4. **Finalize:** Send `[0x04, 0x02, 0x00*62]`, verify response byte[3]==1

## Safety Considerations

- Only the LCD image transfer path is used — firmware flash uses a different VID/PID
- The LCD (likely ST7789 SPI TFT) is a passive display; worst case of a bad transfer is a garbled image
- ACK timeout (5s) prevents hanging on unresponsive device
- Device paths change on reconnect — always re-enumerate
