package net.minecraft.network.codec;
public class ByteBufCodecs {
    public static final StreamCodec<io.netty.buffer.ByteBuf,Integer> VAR_INT=new StreamCodec<>();
}
