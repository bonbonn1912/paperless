import { Component, inject, signal, OnInit, ElementRef, ViewChild, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import * as pdfjsLib from 'pdfjs-dist';
import { DocumentService, DocumentViewerManifest, InDocSearchHit } from '../../core/services/document.service';
import { TagService, TagResponse } from '../../core/services/tag.service';
import { FolderService, FolderNode } from '../../core/services/folder.service';
import { Document } from '../../core/models';
import { DialogDirective } from '../../shared/directives/dialog.directive';
import { IconComponent } from '../../shared/components/icon/icon.component';

// Ensure modern Promise methods required by pdfjs-dist are defined under Zone.js
if (typeof (Promise as any).try !== 'function') {
  (Promise as any).try = function <T>(fn: (...args: any[]) => T, ...args: any[]): Promise<T> {
    return new Promise<T>((resolve) => resolve(fn(...args)));
  };
}
if (typeof (Promise as any).withResolvers !== 'function') {
  (Promise as any).withResolvers = function <T>() {
    let resolve!: (value: T | PromiseLike<T>) => void;
    let reject!: (reason?: any) => void;
    const promise = new Promise<T>((res, rej) => {
      resolve = res;
      reject = rej;
    });
    return { promise, resolve, reject };
  };
}

@Component({
  selector: 'app-document-viewer',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule, IconComponent, DialogDirective],
  templateUrl: './viewer.component.html'
})
export class DocumentViewerComponent implements OnInit, OnDestroy {
  docService = inject(DocumentService);
  tagService = inject(TagService);
  folderService = inject(FolderService);
  route = inject(ActivatedRoute);
  router = inject(Router);

  expanded = signal(false);
  showDelete = signal(false);
  errorMessage = signal<string | null>(null);
  notice = signal<string | null>(null);
  rendering = signal(true);
  searchPerformed = signal(false);
  hitIndex = signal(0);
  imageWidth = signal(640);
  imageHeight = signal(800);
  private renderTask: any = null;
  private renderVersion = 0;
  private destroyed = false;
  private fitMode = true;
  private resizeObserver?: ResizeObserver;
  private loadingTask: any = null;
  @ViewChild('viewportContainer') viewportRef?: ElementRef<HTMLElement>;
  Math = Math;
  docId: string = '';
  doc = signal<Document | null>(null);
  manifest = signal<DocumentViewerManifest | null>(null);

  currentPage = signal<number>(1);
  totalPages = signal<number>(1);
  zoom = signal<number>(1.2);
  rotation = signal<number>(0);
  metaOpen = signal<boolean>(false);
  saving = signal<boolean>(false);

  // Form edit fields
  editTitle: string = '';
  editSender: string = '';
  editDate: string = '';
  editAmount: number | null = null;
  editCurrency: string = 'EUR';
  tagToAdd: string | null = null;
  selectedFolderId: string = '';

  // In doc search
  searchInDocQuery: string = '';
  searchHits = signal<InDocSearchHit[]>([]);

  @ViewChild('pdfCanvas') canvasRef?: ElementRef<HTMLCanvasElement>;
  private pdfDoc: any = null;

  ngOnInit() {
    pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs';

    this.route.params.subscribe(params => {
      this.docId = params['id'];
      this.loadDocumentData();
    });

    this.tagService.loadTags().subscribe();
    this.folderService.loadFolders().subscribe();
  }

  isImage(): boolean {
    const mime = this.doc()?.mime_type || '';
    return mime.startsWith('image/');
  }

  loadDocumentData() {
    this.docService.get(this.docId).subscribe({
      next: (doc) => {
        this.doc.set(doc);
        this.editTitle = doc.title || doc.original_name;
        this.editSender = doc.sender || '';
        this.editDate = doc.document_date || '';
        this.editAmount = doc.amount != null ? doc.amount / 100 : null;
        this.editCurrency = doc.currency || 'EUR';
        this.selectedFolderId = doc.folders?.[0]?.id || '';

        if (!this.isImage()) {
          this.loadPdf();
        }
      },
      error: (err) => {
        console.error('[PDFViewer] Error loading document:', err);
        this.rendering.set(false);
        this.errorMessage.set('Dokument konnte nicht geladen werden.');
      }
    });

    this.docService.getViewerManifest(this.docId).subscribe({
      next: (man) => {
        this.manifest.set(man);
        this.totalPages.set(man.total_pages || 1);
      },
      error: (err) => {
        console.warn('[PDFViewer] Manifest could not be loaded:', err);
      }
    });
  }

  async loadPdf() {
    try {
      this.rendering.set(true);
      this.errorMessage.set(null);
      if (this.loadingTask) {
        try {
          await this.loadingTask.destroy();
        } catch (_) {}
      }
      const loadingTask = this.loadingTask = pdfjsLib.getDocument({
        url: this.docService.getFileUrl(this.docId),
        withCredentials: true
      });
      this.pdfDoc = await loadingTask.promise;
      this.totalPages.set(this.pdfDoc.numPages);
      await this.fitToWidth();
    } catch (err) {
      console.error('[PDFViewer] Error loading PDF:', err);
      if (!this.destroyed) {
        this.rendering.set(false);
        this.errorMessage.set('Die Vorschau konnte nicht geladen werden. Du kannst das Original weiterhin herunterladen.');
      }
    }
  }

  async renderPage(num: number) {
    if (!this.pdfDoc || !this.canvasRef || this.destroyed) return;
    const version = ++this.renderVersion;
    if (this.renderTask) {
      try {
        this.renderTask.cancel();
        await this.renderTask.promise;
      } catch (_) {}
      this.renderTask = null;
    }
    if (version !== this.renderVersion || this.destroyed) return;

    this.rendering.set(true);
    this.errorMessage.set(null);
    try {
      const page = await this.pdfDoc.getPage(num);
      if (version !== this.renderVersion || this.destroyed) return;
      const viewport = page.getViewport({ scale: this.zoom(), rotation: this.rotation() });
      const canvas = this.canvasRef.nativeElement;
      const ratio = Math.min(window.devicePixelRatio || 1, 2, Math.sqrt(8000000 / (viewport.width * viewport.height)));
      canvas.width = Math.floor(viewport.width * ratio);
      canvas.height = Math.floor(viewport.height * ratio);
      canvas.style.width = viewport.width + 'px';
      canvas.style.height = viewport.height + 'px';
      this.renderTask = page.render({ canvasContext: canvas.getContext('2d')!, viewport, transform: [ratio, 0, 0, ratio, 0, 0] });
      await this.renderTask.promise;
      if (version === this.renderVersion) this.rendering.set(false);
    } catch (err: any) {
      if (err?.name !== 'RenderingCancelledException' && !this.destroyed) {
        console.error('[PDFViewer] Error rendering page:', err);
        this.rendering.set(false);
        this.errorMessage.set('Diese Seite konnte nicht dargestellt werden. Bitte eine andere Seite wählen oder erneut öffnen.');
      }
    }
  }

  async fitToWidth() {
    this.fitMode = true;
    if (!this.viewportRef) return;
    const available = Math.max(120, this.viewportRef.nativeElement.clientWidth - 48);
    if (this.isImage()) {
      this.zoom.set(Math.min(1.5, available / (this.rotation() % 180 ? this.imageHeight() : this.imageWidth())));
    } else if (this.pdfDoc) {
      const page = await this.pdfDoc.getPage(this.currentPage());
      if (this.destroyed) return;
      const viewport = page.getViewport({scale:1,rotation:this.rotation()});
      this.zoom.set(Math.min(1.5,available / viewport.width));
      await this.renderPage(this.currentPage());
    }
    if (!this.resizeObserver && this.viewportRef) {
      this.resizeObserver = new ResizeObserver(() => { if (this.fitMode && !this.destroyed) this.fitToWidth(); });
      this.resizeObserver.observe(this.viewportRef.nativeElement);
    }
  }
  onImageLoad(event: Event) { const image = event.target as HTMLImageElement; this.imageWidth.set(image.naturalWidth); this.imageHeight.set(image.naturalHeight); this.rendering.set(false); this.fitToWidth(); }
  imageError() { this.rendering.set(false); this.errorMessage.set('Dieses Bild kann der Browser nicht anzeigen. Lade das Original herunter.'); }
  imageFrameWidth() { return (this.rotation() % 180 ? this.imageHeight() : this.imageWidth()) * this.zoom(); }
  imageFrameHeight() { return (this.rotation() % 180 ? this.imageWidth() : this.imageHeight()) * this.zoom(); }
  highlightStyle(hit: InDocSearchHit): Record<string,string> {
    if (!hit.bbox) return {display:'none'};
    const box = hit.bbox;
    const page = this.manifest()?.pages.find(p => p.page_number === this.currentPage());
    const width = page?.width || this.imageWidth(); const height = page?.height || this.imageHeight();
    let x = box.x0, y = box.y0, w = box.x1-box.x0, h = box.y1-box.y0;
    switch (this.rotation()) {
      case 90: x=height-box.y1; y=box.x0; w=box.y1-box.y0; h=box.x1-box.x0; break;
      case 180: x=width-box.x1; y=height-box.y1; break;
      case 270: x=box.y0; y=width-box.x1; w=box.y1-box.y0; h=box.x1-box.x0; break;
    }
    return {left:x*this.zoom()+'px',top:y*this.zoom()+'px',width:w*this.zoom()+'px',height:h*this.zoom()+'px'};
  }
  moveHit(delta: number) { const hits = this.searchHits(); if (!hits.length) return; this.hitIndex.set((this.hitIndex()+delta+hits.length)%hits.length); this.goToPage(hits[this.hitIndex()].page_number); }

  prevPage() {
    if (this.currentPage() > 1) {
      this.goToPage(this.currentPage() - 1);
    }
  }

  nextPage() {
    if (this.currentPage() < this.totalPages()) {
      this.goToPage(this.currentPage() + 1);
    }
  }

  goToPage(num: number) {
    num = Math.max(1,Math.min(this.totalPages(),num));
    this.currentPage.set(num);
    if (!this.isImage()) {
      this.renderPage(num);
    }
  }

  zoomIn() {
    this.fitMode = false;
    this.zoom.update(z => Math.min(3.0, z + 0.2));
    if (!this.isImage()) this.renderPage(this.currentPage());
  }

  zoomOut() {
    this.fitMode = false;
    this.zoom.update(z => Math.max(0.4, z - 0.2));
    if (!this.isImage()) this.renderPage(this.currentPage());
  }

  rotate() {
    this.rotation.update(r => (r + 90) % 360);
    if (this.fitMode) this.fitToWidth(); else if (!this.isImage()) this.renderPage(this.currentPage());
  }

  onSearchInDoc() {
    if (!this.searchInDocQuery.trim()) {
      this.searchHits.set([]); this.searchPerformed.set(false);
      return;
    }
    this.docService.searchInDocument(this.docId, this.searchInDocQuery.trim()).subscribe(res => {
      this.searchHits.set(res.hits); this.searchPerformed.set(true); this.hitIndex.set(0);
      if (res.hits.length > 0) {
        this.goToPage(res.hits[0].page_number);
      }
    });
  }

  currentPageHits(): InDocSearchHit[] {
    return this.searchHits().filter(h => h.page_number === this.currentPage());
  }

  availableTags(): TagResponse[] {
    const existing = new Set((this.doc()?.tags || []).map(t => t.id));
    return this.tagService.tags().filter(t => !existing.has(t.id));
  }

  addTag() {
    if (!this.tagToAdd) return;
    this.tagService.assignToDocument(this.docId, this.tagToAdd).subscribe(() => {
      this.tagToAdd = null;
      this.loadDocumentData();
    });
  }

  removeTag(tagId: string) {
    this.tagService.removeFromDocument(this.docId, tagId).subscribe(() => {
      this.loadDocumentData();
    });
  }

  onFolderChange() {
    if (this.selectedFolderId) {
      this.folderService.addDocumentToFolder(this.docId, this.selectedFolderId).subscribe(() => {
        this.loadDocumentData();
      });
    }
  }

  saveMetadata() {
    this.saving.set(true);
    const amountCents = this.editAmount != null ? Math.round(this.editAmount * 100) : null;
    this.docService.patch(this.docId, {
      title: this.editTitle,
      sender: this.editSender,
      document_date: this.editDate || null,
      amount: amountCents,
      currency: this.editCurrency
    }).subscribe({
      next: (updated) => {
        this.doc.set(updated);
        this.saving.set(false); this.notice.set('Änderungen gespeichert.');
      },
      error: () => { this.saving.set(false); this.errorMessage.set('Die Änderungen konnten nicht gespeichert werden.'); }
    });
  }

  resolveReview() {
    this.docService.patch(this.docId, {
      resolve_review: true
    }).subscribe(updated => {
      this.doc.set(updated);
    });
  }

  deleteDocument() {
    this.showDelete.set(false);
    this.docService.delete(this.docId).subscribe(() => {
      this.router.navigate(['/documents']);
    });
  }

  formatSize(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  onThumbError(event: any) {
    event.target.style.display = 'none';
  }

  ngOnDestroy() {
    this.destroyed = true; this.renderVersion++; this.resizeObserver?.disconnect(); this.renderTask?.cancel(); this.loadingTask?.destroy();
    this.pdfDoc = null;
  }
}
