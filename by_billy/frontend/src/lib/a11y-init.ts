export const A11Y_KEY = "medseal-a11y";
export const LANG_KEY = "medseal-lang";

// Runs in <head> before first paint so saved settings don't flash. Keep in sync with applyA11y in a11y.ts.
export const INIT_SCRIPT = `(function(){try{var d=document.documentElement;var l=localStorage.getItem("${LANG_KEY}");if(l)d.lang=l;var s=JSON.parse(localStorage.getItem("${A11Y_KEY}")||"{}");if(s.font)d.dataset.font=String(s.font);if(s.contrast&&s.contrast!=="normal")d.dataset.contrast=s.contrast;if(s.grayscale)d.dataset.gray="1";if(s.spacing)d.dataset.spacing="1";if(s.links)d.dataset.links="1";if(s.reduceMotion)d.dataset.reduceMotion="1";}catch(e){}})();`;
