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
  templateUrl: './review.component.html'
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
