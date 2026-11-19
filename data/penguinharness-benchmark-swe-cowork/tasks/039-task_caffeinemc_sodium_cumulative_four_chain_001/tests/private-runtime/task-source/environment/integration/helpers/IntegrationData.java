package net.caffeinemc.mods.sodium.client.render.chunk.translucent_sorting.data;

import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import net.minecraft.core.SectionPos;
import org.joml.Vector3d;

public class IntegrationData extends DynamicData {
    public final AtomicInteger executions = new AtomicInteger();
    public final List<DynamicSorter> sorters = new CopyOnWriteArrayList<>();
    public final List<net.caffeinemc.mods.sodium.client.util.NativeBuffer> buffers = new CopyOnWriteArrayList<>();
    public final CountDownLatch started = new CountDownLatch(1);
    public final CountDownLatch release;

    public IntegrationData(SectionPos position, boolean blocked) {
        super(position, 2, null, new Vector3d());
        this.release = new CountDownLatch(blocked ? 1 : 0);
    }

    @Override
    public DynamicSorter getSorter() {
        var sorter = new DynamicSorter(2, this) {
            @Override
            void writeSort(CombinedCameraPos camera, boolean initial) {
                buffers.add(getIndexBuffer());
                executions.incrementAndGet();
                started.countDown();
                try {
                    if (!release.await(5, TimeUnit.SECONDS)) throw new AssertionError("worker barrier timed out");
                } catch (InterruptedException failure) {
                    throw new AssertionError(failure);
                }
            }
        };
        sorters.add(sorter);
        return sorter;
    }
}
