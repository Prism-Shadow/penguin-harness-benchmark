"use strict";

const {
  THREE,
  assert,
  components,
  globalScope,
  load,
  loadOrEmpty,
  object3D,
  pinningBoundaryMocks,
  requireFunction,
  unexpectedBoundary,
  world
} = require("./common.cjs");

function mediaLoaderFixture() {
  const { harness } = require("./common.cjs");
  const ecs = harness.createEcs();
  const bit = components({
    MediaLoader: { src: "ui32", flags: "ui8", fileId: "ui32", count: "ui8", mediaRef: "eid" },
    MediaLoading: true,
    Networked: true
  });
  return { ecs, bit, testWorld: world() };
}

function mediaLoadingBoundaryMocks() {
  const constants = {
    SHAPE: { BOX: "BOX", HULL: "HULL" },
    FIT: { ALL: "ALL", MANUAL: "MANUAL" }
  };
  return {
    "three-ammo": { CONSTANTS: constants },
    "three-ammo/constants": constants,
    "../prefabs/loading-object": { LoadingObject: unexpectedBoundary("LoadingObject") },
    "../utils/error-texture": { errorTexture: new THREE.Texture() },
    "../utils/load-texture": {
      loadTexture: unexpectedBoundary("loadTexture"),
      loadTextureFromCache: unexpectedBoundary("loadTextureFromCache")
    },
    "./networking": { isPinned: unexpectedBoundary("isPinned") },
    "../utils/jsx-entity": {
      ...require("./common.cjs").mockJsx(),
      renderAsEntity: unexpectedBoundary("renderAsEntity"),
      addObject3DComponent: unexpectedBoundary("addObject3DComponent")
    },
    "../utils/media-utils": {
      MediaType: { MODEL: 1, IMAGE: 2, VIDEO: 4, PDF: 8, HTML: 16, AUDIO: 32 },
      mediaTypeName: unexpectedBoundary("mediaTypeName"),
      resolveMediaInfo: unexpectedBoundary("resolveMediaInfo")
    },
    ...Object.fromEntries(["Image", "Model", "PDF", "Video", "Audio", "Html"].map(kind => [
      `../utils/load-${kind.toLowerCase()}`, { [`load${kind}`]: unexpectedBoundary(`load${kind}`) }
    ]))
  };
}

function loaderFlags(ecs, bit) {
  const mediaLoading = load("src/bit-systems/media-loading.ts", ecs, bit, mediaLoadingBoundaryMocks());
  return mediaLoading.MEDIA_LOADER_FLAGS;
}

function test6371() {
  const { ecs, bit, testWorld } = mediaLoaderFixture();
  bit.MediaLoader.count[7] = 12;
  bit.MediaLoader.mediaRef[7] = 91;
  const flags = { RECENTER: 1, RESIZE: 2, ANIMATE_LOAD: 4, IS_OBJECT_MENU_TARGET: 8 };
  globalScope({ APP: { getSid: value => ({ "media://nested": 91, "file-7": 37 })[value] } }, () => {
    const moduleExports = load("src/inflators/media-loader.ts", ecs, bit, {
      "../bit-systems/media-loading": { MEDIA_LOADER_FLAGS: flags }
    });
    requireFunction(moduleExports, "inflateMediaLoader")(testWorld, 7, {
      src: "media://nested",
      fileId: "file-7",
      recenter: true,
      resize: true,
      animateLoad: true,
      isObjectMenuTarget: true
    });
  });
  assert.equal(ecs.hasComponent(testWorld, bit.MediaLoader, 7), true, "loader component is attached");
  assert.equal(ecs.hasComponent(testWorld, bit.MediaLoading, 7), true, "loading lifecycle starts at inflation");
  assert.equal(bit.MediaLoader.src[7], 91, "source is stored through APP.getSid");
  assert.equal(bit.MediaLoader.fileId[7], 37, "file identity is stored through APP.getSid");
  assert.equal(bit.MediaLoader.count[7], 0, "nested loading counter starts at zero");
  assert.equal(bit.MediaLoader.mediaRef[7], 0, "reused slots do not retain stale content references");
  assert.equal(bit.MediaLoader.flags[7], 15, "all independent lifecycle flags are encoded");
}

function test6387() {
  const { ecs, bit, testWorld } = mediaLoaderFixture();
  globalScope({ APP: { getSid: () => 4 } }, () => {
    const flags = loaderFlags(ecs, bit);
    assert.deepEqual(
      [flags.RECENTER, flags.RESIZE, flags.ANIMATE_LOAD, flags.IS_OBJECT_MENU_TARGET],
      [1, 2, 4, 8],
      "bounded resizing must preserve the persisted loader flag layout"
    );
    const moduleExports = load("src/inflators/media-loader.ts", ecs, bit, {
      "../bit-systems/media-loading": { MEDIA_LOADER_FLAGS: flags }
    });
    moduleExports.inflateMediaLoader(testWorld, 12, {
      src: "media://flags",
      recenter: true,
      resize: true,
      animateLoad: true,
      isObjectMenuTarget: true
    });
  });
  assert.equal(bit.MediaLoader.flags[12], 15, "inflation composes all four compatibility bits");
}

function test6388() {
  const { harness } = require("./common.cjs");
  const ecs = harness.createEcs();
  const bit = components({ MediaLoader: true });
  const testWorld = world();
  ecs.addComponent(testWorld, bit.MediaLoader, 31);
  const moduleExports = load("src/bit-systems/media-loading.ts", ecs, bit, {
    ...mediaLoadingBoundaryMocks(),
    "../utils/coroutine": { crNextFrame: () => ({ frame: true }) }
  });
  const generator = requireFunction(moduleExports, "waitForMediaLoaded")(testWorld, 31);
  assert.deepEqual(generator.next(), { done: false, value: { frame: true } }, "loader presence yields exactly one frame token");
  ecs.removeComponent(testWorld, bit.MediaLoader, 31);
  assert.equal(generator.next().done, true, "removing the loader terminates the wait lifecycle");
}

function test6377() {
  const { harness } = require("./common.cjs");
  const ecs = harness.createEcs();
  const bit = components({
    NetworkedMediaFrame: true,
    Networked: true,
    MediaFrame: {
      mediaType: "ui8",
      bounds: ["f32", 3],
      align: ["ui8", 3],
      guide: "eid",
      flags: "ui8"
    }
  });
  const testWorld = world();
  const addedObjects = [];
  const moduleExports = load("src/inflators/media-frame.js", ecs, bit, {
    "../utils/jsx-entity": { addObject3DComponent: (w, eid, obj) => addedObjects.push({ eid, obj }) },
    "../utils/media-utils": { MediaType: { ALL: 1, ALL_2D: 2, MODEL: 3, IMAGE: 4, VIDEO: 5, PDF: 6 } },
    "../constants": { COLLISION_LAYERS: { MEDIA_FRAMES: 11, INTERACTABLES: 12 } },
    "../camera-layers": { Layers: { CAMERA_LAYER_UI: 3 } },
    "./rigid-body": { Type: { KINEMATIC: "kinematic" }, inflateRigidBody() {} },
    "./physics-shape": { Fit: { MANUAL: "manual" }, Shape: { BOX: "box" }, inflatePhysicsShape() {} }
  });
  requireFunction(moduleExports, "inflateMediaFrame")(testWorld, 44, {
    bounds: { x: 2, y: 3, z: 4 },
    mediaType: "video",
    scaleToBounds: false,
    align: { x: "min", y: "center", z: "max" }
  });
  assert.deepEqual(Array.from(bit.MediaFrame.bounds[44]), [2, 3, 4], "frame stores its three production bounds");
  assert.deepEqual(
    Array.from(bit.MediaFrame.align[44]),
    [moduleExports.AxisAlignType.MIN, moduleExports.AxisAlignType.CENTER, moduleExports.AxisAlignType.MAX],
    "each axis stores an independent alignment mode"
  );
  assert.equal(bit.MediaFrame.flags[44], 0, "scale-to-bounds can be disabled independently");
  assert.equal(addedObjects.length, 1, "inflation registers the visible frame guide");
}

function test6389() {
  const { ecs, bit, testWorld } = mediaLoaderFixture();
  globalScope({ APP: { getSid: () => 88 } }, () => {
    const flags = loaderFlags(ecs, bit);
    assert.equal(flags.MOVE_PARENT_NOT_OBJECT, 16, "parent-preserving mode occupies bit 16");
    const moduleExports = load("src/inflators/media-loader.ts", ecs, bit, {
      "../bit-systems/media-loading": { MEDIA_LOADER_FLAGS: flags }
    });
    moduleExports.inflateMediaLoader(testWorld, 51, {
      src: "media://offset",
      recenter: false,
      resize: false,
      animateLoad: false,
      isObjectMenuTarget: false,
      moveParentNotObject: true
    });
  });
  assert.equal(bit.MediaLoader.flags[51], 16, "inflator selects only the parent-preserving branch");
}

function test6390() {
  const createMessageDatas = new Map();
  globalScope({ APP: { store: { state: { uploadPromotionTokens: [] } } } }, () => {
    const moduleExports = load("src/utils/bit-pinning-helper.ts", {}, {}, {
      ...pinningBoundaryMocks(),
      "../bit-systems/networking": {
        createMessageDatas,
        isNetworkInstantiated: () => false,
        isPinned: () => false
      }
    });
    assert.doesNotThrow(() => moduleExports.canPin({ can: () => true }, 61), "missing create metadata is a handled boundary");
    assert.equal(moduleExports.canPin({ can: () => true }, 61), false, "a non-instantiated entity without metadata is not pinnable");
  });
}

function test6391() {
  const { harness } = require("./common.cjs");
  const ecs = harness.createEcs();
  const bit = components({
    CursorRaycastable: true,
    HandCollisionTarget: true,
    ObjectSpawner: { src: "ui32", flags: "ui8" },
    RemoteHoverTarget: true,
    SingleActionButton: true,
    TogglesHoveredActionSet: true
  });
  const testWorld = world();
  globalScope({ APP: { getSid: value => (value === "media://gravity" ? 99 : 0) } }, () => {
    const moduleExports = load("src/inflators/spawner.ts", ecs, bit, {
      "../bit-systems/object-spawner": { OBJECT_SPAWNER_FLAGS: { APPLY_GRAVITY: 1 } },
      "../constants": { COLLISION_LAYERS: { INTERACTABLES: 3, DEFAULT_SPAWNER: 5 } },
      "./media-loader": { inflateMediaLoader() {} },
      "./rigid-body": { Type: { STATIC: "static" }, inflateRigidBody() {} }
    });
    moduleExports.inflateSpawner(testWorld, 71, { src: "media://gravity", mediaOptions: { applyGravity: true } });
    moduleExports.inflateSpawner(testWorld, 72, { src: "media://no-gravity", mediaOptions: { applyGravity: false } });
  });
  assert.equal(bit.ObjectSpawner.src[71], 99, "spawner source remains interned through APP.getSid");
  assert.equal(bit.ObjectSpawner.flags[71], 1, "gravity uses persisted bit 1");
  assert.equal(bit.ObjectSpawner.flags[72], 0, "disabled gravity does not leak from another spawner");
}

function test6455() {
  const { harness } = require("./common.cjs");
  const ecs = harness.createEcs();
  const bit = components({
    AudioEmitter: true,
    CursorRaycastable: true,
    Deleting: true,
    EntityStateDirty: true,
    Held: true,
    HeldRemoteRight: true,
    HoveredRemoteRight: true,
    Interacted: true,
    MediaInfo: { mediaType: "ui8" },
    MediaLoader: true,
    MediaSnapped: true,
    MediaVideo: { ratio: "f32", flags: "ui8" },
    MediaVideoUpdated: true,
    NetworkedVideo: true,
    ObjectMenuTransform: { targetObjectRef: "eid", flags: "ui8" },
    VideoMenu: {
      videoRef: "eid",
      sliderRef: "eid",
      timeLabelRef: "eid",
      headRef: "eid",
      trackRef: "eid",
      playIndicatorRef: "eid",
      pauseIndicatorRef: "eid",
      snapRef: "eid",
      volUpRef: "eid",
      volDownRef: "eid",
      clearTargetTimer: "f64"
    }
  });
  bit.MediaVideoData = new Map();
  const testWorld = world();
  const menu = 81;
  const videoEid = 82;
  const refs = { slider: 83, time: 84, head: 85, track: 86, play: 87, pause: 88, snap: 89, up: 90, down: 91 };
  ecs.addComponent(testWorld, bit.VideoMenu, menu);
  testWorld.entities.add(videoEid);
  bit.VideoMenu.videoRef[menu] = videoEid;
  bit.VideoMenu.clearTargetTimer[menu] = 1000;
  bit.VideoMenu.sliderRef[menu] = refs.slider;
  bit.VideoMenu.timeLabelRef[menu] = refs.time;
  bit.VideoMenu.headRef[menu] = refs.head;
  bit.VideoMenu.trackRef[menu] = refs.track;
  bit.VideoMenu.playIndicatorRef[menu] = refs.play;
  bit.VideoMenu.pauseIndicatorRef[menu] = refs.pause;
  bit.VideoMenu.snapRef[menu] = refs.snap;
  bit.VideoMenu.volUpRef[menu] = refs.up;
  bit.VideoMenu.volDownRef[menu] = refs.down;
  bit.MediaVideo.ratio[videoEid] = 1;
  bit.MediaVideo.flags[videoEid] = 0;
  bit.MediaInfo.mediaType[videoEid] = 2;
  bit.MediaVideoData.set(videoEid, { paused: true, duration: 120, currentTime: 0, play() {}, pause() {} });

  const menuObj = object3D();
  menuObj.visible = true;
  menuObj.removeFromParent = () => {};
  testWorld.eid2obj.set(menu, menuObj);
  testWorld.eid2obj.set(videoEid, object3D());
  for (const eid of Object.values(refs)) testWorld.eid2obj.set(eid, object3D());
  testWorld.eid2obj.get(refs.time).text = "";

  const app = {
    world: testWorld,
    audios: new Map(),
    gainMultipliers: new Map(),
    isAudioPaused: new Set()
  };
  globalScope({ APP: app }, () => {
    const moduleExports = load("src/bit-systems/video-menu-system.ts", ecs, bit, {
      "../components/media-video": { timeFmt: value => String(value) },
      "../utils/take-ownership": { takeOwnership() {} },
      "../systems/userinput/paths": { paths: { actions: { cursor: { right: { pose: "pose" } } } } },
      "../utils/three-utils": { isFacingCamera: () => true },
      "./audio-emitter-system": { Emitter2Audio: new Map() },
      "../utils/bit-utils": {
        findAncestorWithComponent: () => 0,
        findChildWithComponent: () => 0,
        hasAnyComponent: () => false
      },
      "../inflators/object-menu-transform": { ObjectMenuTransformFlags: { Enabled: 1 } },
      "../utils/media-utils": { MediaType: { VIDEO: 2 } },
      "../prefabs/video-menu": { VolumeControlsMaterial: { uniforms: { volume: { value: 0 } } } },
      "../update-audio-settings": { updateAudioSettings() {} },
      "../inflators/video": { VIDEO_FLAGS: { CONTROLS: 1 } },
      "three/src/math/MathUtils": {
        clamp: THREE.MathUtils.clamp,
        mapLinear: THREE.MathUtils.mapLinear
      }
    });
    moduleExports.videoMenuSystem(testWorld, { get: () => null }, false);
  });
  assert.equal(menuObj.visible, false, "an audio/video target without the controls flag keeps its menu hidden");
}

const tests = {
  6371: test6371,
  6387: test6387,
  6388: test6388,
  6377: test6377,
  6389: test6389,
  6390: test6390,
  6391: test6391,
  6455: test6455
};

module.exports = { tests, mediaLoadingBoundaryMocks };
