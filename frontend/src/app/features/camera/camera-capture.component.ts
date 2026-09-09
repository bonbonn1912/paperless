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
  template: `
    <div class="max-w-3xl mx-auto space-y-6">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold tracking-tight">Kamera-Scan</h1>
          <p class="text-xs text-slate-500 mt-0.5">
            Dokumentseiten mit der Kamera erfassen, zuschneiden, drehen und als PDF speichern.
          </p>
        </div>

        <button
          *ngIf="pages().length > 0"
          type="button"
          (click)="finalizeDocument()"
          [disabled]="finalizing()"
          class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-xl text-xs font-bold touch-target transition shadow-xs flex items-center gap-2"
        >
          <span *ngIf="finalizing()" class="animate-spin">
            <app-icon name="refresh-cw" [size]="14"></app-icon>
          </span>
          <span>{{ finalizing() ? 'PDF wird erstellt...' : 'PDF fertigstellen (' + pages().length + ' Seiten)' }}</span>
        </button>
      </div>

      <!-- Live Viewfinder / Capture Box -->
      <div class="relative bg-black rounded-3xl overflow-hidden aspect-3/4 sm:aspect-4/3 max-h-[550px] flex items-center justify-center shadow-lg">
        <!-- Live Video Element -->
        <video
          #videoElement
          autoplay
          playsinline
          muted
          class="w-full h-full object-cover"
          [class.hidden]="!cameraActive()"
        ></video>

        <!-- Hidden canvas for capturing frames -->
        <canvas #captureCanvas class="hidden"></canvas>

        <!-- Document Framing Overlay Guide -->
        <div *ngIf="cameraActive()" class="absolute inset-8 sm:inset-12 border-2 border-white/60 border-dashed rounded-2xl pointer-events-none flex flex-col justify-between p-4">
          <span class="text-[11px] font-semibold text-white/80 bg-black/40 px-2 py-0.5 rounded backdrop-blur-xs self-center">
            Dokument im Rahmen ausrichten
          </span>
          <div class="flex justify-between text-white/60 text-xs">
            <span>┌</span>
            <span>┐</span>
          </div>
        </div>

        <!-- Camera Fallback / Inactive State -->
        <div *ngIf="!cameraActive()" class="p-8 text-center text-white space-y-4">
          <div class="inline-flex p-4 bg-white/10 rounded-full">
            <app-icon name="camera" [size]="36"></app-icon>
          </div>
          <div class="space-y-1">
            <p class="text-sm font-semibold">Kamera nicht aktiv oder Zugriff nicht gewährt</p>
            <p class="text-xs text-slate-400">Sie können die Kamera aktivieren oder Fotos von Ihrem Gerät auswählen.</p>
          </div>
          <div class="flex items-center justify-center gap-3 pt-2">
            <button
              type="button"
              (click)="startCamera()"
              class="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold touch-target transition shadow-xs"
            >
              Kamera starten
            </button>
            <button
              type="button"
              (click)="photoInput.click()"
              class="px-4 py-2 bg-white/20 hover:bg-white/30 text-white rounded-xl text-xs font-semibold touch-target transition"
            >
              Foto auswählen
            </button>
          </div>
        </div>

        <!-- Shutter Button Overlay (when camera active) -->
        <div *ngIf="cameraActive()" class="absolute bottom-6 inset-x-0 flex items-center justify-center gap-6">
          <button
            type="button"
            (click)="captureFrame()"
            class="w-16 h-16 rounded-full border-4 border-white bg-indigo-600 hover:bg-indigo-700 active:scale-95 shadow-xl touch-target transition flex items-center justify-center"
            title="Foto aufnehmen"
          >
            <div class="w-12 h-12 rounded-full border-2 border-white/40"></div>
          </button>
        </div>

        <input
          #photoInput
          type="file"
          accept="image/*"
          (change)="onFileCapture($event)"
          class="hidden"
        />
      </div>

      <!-- Scanned Pages Tray & Reorder / Rotate Controls -->
      <div *ngIf="pages().length > 0" class="bg-white dark:bg-slate-850 rounded-3xl border border-slate-200 dark:border-slate-800 p-5 space-y-4 shadow-xs">
        <div class="flex items-center justify-between">
          <h3 class="font-bold text-sm">Erfasste Seiten ({{ pages().length }})</h3>
          <p class="text-xs text-slate-400">Reihenfolge ändern oder Seiten drehen</p>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 gap-3">
          <div
            *ngFor="let page of pages(); let idx = index"
            class="relative group rounded-2xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-850 p-2 flex flex-col justify-between overflow-hidden shadow-xs"
          >
            <!-- Page Number Badge -->
            <span class="absolute top-3 left-3 z-10 px-2 py-0.5 bg-black/60 text-white rounded-md text-[10px] font-mono">
              #{{ idx + 1 }}
            </span>

            <!-- Image preview with rotation applied -->
            <div class="aspect-3/4 bg-slate-200 dark:bg-slate-800 rounded-xl overflow-hidden flex items-center justify-center relative">
              <img
                [src]="page.localDataUrl || ''"
                [style.transform]="'rotate(' + page.rotation + 'deg)'"
                class="w-full h-full object-cover transition-transform duration-200"
                alt="Page scan"
              />
            </div>

            <!-- Page actions -->
            <div class="flex items-center justify-between gap-1 pt-2">
              <button
                type="button"
                (click)="movePageLeft(idx)"
                [disabled]="idx === 0"
                class="p-1 rounded text-slate-400 hover:text-slate-700 disabled:opacity-20 touch-target"
                title="Nach links schieben"
              >
                <app-icon name="chevron-left" [size]="14"></app-icon>
              </button>

              <button
                type="button"
                (click)="rotatePage(page)"
                class="p-1 rounded text-slate-400 hover:text-indigo-600 touch-target"
                title="90° drehen"
              >
                <app-icon name="rotate-cw" [size]="14"></app-icon>
              </button>

              <button
                type="button"
                (click)="deletePage(page.id)"
                class="p-1 rounded text-slate-400 hover:text-rose-600 touch-target"
                title="Seite entfernen"
              >
                <app-icon name="trash" [size]="14"></app-icon>
              </button>

              <button
                type="button"
                (click)="movePageRight(idx)"
                [disabled]="idx === pages().length - 1"
                class="p-1 rounded text-slate-400 hover:text-slate-700 disabled:opacity-20 touch-target"
                title="Nach rechts schieben"
              >
                <app-icon name="chevron-right" [size]="14"></app-icon>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  `
})
export class CameraCaptureComponent implements OnInit, OnDestroy {
  captureService = inject(CaptureService);
  router = inject(Router);

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
      this.startCamera();
    });
  }

  async startCamera() {
    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } }
      });
      if (this.videoRef) {
        this.videoRef.nativeElement.srcObject = this.mediaStream;
        this.cameraActive.set(true);
      }
    } catch (err) {
      console.warn('Camera access denied or unavailable:', err);
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

  onFileCapture(e: any) {
    const file = e.target.files?.[0];
    if (!file || !this.sessionId()) return;

    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      this.uploadScannedBlob(file, dataUrl);
    };
    reader.readAsDataURL(file);
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
        console.error('Error uploading scanned page:', err);
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

    this.captureService.updateSession(this.sessionId()!, this.currentRevision, patchData).subscribe(res => {
      this.currentRevision = res.revision;
    });
  }

  finalizeDocument() {
    if (!this.sessionId() || this.pages().length === 0) return;
    this.finalizing.set(true);

    const orderedIds = this.pages().map(p => p.id);
    this.captureService.finalizeSession(this.sessionId()!, orderedIds, this.currentRevision, 'Scanned Document').subscribe({
      next: (res) => {
        this.finalizing.set(false);
        this.stopCamera();
        this.router.navigate(['/documents', res.document_id]);
      },
      error: (err) => {
        this.finalizing.set(false);
        console.error('Error finalizing capture session:', err);
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
