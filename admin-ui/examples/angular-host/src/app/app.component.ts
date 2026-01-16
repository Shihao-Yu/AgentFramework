import {
  Component,
  ElementRef,
  ViewChild,
  AfterViewInit,
  OnDestroy,
  CUSTOM_ELEMENTS_SCHEMA,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

interface EventLog {
  type: string;
  detail: unknown;
  time: string;
}

interface AdminUIWidgetElement extends HTMLElement {
  navigate(path: string): void;
  refresh(): void;
  setTheme(theme: 'light' | 'dark' | 'system'): void;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
  template: `
    <div class="app">
      <header class="header">
        <h1>Angular Host App (Angular 17)</h1>
        <nav class="nav-buttons">
          <button
            *ngFor="let route of routes"
            [class.active]="currentRoute === route.path"
            (click)="navigateTo(route.path)"
          >
            {{ route.label }}
          </button>
        </nav>
      </header>

      <div class="controls">
        <div class="control-group">
          <label>Theme:</label>
          <select [(ngModel)]="theme" (ngModelChange)="onThemeChange($event)">
            <option value="system">System</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </div>
        <div class="control-group">
          <label>API URL:</label>
          <input type="text" [(ngModel)]="apiUrl" style="width: 200px" />
        </div>
        <div class="control-group">
          <label>Tenant:</label>
          <input type="text" [(ngModel)]="tenantId" style="width: 120px" />
        </div>
      </div>

      <div class="widget-container">
        <context-management-widget
          #adminWidget
          [attr.api-base-url]="apiUrl"
          [attr.tenant-id]="tenantId"
          [attr.initial-route]="currentRoute"
          [attr.theme]="theme"
        ></context-management-widget>
      </div>

      <div class="events-panel">
        <h3>Events from Widget ({{ events.length }})</h3>
        <div *ngIf="events.length === 0" class="event-item" style="opacity: 0.5">
          Waiting for events...
        </div>
        <div *ngFor="let event of events" class="event-item">
          <span class="event-time">[{{ event.time }}]</span>
          <span class="event-type">{{ event.type }}</span>
          <span>{{ event.detail | json }}</span>
        </div>
      </div>
    </div>
  `,
  styles: [
    `
      .app {
        min-height: 100vh;
        display: flex;
        flex-direction: column;
      }

      .header {
        background: linear-gradient(135deg, #dc2626 0%, #9333ea 100%);
        color: white;
        padding: 16px 24px;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .header h1 {
        font-size: 20px;
        font-weight: 600;
      }

      .nav-buttons {
        display: flex;
        gap: 8px;
      }

      .nav-buttons button {
        padding: 8px 16px;
        border: none;
        border-radius: 6px;
        background: rgba(255, 255, 255, 0.2);
        color: white;
        cursor: pointer;
        font-size: 14px;
        transition: background 0.2s;
      }

      .nav-buttons button:hover {
        background: rgba(255, 255, 255, 0.3);
      }

      .nav-buttons button.active {
        background: white;
        color: #dc2626;
      }

      .controls {
        background: white;
        padding: 12px 24px;
        border-bottom: 1px solid #e5e5e5;
        display: flex;
        gap: 16px;
        align-items: center;
      }

      .control-group {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .control-group label {
        font-size: 14px;
        color: #666;
      }

      .control-group select,
      .control-group input {
        padding: 6px 12px;
        border: 1px solid #ddd;
        border-radius: 4px;
        font-size: 14px;
      }

      .widget-container {
        flex: 1;
        min-height: 600px;
      }

      context-management-widget {
        display: block;
        width: 100%;
        height: 100%;
        min-height: 600px;
      }

      .events-panel {
        background: #1a1a2e;
        color: white;
        padding: 16px 24px;
        max-height: 200px;
        overflow-y: auto;
      }

      .events-panel h3 {
        font-size: 14px;
        margin-bottom: 12px;
        opacity: 0.7;
      }

      .event-item {
        font-family: monospace;
        font-size: 12px;
        padding: 4px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      }

      .event-item:last-child {
        border-bottom: none;
      }

      .event-type {
        color: #f472b6;
        margin-right: 8px;
      }

      .event-time {
        color: #a78bfa;
        margin-right: 8px;
      }
    `,
  ],
})
export class AppComponent implements AfterViewInit, OnDestroy {
  @ViewChild('adminWidget') widgetRef!: ElementRef<AdminUIWidgetElement>;

  routes = [
    { path: '/', label: 'FAQs' },
    { path: '/graph', label: 'Graph' },
    { path: '/permissions', label: 'Permissions' },
    { path: '/schemas', label: 'Schemas' },
    { path: '/analytics', label: 'Analytics' },
  ];

  currentRoute = '/';
  theme: 'light' | 'dark' | 'system' = 'system';
  apiUrl = 'http://localhost:8000';
  tenantId = 'demo-tenant';
  events: EventLog[] = [];

  private eventListeners: Array<{ type: string; handler: EventListener }> = [];

  ngAfterViewInit(): void {
    const widget = this.widgetRef.nativeElement;
    const eventTypes = [
      'ready',
      'config-changed',
      'route-changed',
      'faq-created',
      'faq-updated',
      'faq-deleted',
      'node-selected',
      'error',
    ];

    eventTypes.forEach((type) => {
      const handler = (e: Event) => {
        this.logEvent(type, (e as CustomEvent).detail);
      };
      widget.addEventListener(type, handler);
      this.eventListeners.push({ type, handler });
    });
  }

  ngOnDestroy(): void {
    const widget = this.widgetRef?.nativeElement;
    if (widget) {
      this.eventListeners.forEach(({ type, handler }) => {
        widget.removeEventListener(type, handler);
      });
    }
  }

  navigateTo(path: string): void {
    this.currentRoute = path;
    const widget = this.widgetRef?.nativeElement;
    if (widget) {
      widget.setAttribute('initial-route', path);
      widget.refresh();
    }
  }

  onThemeChange(theme: 'light' | 'dark' | 'system'): void {
    this.widgetRef?.nativeElement?.setTheme(theme);
  }

  private logEvent(type: string, detail: unknown): void {
    this.events = [
      {
        type,
        detail,
        time: new Date().toLocaleTimeString(),
      },
      ...this.events,
    ].slice(0, 50);
  }
}
