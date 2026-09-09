import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { BatchService, UploadQueueItem } from '../../core/services/batch.service';
import { SettingsService } from '../../core/services/settings.service';
import { PollingService } from '../../core/services/polling.service';
import { IconComponent } from '../../shared/components/icon/icon.component';

@Component({
  selector: 'app-batch-upload',
  standalone: true,
  imports: [CommonModule, RouterModule, IconComponent],
  templateUrl: './batch-upload.component.html'
})
export class BatchUploadComponent implements OnInit {
  settingsService = inject(SettingsService);
  polling = inject(PollingService);
  uploadError = signal<string | null>(null);
  ngOnInit() { this.settingsService.loadCapabilities().subscribe({ error: () => {} }); }
  trackItem(_index: number, item: UploadQueueItem) { return item.clientId; }
  async startUpload() {
    this.uploadError.set(null);
    const max = this.settingsService.capabilities()?.max_batch_files || 100;
    if (this.pendingCount() > max) { this.uploadError.set(`Bitte höchstens ${max} Dateien pro Stapel auswählen.`); return; }
    await this.batchService.startBatchUpload();
    if (this.batchService.queue().some(i => i.status === 'pending')) this.uploadError.set('Der Upload konnte nicht gestartet werden. Bitte erneut versuchen.');
  }
  statusLabel(item: UploadQueueItem) {
    const status = this.polling.activeItems().find(s => s.document_id && s.document_id === item.documentId);
    if (status?.classification_state === 'needs_review') return 'Zu prüfen';
    if (status?.processing_state === 'ready') return 'Im Archiv';
    if (status?.processing_state === 'processing') return 'In Verarbeitung';
    return ({ pending: 'Bereit zum Upload', uploading: 'Wird übertragen', accepted: 'Eingereiht', processing: 'In Verarbeitung', ready: 'Im Archiv', duplicate: 'Bereits vorhanden', failed: 'Fehlgeschlagen' })[item.status];
  }
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
