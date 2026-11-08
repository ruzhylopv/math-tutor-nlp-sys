// The graph, in the style of a GitHub Actions run. The SVG is built once per graph shape; after
// that only classes and text change, so the spinner keeps turning. Model text uses textContent.
const SVG = "http://www.w3.org/2000/svg";
const WIDTH = 360;
const CARD = { w: 106, h: 42 };
const DOT = { w: 62, h: 24 };
const COLUMN = 122;
const GAP = 34;
const GROUP_PAD = { x: 9, top: 24, bottom: 10 };
const MAX_LABEL = 13;
const STATUS_TEXT = { idle: "not reached", running: "running", done: "done", failed: "failed" };

function svg(tag, attrs = {}, parent = null) {
  const el = document.createElementNS(SVG, tag);
  for (const [name, value] of Object.entries(attrs)) el.setAttribute(name, value);
  if (parent) parent.append(el);
  return el;
}

function html(tag, className, text, parent) {
  const el = document.createElement(tag);
  el.className = className;
  if (text !== undefined) el.textContent = text;
  parent.append(el);
  return el;
}

function seconds(value) {
  if (value < 60) return `${value.toFixed(1)}s`;
  return `${Math.floor(value / 60)}m ${Math.round(value % 60)}s`;
}

// Where each node goes: rows from `rank` (a row is as tall as its tallest node), columns from `slot`.
function place(view) {
  const size = (node) => (node.terminal ? DOT : CARD);
  const ranks = [...new Set(view.nodes.map((n) => n.rank))].sort((a, b) => a - b);
  const boxes = new Map();
  let y = 6;
  for (const rank of ranks) {
    const row = view.nodes.filter((n) => n.rank === rank);
    const groupStarts = view.groups.some((g) => row.some((n) => n.group === g.id) &&
      !view.nodes.some((n) => n.group === g.id && n.rank < rank));
    if (groupStarts) y += GROUP_PAD.top - 12;
    const height = Math.max(...row.map((n) => size(n).h));
    for (const node of row) {
      const { w, h } = size(node);
      const x = WIDTH / 2 + node.slot * COLUMN - w / 2;
      boxes.set(node.id, { x, y: y + (height - h) / 2, w, h });
    }
    y += height + GAP;
  }
  const groups = new Map();
  for (const group of view.groups) {
    const inner = view.nodes.filter((n) => n.group === group.id).map((n) => boxes.get(n.id));
    const x = Math.min(...inner.map((b) => b.x)) - GROUP_PAD.x;
    const top = Math.min(...inner.map((b) => b.y)) - GROUP_PAD.top;
    const right = Math.max(...inner.map((b) => b.x + b.w)) + GROUP_PAD.x;
    const bottom = Math.max(...inner.map((b) => b.y + b.h)) + GROUP_PAD.bottom;
    groups.set(group.id, { x, y: top, w: right - x, h: bottom - top });
  }
  const height = Math.max(...[...boxes.values(), ...groups.values()].map((b) => b.y + b.h)) + 6;
  return { boxes, groups, height };
}

function edgePath(edge, layout, groupOf) {
  const from = layout.boxes.get(edge.source);
  const to = layout.boxes.get(edge.target);
  if (!edge.back) {
    const [x1, y1, x2, y2] = [from.x + from.w / 2, from.y + from.h, to.x + to.w / 2, to.y];
    const bend = (y2 - y1) / 2;
    return `M${x1} ${y1} C${x1} ${y1 + bend},${x2} ${y2 - bend},${x2} ${y2}`;
  }
  // A loop back leaves from the top of its node (or of its group) and enters the target's side.
  const box = layout.groups.get(groupOf.get(edge.source)) ?? from;
  const onLeft = box.x + box.w / 2 < to.x + to.w / 2;
  const x1 = onLeft ? box.x + 16 : box.x + box.w - 16;
  const [x2, y2] = [onLeft ? to.x : to.x + to.w, to.y + to.h / 2];
  return `M${x1} ${box.y} C${x1} ${y2},${x1} ${y2},${x2} ${y2}`;
}

function drawIcon(group, status) {
  group.replaceChildren();
  group.setAttribute("class", `icon icon-${status}`);
  if (status === "running") {
    svg("circle", { r: 6.5, class: "ring-track" }, group);
    svg("path", { d: "M0 -6.5 A6.5 6.5 0 0 1 6.5 0", class: "ring-head" }, group);
  } else if (status === "done") {
    svg("circle", { r: 7.5, class: "badge" }, group);
    svg("path", { d: "M-3.4 0.2 L-1 2.7 L3.5 -2.4", class: "mark" }, group);
  } else if (status === "failed") {
    svg("circle", { r: 7.5, class: "badge" }, group);
    svg("path", { d: "M-2.7 -2.7 L2.7 2.7 M2.7 -2.7 L-2.7 2.7", class: "mark" }, group);
  } else {
    svg("circle", { r: 6.5, class: "idle-ring" }, group);
  }
}

function buildNode(node, box, parent, select) {
  const group = svg("g", {
    transform: `translate(${box.x} ${box.y})`,
    tabindex: 0,
    role: "button",
  }, parent);
  group.dataset.id = node.id;
  group.addEventListener("click", () => select(node.id));
  group.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      select(node.id);
    }
  });
  svg("rect", { width: box.w, height: box.h, rx: node.terminal ? box.h / 2 : 8, class: "card" }, group);
  const short = node.label.length > MAX_LABEL ? `${node.label.slice(0, MAX_LABEL - 1)}…` : node.label;
  if (node.terminal) {
    const place = svg("g", { transform: `translate(12 ${box.h / 2}) scale(0.72)` }, group);
    const name = svg("text", { x: 23, y: box.h / 2 + 4, class: "name" }, group);
    name.textContent = short;
    return { group, icon: svg("g", {}, place) };
  }
  // The icon is one level inside its positioned parent, so spinning it turns it on the spot.
  const icon = svg("g", {}, svg("g", { transform: `translate(15 ${box.h / 2})` }, group));
  const name = svg("text", { x: 29, y: 17, class: "name" }, group);
  name.textContent = short;
  const title = svg("title", {}, group);
  title.textContent = node.label;
  const time = svg("text", { x: 29, y: 32, class: "time" }, group);
  const count = svg("text", { x: box.w - 8, y: 32, class: "count" }, group);
  return { group, icon, name, time, count, middle: box.h / 2 + 4 };
}

function build(root, view, select) {
  root.replaceChildren();
  const layout = place(view);
  const canvas = svg("svg", {
    viewBox: `0 0 ${WIDTH} ${layout.height}`,
    role: "group",
    "aria-label": "Tutor graph",
  }, root);
  const defs = svg("defs", {}, canvas);
  const marker = svg("marker", {
    id: "arrow", viewBox: "0 0 8 8", refX: 7, refY: 4, markerWidth: 6, markerHeight: 6, orient: "auto",
  }, defs);
  svg("path", { d: "M0 0.5 L7 4 L0 7.5 Z", fill: "context-stroke" }, marker);
  const groupOf = new Map(view.nodes.map((n) => [n.id, n.group]));
  const parts = { nodes: new Map(), edges: new Map(), groups: new Map() };
  for (const group of view.groups) {
    const box = layout.groups.get(group.id);
    const rect = svg("rect", { x: box.x, y: box.y, width: box.w, height: box.h, rx: 10 }, canvas);
    const label = svg("text", { x: box.x + 10, y: box.y + 15, class: "group-label" }, canvas);
    label.textContent = group.id;
    parts.groups.set(group.id, rect);
  }
  for (const edge of view.edges) {
    const path = svg("path", { d: edgePath(edge, layout, groupOf) }, canvas);
    if (edge.back) path.setAttribute("marker-end", "url(#arrow)");
    parts.edges.set(`${edge.source}>${edge.target}`, path);
  }
  for (const node of view.nodes) {
    parts.nodes.set(node.id, buildNode(node, layout.boxes.get(node.id), canvas, select));
  }
  const detail = html("div", "detail", undefined, root);
  return { parts, detail };
}

function paintNode(node, part, selected) {
  part.group.setAttribute(
    "class",
    `node status-${node.status}${node.id === selected ? " selected" : ""}`,
  );
  part.group.setAttribute("aria-pressed", String(node.id === selected));
  part.group.setAttribute("aria-label", `${node.label}: ${STATUS_TEXT[node.status]}`);
  if (part.status !== node.status) {
    drawIcon(part.icon, node.status);
    part.status = node.status;
  }
  if (part.time) {
    part.time.textContent = node.status === "running"
      ? "running…"
      : node.runs.length ? seconds(node.seconds) : "";
    part.name.setAttribute("y", part.time.textContent ? 17 : part.middle);
  }
  if (part.count) part.count.textContent = node.count > 1 ? `×${node.count}` : "";
}

function paintDetail(detail, view, selected) {
  detail.replaceChildren();
  const node = view.nodes.find((n) => n.id === selected);
  if (!node) {
    html("div", "detail-hint", "Click a node to see what it did in this turn.", detail);
    return;
  }
  const header = html("div", "detail-header", undefined, detail);
  html("span", "detail-name", node.label, header);
  html("span", `detail-status text-${node.status}`, STATUS_TEXT[node.status], header);
  if (node.runs.length === 0) {
    const empty = node.status === "running" ? "Still working." : "Nothing recorded in this turn.";
    html("div", "detail-hint", empty, detail);
    return;
  }
  node.runs.forEach((run, index) => {
    const block = html("div", "run", undefined, detail);
    const mark = run.failed ? "✗" : "✓";
    const title = node.runs.length > 1 ? `${mark} run ${index + 1}` : mark;
    html("div", "run-title", `${title} · ${seconds(run.seconds)}`, block);
    for (const line of run.details) html("div", "run-line", line, block);
  });
}

function paint(ui, view, store) {
  for (const node of view.nodes) paintNode(node, ui.parts.nodes.get(node.id), store.selected);
  for (const edge of view.edges) {
    const kind = `edge${edge.taken ? " taken" : ""}${edge.conditional ? " conditional" : ""}${edge.back ? " back" : ""}`;
    ui.parts.edges.get(`${edge.source}>${edge.target}`).setAttribute("class", kind);
  }
  for (const group of view.groups) {
    ui.parts.groups.get(group.id).setAttribute("class", `group status-${group.status}`);
  }
  paintDetail(ui.detail, view, store.selected);
}

function shape(view) {
  return JSON.stringify([view.nodes.map((n) => [n.id, n.rank, n.slot]), view.edges.map((e) => [e.source, e.target])]);
}

export default function ({ data, parentElement }) {
  const store = (window.__tutorTrace ??= { view: null, selected: null });
  if (!store.view || data.stamp >= store.view.stamp) store.view = data;
  const root = parentElement.querySelector("#root");

  const redraw = () => {
    const view = store.view;
    const key = shape(view);
    if (root.__ui?.key !== key) {
      const select = (id) => {
        store.selected = store.selected === id ? null : id;
        paint(root.__ui, store.view, store);
      };
      root.__ui = { key, ...build(root, view, select) };
    }
    paint(root.__ui, view, store);
  };

  window.removeEventListener("tutor-trace", store.listener);
  store.listener = redraw;
  window.addEventListener("tutor-trace", redraw);
  redraw();
}
