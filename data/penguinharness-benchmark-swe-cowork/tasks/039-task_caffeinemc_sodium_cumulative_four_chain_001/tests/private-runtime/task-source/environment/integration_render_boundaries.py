"""Headless rendering/world I/O adapters, not job/queue/cull implementations."""


def render_sources():
    return {
        'com.mojang.jtracy.Zone': 'public class Zone { public void close() {} }',
        'com.mojang.jtracy.TracyClient': 'public class TracyClient { public static Zone beginZone(String name,boolean active) { return new Zone(); } }',
        'net.minecraft.SharedConstants': 'public class SharedConstants { public static final boolean IS_RUNNING_IN_IDE=false; }',
        'net.minecraft.ReportedException': 'public class ReportedException extends RuntimeException { private final CrashReport report; public ReportedException(CrashReport report) { this.report=report; } public CrashReport getReport() { return report; } }',
        'net.minecraft.client.multiplayer.ClientLevel': '''public class ClientLevel extends net.minecraft.world.level.Level {
 public net.minecraft.world.level.chunk.ChunkAccess getChunk(int x,int z) { return new net.minecraft.world.level.chunk.ChunkAccess(); }
 public net.minecraft.world.level.block.state.BlockState getBlockState(net.minecraft.core.BlockPos pos) { return new net.minecraft.world.level.block.state.BlockState(); }
}''',
        'net.minecraft.client.renderer.texture.TextureAtlasSprite': 'public class TextureAtlasSprite { public Object contents() { throw new UnsupportedOperationException("GPU sprite boundary"); } }',
        'net.minecraft.world.level.block.entity.BlockEntity': 'public class BlockEntity { public BlockEntityType<?> getType() { return new BlockEntityType<>(); } }',
        'net.minecraft.world.level.block.state.BlockState': '''public class BlockState {
 public boolean isSolidRender() { return false; }
 public boolean isAir() { return true; } public boolean hasBlockEntity() { return false; }
 public net.minecraft.world.level.block.RenderShape getRenderShape() { return net.minecraft.world.level.block.RenderShape.INVISIBLE; }
 public net.minecraft.world.level.material.FluidState getFluidState() { return new net.minecraft.world.level.material.FluidState(); }
}''',
        'net.minecraft.world.level.Level': '''public class Level {
 public int getMinSectionY() { return -4; } public int getMaxSectionY() { return 19; }
 public int getSectionsCount() { return 24; }
 public int getMinY() { return -64; } public int getMaxY() { return 319; }
 public int getHeight() { return 384; }
 public int getSectionIndexFromSectionY(int section) { return section-getMinSectionY(); }
}''',
        'net.minecraft.world.level.chunk.LevelChunkSection': 'public class LevelChunkSection { public boolean hasOnlyAir() { return true; } }',
        'net.minecraft.world.level.chunk.ChunkAccess': '''public class ChunkAccess {
 public LevelChunkSection[] getSections() { var sections=new LevelChunkSection[24]; java.util.Arrays.setAll(sections,index->new LevelChunkSection()); return sections; }
}''',
        'net.minecraft.world.phys.Vec3': '''public class Vec3 {
 public final double x,y,z;
 public Vec3(double x,double y,double z) { this.x=x; this.y=y; this.z=z; }
 public double x() { return x; } public double y() { return y; } public double z() { return z; }
 public double distanceTo(Vec3 other) { return Math.sqrt(distanceToSqr(other)); }
 public double distanceToSqr(Vec3 other) { return (x-other.x)*(x-other.x)+(y-other.y)*(y-other.y)+(z-other.z)*(z-other.z); }
}''',
        'net.minecraft.client.Camera': '''public class Camera {
 public net.minecraft.world.phys.Vec3 getPosition() { return new net.minecraft.world.phys.Vec3(0,0,0); }
 public net.minecraft.core.BlockPos getBlockPosition() { return new net.minecraft.core.BlockPos(0,0,0); }
 public net.minecraft.world.phys.Vec3 position() { return getPosition(); }
 public net.minecraft.core.BlockPos blockPosition() { return getBlockPosition(); }
}''',
        'net.minecraft.core.BlockPos': '''public class BlockPos {
 protected int x,y,z;
 public BlockPos(int x,int y,int z) { this.x=x; this.y=y; this.z=z; }
 public int getX() { return x; } public int getY() { return y; } public int getZ() { return z; }
 public static BlockPos containing(double x,double y,double z) { return new BlockPos((int)Math.floor(x),(int)Math.floor(y),(int)Math.floor(z)); }
 public static class MutableBlockPos extends BlockPos {
  public MutableBlockPos() { super(0,0,0); } public MutableBlockPos(int x,int y,int z) { super(x,y,z); }
  public void set(int x,int y,int z) { this.x=x; this.y=y; this.z=z; }
 }
}''',
        'com.mojang.blaze3d.textures.GpuSampler': 'public class GpuSampler {}',
        'com.mojang.blaze3d.systems.RenderSystem': 'public class RenderSystem { public static org.joml.Matrix4f getProjectionMatrix() { return new org.joml.Matrix4f(); } }',
        'com.mojang.blaze3d.vertex.PoseStack': 'public class PoseStack { public Pose last() { return new Pose(); } public static class Pose { public org.joml.Matrix4f pose() { return new org.joml.Matrix4f(); } } }',
        'net.minecraft.util.profiling.Profiler': 'public class Profiler { public static ProfilerFiller get() { return new ProfilerFiller(); } }',
        'net.minecraft.util.profiling.ProfilerFiller': 'public class ProfilerFiller { public void push(String name) {} public void pop() {} public void popPush(String name) {} }',
        'org.apache.commons.lang3.ArrayUtils': 'public class ArrayUtils { public static boolean isEmpty(Object[] array) { return array==null || array.length==0; } }',
        'net.minecraft.world.level.material.FluidState': 'public class FluidState { public boolean isEmpty() { return true; } }',
        'net.minecraft.client.renderer.ItemBlockRenderTypes': '''public class ItemBlockRenderTypes {
 public static RenderType getChunkRenderType(net.minecraft.world.level.block.state.BlockState state) { return RenderType.solid(); }
 public static RenderType getRenderLayer(net.minecraft.world.level.material.FluidState state) { return RenderType.translucent(); }
}''',
        'net.minecraft.core.Direction': '''public enum Direction {
 DOWN(0,-1,0), UP(0,1,0), NORTH(0,0,-1), SOUTH(0,0,1), WEST(-1,0,0), EAST(1,0,0);
 private final org.joml.Vector3f vector;
 Direction(int x,int y,int z) { vector=new org.joml.Vector3f(x,y,z); }
 public org.joml.Vector3f step() { return vector; }
 public Direction getOpposite() { return values()[ordinal()^1]; }
 public int getStepX() { return (int)vector.x; } public int getStepY() { return (int)vector.y; } public int getStepZ() { return (int)vector.z; }
}''',
        'net.minecraft.client.renderer.RenderType': '''public class RenderType {
 public void setupRenderState() {} public void clearRenderState() {}
 public static RenderType solid() { return new RenderType(); }
 public static RenderType cutout() { return new RenderType(); }
 public static RenderType cutoutMipped() { return new RenderType(); }
 public static RenderType translucent() { return new RenderType(); }
 public static RenderType tripwire() { return new RenderType(); }
}''',
        'net.minecraft.client.renderer.chunk.VisibilitySet': '''public class VisibilitySet {
 private final boolean[][] visible=new boolean[6][6];
 public boolean visibilityBetween(net.minecraft.core.Direction from,net.minecraft.core.Direction to) { return visible[from.ordinal()][to.ordinal()]; }
 public void setAll(boolean value) { for(boolean[] row:visible) java.util.Arrays.fill(row,value); }
 public void add(java.util.Set<net.minecraft.core.Direction> directions) { for(var first:directions) for(var second:directions) visible[first.ordinal()][second.ordinal()]=true; }
 public void set(net.minecraft.core.Direction first,net.minecraft.core.Direction second,boolean value) { visible[first.ordinal()][second.ordinal()]=value; visible[second.ordinal()][first.ordinal()]=value; }
}''',
        'net.caffeinemc.mods.sodium.client.render.chunk.compile.pipeline.DefaultFluidRenderer': 'public class DefaultFluidRenderer { public static final float EPSILON=0.001f; }',
        'net.caffeinemc.mods.sodium.client.render.chunk.translucent_sorting.TranslucentGeometryCollector': '''public class TranslucentGeometryCollector {
 public TranslucentGeometryCollector(net.minecraft.core.SectionPos pos,SortBehavior behavior) {}
 public int getQuadHash() { throw new UnsupportedOperationException("geometry input boundary"); }
 public SortType finishRendering() { throw new UnsupportedOperationException("geometry input boundary"); }
 public net.caffeinemc.mods.sodium.client.render.chunk.translucent_sorting.data.TranslucentData getTranslucentData(net.caffeinemc.mods.sodium.client.render.chunk.translucent_sorting.data.TranslucentData previous,net.caffeinemc.mods.sodium.client.render.chunk.translucent_sorting.data.CombinedCameraPos camera) { throw new UnsupportedOperationException("geometry input boundary"); }
}''',
        'net.caffeinemc.mods.sodium.client.render.chunk.vertex.builder.ChunkMeshBufferBuilder': '''public class ChunkMeshBufferBuilder {
 public void writeExternal(java.nio.ByteBuffer buffer,int offset,net.caffeinemc.mods.sodium.client.render.chunk.vertex.format.ChunkVertexEncoder.Vertex[] vertices,net.caffeinemc.mods.sodium.client.render.chunk.terrain.material.Material material) { throw new UnsupportedOperationException("GPU mesh boundary"); }
}''',
        'net.minecraft.core.SectionPos': '''public record SectionPos(int x,int y,int z) {
 public static SectionPos of(int x,int y,int z) { return new SectionPos(x,y,z); }
 public static int sectionToBlockCoord(int value) { return value<<4; }
 public static int blockToSectionCoord(int value) { return value>>4; }
 public static int posToSectionCoord(double value) { return (int)Math.floor(value)>>4; }
 public static long asLong(int x,int y,int z) { return ((long)x&0x3FFFFF)<<42 | ((long)z&0x3FFFFF)<<20 | ((long)y&0xFFFFF); }
 public long asLong() { return asLong(x,y,z); }
 public int getX() { return x; } public int getY() { return y; } public int getZ() { return z; }
 public int minBlockX() { return x<<4; } public int minBlockY() { return y<<4; } public int minBlockZ() { return z<<4; }
}''',
        'net.caffeinemc.mods.sodium.client.render.chunk.compile.ChunkBuildContext': '''public class ChunkBuildContext {
 public final ChunkBuildBuffers buffers=new ChunkBuildBuffers();
 public final net.caffeinemc.mods.sodium.client.render.chunk.compile.pipeline.BlockRenderCache cache=new net.caffeinemc.mods.sodium.client.render.chunk.compile.pipeline.BlockRenderCache();
 public ChunkBuildContext(net.minecraft.client.multiplayer.ClientLevel level,net.caffeinemc.mods.sodium.client.render.chunk.vertex.format.ChunkVertexType type) {}
 public void cleanup() {}
}''',
        'net.caffeinemc.mods.sodium.client.render.chunk.vertex.format.ChunkVertexType': 'public interface ChunkVertexType {}',
        'net.caffeinemc.mods.sodium.client.render.chunk.vertex.format.ChunkMeshFormats': 'public class ChunkMeshFormats { public static final ChunkVertexType COMPACT=new ChunkVertexType() {}; }',
        'net.caffeinemc.mods.sodium.client.gl.device.CommandList': 'public interface CommandList extends AutoCloseable { default void flush() {} default void close() {} }',
        'net.caffeinemc.mods.sodium.client.gl.device.RenderDevice': 'public class RenderDevice { public static final RenderDevice INSTANCE=new RenderDevice(); public CommandList createCommandList() { return new CommandList() {}; } }',
        'net.caffeinemc.mods.sodium.client.render.chunk.DefaultChunkRenderer': '''public class DefaultChunkRenderer implements ChunkRenderer {
 public DefaultChunkRenderer(Object device,Object format) {}
 public static int getVisibleFaces(int cameraX,int cameraY,int cameraZ,int sectionX,int sectionY,int sectionZ) { return 127; }
 public void render(ChunkRenderMatrices matrices,net.caffeinemc.mods.sodium.client.gl.device.CommandList command,net.caffeinemc.mods.sodium.client.render.chunk.lists.ChunkRenderListIterable lists,net.caffeinemc.mods.sodium.client.render.chunk.terrain.TerrainRenderPass pass,net.caffeinemc.mods.sodium.client.render.viewport.CameraTransform camera) { throw new UnsupportedOperationException("GPU drawing boundary"); }
 public void delete(net.caffeinemc.mods.sodium.client.gl.device.CommandList command) {}
}''',
        'net.caffeinemc.mods.sodium.client.render.chunk.region.RenderRegionManager': '''public class RenderRegionManager {
 public static final java.util.List<net.caffeinemc.mods.sodium.client.render.chunk.compile.BuilderTaskOutput> UPLOADS=new java.util.ArrayList<>();
 private final java.util.Map<Long,RenderRegion> regions=new java.util.HashMap<>();
 public RenderRegionManager(net.caffeinemc.mods.sodium.client.gl.device.CommandList command) {}
 public RenderRegion createForChunk(int x,int y,int z) { return regions.computeIfAbsent(RenderRegion.key(x,y,z),key->new RenderRegion()); }
 public java.util.Collection<RenderRegion> getLoadedRegions() { return regions.values(); }
 public RenderRegion getRegion(long key) { return regions.get(key); }
 public RenderRegion getForChunk(int x,int y,int z) { return getRegion(RenderRegion.key(x,y,z)); }
 public void update() {} public void delete(net.caffeinemc.mods.sodium.client.gl.device.CommandList command) {}
 public Staging getStagingBuffer() { return new Staging(); }
 public void uploadResults(net.caffeinemc.mods.sodium.client.gl.device.CommandList command,java.util.List<? extends net.caffeinemc.mods.sodium.client.render.chunk.compile.BuilderTaskOutput> outputs) { UPLOADS.addAll(outputs); }
 public static class Staging { public static long limit=Long.MAX_VALUE; public long getUploadSizeLimit(long duration) { return limit; } }
}''',
        'net.caffeinemc.mods.sodium.client.world.cloned.ClonedChunkSectionCache': '''public class ClonedChunkSectionCache {
 public ClonedChunkSectionCache(net.minecraft.client.multiplayer.ClientLevel level) {}
 public void cleanup() {} public void invalidate(int x,int y,int z) {}
}''',
        'net.caffeinemc.mods.sodium.client.world.cloned.ChunkRenderContext': 'public class ChunkRenderContext { public java.util.List<?> getRenderers() { return java.util.List.of(); } public Object getVolume() { return null; } }',
        'net.caffeinemc.mods.sodium.client.world.LevelSlice': '''public class LevelSlice implements net.minecraft.world.level.BlockGetter {
 public net.minecraft.world.level.block.state.BlockState getBlockState(int x,int y,int z) { return new net.minecraft.world.level.block.state.BlockState(); }
 public net.minecraft.world.level.block.state.BlockState getBlockState(net.minecraft.core.BlockPos pos) { return getBlockState(pos.getX(),pos.getY(),pos.getZ()); }
 public net.minecraft.world.level.block.entity.BlockEntity getBlockEntity(net.minecraft.core.BlockPos pos) { return null; }
 public static net.caffeinemc.mods.sodium.client.world.cloned.ChunkRenderContext prepare(net.minecraft.client.multiplayer.ClientLevel level,net.minecraft.core.SectionPos position,net.caffeinemc.mods.sodium.client.world.cloned.ClonedChunkSectionCache cache) { return null; }
}''',
        'net.caffeinemc.mods.sodium.client.render.util.RenderAsserts': 'public class RenderAsserts { public static void assertOnRenderThread() {} public static void validateCurrentThread() {} }',
        'net.caffeinemc.mods.sodium.client.services.PlatformRuntimeInformation': 'public class PlatformRuntimeInformation { public static PlatformRuntimeInformation getInstance() { return new PlatformRuntimeInformation(); } public boolean isDevelopmentEnvironment() { return false; } }',
        'net.caffeinemc.mods.sodium.client.render.chunk.region.RenderRegion': '''public class RenderRegion {
 public static final int REGION_WIDTH=8,REGION_HEIGHT=4,REGION_LENGTH=8,REGION_WIDTH_M=7,REGION_HEIGHT_M=3,REGION_LENGTH_M=7,REGION_WIDTH_SH=3,REGION_HEIGHT_SH=2,REGION_LENGTH_SH=3,REGION_SIZE=256,SECTION_BUFFER_ESTIMATE=32768;
 private final net.caffeinemc.mods.sodium.client.render.chunk.RenderSection[] sections=new net.caffeinemc.mods.sodium.client.render.chunk.RenderSection[REGION_SIZE];
 private final net.caffeinemc.mods.sodium.client.render.chunk.lists.ChunkRenderList renderList=new net.caffeinemc.mods.sodium.client.render.chunk.lists.ChunkRenderList(this);
 public void removeSection(net.caffeinemc.mods.sodium.client.render.chunk.RenderSection section) { sections[section.getSectionIndex()]=null; }
 public void clearAllCachedBatches() {}
 public void addSection(net.caffeinemc.mods.sodium.client.render.chunk.RenderSection section) { sections[section.getSectionIndex()]=section; }
 public long getCreationTime() { return 0; }
 public static long key(int x,int y,int z) { return net.minecraft.core.SectionPos.asLong(x>>3,y>>2,z>>3); }
 public int getChunkX() { return 0; } public int getChunkY() { return 0; } public int getChunkZ() { return 0; }
 public int getOriginX() { return 0; } public int getOriginY() { return 0; } public int getOriginZ() { return 0; }
 public int getX() { return 0; } public int getY() { return 0; } public int getZ() { return 0; }
 public float getFillFractionInv() { return 256; }
 public net.caffeinemc.mods.sodium.client.render.chunk.RenderSection getSection(int index) { return sections[index]; }
 public net.caffeinemc.mods.sodium.client.render.chunk.lists.ChunkRenderList getRenderList() { return renderList; }
 public net.minecraft.client.renderer.texture.TextureAtlasSprite[] getAnimatedSprites(int index) { return null; }
 public Resources getResources() { return null; }
 public static class Resources { public Arena getGeometryArena() { return new Arena(); } public Arena getIndexArena() { return new Arena(); } }
 public static class Arena { public long getDeviceUsedMemory() { return 0; } public long getDeviceAllocatedMemory() { return 0; } }
 private final int[] flags=new int[REGION_SIZE];
 public int getSectionFlags(int index) { return flags[index]; }
 public void clearSectionRenderState(int index) { flags[index]=0; }
 public void setSectionRenderState(int index,net.caffeinemc.mods.sodium.client.render.chunk.data.BuiltSectionInfo info) { flags[index]=info.flags; }
 public boolean sectionNeedsRender(int index) { return net.caffeinemc.mods.sodium.client.render.chunk.RenderSectionFlags.needsRender(flags[index]); }
}''',
        'net.caffeinemc.mods.sodium.client.util.NativeBuffer': '''public class NativeBuffer {
 private final java.nio.ByteBuffer buffer;
 private boolean freed;
 public NativeBuffer(int size) { buffer=java.nio.ByteBuffer.allocate(size); }
 public long getLength() { if(freed) throw new IllegalStateException("freed buffer"); return buffer.capacity(); }
 public java.nio.ByteBuffer getDirectBuffer() { if(freed) throw new IllegalStateException("freed buffer"); return buffer; }
 public void free() { if(freed) throw new IllegalStateException("double free"); freed=true; }
 public boolean isFreed() { return freed; }
}''',
    }
