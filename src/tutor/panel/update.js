// Hands a newer view to the mounted graph (see __init__.py for why this is a separate component).
export default function ({ data }) {
  const store = (window.__tutorTrace ??= { view: null, selected: null });
  if (!store.view || data.stamp >= store.view.stamp) {
    store.view = data;
    window.dispatchEvent(new CustomEvent("tutor-trace"));
  }
}
