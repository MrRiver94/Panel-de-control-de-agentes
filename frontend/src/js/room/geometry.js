import { CaveFloor, MeadowFloor, RoomCorridor } from '../config.js';

function isRoomPointWalkable(point) {
  const [x, y] = point;
  const inCave = pointInPolygon(point, CaveFloor);
  const inCorridor =
    x >= RoomCorridor.left &&
    x <= RoomCorridor.right &&
    y >= RoomCorridor.top &&
    y <= RoomCorridor.bottom;
  return inCave || inCorridor || pointInPolygon(point, MeadowFloor);
}

function pointInPolygon([x, y], polygon) {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [xi, yi] = polygon[i];
    const [xj, yj] = polygon[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

export { isRoomPointWalkable, pointInPolygon };
