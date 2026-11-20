ipcRenderer.on("sozi-export-command", async (event, {callerId, reply, command}) => {
    try {
        ipcRenderer.sendTo(callerId, reply, await applyPlayerCommand(command));
    }
    catch (error) {
        ipcRenderer.sendTo(callerId, reply, {error: String(error)});
    }
});
