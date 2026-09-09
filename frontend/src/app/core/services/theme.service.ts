import { Injectable, signal, effect } from '@angular/core';

export type Theme = 'light' | 'dark' | 'system';

@Injectable({
  providedIn: 'root'
})
export class ThemeService {
  currentTheme = signal<Theme>((localStorage.getItem('paperless_theme') as Theme) || 'system');
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
      localStorage.setItem('paperless_theme', theme);
      this.updateTheme();
    });
  }

  setTheme(theme: Theme) {
    this.currentTheme.set(theme);
  }

  private updateTheme() {
    const theme = this.currentTheme();
    let dark = false;
    if (theme === 'dark') {
      dark = true;
    } else if (theme === 'light') {
      dark = false;
    } else {
      dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    this.isDark.set(dark);
    if (dark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }
}
