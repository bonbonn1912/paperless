import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { BatchService, UploadQueueItem } from '../../core/services/batch.service';
import { IconComponent } from '../../shared/components/icon/icon.component';

@Component({
  selector: 'app-batch-upload',
  standalone: true,
  imports: [CommonModule, RouterModule, IconComponent],
  template: `
    <div class="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 class="text-2xl font-bold tracking-tight">Dokumente hochladen</h1>
        <p class="text-xs text-slate-500 mt-0.5">
          Ziehen Sie bis zu 100 Dateien (PDF, JPG, PNG, WEBP) gleichzeitig hierher.
        </p>
      </div>

      <!-- Drag & Drop Zone -->
      <div
        (dragover)="onDragOver($event)"
        (dragleave)="onDragLeave($event)"
        (drop)="onDrop($event)"
        [class.border-indigo-500]="isDragging()"
        [class.bg-indigo-50/50]="isDragging()"
        [class.dark:bg-indigo-950/20]="isDragging()"
        class="border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-3xl p-8 sm:p-12 text-center transition flex flex-col items-center justify-center gap-4 bg-white dark:bg-slate-850 cursor-pointer shadow-xs"
        (click)="fileInput.click()"
      >
        <div class="p-4 bg-indigo-50 dark:bg-indigo-950/60 rounded-2xl text-indigo-600 dark:text-indigo-400">
          <app-icon name="upload" [size]="36"></app-icon>
        </div>
        <div class="space-y-1">
          <p class="font-semibold text-sm">Dateien hierher ziehen oder klicken zum Auswählen</p>
          <p class="text-xs text-slate-400">PDF, JPEG, PNG, WEBP bis 50MB pro Datei</p>
        </div>

        <input
          #fileInput
          type="file"
          multiple
          (change)="onFileSelected($event)"
          accept=".pdf,image/jpeg,image/png,image/webp"
          class="hidden"
        />
      </div>

      <!-- Upload Queue Section -->
      <div *ngIf="batchService.queue().length > 0" class="bg-white dark:bg-slate-850 rounded-3xl border border-slate-200 dark:border-slate-800 p-5 space-y-4 shadow-xs">
        <div class="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h3 class="font-bold text-sm">Upload-Warteschlange ({{ batchService.queue().length }} Dateien)</h3>
            <p class="text-xs text-slate-400">
              {{ completedCount() }} von {{ batchService.queue().length }} abgeschlossen
            </p>
          </div>

          <div class="flex items-center gap-2">
            <button
              type="button"
              (click)="batchService.clearQueue()"
              [disabled]="batchService.isUploading()"
              class="px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700 text-xs font-semibold hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-40 touch-target transition"
            >
              Warteschlange leeren
            </button>
            <button
              type="button"
              (click)="batchService.startBatchUpload()"
              [disabled]="batchService.isUploading() || pendingCount() === 0"
              class="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-xl text-xs font-bold touch-target transition shadow-xs flex items-center gap-2"
            >
              <span *ngIf="batchService.isUploading()" class="animate-spin">
                <app-icon name="refresh-cw" [size]="14"></app-icon>
              </span>
              <span>{{ batchService.isUploading() ? 'Wird hochgeladen...' : 'Upload starten (' + pendingCount() + ')' }}</span>
            </button>
          </div>
        </div>

        <!-- Overall Progress Bar -->
        <div class="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
          <div
            class="bg-indigo-600 h-full transition-all duration-300"
            [style.width.%]="overallProgress()"
          ></div>
        </div>

        <!-- File List -->
        <div class="divide-y divide-slate-100 dark:divide-slate-800 max-h-96 overflow-y-auto">
          <div
            *ngFor="let item of batchService.queue()"
            class="py-3 flex items-center justify-between gap-3 text-xs"
          >
            <div class="flex items-center gap-3 min-w-0 flex-1">
              <div class="p-2 bg-slate-100 dark:bg-slate-800 rounded-lg text-slate-500 shrink-0">
                <app-icon name="file-text" [size]="18"></app-icon>
              </div>
              <div class="min-w-0 flex-1">
                <p class="font-semibold truncate">{{ item.name }}</p>
                <p class="text-[11px] text-slate-400">{{ formatSize(item.size) }}</p>
              </div>
            </div>

            <!-- Status Pill -->
            <div class="flex items-center gap-3 shrink-0">
              <span
                *ngIf="item.status === 'pending'"
                class="px-2.5 py-1 bg-slate-100 dark:bg-slate-800 text-slate-500 rounded-full text-[11px] font-medium"
              >
                Wartend
              </span>

              <span
                *ngIf="item.status === 'uploading'"
                class="px-2.5 py-1 bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 rounded-full text-[11px] font-medium flex items-center gap-1"
              >
                <app-icon name="refresh-cw" [size]="12" extraClass="animate-spin"></app-icon>
                <span>Upload</span>
              </span>

              <span
                *ngIf="item.status === 'accepted'"
                class="px-2.5 py-1 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 rounded-full text-[11px] font-semibold flex items-center gap-1"
              >
                <app-icon name="check" [size]="12"></app-icon>
                <span>Eingereiht</span>
              </span>

              <span
                *ngIf="item.status === 'duplicate'"
                class="px-2.5 py-1 bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400 rounded-full text-[11px] font-semibold"
              >
                Duplikat erkannt
              </span>

              <span
                *ngIf="item.status === 'failed'"
                class="px-2.5 py-1 bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400 rounded-full text-[11px] font-semibold"
                [title]="item.error || 'Fehler beim Upload'"
              >
                Fehlgeschlagen
              </span>

              <button
                *ngIf="item.status === 'pending' || item.status === 'failed'"
                type="button"
                (click)="batchService.removeItem(item.clientId)"
                class="p-1 rounded text-slate-400 hover:text-rose-600 touch-target"
              >
                <app-icon name="x" [size]="14"></app-icon>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  `
})
export class BatchUploadComponent {
  batchService = inject(BatchService);
  isDragging = signal<boolean>(false);

  onDragOver(e: DragEvent) {
    e.preventDefault();
    this.isDragging.set(true);
  }

  onDragLeave(e: DragEvent) {
    e.preventDefault();
    this.isDragging.set(false);
  }

  onDrop(e: DragEvent) {
    e.preventDefault();
    this.isDragging.set(false);
    if (e.dataTransfer?.files) {
      this.batchService.addFiles(e.dataTransfer.files);
    }
  }

  onFileSelected(e: any) {
    if (e.target.files) {
      this.batchService.addFiles(e.target.files);
    }
  }

  pendingCount(): number {
    return this.batchService.queue().filter(i => i.status === 'pending' || i.status === 'failed').length;
  }

  completedCount(): number {
    return this.batchService.queue().filter(i => i.status === 'accepted' || i.status === 'duplicate').length;
  }

  overallProgress(): number {
    const q = this.batchService.queue();
    if (q.length === 0) return 0;
    const finished = q.filter(i => i.status === 'accepted' || i.status === 'duplicate').length;
    return Math.round((finished / q.length) * 100);
  }

  formatSize(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }
}
