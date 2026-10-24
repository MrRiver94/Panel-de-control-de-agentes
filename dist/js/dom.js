const $ = (selector) => document.querySelector(selector);

const numberFormatter = new Intl.NumberFormat('es-ES');
const formatNumber = (value) => numberFormatter.format(value);

const uppercase = (value) => value.toUpperCase();

export { $, formatNumber, uppercase };
