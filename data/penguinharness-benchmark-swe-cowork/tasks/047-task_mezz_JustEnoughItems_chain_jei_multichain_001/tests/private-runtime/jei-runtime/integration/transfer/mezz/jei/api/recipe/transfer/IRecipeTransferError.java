package mezz.jei.api.recipe.transfer;
public interface IRecipeTransferError {
    Type getType();
    class Type {
        public boolean allowsTransfer;
    }
}
