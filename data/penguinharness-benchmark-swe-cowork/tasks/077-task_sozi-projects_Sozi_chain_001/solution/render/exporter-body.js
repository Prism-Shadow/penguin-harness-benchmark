let requestSequence = 0;

function requestPlayer(window, command) {
    const reply = `sozi-export-reply-${window.webContents.id}-${++requestSequence}`;
    return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
            ipcRenderer.removeListener(reply, onReply);
            reject(new Error("Player command timed out"));
        }, 15000);
        function onReply(event, result) {
            clearTimeout(timer);
            if (result.error) {
                reject(new Error(result.error));
            }
            else {
                resolve(result);
            }
        }
        ipcRenderer.once(reply, onReply);
        try {
            window.webContents.send("sozi-export-command", {
                callerId: remote.getCurrentWindow().webContents.id, reply, command
            });
        }
        catch (error) {
            clearTimeout(timer);
            ipcRenderer.removeListener(reply, onReply);
            reject(error);
        }
    });
}

async function withPlayer(htmlFileName, geometry, visible, operation) {
    if (typeof htmlFileName !== "string" || !htmlFileName.length) {
        throw new Error("A saved HTML path is required");
    }
    const window = new remote.BrowserWindow({
        width: geometry.width, height: geometry.height, frame: false, show: visible,
        webPreferences: {
            preload: path.join(__dirname, "exporter-preload.js"),
            offscreen: !visible, backgroundThrottling: false, contextIsolation: false, nodeIntegration: false
        }
    });
    try {
        await window.loadURL(require("url").pathToFileURL(htmlFileName).href);
        return await operation(window);
    }
    finally {
        if (!window.isDestroyed()) {
            if (window.webContents.debugger.isAttached()) {
                window.webContents.debugger.detach();
            }
            window.destroy();
        }
    }
}

async function screenshot(window, fileName) {
    const image = await window.webContents.debugger.sendCommand("Page.captureScreenshot", {format: "png"});
    await fs.promises.writeFile(fileName, Buffer.from(image.data, "base64"));
}

function selectedFrames(presentation, include, exclude) {
    const selection = markFramesFromLists(presentation, include, exclude);
    return presentation.frames.map((frame, index) => index).filter(index => selection[index]);
}

async function withTemporaryDirectory(operation) {
    const temporary = tmp.dirSync({unsafeCleanup: true});
    try {
        return await operation(temporary.name);
    }
    finally {
        // Both tmp generations expose a one-argument callback, but dirSync's
        // cleanup in newer versions is synchronous and ignores that argument.
        await new Promise((resolve, reject) => {
            temporary.removeCallback(error => error ? reject(error) : resolve());
            if (!fs.existsSync(temporary.name)) {
                resolve();
            }
        });
    }
}

export async function exportToPDF(presentation, htmlFileName) {
    const geometry = pdfPageGeometry[presentation.exportToPDFPageSize];
    if (!geometry) {
        throw new Error("Unsupported PDF page size");
    }
    const landscape = presentation.exportToPDFPageOrientation === "landscape";
    const page = landscape ? geometry : {width: geometry.height, height: geometry.width};
    // Scale the viewport uniformly to the public bounds; physical paper stays unchanged.
    const scale = Math.min(2000 / page.width, 1600 / page.height,
                           Math.max(1, 700 / page.width));
    const size = {width: Math.round(page.width * scale), height: Math.round(page.height * scale)};
    const indices = selectedFrames(presentation, presentation.exportToPDFInclude, presentation.exportToPDFExclude);
    if (!indices.length) {
        throw new Error("No frames selected for export");
    }
    await withPlayer(htmlFileName, size, false, async window => {
        const document = await PDFDocument.create();
        for (const index of indices) {
            await requestPlayer(window, {action: "jump", index});
            const data = await window.webContents.printToPDF({
                pageSize: presentation.exportToPDFPageSize, landscape, marginsType: 2, printBackground: true
            });
            const captured = await PDFDocument.load(data);
            const pages = await document.copyPages(captured, [0]);
            document.addPage(pages[0]);
        }
        await fs.promises.writeFile(htmlFileName.replace(/html$/, "pdf"), await document.save());
    });
}

export async function exportToPPTX(presentation, htmlFileName) {
    const ratio = pptxSlideGeometry[presentation.exportToPPTXSlideSize];
    if (!ratio) {
        throw new Error("Unsupported PPTX slide size");
    }
    const geometry = {width: Math.round(ratio.width * pptxSlideHeightPx / ratio.height), height: pptxSlideHeightPx};
    const indices = selectedFrames(presentation, presentation.exportToPPTXInclude, presentation.exportToPPTXExclude);
    if (!indices.length) {
        throw new Error("No frames selected for export");
    }
    await withPlayer(htmlFileName, geometry, true, window =>
        withTemporaryDirectory(async directory => {
            window.webContents.debugger.attach("1.2");
            const document = officegen("pptx");
            document.setSlideSize(geometry.width, geometry.height, presentation.exportToPPTXSlideSize);
            for (const index of indices) {
                await requestPlayer(window, {action: "jump", index});
                const fileName = path.join(directory, `${index}.png`);
                await screenshot(window, fileName);
                document.makeNewSlide().addImage(fileName, {x: 0, y: 0, cx: "100%", cy: "100%"});
            }
            await new Promise((resolve, reject) => {
                const output = fs.createWriteStream(htmlFileName.replace(/html$/, "pptx"));
                const fail = error => { output.destroy(); reject(error); };
                output.once("error", fail);
                document.once("error", fail);
                output.once("finish", resolve);
                document.generate(output);
            });
        })
    );
}

export async function exportToVideo(presentation, htmlFileName) {
    const geometry = {width: presentation.exportToVideoWidth, height: presentation.exportToVideoHeight};
    const rate = presentation.exportToVideoFrameRate;
    if (![rate, geometry.width, geometry.height].every(value => Number.isFinite(value) && value > 0) || !presentation.frames.length) {
        throw new Error("Invalid video geometry, frame rate or empty presentation");
    }
    await withPlayer(htmlFileName, geometry, false, async window => {
        const sequence = presentation.exportToVideoFormat === "png";
        const capture = async directory => {
            if (sequence) {
                await fs.promises.mkdir(directory, {recursive: true});
            }
            window.webContents.debugger.attach("1.2");
            let imageIndex = 0;
            const step = 1000 / rate;
            for (let index = 0; index < presentation.frames.length; index++) {
                const frame = presentation.frames[index];
                await requestPlayer(window, {action: "jump", index});
                let firstImage;
                for (let time = 0; time < frame.timeoutMs; time += step) {
                    const image = path.join(directory, `img${imageIndex++}.png`);
                    if (firstImage) {
                        await fs.promises.copyFile(firstImage, image);
                    }
                    else {
                        await screenshot(window, image);
                        firstImage = image;
                    }
                }
                if (index + 1 < presentation.frames.length || frame.timeoutEnable) {
                    const target = (index + 1) % presentation.frames.length;
                    const duration = presentation.frames[target].transitionDurationMs;
                    for (let time = 0; time < duration; time += step) {
                        await requestPlayer(window, {action: "step", index: target, progress: time / duration});
                        await screenshot(window, path.join(directory, `img${imageIndex++}.png`));
                    }
                }
            }
            if (!sequence) {
                const args = ["-r", rate, "-f", "image2", "-i", path.join(directory, "img%d.png"),
                    "-b:v", presentation.exportToVideoBitRate, "-y", htmlFileName.replace(/html$/, presentation.exportToVideoFormat)];
                let result = spawnSync("ffmpeg", args, {stdio: "inherit"});
                if (result.error) {
                    result = spawnSync(path.join(process.resourcesPath, process.platform === "win32" ? "ffmpeg.exe" : "ffmpeg"), args, {stdio: "inherit"});
                }
                if (result.error || result.status !== 0) {
                    throw result.error || new Error(`FFmpeg exited ${result.status}`);
                }
            }
        };
        if (sequence) {
            await capture(htmlFileName.replace(/(?:\.sozi)?\.html$/, "-sozi-export"));
        }
        else {
            await withTemporaryDirectory(capture);
        }
    });
}
