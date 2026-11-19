package mezz.jei.common.input;
public class IInternalKeyMappings {
    public static class Key {
        public boolean isDown(){
            return false;
        }
        public boolean isUnbound(){
            return false;
        }
    }
    public Key getToggleOverlay(){
        return new Key();
    }
    public Key getPauseRecipeCycling(){
        return new Key();
    }
    public Key getLeftClick(){
        return new Key();
    }
    public Key getCloseRecipeGui(){
        return new Key();
    }
    public Key getRecipeBack(){
        return new Key();
    }
    public Key getRecipeForward(){
        return new Key();
    }
    public Key getNextCategory(){
        return new Key();
    }
    public Key getPreviousCategory(){
        return new Key();
    }
    public Key getNextRecipePage(){
        return new Key();
    }
    public Key getPreviousRecipePage(){
        return new Key();
    }
}
