# Rendering Pipeline

## RGB565 Format

Each pixel is 2 bytes (16 bits), little-endian:

```
Bits:  RRRRR GGGGGG BBBBB
       15-11  10-5    4-0
```

Conversion from 8-bit RGB:
```python
r5 = r >> 3      # 8-bit -> 5-bit
g6 = g >> 2      # 8-bit -> 6-bit
b5 = b >> 3      # 8-bit -> 5-bit
value = (r5 << 11) | (g6 << 5) | b5
# Pack as little-endian uint16
```

### Reference Values

| Color | RGB | RGB565 | LE Bytes |
|-------|-----|--------|----------|
| Red | (255,0,0) | 0xF800 | `[0x00, 0xF8]` |
| Green | (0,255,0) | 0x07E0 | `[0xE0, 0x07]` |
| Blue | (0,0,255) | 0x001F | `[0x1F, 0x00]` |

## Frame Layout

- Screen: 135x240 pixels = 32,400 pixels = 64,800 bytes
- Total wire data: 16 chunks x 4096 bytes = 65,536 bytes

### Chunk Structure

```
Chunk 0:
  [0:1]     Frame count (1 for single image)
  [1:256]   0xFF padding (header)
  [256:4096] First 3840 bytes of pixel data

Chunks 1-14:
  [0:4096]  Pixel data (4096 bytes each)

Chunk 15 (last):
  [0:N]     Remaining pixel data
  [N:4096]  0xFF padding
```

Total pixel data capacity: 3840 + (14 * 4096) + 4096 = 65,280 bytes
Actual pixel data: 64,800 bytes -> 480 bytes of 0xFF padding in last chunk

## Image Preprocessing

Input images are:
1. Converted to RGB mode (handles RGBA, grayscale, etc.)
2. Resized to exactly 135x240 using Pillow's default resampling
3. Converted pixel-by-pixel to RGB565-LE
