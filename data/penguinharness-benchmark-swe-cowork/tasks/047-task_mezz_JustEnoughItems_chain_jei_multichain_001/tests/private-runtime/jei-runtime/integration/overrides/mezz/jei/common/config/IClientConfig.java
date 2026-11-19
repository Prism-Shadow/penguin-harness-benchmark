package mezz.jei.common.config;
public interface IClientConfig {
    record Value(boolean getValue){
    }
    default Value recipeSlotCyclingEnabled(){
        return new Value(true);
    }
    default Value hideSingleTagContentTooltipEnabled(){
        return new Value(false);
    }
    default Value tagContentTooltipEnabled(){
        return new Value(false);
    }
}
