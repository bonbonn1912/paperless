import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SettingsService, ScheduleItem, CapabilitiesData } from '../../core/services/settings.service';
import { IconComponent } from '../../shared/components/icon/icon.component';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [CommonModule, FormsModule, IconComponent],
  template: `
    <div class="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 class="text-2xl font-bold tracking-tight">Einstellungen & System</h1>
        <p class="text-xs text-slate-500 mt-0.5">
          Systemlimits, Wartungszeitpläne und SQLite-Backups verwalten.
        </p>
      </div>

      <!-- Backup & Data Export Card -->
      <div class="bg-white dark:bg-slate-850 rounded-3xl border border-slate-200 dark:border-slate-800 p-6 space-y-4 shadow-xs">
        <div class="flex items-center gap-3">
          <div class="p-2.5 bg-indigo-50 dark:bg-indigo-950/60 rounded-xl text-indigo-600 dark:text-indigo-400">
            <app-icon name="download" [size]="22"></app-icon>
          </div>
          <div>
            <h3 class="font-bold text-sm">Datensicherung & Export</h3>
            <p class="text-xs text-slate-400">Online-SQLite-Backup und JSON-Manifest erstellen</p>
          </div>
        </div>

        <div *ngIf="exportMessage()" class="p-3 bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-900 rounded-xl text-xs flex items-center gap-2">
          <app-icon name="check" [size]="16"></app-icon>
          <span>{{ exportMessage() }}</span>
        </div>

        <div class="flex items-center gap-3 pt-2">
          <button
            type="button"
            (click)="triggerExport()"
            [disabled]="exporting()"
            class="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-xl text-xs font-semibold touch-target transition shadow-xs flex items-center gap-2"
          >
            <span *ngIf="exporting()" class="animate-spin">
              <app-icon name="refresh-cw" [size]="14"></app-icon>
            </span>
            <span>{{ exporting() ? 'Backup läuft...' : 'Jetzt Backup ausführen' }}</span>
          </button>
        </div>
      </div>

      <!-- Schedules / Cron Tasks Card -->
      <div class="bg-white dark:bg-slate-850 rounded-3xl border border-slate-200 dark:border-slate-800 p-6 space-y-4 shadow-xs">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="p-2.5 bg-amber-50 dark:bg-amber-950/60 rounded-xl text-amber-600 dark:text-amber-400">
              <app-icon name="settings" [size]="22"></app-icon>
            </div>
            <div>
              <h3 class="font-bold text-sm">Geplante Aufgaben (Scheduler)</h3>
              <p class="text-xs text-slate-400">Automatischer OCR-Import und periodische Wartungsarbeiten</p>
            </div>
          </div>

          <button
            type="button"
            (click)="showScheduleModal.set(true)"
            class="px-3.5 py-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-xl text-xs font-semibold touch-target transition"
          >
            + Zeitplan hinzufügen
          </button>
        </div>

        <!-- Schedule Items List -->
        <div *ngIf="settingsService.schedules().length > 0" class="divide-y divide-slate-100 dark:divide-slate-800">
          <div
            *ngFor="let s of settingsService.schedules()"
            class="py-3 flex items-center justify-between gap-3 text-xs"
          >
            <div>
              <p class="font-semibold">{{ s.job_type }}</p>
              <p class="text-[11px] text-slate-400">
                Uhrzeit: {{ s.local_time }} ({{ s.timezone }}) · Nächster Lauf: {{ s.next_run_at ? (s.next_run_at | date:'dd.MM.yyyy HH:mm') : 'Deaktiviert' }}
              </p>
            </div>

            <div class="flex items-center gap-2">
              <button
                type="button"
                (click)="runNow(s.id)"
                class="px-2.5 py-1 bg-slate-100 dark:bg-slate-800 hover:bg-indigo-600 hover:text-white rounded-lg text-[11px] font-medium touch-target transition"
              >
                Jetzt ausführen
              </button>
              <button
                type="button"
                (click)="deleteSchedule(s.id)"
                class="p-1 rounded text-slate-400 hover:text-rose-600 touch-target"
              >
                <app-icon name="trash" [size]="14"></app-icon>
              </button>
            </div>
          </div>
        </div>

        <div *ngIf="settingsService.schedules().length === 0" class="p-6 text-center text-xs text-slate-400">
          Keine aktiven Zeitpläne konfiguriert.
        </div>
      </div>

      <!-- System Capabilities & Resource Profile Card -->
      <div *ngIf="settingsService.capabilities()" class="bg-white dark:bg-slate-850 rounded-3xl border border-slate-200 dark:border-slate-800 p-6 space-y-4 shadow-xs">
        <h3 class="font-bold text-sm">System-Ressourcenprofil (Linux 4 Cores / 6 GB)</h3>

        <div class="grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs">
          <div class="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-800">
            <span class="text-slate-400 block text-[11px]">Max. Upload-Dateigröße</span>
            <span class="font-bold text-sm">{{ settingsService.capabilities()?.max_upload_mb }} MB</span>
          </div>

          <div class="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-800">
            <span class="text-slate-400 block text-[11px]">Max. Batch-Dateien</span>
            <span class="font-bold text-sm">{{ settingsService.capabilities()?.max_batch_files }} Dateien</span>
          </div>

          <div class="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-800">
            <span class="text-slate-400 block text-[11px]">Schwere Worker-Jobs (OCR)</span>
            <span class="font-bold text-sm">{{ settingsService.capabilities()?.heavy_job_concurrency }} (Sequentiell)</span>
          </div>

          <div class="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-800">
            <span class="text-slate-400 block text-[11px]">Worker Speicherlimit</span>
            <span class="font-bold text-sm">{{ settingsService.capabilities()?.heavy_memory_mb }} MB</span>
          </div>

          <div class="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-800">
            <span class="text-slate-400 block text-[11px]">OCR-Sprachen</span>
            <span class="font-bold text-sm">{{ settingsService.capabilities()?.available_ocr_languages?.join(', ') }}</span>
          </div>

          <div class="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-800">
            <span class="text-slate-400 block text-[11px]">Max. Kamera-Seiten</span>
            <span class="font-bold text-sm">{{ settingsService.capabilities()?.max_capture_pages }} Seiten</span>
          </div>
        </div>
      </div>

      <!-- Add Schedule Modal -->
      <div *ngIf="showScheduleModal()" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
        <div class="bg-white dark:bg-slate-850 rounded-2xl shadow-xl max-w-sm w-full p-5 space-y-4">
          <h3 class="text-base font-bold">Neuen Zeitplan anlegen</h3>

          <div>
            <label class="block text-xs font-semibold mb-1 text-slate-500">Aufgabentyp</label>
            <select
              [(ngModel)]="newJobType"
              class="w-full px-3 py-2 text-xs bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-hidden"
            >
              <option value="base_pipeline">Automatische OCR-Pipeline</option>
              <option value="backup">SQLite-Datenbank-Backup</option>
            </select>
          </div>

          <div>
            <label class="block text-xs font-semibold mb-1 text-slate-500">Ausführungszeit (Lokal)</label>
            <input
              type="time"
              [(ngModel)]="newLocalTime"
              class="w-full px-3 py-2 text-xs bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-hidden"
            />
          </div>

          <div class="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              (click)="showScheduleModal.set(false)"
              class="px-4 py-2 text-xs rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 touch-target"
            >
              Abbrechen
            </button>
            <button
              type="button"
              (click)="createSchedule()"
              class="px-4 py-2 text-xs bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl touch-target font-semibold shadow-xs"
            >
              Speichern
            </button>
          </div>
        </div>
      </div>
    </div>
  `
})
export class SettingsComponent implements OnInit {
  settingsService = inject(SettingsService);

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
      error: () => this.exporting.set(false)
    });
  }

  runNow(scheduleId: string) {
    this.settingsService.runScheduleNow(scheduleId).subscribe(() => {
      alert('Aufgabe erfolgreich angestoßen!');
    });
  }

  deleteSchedule(scheduleId: string) {
    if (!confirm('Zeitplan löschen?')) return;
    this.settingsService.deleteSchedule(scheduleId).subscribe();
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
