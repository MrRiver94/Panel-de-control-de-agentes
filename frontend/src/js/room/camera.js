import { State } from '../state.js';
import { $ } from '../dom.js';

function roomCameraPose(zoom, x, y) {
  const scale = Math.max(1, Math.min(2.4, Number.isFinite(zoom) ? zoom : 1));
  // Offsets are camera coordinates, expressed as a percentage of the viewport.
  const limit = (scale - 1) * 50;
  const clamp = (value) =>
    Math.max(-limit, Math.min(limit, Number.isFinite(value) ? value : 0)) || 0;
  return { zoom: scale, x: clamp(x), y: clamp(y), limit };
}

function applyRoomCamera(world) {
  const pose = roomCameraPose(State.roomZoom, State.roomPan, State.roomPanY);
  State.roomZoom = pose.zoom;
  State.roomPan = pose.x;
  State.roomPanY = pose.y;
  world.style.setProperty('--room-zoom', pose.zoom);
  // Looking right moves the world left; the HUD stays outside this transform.
  world.style.setProperty('--room-pan-x', `${-pose.x}%`);
  world.style.setProperty('--room-pan-y', `${-pose.y}%`);
  const disabled = {
    out: pose.zoom <= 1,
    in: pose.zoom >= 2.4,
    left: pose.x <= -pose.limit,
    right: pose.x >= pose.limit,
    up: pose.y <= -pose.limit,
    down: pose.y >= pose.limit,
  };
  document.querySelectorAll('[data-camera]').forEach((button) => {
    button.disabled = Boolean(disabled[button.dataset.camera]);
  });
}

function controlRoomCamera(command) {
  if (command === 'in') State.roomZoom = +(State.roomZoom + 0.2).toFixed(2);
  if (command === 'out') State.roomZoom = +(State.roomZoom - 0.2).toFixed(2);
  if (command === 'left') State.roomPan -= 5;
  if (command === 'right') State.roomPan += 5;
  if (command === 'up') State.roomPanY -= 5;
  if (command === 'down') State.roomPanY += 5;
  if (command === 'center') {
    State.roomZoom = 1;
    State.roomPan = 0;
    State.roomPanY = 0;
  }
  const pose = roomCameraPose(State.roomZoom, State.roomPan, State.roomPanY);
  State.roomZoom = pose.zoom;
  State.roomPan = pose.x;
  State.roomPanY = pose.y;
  applyRoomCamera($('#roomWorld'));
}

export { roomCameraPose, applyRoomCamera, controlRoomCamera };
