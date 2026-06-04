export interface StarNode {
  id: string;
  x: number;
  y: number;
  file: string;
  room: string;
  snippet: string;
}

export interface TransformState {
  x: number;
  y: number;
  scale: number;
}

export interface SeededStar {
  x: number;
  y: number;
  size: number;
  opacityMult: number;
}
