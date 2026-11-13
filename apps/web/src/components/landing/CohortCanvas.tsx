"use client";

// WebGL dot field for the hero: one point per sample, laid out on a fixed grid. When the stage changes, the
// samples still in the count reflow to the top in layout order and the ones set aside fade out, so the
// shrinking denominator reads as area. Plain WebGL (no library): 1,247 points, one buffer upload per frame,
// and the loop only runs while dots are moving. Colours are read from the design tokens on :root.

import { useEffect, useRef } from "react";
import { cohortGroups, CLAIMED, LUM_A, STAGES, TOTAL, type Group } from "./cohort";

type RGBA = [number, number, number, number];

const FLOATS_PER_DOT = 8; // x, y, r, g, b, a, size, ring
const DURATION_MS = 750;
const STAGGER_MS = 520; // the last row starts this much later than the first

const VERTEX = `
attribute vec2 a_pos;
attribute vec4 a_color;
attribute float a_size;
attribute float a_ring;
uniform vec2 u_res;
uniform float u_dpr;
varying vec4 v_color;
varying float v_ring;
void main() {
  vec2 clip = (a_pos / u_res) * 2.0 - 1.0;
  gl_Position = vec4(clip.x, -clip.y, 0.0, 1.0);
  gl_PointSize = a_size * u_dpr;
  v_color = a_color;
  v_ring = a_ring;
}`;

const FRAGMENT = `
precision mediump float;
uniform vec4 u_ring_color;
varying vec4 v_color;
varying float v_ring;
void main() {
  float d = length(gl_PointCoord - 0.5) * 2.0;
  float edge = fwidth(d);
  float disk = 1.0 - smoothstep(1.0 - edge, 1.0, d);
  // A ringed dot shrinks its fill and draws an outline in the correcting red.
  float fillR = mix(1.0, 0.5, v_ring);
  float fill = 1.0 - smoothstep(fillR - edge, fillR, d);
  float ring = disk * smoothstep(0.72 - edge, 0.72, d) * v_ring;
  // Tint the fill too, so the ring still reads when dots are only a few pixels wide.
  vec4 fillColor = mix(v_color, vec4(u_ring_color.rgb, 0.4), v_ring);
  vec4 color = fillColor * fill + u_ring_color * ring;
  gl_FragColor = vec4(color.rgb * color.a, color.a);
}`;

function readToken(name: string, alpha = 1): RGBA {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const hex = /^#([0-9a-f]{6})$/i.exec(value)?.[1];
  if (!hex) return [0.4, 0.42, 0.46, alpha];
  const n = parseInt(hex, 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255, alpha];
}

function compile(gl: WebGLRenderingContext, type: number, source: string): WebGLShader | null {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  return gl.getShaderParameter(shader, gl.COMPILE_STATUS) ? shader : null;
}

interface Palette {
  plain: RGBA;
  quiet: RGBA;
  pen: RGBA;
  ring: RGBA;
}

interface Layout {
  cols: number;
  pitch: number;
  rows: number;
  offsetX: number;
}

function layoutFor(width: number, height: number): Layout {
  // Try every column count and keep the one with the largest pitch that fits all TOTAL dots in the box.
  let best: Layout = { cols: 1, pitch: 0, rows: TOTAL, offsetX: 0 };
  for (let cols = 1; cols <= TOTAL; cols++) {
    const rows = Math.ceil(TOTAL / cols);
    const pitch = Math.min(width / cols, height / rows);
    if (pitch > best.pitch) best = { cols, pitch, rows, offsetX: (width - cols * pitch) / 2 };
  }
  return best;
}

/** Where each dot should be, and how it should look, at one stage. */
function targetsFor(stageIndex: number, groups: Group[], layout: Layout, palette: Palette, current: Float32Array) {
  const stage = STAGES[stageIndex];
  const keep = new Set(stage.keep);
  const out = new Float32Array(groups.length * FLOATS_PER_DOT);
  const delays = new Float32Array(groups.length);
  const size = layout.pitch * 0.72;
  let rank = 0;

  groups.forEach((group, i) => {
    const o = i * FLOATS_PER_DOT;
    if (keep.has(group)) {
      const col = rank % layout.cols;
      const row = Math.floor(rank / layout.cols);
      out[o] = layout.offsetX + (col + 0.5) * layout.pitch;
      out[o + 1] = (row + 0.5) * layout.pitch;
      const isLumA = group === "lumA";
      const color = stage.highlight ? (isLumA ? palette.pen : palette.quiet) : palette.plain;
      out.set(color, o + 2);
      out[o + 6] = size;
      out[o + 7] = stage.showClaim && rank >= LUM_A && rank < CLAIMED ? 1 : 0;
      delays[i] = (row / layout.rows) * STAGGER_MS;
      rank += 1;
    } else {
      // Set aside: sink a little and fade out from where it is now.
      out[o] = current[o];
      out[o + 1] = current[o + 1] + layout.pitch * 1.5;
      out.set([current[o + 2], current[o + 3], current[o + 4], 0], o + 2);
      out[o + 6] = size * 0.4;
      out[o + 7] = 0;
      delays[i] = (Math.min(current[o + 1] / (layout.rows * layout.pitch), 1) || 0) * STAGGER_MS;
    }
  });
  return { out, delays };
}

const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

/**
 * Draws the cohort at `stage`, animating between stages unless `instant`.
 * Calls `onUnsupported` once if WebGL is not available, so the caller can drop the figure's canvas.
 */
export default function CohortCanvas({
  stage,
  instant,
  onUnsupported,
}: {
  stage: number;
  instant: boolean;
  onUnsupported: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // Imperative handle into the GL state, so a stage change can start a transition without re-creating it.
  const goTo = useRef<((stage: number, instant: boolean) => void) | null>(null);
  const initial = useRef({ stage, instant, onUnsupported });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const gl = canvas.getContext("webgl", { antialias: true, premultipliedAlpha: true, alpha: true });
    const derivatives = gl?.getExtension("OES_standard_derivatives");
    if (!gl || !derivatives) {
      initial.current.onUnsupported();
      return;
    }

    const vs = compile(gl, gl.VERTEX_SHADER, VERTEX);
    const fs = compile(gl, gl.FRAGMENT_SHADER, `#extension GL_OES_standard_derivatives : enable\n${FRAGMENT}`);
    const program = gl.createProgram();
    if (!vs || !fs || !program) {
      initial.current.onUnsupported();
      return;
    }
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      initial.current.onUnsupported();
      return;
    }
    gl.useProgram(program);

    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    const stride = FLOATS_PER_DOT * 4;
    const attr = (name: string, size: number, offset: number) => {
      const loc = gl.getAttribLocation(program, name);
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, size, gl.FLOAT, false, stride, offset * 4);
    };
    attr("a_pos", 2, 0);
    attr("a_color", 4, 2);
    attr("a_size", 1, 6);
    attr("a_ring", 1, 7);
    const uRes = gl.getUniformLocation(program, "u_res");
    const uDpr = gl.getUniformLocation(program, "u_dpr");
    const uRing = gl.getUniformLocation(program, "u_ring_color");
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);

    const palette: Palette = {
      plain: readToken("--color-ink-faint", 0.62),
      quiet: readToken("--color-rule-strong", 0.85),
      pen: readToken("--color-pen"),
      ring: readToken("--color-contradicted"),
    };
    gl.uniform4fv(uRing, palette.ring);

    const groups = cohortGroups();
    const n = groups.length;
    let current = new Float32Array(n * FLOATS_PER_DOT);
    let from = current;
    let to = current;
    let delays = new Float32Array(n);
    let startedAt = 0;
    let frame = 0;
    let layout: Layout = layoutFor(1, 1);
    let stageNow = initial.current.stage;
    let width = 0;
    let height = 0;

    const draw = () => {
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.bufferData(gl.ARRAY_BUFFER, current, gl.DYNAMIC_DRAW);
      gl.drawArrays(gl.POINTS, 0, n);
    };

    const tick = (now: number) => {
      let moving = false;
      for (let i = 0; i < n; i++) {
        const t = Math.min(Math.max((now - startedAt - delays[i]) / DURATION_MS, 0), 1);
        if (t < 1) moving = true;
        const k = ease(t);
        const o = i * FLOATS_PER_DOT;
        for (let j = 0; j < FLOATS_PER_DOT; j++) current[o + j] = from[o + j] + (to[o + j] - from[o + j]) * k;
      }
      draw();
      frame = moving ? requestAnimationFrame(tick) : 0;
    };

    const go = (next: number, snap: boolean) => {
      stageNow = next;
      cancelAnimationFrame(frame);
      const target = targetsFor(next, groups, layout, palette, current);
      if (snap) {
        current = target.out.slice();
        from = to = current;
        draw();
        return;
      }
      from = current.slice();
      to = target.out;
      delays = target.delays;
      startedAt = performance.now();
      frame = requestAnimationFrame(tick);
    };
    goTo.current = go;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      if (rect.width === width && rect.height === height) return;
      width = rect.width;
      height = rect.height;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      gl.uniform2f(uRes, width, height);
      gl.uniform1f(uDpr, dpr);
      layout = layoutFor(width, height);
      // On a resize every dot jumps to its place: re-running the stage keeps set-aside dots invisible.
      current = targetsFor(0, groups, layout, palette, current).out;
      go(stageNow, true);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();

    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
      goTo.current = null;
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
    };
  }, []);

  useEffect(() => {
    goTo.current?.(stage, instant);
  }, [stage, instant]);

  return <canvas ref={canvasRef} aria-hidden="true" className="block h-full w-full" />;
}
