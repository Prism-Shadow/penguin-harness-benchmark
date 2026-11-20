package net.minecraft.network.codec;
public class StreamCodec<B,T> {
    public interface Three<A,C,D,R>{
        R apply(A a,C c,D d);
    }
    public static <B,A,C,T> StreamCodec<B,T> composite(StreamCodec<B,A>a,java.util.function.Function<T,A> fa,StreamCodec<B,C> c,java.util.function.Function<T,C> fc,java.util.function.BiFunction<A,C,T> make){
        return new StreamCodec<>();
    }
    public static <B,A,C,D,T> StreamCodec<B,T> composite(StreamCodec<B,A>a,java.util.function.Function<T,A> fa,StreamCodec<B,C> c,java.util.function.Function<T,C> fc,StreamCodec<B,D>d,java.util.function.Function<T,D> fd,Three<A,C,D,T> make){
        return new StreamCodec<>();
    }
}
