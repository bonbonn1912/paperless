import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SettingsService } from '../../core/services/settings.service';
import {
  ACCENT_PRESETS,
  SURFACE_TONES,
  Theme,
  ThemeService,
  ToneColors,
  ToneId
} from '../../core/services/theme.service';
import { DialogDirective } from '../../shared/directives/dialog.directive';
import { IconComponent } from '../../shared/components/icon/icon.component';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [CommonModule, FormsModule, IconComponent, DialogDirective],
  templateUrl: './settings.component.html'
})
export class SettingsComponent implements OnInit {
  settingsService = inject(SettingsService);
  themeService = inject(ThemeService);
  themeOptions: { value: Theme; label: string }[] = [{value:'light',label:'Hell'},{value:'dark',label:'Dunkel'},{value:'system',label:'System'}];
  toneOptions = SURFACE_TONES;
  accentPresets = ACCENT_PRESETS;
  notice = signal<string | null>(null);
  errorMessage = signal<string | null>(null);
  scheduleToDelete = signal<string | null>(null);
  jobLabel(type: string) { return ({base_pipeline:'Dokumente verarbeiten',backup:'Datenbank sichern'} as Record<string,string>)[type] || type; }

  exporting = signal<boolean>(false);
  exportMessage = signal<string | null>(null);

  showScheduleModal = signal<boolean>(false);
  newJobType: string = 'base_pipeline';
  newLocalTime: string = '02:00';

  ngOnInit() {
    this.settingsService.loadCapabilities().subscribe();
    this.settingsService.loadSchedules().subscribe();
  }

  setTone(tone: ToneId) {
    this.themeService.setTone(tone);
    this.notice.set(null);
  }

  setAccent(color: string) {
    this.themeService.setAccent(color);
    this.notice.set(null);
  }

  onAccentInput(event: Event) {
    this.setAccent((event.target as HTMLInputElement).value);
  }

  isPresetActive(value: string) {
    return this.themeService.accent().toLowerCase() === value;
  }

  isCustomAccent() {
    return !this.accentPresets.some((preset) => preset.value === this.themeService.accent());
  }

  isDefaultAppearance() {
    return this.themeService.currentTheme() === 'system'
      && this.themeService.tone() === 'papier'
      && this.themeService.isDefaultAccent();
  }

  toneColors(id: ToneId): ToneColors {
    return this.themeService.toneColors(id);
  }

  resetAppearance() {
    this.themeService.resetAppearance();
    this.notice.set('Das Erscheinungsbild ist wieder auf den Standard gesetzt.');
  }

  triggerExport() {
    this.exporting.set(true);
    this.exportMessage.set(null);
    this.settingsService.triggerExport().subscribe({
      next: (res) => {
        this.exporting.set(false);
        this.exportMessage.set(res.message);
      },
      error: () => { this.exporting.set(false); this.errorMessage.set('Die Sicherung konnte nicht gestartet werden.'); }
    });
  }

  runNow(scheduleId: string) {
    this.settingsService.runScheduleNow(scheduleId).subscribe(() => {
      this.notice.set('Die Aufgabe wurde zur Verarbeitung eingereiht.');
    });
  }

  deleteSchedule(scheduleId: string) {
    this.settingsService.deleteSchedule(scheduleId).subscribe({ next: () => this.scheduleToDelete.set(null), error: () => { this.scheduleToDelete.set(null); this.errorMessage.set('Der Zeitplan konnte nicht gelöscht werden.'); } });
  }

  createSchedule() {
    this.settingsService.createSchedule({
      job_type: this.newJobType,
      mode: 'scheduled',
      weekdays: [1, 2, 3, 4, 5, 6, 7],
      local_time: this.newLocalTime,
      timezone: 'Europe/Berlin'
    }).subscribe(() => {
      this.showScheduleModal.set(false);
    });
  }
}
