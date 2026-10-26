const $ = (selector) => document.querySelector(selector);
const textElement = (tag, text) => {
  const element = document.createElement(tag);
  element.textContent = text;
  return element;
};

const numberFormatter = new Intl.NumberFormat('es-ES');
const formatNumber = (value) => numberFormatter.format(value);

const uppercase = (value) => value.toUpperCase();
const escapeHtml = (value) =>
  String(value ?? '').replace(
    /[&<>"']/g,
    (character) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character],
  );

export { $, textElement, formatNumber, uppercase, escapeHtml };
