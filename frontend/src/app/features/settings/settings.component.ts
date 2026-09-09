import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SettingsService, ScheduleItem, CapabilitiesData } from '../../core/services/settings.service';
import { ThemeService, Theme } from '../../core/services/theme.service';
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
