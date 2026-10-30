export type ThemePreference = "system" | "light" | "dark";
export const THEME_KEY = "midwestball-theme-preference-v1";
export function parseThemePreference(raw: string | null): ThemePreference {
  return raw === "light" || raw === "dark" ? raw : "system";
}
export function resolveTheme(preference: ThemePreference, light: boolean, dark: boolean): "light" | "dark" {
  return preference === "system" ? light && !dark ? "light" : "dark" : preference;
}
/** Executed before paint; CSS remains authoritative in system mode. */
export const THEME_BOOTSTRAP = `(function(){function apply(){try{var v=localStorage.getItem('${THEME_KEY}');if(v==='light'||v==='dark')document.documentElement.dataset.theme=v;else delete document.documentElement.dataset.theme;}catch(e){delete document.documentElement.dataset.theme;}}apply();window.addEventListener('storage',function(e){if(e.key==='${THEME_KEY}'||e.key===null)apply();});})();`;
