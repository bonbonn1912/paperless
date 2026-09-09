import { AfterViewInit, Directive, ElementRef, EventEmitter, HostListener, OnDestroy, Output, inject } from '@angular/core';

/** Keyboard and focus behaviour shared by every modal/sheet. */
@Directive({ selector: '[appDialog]', standalone: true, host: { role: 'dialog', 'aria-modal': 'true', tabindex: '-1' } })
export class DialogDirective implements AfterViewInit, OnDestroy {
  @Output() dialogClose = new EventEmitter<void>();
  private element = inject(ElementRef) as ElementRef<HTMLElement>;
  private previous = document.activeElement as HTMLElement | null;
  private overflow = document.body.style.overflow;
  private focusable(): HTMLElement[] {
    return (Array.from(this.element.nativeElement.querySelectorAll('a[href],button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]')) as HTMLElement[]).filter(el => el.getClientRects().length > 0);
  }
  ngAfterViewInit() { document.body.style.overflow = 'hidden'; (this.focusable().find(el => el.tagName === 'INPUT') || this.focusable()[0] || this.element.nativeElement).focus(); }
  @HostListener('keydown', ['$event']) onKey(event: KeyboardEvent) {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); this.dialogClose.emit(); }
    if (event.key !== 'Tab') return;
    const items = this.focusable(); const first = items[0]; const last = items[items.length - 1];
    if (!first) { event.preventDefault(); return; }
    if (event.shiftKey && (document.activeElement === first || document.activeElement === this.element.nativeElement)) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
  @HostListener('click', ['$event']) onClick(event: MouseEvent) { if (event.target === this.element.nativeElement) this.dialogClose.emit(); }
  ngOnDestroy() { document.body.style.overflow = this.overflow; if (this.previous?.isConnected) this.previous.focus(); }
}
