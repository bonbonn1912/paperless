import { Injectable, signal, effect } from '@angular/core';

export type Theme = 'light' | 'dark' | 'system';
export type ToneId = 'papier' | 'neutral' | 'kuehl' | 'tinte';

export interface AccentPreset {
  id: string;
  label: string;
  value: string;
}

export interface SurfaceTone {
  id: ToneId;
  label: string;
  description: string;
  light: ToneColors;
  dark: ToneColors;
}

export interface ToneColors {
  bg: string;
  surface: string;
  surfaceSubtle: string;
  surfaceHover: string;
  sidebar: string;
  border: string;
}

export const DEFAULT_ACCENT = '#285941';
const STORAGE_THEME = 'paperless_theme';
const STORAGE_TONE = 'paperless_tone';
const STORAGE_ACCENT = 'paperless_accent';
const STORAGE_VARS = 'paperless_vars';

export const ACCENT_PRESETS: AccentPreset[] = [
  { id: 'wald', label: 'Wald', value: '#285941' },
  { id: 'ozean', label: 'Ozean', value: '#0f6b8a' },
  { id: 'blau', label: 'Blau', value: '#0071e3' },
  { id: 'indigo', label: 'Indigo', value: '#5b5bd6' },
  { id: 'beere', label: 'Beere', value: '#a33a6b' },
  { id: 'terrakotta', label: 'Terrakotta', value: '#b45309' },
  { id: 'graphit', label: 'Graphit', value: '#48484a' }
];

export const SURFACE_TONES: SurfaceTone[] = [
  {
    id: 'papier',
    label: 'Papier',
    description: 'Warm und natürlich',
    light: { bg: '#f4f4f1', surface: '#ffffff', surfaceSubtle: '#f0f0ec', surfaceHover: '#e9e9e4', sidebar: '#efefeb', border: '#e3e3de' },
    dark: { bg: '#171716', surface: '#1f1f1e', surfaceSubtle: '#262625', surfaceHover: '#302f2c', sidebar: '#1b1b1a', border: '#343430' }
  },
  {
    id: 'neutral',
    label: 'Neutral',
    description: 'Ruhiges Grau',
    light: { bg: '#f5f5f5', surface: '#ffffff', surfaceSubtle: '#f1f1f1', surfaceHover: '#eaeaea', sidebar: '#f0f0f0', border: '#e4e4e4' },
    dark: { bg: '#171719', surface: '#1f1f21', surfaceSubtle: '#26262a', surfaceHover: '#303034', sidebar: '#1b1b1d', border: '#343438' }
  },
  {
    id: 'kuehl',
    label: 'Kühl',
    description: 'Leicht ins Blaugraue',
    light: { bg: '#f3f5f8', surface: '#ffffff', surfaceSubtle: '#eef1f5', surfaceHover: '#e7ebf0', sidebar: '#edf0f4', border: '#dfe4ea' },
    dark: { bg: '#15181c', surface: '#1e2227', surfaceSubtle: '#252a30', surfaceHover: '#2f353c', sidebar: '#1a1e22', border: '#323840' }
  },
  {
    id: 'tinte',
    label: 'Tinte',
    description: 'Mehr Kontrast',
    light: { bg: '#ededea', surface: '#fafaf9', surfaceSubtle: '#e7e7e4', surfaceHover: '#dfdfdb', sidebar: '#e5e5e2', border: '#d6d6d2' },
    dark: { bg: '#111110', surface: '#181817', surfaceSubtle: '#1f1f1e', surfaceHover: '#292928', sidebar: '#141413', border: '#2d2d2b' }
  }
];

interface Rgb { r: number; g: number; b: number; }

function hexToRgb(hex: string): Rgb | null {
  const match = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!match) return null;
  const value = parseInt(match[1], 16);
  return { r: (value >> 16) & 255, g: (value >> 8) & 255, b: value & 255 };
}

function rgbToHex({ r, g, b }: Rgb): string {
  const channel = (v: number) => Math.round(Math.min(255, Math.max(0, v))).toString(16).padStart(2, '0');
  return `#${channel(r)}${channel(g)}${channel(b)}`;
}

function mix(a: string, b: string, t: number): string {
  const ca = hexToRgb(a);
  const cb = hexToRgb(b);
  if (!ca || !cb) return a;
  return rgbToHex({
    r: ca.r + (cb.r - ca.r) * t,
    g: ca.g + (cb.g - ca.g) * t,
    b: ca.b + (cb.b - ca.b) * t
  });
}

function luminance(hex: string): number {
  const c = hexToRgb(hex);
  if (!c) return 1;
  return (0.299 * c.r + 0.587 * c.g + 0.114 * c.b) / 255;
}

function readableOn(hex: string): string {
  return luminance(hex) > 0.62 ? '#141414' : '#ffffff';
}

function isValidHex(value: string | null): value is string {
  return !!value && /^#[0-9a-f]{6}$/i.test(value.trim());
}

@Injectable({
  providedIn: 'root'
})
export class ThemeService {
  currentTheme = signal<Theme>(this.readTheme());
  tone = signal<ToneId>(this.readTone());
  accent = signal<string>(this.readAccent());
  isDark = signal<boolean>(false);

  constructor() {
    this.updateTheme();
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (this.currentTheme() === 'system') {
        this.updateTheme();
      }
    });

    effect(() => {
      const theme = this.currentTheme();
      this.write(STORAGE_THEME, theme);
      this.updateTheme();
    });

    effect(() => {
      const tone = this.tone();
      const accent = this.accent();
      this.write(STORAGE_TONE, tone);
      this.write(STORAGE_ACCENT, accent);
      this.updateTheme();
    });
  }

  setTheme(theme: Theme) {
    this.currentTheme.set(theme);
  }

  setTone(tone: ToneId) {
    this.tone.set(tone);
  }

  setAccent(accent: string) {
    if (isValidHex(accent)) {
      this.accent.set(accent.toLowerCase());
    }
  }

  resetAppearance() {
    this.currentTheme.set('system');
    this.tone.set('papier');
    this.accent.set(DEFAULT_ACCENT);
  }

  isDefaultAccent(): boolean {
    return this.accent().toLowerCase() === DEFAULT_ACCENT;
  }

  toneById(id: ToneId): SurfaceTone {
    return SURFACE_TONES.find((tone) => tone.id === id) || SURFACE_TONES[0];
  }

  toneColors(id: ToneId): ToneColors {
    const tone = this.toneById(id);
    return this.isDark() ? tone.dark : tone.light;
  }

  contrastColor(color: string): string {
    return readableOn(color);
  }

  private computeDark(): boolean {
    const theme = this.currentTheme();
    if (theme === 'dark') return true;
    if (theme === 'light') return false;
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  }

  private updateTheme() {
    const dark = this.computeDark();
    this.isDark.set(dark);
    document.documentElement.classList.toggle('dark', dark);
    this.apply(dark);
  }

  private resolvedVars(dark: boolean): Record<string, string> {
    const tone = this.toneById(this.tone())[dark ? 'dark' : 'light'];
    const base = this.accent();
    const accent = dark
      ? mix(base, '#ffffff', Math.min(0.55, Math.max(0, 0.78 - luminance(base))))
      : base;

    return {
      '--bg': tone.bg,
      '--surface': tone.surface,
      '--surface-subtle': tone.surfaceSubtle,
      '--surface-hover': tone.surfaceHover,
      '--sidebar': tone.sidebar,
      '--border': tone.border,
      '--accent': accent,
      '--accent-hover': dark ? mix(accent, '#ffffff', 0.14) : mix(accent, '#000000', 0.14),
      '--accent-soft': mix(accent, dark ? tone.surface : '#ffffff', 0.86),
      '--on-accent': readableOn(accent),
      '--scrim': dark ? 'rgb(0 0 0 / .62)' : 'rgb(20 20 18 / .4)'
    };
  }

  private apply(dark: boolean) {
    const root = document.documentElement;
    const vars = this.resolvedVars(dark);
    for (const [key, value] of Object.entries(vars)) {
      root.style.setProperty(key, value);
    }

    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
      meta.setAttribute('content', vars['--bg']);
    }

    this.write(STORAGE_VARS, JSON.stringify({
      light: this.resolvedVars(false),
      dark: this.resolvedVars(true)
    }));
  }

  private readTheme(): Theme {
    const stored = this.read(STORAGE_THEME);
    return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system';
  }

  private readTone(): ToneId {
    const stored = this.read(STORAGE_TONE);
    return SURFACE_TONES.some((tone) => tone.id === stored) ? (stored as ToneId) : 'papier';
  }

  private readAccent(): string {
    const stored = this.read(STORAGE_ACCENT);
    return isValidHex(stored) ? stored.toLowerCase() : DEFAULT_ACCENT;
  }

  private read(key: string): string | null {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  }

  private write(key: string, value: string) {
    try {
      localStorage.setItem(key, value);
    } catch {
      // Storage may be unavailable (private mode); the UI still works for this session.
    }
  }
}
