async function applyPlayerCommand(command) {
    const player = sozi.player;
    player.pause();
    if (player.disableMedia) {
        player.disableMedia();
    }
    for (const layer of sozi.presentation.layers) {
        layer.isVisible = true;
    }
    document.querySelector(".sozi-blank-screen").style.display = "none";
    if (command.action === "jump") {
        player.jumpToFrame(command.index);
    }
    else {
        if (command.progress === 0) {
            player.targetFrame = sozi.presentation.frames[command.index];
            for (const camera of sozi.viewport.cameras) {
                const properties = player.targetFrame.layerProperties[camera.layer.index];
                player.setupTransition(camera, properties.transitionTimingFunction, properties.transitionRelativeZoom, properties.transitionPath);
            }
        }
        player.onAnimatorStep(command.progress);
    }
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    return {frame: player.currentFrame.index};
}
