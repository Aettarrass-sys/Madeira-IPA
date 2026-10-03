#!/usr/bin/env python3
"""Execute the production ring allocator with counted fake GPU buffers."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / 'dxmt/src/dxmt/dxmt_ring_bump_allocator.hpp').read_text()
decl = src[src.index('template <typename Allocator, size_t BlockSize'):src.index('class GpuPrivateBufferBlockAllocator')]
impl = src[src.index('template <typename Allocator, size_t BlockSize', src.index('class HostBufferBlockAllocator')):src.rindex('} // namespace dxmt')]
program = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <mutex>
#include <queue>
#include <utility>
#define WARN(...) ((void)0)
namespace dxmt {
using mutex = std::mutex;
constexpr size_t kStagingBlockSize = 32, kStagingBlockLifetime = 300;
bool reuse = false;
bool ringOversizeReuseEnabled() { return reuse; }
size_t align(size_t n, size_t a) { return (n+a-1)&~(a-1); }
namespace this_thread { uint32_t get_id() { return 1; } }
'''+decl+impl+r'''
struct Counted {
  static inline unsigned live=0, frees=0, allocations=0;
  struct Block {
    bool owns=true;
    Block() { ++live; ++allocations; }
    Block(Block&& b):owns(b.owns) { b.owns=false; }
    ~Block() { if(owns) { --live; ++frees; } }
  };
  Block allocate(size_t) { return {}; }
};
}
int main() {
 using namespace dxmt;
 // Loading burst: GPU still owns all 39 buffers. Retire incrementally,
 // preserving the uncompleted tail, then retain just two spare blocks.
 {
  RingBumpState<Counted,8> ring(Counted{},false,2);
  for(unsigned n=1;n<=39;++n) ring.allocate(n,0,8,1);
  assert(Counted::live==39);
  ring.free_blocks(0); assert(Counted::live==39);
  ring.free_blocks(20); assert(Counted::live==19);
  ring.free_blocks(39); assert(Counted::live==2);
  unsigned before=Counted::allocations;
  ring.allocate(40,39,8,1); assert(Counted::allocations==before);
  ring.free_blocks(39); assert(Counted::live==2);
  ring.free_blocks(~0ull); assert(Counted::live==0);
 }
 // A partly used latest block may extend its lifetime into a later chunk.
 {
  RingBumpState<Counted,8> ring(Counted{},false,0);
  ring.allocate(1,0,2,1); ring.allocate(2,0,2,1);
  ring.free_blocks(1); assert(Counted::live==1);
  ring.free_blocks(2); assert(Counted::live==0);
 }
 // Deferred/replayable rings keep the old policy until explicitly reset.
 {
  RingBumpState<Counted,8> ring(Counted{});
  for(unsigned n=0;n<39;++n) ring.allocate(1,0,8,1);
  ring.free_blocks(0); assert(Counted::live==39);
  ring.free_blocks(1); assert(Counted::live==39);
  ring.free_blocks(~0ull); assert(Counted::live==0);
 }
 // Oversize blocks and optional oversize reuse retain completion safety.
 for(bool enabled:{false,true}) {
  reuse=enabled;
  RingBumpState<Counted,8> ring(Counted{},false,2);
  ring.allocate(1,0,16,1);
  ring.free_blocks(0); assert(Counted::live==1);
  ring.free_blocks(1); assert(Counted::live==unsigned(enabled));
  ring.free_blocks(~0ull); assert(Counted::live==0);
 }
 assert(Counted::frees==Counted::allocations);
}
'''
with tempfile.TemporaryDirectory(prefix='staging-test-', dir=ROOT) as td:
    path=Path(td)
    (path/'test.cpp').write_text(program)
    if os.name=='nt':
        posix='/mnt/'+path.drive[0].lower()+path.as_posix()[2:]
        compile_cmd=['wsl','g++','-std=c++20','-Wall','-Wextra','-Werror']
        file=posix+'/test.cpp'; binary=posix+'/test'
        run=['wsl',binary]
    else:
        compile_cmd=['c++','-std=c++20','-Wall','-Wextra','-Werror']
        file=str(path/'test.cpp'); binary=str(path/'test'); run=[binary]
    for debug in (False,True):
        subprocess.run(compile_cmd+(['-DDXMT_DEBUG'] if debug else [])+[file,'-o',binary],check=True)
        subprocess.run(run,check=True)

queue=(ROOT/'dxmt/src/dxmt/dxmt_command_queue.hpp').read_text()
assert 'RingBumpState<StagingBufferBlockAllocator, kBoundedStagingBlockSize> staging_allocator' in queue
assert 'kBoundedStagingBlockSize = 0x800000' in src
workflow=(ROOT/'.github/workflows/build.yml').read_text()
assert workflow.index('dxmt-staging-memory.patch') < workflow.index('bash tools/build-dsr-dxmt.sh') < workflow.index('Build unsigned Debug app')
print('PASS: production ring in release/debug; 39-block burst, GPU completion, partial reuse, deferred replay, oversized uploads, PE rebuild wiring')
