const STOPS: [number, [number, number, number]][] = [
  [0, [254, 226, 226]],
  [0.25, [255, 237, 213]],
  [0.5, [254, 249, 195]],
  [0.75, [217, 249, 157]],
  [1.0, [209, 250, 229]],
];

export function scoreToColor(value: number): string {
  value = Math.max(0, Math.min(1, value));
  let lo = STOPS[0];
  let hi = STOPS[STOPS.length - 1];
  for (let i = 0; i < STOPS.length - 1; i++) {
    if (value <= STOPS[i + 1][0]) {
      lo = STOPS[i];
      hi = STOPS[i + 1];
      break;
    }
  }
  const t = hi[0] - lo[0] === 0 ? 0 : (value - lo[0]) / (hi[0] - lo[0]);
  const [r, g, b] = [0, 1, 2].map((c) => Math.round(lo[1][c] + t * (hi[1][c] - lo[1][c])));
  return `rgb(${r},${g},${b})`;
}
