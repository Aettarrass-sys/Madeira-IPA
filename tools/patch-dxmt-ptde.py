#!/usr/bin/env python3
"""Fix BC zero-upload sizing and reject out-of-bounds Metal texture copies."""

import argparse
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    source = path.read_text(encoding="utf-8")
    if source.count(old) != 1:
        raise SystemExit(f"Expected one pinned DXMT block in {path}; found {source.count(old)}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dxmt_root", type=Path)
    root = parser.parse_args().dxmt_root
    initializer = root / "src/dxmt/dxmt_resource_initializer.cpp"
    replace_once(initializer,
                 "namespace dxmt {\n\n#define ALLOC_BLIT",
                 "namespace dxmt {\n\nstatic inline uint32_t bc_fill_texel_size(enum WMTPixelFormat f);\n\n#define ALLOC_BLIT")
    replace_once(initializer,
                 """  bool is_3d_tex = texture->textureType() == WMTTextureType3D;
  size_t texel_size = MTLGetTexelSize(texture->pixelFormat());
  size_t bytes_per_row_needed = texel_size * align(width_sub, block_size) / block_size;""",
                 """  bool is_3d_tex = texture->textureType() == WMTTextureType3D;
  size_t texel_size = MTLGetTexelSize(texture->pixelFormat());
  const bool remapped_bc = block_size == 4u && !device_.supportsBCTextureCompression();
  if (remapped_bc) {
    // Metal stores this BC texture in its uncompressed fallback format.
    // A 1024x1024 RGBA8 zero copy needs 4 MB, not the BC-sized 1 MB.
    block_size = 1u;
    texel_size = bc_fill_texel_size(texture->pixelFormat());
  }
  size_t bytes_per_row_needed = texel_size * align(width_sub, block_size) / block_size;""")
    replace_once(initializer,
                 """    ALLOC_ZERO(zero, total_bytes_needed);
    RETAIN(allocation);
    ALLOC_BLIT(wmtcmd_blit_copy_from_buffer_to_texture, copy);""",
                 """    ALLOC_ZERO(zero, total_bytes_needed);
    if (remapped_bc && width_sub >= 512 && height_sub >= 256) {
      static unsigned logged;
      if (logged++ < 16)
        WARN("[ptde-zero-layout] size=", width_sub, "x", height_sub, "x", depth_sub,
             " fmt=", (unsigned)texture->pixelFormat(), " row=", bytes_per_row_needed,
             " required=", total_bytes_needed, " cached=", zero_buffer_size_);
    }
    RETAIN(allocation);
    ALLOC_BLIT(wmtcmd_blit_copy_from_buffer_to_texture, copy);""")

    metal = root / "src/winemetal/unix/winemetal_unix.c"
    replace_once(metal,
                 """      if (!texture_upload_pitch_ok(dst, body->size.width, body->bytes_per_row))
        break;
      wmt_stale_check(body->src, "blit copy src"); wmt_stale_check(body->dst, "blit copy dst");
      [encoder copyFromBuffer:(id<MTLBuffer>)body->src""",
                 """      if (!texture_upload_pitch_ok(dst, body->size.width, body->bytes_per_row))
        break;
      wmt_stale_check(body->src, "blit copy src"); wmt_stale_check(body->dst, "blit copy dst");
      id<MTLBuffer> src = (id<MTLBuffer>)body->src;
      size_t bpp;
      if (format_bytes_per_pixel([dst pixelFormat], &bpp) &&
          body->size.width && body->size.height && body->size.depth) {
        const uint64_t row_bytes = (uint64_t)body->size.width * bpp;
        const uint64_t image_stride = body->bytes_per_image ? body->bytes_per_image :
                                      (uint64_t)body->bytes_per_row * body->size.height;
        const uint64_t length = [src length];
        uint64_t remaining = body->src_offset <= length ? length - body->src_offset : 0;
        bool valid = body->src_offset <= length && body->bytes_per_row >= row_bytes;
        const uint64_t image_skip = (uint64_t)(body->size.depth - 1) * image_stride;
        const uint64_t row_skip = (uint64_t)(body->size.height - 1) * body->bytes_per_row;
        if (valid && image_skip <= remaining) remaining -= image_skip; else valid = false;
        if (valid && row_skip <= remaining) remaining -= row_skip; else valid = false;
        if (!valid || row_bytes > remaining) {
          static _Atomic unsigned bad_copies;
          unsigned n = atomic_fetch_add_explicit(&bad_copies, 1, memory_order_relaxed) + 1;
          if (n <= 32 || (n & 255u) == 0)
            fprintf(stderr, "[buffer-to-texture-bounds] SKIP #%u len=%llu offset=%llu row=%u image=%u size=%ux%ux%u bpp=%zu fmt=%lu level=%u\\n",
                    n, (unsigned long long)length, (unsigned long long)body->src_offset,
                    body->bytes_per_row, body->bytes_per_image, body->size.width,
                    body->size.height, body->size.depth, bpp,
                    (unsigned long)[dst pixelFormat], body->level);
          break;
        }
      }
      [encoder copyFromBuffer:src""")


if __name__ == "__main__":
    main()
