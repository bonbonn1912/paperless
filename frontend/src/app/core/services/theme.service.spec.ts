import { TestBed } from '@angular/core/testing';
import { DEFAULT_ACCENT, ThemeService } from './theme.service';

describe('ThemeService', () => {
  let service: ThemeService;
  let root: HTMLElement;

  beforeEach(() => {
    localStorage.clear();
    root = document.documentElement;
    root.classList.remove('dark');
    root.removeAttribute('style');

    TestBed.configureTestingModule({});
    service = TestBed.inject(ThemeService);
  });

  afterEach(() => {
    root.classList.remove('dark');
    root.removeAttribute('style');
    localStorage.clear();
  });

  it('starts with the default appearance', () => {
    expect(service.currentTheme()).toBe('system');
    expect(service.tone()).toBe('papier');
    expect(service.accent()).toBe(DEFAULT_ACCENT);
    expect(service.isDefaultAccent()).toBe(true);
  });

  it('applies tone and accent as CSS variables and stores them', () => {
    service.setTheme('light');
    service.setTone('kuehl');
    service.setAccent('#0071e3');
    TestBed.flushEffects();

    expect(root.style.getPropertyValue('--accent')).toBe('#0071e3');
    expect(root.style.getPropertyValue('--bg')).toBe('#f3f5f8');
    expect(localStorage.getItem('paperless_tone')).toBe('kuehl');
    expect(localStorage.getItem('paperless_accent')).toBe('#0071e3');
  });

  it('derives a lighter, dark-on-accent accent for dark mode', () => {
    service.setTheme('dark');
    TestBed.flushEffects();

    expect(root.classList.contains('dark')).toBe(true);
    const accent = root.style.getPropertyValue('--accent');
    expect(accent).not.toBe(DEFAULT_ACCENT);
    expect(root.style.getPropertyValue('--on-accent')).toBe('#141414');
  });

  it('ignores malformed accent values', () => {
    service.setAccent('not-a-colour');
    expect(service.accent()).toBe(DEFAULT_ACCENT);
  });

  it('resets mode, tone and accent together', () => {
    service.setTheme('dark');
    service.setTone('tinte');
    service.setAccent('#a33a6b');
    service.resetAppearance();

    expect(service.currentTheme()).toBe('system');
    expect(service.tone()).toBe('papier');
    expect(service.accent()).toBe(DEFAULT_ACCENT);
    expect(service.isDefaultAccent()).toBe(true);
  });
});
