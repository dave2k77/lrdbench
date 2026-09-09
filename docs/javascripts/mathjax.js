// Arithmatex protects TeX from Markdown; MathJax typesets those wrappers on page load.
// navigation.instant is deliberately disabled, so each navigation has a fresh startup.
window.MathJax = {
  tex: {
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex"
  }
};
