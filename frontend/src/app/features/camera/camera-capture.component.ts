import { Component, inject, signal, OnInit, OnDestroy, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { CaptureService, CapturePageItem } from '../../core/services/capture.service';
import { IconComponent } from '../../shared/components/icon/icon.component';

@Component({
  selector: 'app-camera-capture',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule, IconComponent],
  templateUrl: './camera-capture.component.html'
})
export class CameraCaptureComponent implements OnInit, OnDestroy {
  captureService = inject(CaptureService);
  router = inject(Router);

  errorMessage = signal<string | null>(null);
  syncing = signal(false);
  pendingUploads() { return this.pages().some(p => p.upload_status === 'uploading' || p.upload_status === 'failed'); }
  cameraActive = signal<boolean>(false);
  finalizing = signal<boolean>(false);
  sessionId = signal<string | null>(null);
  pages = signal<CapturePageItem[]>([]);

  @ViewChild('videoElement') videoRef?: ElementRef<HTMLVideoElement>;
  @ViewChild('captureCanvas') canvasRef?: ElementRef<HTMLCanvasElement>;

  private mediaStream: MediaStream | null = null;
  private currentRevision: number = 0;

  ngOnInit() {
    this.initSession();
  }

  initSession() {
    this.captureService.createSession().subscribe(session => {
      this.sessionId.set(session.id);
      this.currentRevision = session.revision;
      // Camera permission is requested only after an explicit button press.
    });
  }

  async startCamera() {
    this.errorMessage.set(null);
    this.stopCamera();
    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } }
      });
      if (this.videoRef) {
        this.videoRef.nativeElement.srcObject = this.mediaStream;
        this.cameraActive.set(true);
      }
    } catch (err) {
      this.errorMessage.set('Die Kamera ist nicht verfügbar. Erlaube den Zugriff im Browser oder wähle Fotos von deinem Gerät.');
      this.cameraActive.set(false);
    }
  }

  captureFrame() {
    if (!this.videoRef || !this.canvasRef || !this.sessionId()) return;

    const video = this.videoRef.nativeElement;
    const canvas = this.canvasRef.nativeElement;
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const dataUrl = canvas.toDataURL('image/jpeg', 0.85);

    canvas.toBlob(blob => {
      if (blob) {
        this.uploadScannedBlob(blob, dataUrl);
      }
    }, 'image/jpeg', 0.85);
  }

  onFileCapture(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files || !this.sessionId()) return;
    for (const file of Array.from(input.files)) {
      const reader = new FileReader();
      reader.onload = () => this.uploadScannedBlob(file, reader.result as string);
      reader.readAsDataURL(file);
    }
    input.value = '';
  }

  private uploadScannedBlob(blob: Blob, dataUrl: string) {
    const sessId = this.sessionId()!;
    const pageNum = this.pages().length + 1;
    const pageId = `page_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;

    // Optimistic UI page
    const tempPage: CapturePageItem = {
      id: pageId,
      session_id: sessId,
      page_number: pageNum,
      rotation: 0,
      upload_status: 'uploading',
      created_at: new Date().toISOString(),
      localDataUrl: dataUrl
    };

    this.pages.update(p => [...p, tempPage]);

    this.captureService.uploadPage(sessId, pageId, blob, pageNum).subscribe({
      next: (serverPage) => {
        this.pages.update(pages => pages.map(p => p.id === pageId ? { ...serverPage, localDataUrl: dataUrl } : p));
      },
      error: (err) => {
        this.pages.update(pages => pages.map(p => p.id === pageId ? {...p, upload_status:'failed'} : p));
        this.errorMessage.set('Eine Seite konnte nicht gespeichert werden. Entferne sie und füge sie erneut hinzu.');
      }
    });
  }

  rotatePage(page: CapturePageItem) {
    page.rotation = (page.rotation + 90) % 360;
    this.pages.update(p => [...p]);
    this.syncSessionPatch();
  }

  deletePage(pageId: string) {
    this.pages.update(p => p.filter(it => it.id !== pageId));
    this.syncSessionPatch();
  }

  movePageLeft(idx: number) {
    if (idx <= 0) return;
    const list = [...this.pages()];
    const temp = list[idx];
    list[idx] = list[idx - 1];
    list[idx - 1] = temp;
    this.pages.set(list);
    this.syncSessionPatch();
  }

  movePageRight(idx: number) {
    const list = [...this.pages()];
    if (idx >= list.length - 1) return;
    const temp = list[idx];
    list[idx] = list[idx + 1];
    list[idx + 1] = temp;
    this.pages.set(list);
    this.syncSessionPatch();
  }

  private syncSessionPatch() {
    if (!this.sessionId()) return;
    const patchData = this.pages().map((p, idx) => ({
      id: p.id,
      page_number: idx + 1,
      rotation: p.rotation
    }));

    this.syncing.set(true);
    this.captureService.updateSession(this.sessionId()!, this.currentRevision, patchData).subscribe({ next: res => { this.currentRevision = res.revision; this.syncing.set(false); }, error: () => { this.syncing.set(false); this.errorMessage.set('Die Seitenänderung konnte nicht gespeichert werden. Bitte erneut versuchen.'); } });
  }

  finalizeDocument() {
    if (!this.sessionId() || this.pages().length === 0 || this.pendingUploads() || this.syncing()) return;
    this.finalizing.set(true);

    const orderedIds = this.pages().map(p => p.id);
    this.captureService.finalizeSession(this.sessionId()!, orderedIds, this.currentRevision, 'Scan vom ' + new Intl.DateTimeFormat('de-DE').format(new Date())).subscribe({
      next: (res) => {
        this.finalizing.set(false);
        this.stopCamera();
        this.router.navigate(['/documents', res.document_id]);
      },
      error: (err) => {
        this.finalizing.set(false);
        this.errorMessage.set('Das PDF konnte nicht erstellt werden. Deine Seiten bleiben erhalten. Bitte erneut versuchen.');
      }
    });
  }

  stopCamera() {
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(t => t.stop());
      this.mediaStream = null;
    }
    this.cameraActive.set(false);
  }

  ngOnDestroy() {
    this.stopCamera();
  }
}
