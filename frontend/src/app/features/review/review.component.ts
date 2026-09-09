import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ReviewService } from '../../core/services/review.service';
import { DocumentService } from '../../core/services/document.service';
import { TagService, TagResponse } from '../../core/services/tag.service';
import { Document } from '../../core/models';
import { IconComponent } from '../../shared/components/icon/icon.component';

@Component({
  selector: 'app-review',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule, IconComponent],
  template: `
    <div class="space-y-6">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold tracking-tight">Zu prüfen</h1>
          <p class="text-xs text-slate-500 mt-0.5">
            Dokumente mit unsicherer Klassifizierung oder fehlenden Metadaten manuell freigeben.
          </p>
        </div>
        <span class="px-3 py-1 bg-amber-100 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800 rounded-full text-xs font-bold">
          {{ reviewService.needsReviewCount() }} Dokumente offen
        </span>
      </div>

      <!-- Review Queue Split / List -->
      <div *ngIf="documents().length > 0" class="space-y-4">
        <div
          *ngFor="let doc of documents()"
          class="bg-white dark:bg-slate-850 rounded-2xl border border-slate-200 dark:border-slate-800 p-4 sm:p-5 shadow-xs flex flex-col md:flex-row gap-5"
        >
          <!-- Thumbnail & Quick View -->
          <div class="w-full md:w-44 shrink-0 aspect-3/4 bg-slate-100 dark:bg-slate-800 rounded-xl overflow-hidden relative group">
            <img
              [src]="docService.getThumbnailUrl(doc.id)"
              [alt]="doc.title || doc.original_name"
              class="w-full h-full object-cover object-top"
            />
            <a
              [routerLink]="['/documents', doc.id]"
              target="_blank"
              class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center text-white text-xs font-semibold gap-1.5 transition backdrop-blur-xs"
            >
              <app-icon name="eye" [size]="16"></app-icon>
              <span>Vorschau öffnen</span>
            </a>
          </div>

          <!-- Metadata & Triage Fields -->
          <div class="flex-1 flex flex-col justify-between space-y-4">
            <div>
              <div class="flex items-start justify-between gap-2">
                <div>
                  <h3 class="font-bold text-base text-slate-800 dark:text-slate-100">
                    {{ doc.title || doc.original_name }}
                  </h3>
                  <p class="text-xs text-slate-400">
                    Dateiname: {{ doc.original_name }} · Hochgeladen am {{ doc.created_at | date:'dd.MM.yyyy HH:mm' }}
                  </p>
                </div>
              </div>

              <!-- Editable Fast-Fields -->
              <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-4">
                <div>
                  <label class="block text-[11px] font-semibold text-slate-500 mb-1">Absender</label>
                  <input
                    type="text"
                    [(ngModel)]="doc.sender"
                    placeholder="Absender eingeben"
                    class="w-full px-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-hidden"
                  />
                </div>

                <div>
                  <label class="block text-[11px] font-semibold text-slate-500 mb-1">Datum</label>
                  <input
                    type="date"
                    [(ngModel)]="doc.document_date"
                    class="w-full px-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-hidden"
                  />
                </div>

                <div>
                  <label class="block text-[11px] font-semibold text-slate-500 mb-1">Betrag</label>
                  <input
                    type="text"
                    [(ngModel)]="doc.amount_decimal"
                    placeholder="0.00"
                    class="w-full px-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-hidden"
                  />
                </div>

                <div>
                  <label class="block text-[11px] font-semibold text-slate-500 mb-1">Währung</label>
                  <input
                    type="text"
                    [(ngModel)]="doc.currency"
                    placeholder="EUR"
                    class="w-full px-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-hidden"
                  />
                </div>
              </div>

              <!-- Tags Management in Review -->
              <div class="mt-4">
                <label class="block text-[11px] font-semibold text-slate-500 mb-1.5">Tags bestätigen / anpassen</label>
                <div class="flex items-center gap-1.5 flex-wrap">
                  <span
                    *ngFor="let t of doc.tags"
                    class="px-2.5 py-1 text-xs font-medium rounded-lg flex items-center gap-1.5"
                    [style.backgroundColor]="t.color + '20'"
                    [style.color]="t.color"
                  >
                    <span>{{ t.name }}</span>
                    <button type="button" (click)="removeDocTag(doc, t.id)" class="hover:opacity-75">
                      <app-icon name="x" [size]="12"></app-icon>
                    </button>
                  </span>

                  <!-- Quick Add Tag -->
                  <select
                    (change)="addDocTag(doc, $event)"
                    class="px-2.5 py-1 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs font-medium focus:outline-hidden"
                  >
                    <option value="" selected disabled>+ Tag hinzufügen</option>
                    <option *ngFor="let at of tagService.tags()" [value]="at.id">{{ at.name }}</option>
                  </select>
                </div>
              </div>
            </div>

            <!-- Triage Actions -->
            <div class="flex items-center justify-between pt-3 border-t border-slate-100 dark:border-slate-800 flex-wrap gap-2">
              <button
                type="button"
                (click)="openRuleModal(doc)"
                class="px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 touch-target transition flex items-center gap-1.5"
              >
                <app-icon name="settings" [size]="14"></app-icon>
                <span>Regel erstellen...</span>
              </button>

              <div class="flex items-center gap-2">
                <a
                  [routerLink]="['/documents', doc.id]"
                  class="px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700 text-xs font-semibold hover:bg-slate-100 dark:hover:bg-slate-800 touch-target transition"
                >
                  Detailansicht
                </a>
                <button
                  type="button"
                  (click)="confirmDocReview(doc)"
                  class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold touch-target transition flex items-center gap-1.5 shadow-xs"
                >
                  <app-icon name="check" [size]="16"></app-icon>
                  <span>Bestätigen & Freigeben</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div *ngIf="!loading() && documents().length === 0" class="p-12 text-center bg-white dark:bg-slate-850 rounded-3xl border border-slate-200 dark:border-slate-800 space-y-3">
        <div class="inline-flex p-4 bg-emerald-50 dark:bg-emerald-950/50 rounded-full text-emerald-500">
          <app-icon name="check" [size]="36"></app-icon>
        </div>
        <h3 class="font-bold text-base">Alles erledigt!</h3>
        <p class="text-xs text-slate-500 max-w-sm mx-auto">
          Aktuell stehen keine Dokumente zur manuellen Prüfung an.
        </p>
      </div>

      <!-- Rule Creation Modal -->
      <div *ngIf="ruleModalDoc()" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
        <div class="bg-white dark:bg-slate-850 rounded-2xl shadow-xl max-w-md w-full p-5 space-y-4">
          <h3 class="text-base font-bold">Klassifizierungsregel anlegen</h3>
          <p class="text-xs text-slate-500">
            Zukünftige Dokumente dieses Absenders automatisch mit diesen Tags versehen.
          </p>

          <div>
            <label class="block text-xs font-semibold mb-1 text-slate-500">Regelname</label>
            <input
              type="text"
              [(ngModel)]="ruleName"
              class="w-full px-3 py-2 text-xs bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-hidden"
            />
          </div>

          <div>
            <label class="block text-xs font-semibold mb-1 text-slate-500">Bedingung: Absender enthält</label>
            <input
              type="text"
              [value]="ruleModalDoc()?.sender || ''"
              disabled
              class="w-full px-3 py-2 text-xs bg-slate-200 dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-xl opacity-75"
            />
          </div>

          <div class="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              (click)="ruleModalDoc.set(null)"
              class="px-4 py-2 text-xs rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 touch-target"
            >
              Abbrechen
            </button>
            <button
              type="button"
              (click)="saveRuleAndConfirm()"
              class="px-4 py-2 text-xs bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl touch-target font-semibold shadow-xs"
            >
              Regel speichern & Dokument freigeben
            </button>
          </div>
        </div>
      </div>
    </div>
  `
})
export class ReviewComponent implements OnInit {
  reviewService = inject(ReviewService);
  docService = inject(DocumentService);
  tagService = inject(TagService);

  documents = signal<Document[]>([]);
  loading = signal<boolean>(false);
  ruleModalDoc = signal<Document | null>(null);
  ruleName: string = '';

  ngOnInit() {
    this.tagService.loadTags().subscribe();
    this.loadDocs();
  }

  loadDocs() {
    this.loading.set(true);
    this.reviewService.getNeedsReviewDocs(50).subscribe({
      next: (res) => {
        this.documents.set(res.items);
        this.loading.set(false);
      },
      error: () => this.loading.set(false)
    });
  }

  removeDocTag(doc: Document, tagId: string) {
    doc.tags = doc.tags.filter(t => t.id !== tagId);
  }

  addDocTag(doc: Document, event: any) {
    const tagId = event.target.value;
    if (!tagId) return;
    const tag = this.tagService.tags().find(t => t.id === tagId);
    if (tag && !doc.tags.some(t => t.id === tag.id)) {
      doc.tags.push(tag as any);
    }
    event.target.value = '';
  }

  confirmDocReview(doc: Document, createRule: boolean = false) {
    const amountVal = doc.amount_decimal ? Math.round(parseFloat(doc.amount_decimal) * 100) : null;
    this.reviewService.confirmReview(doc.id, {
      tag_ids: doc.tags.map(t => t.id),
      field_overrides: {
        sender: doc.sender,
        title: doc.title,
        amount: amountVal,
        currency: doc.currency,
        document_date: doc.document_date
      },
      mark_as_reviewed: true,
      create_rule: createRule,
      rule_name: this.ruleName
    }).subscribe(() => {
      this.documents.update(docs => docs.filter(d => d.id !== doc.id));
      this.ruleModalDoc.set(null);
    });
  }

  openRuleModal(doc: Document) {
    this.ruleModalDoc.set(doc);
    this.ruleName = `Immer als ${doc.tags?.[0]?.name || 'Dokument'} klassifizieren (${doc.sender || 'Absender'})`;
  }

  saveRuleAndConfirm() {
    const doc = this.ruleModalDoc();
    if (doc) {
      this.confirmDocReview(doc, true);
    }
  }
}
