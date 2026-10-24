const $ = (selector) => document.querySelector(selector);

const numberFormatter = new Intl.NumberFormat('es-ES');
const formatNumber = (value) => numberFormatter.format(value);

const uppercase = (value) => value.toUpperCase();
const escapeHtml = (value) =>
  String(value ?? '').replace(
    /[&<>"']/g,
    (character) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character],
  );

export { $, formatNumber, uppercase, escapeHtml };
