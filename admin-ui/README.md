# Knowledge Base Admin UI

Admin panel for managing a multi-type knowledge base system with AI-powered content suggestions.

## Features

- **FAQs** - Question/answer pairs with markdown support
- **Feature Permissions** - Document what permissions users need per feature
- **Schemas & Examples** - YAML schema definitions with usage examples
- **Playbooks** - Domain-specific guides and documentation
- **Staging Queue** - Review AI-generated content from support tickets
- **Metrics Dashboard** - Usage analytics and performance tracking
- **Dark/Light Theme** - System-aware theme with manual toggle

## Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Build web component
npm run build:wc
```

## Web Component Usage

The Admin UI can be embedded in Angular, React, or any web application as a custom element.

### Installation

```bash
npm install @anthropic/admin-ui-widget
```

### Basic Usage

```html
<!-- Include the script -->
<script type="module" src="path/to/admin-ui-widget.es.js"></script>

<!-- Use the component -->
<admin-ui-widget
  api-base-url="https://api.example.com"
  tenant-id="your-tenant"
  initial-route="/"
  theme="system"
></admin-ui-widget>
```

### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `api-base-url` | string | `''` | Backend API base URL |
| `tenant-id` | string | `'default'` | Tenant identifier for multi-tenant setups |
| `initial-route` | string | `'/'` | Initial page to display |
| `theme` | `'light'` \| `'dark'` \| `'system'` | `'system'` | Color theme |

### Events

The component emits the following events:

| Event | Detail | Description |
|-------|--------|-------------|
| `ready` | `{}` | Component fully initialized |
| `config-changed` | `{ attribute, oldValue, newValue }` | Configuration attribute changed |
| `route-changed` | `{ path }` | Internal navigation occurred |
| `faq-created` | `{ id, title }` | New FAQ created |
| `faq-updated` | `{ id, title }` | FAQ updated |
| `faq-deleted` | `{ id }` | FAQ deleted |
| `node-selected` | `{ id, type }` \| `null` | Graph node selected/deselected |
| `error` | `{ message, code? }` | Error occurred |

### Angular Usage

```typescript
// app.module.ts
import { CUSTOM_ELEMENTS_SCHEMA, NgModule } from '@angular/core';

@NgModule({
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
  // ...
})
export class AppModule {}

// component.ts
@Component({
  template: `
    <admin-ui-widget
      api-base-url="https://api.example.com"
      tenant-id="my-tenant"
      (faq-created)="onFaqCreated($event)"
    ></admin-ui-widget>
  `
})
export class AdminComponent {
  onFaqCreated(event: CustomEvent) {
    console.log('FAQ created:', event.detail);
  }
}
```

### React Usage

```tsx
import '@anthropic/admin-ui-widget';
import { useEffect, useRef } from 'react';

function AdminPage() {
  const widgetRef = useRef<HTMLElement>(null);
  
  useEffect(() => {
    const widget = widgetRef.current;
    if (!widget) return;
    
    const handleFaqCreated = (e: CustomEvent) => {
      console.log('FAQ created:', e.detail);
    };
    
    widget.addEventListener('faq-created', handleFaqCreated);
    return () => widget.removeEventListener('faq-created', handleFaqCreated);
  }, []);
  
  return (
    <admin-ui-widget
      ref={widgetRef}
      api-base-url="https://api.example.com"
      tenant-id="my-tenant"
    />
  );
}
```

### Methods

```javascript
const widget = document.querySelector('admin-ui-widget');

// Navigate to a specific route
widget.navigate('/graph');

// Refresh the component
widget.refresh();

// Change theme programmatically
widget.setTheme('dark');
```

### Styling

The component uses Shadow DOM for style isolation. Your host app's styles will not affect the component, and vice versa.

For best appearance, ensure these fonts are available:
- **Inter** - UI text
- **JetBrains Mono** - Code editors

### Known Limitations

**Monaco Editor Styles**: The code editor (Monaco) injects some global CSS into `document.head`. This is unavoidable due to Monaco's architecture. If your host app also uses Monaco, ensure versions are compatible.

## Tech Stack

- React 19 + TypeScript + Vite
- Tailwind CSS v4
- Radix UI / shadcn components
- TanStack Table & Query
- Monaco Editor, MDEditor
- Zod + react-hook-form

## Project Structure

```
src/
├── components/
│   ├── editors/          # Monaco, Markdown editors
│   ├── faq/              # FAQ-specific components
│   ├── graph/            # Graph visualization
│   ├── layout/           # Sidebar, AppLayout
│   ├── permissions/      # Permission components
│   ├── playbooks/        # Playbook components
│   ├── schema/           # Schema/Example components
│   └── ui/               # Base UI components (shadcn)
├── hooks/                # Data hooks
├── lib/                  # Utilities
├── pages/                # Page components
├── types/                # TypeScript types
├── AppContext.tsx        # Web component configuration context
└── web-component.tsx     # Web component entry point
```

## API Integration

See [docs/API_INTEGRATION.md](docs/API_INTEGRATION.md) for:

- Complete API endpoint specifications
- Request/response types
- Integration examples with TanStack Query
- Environment configuration

## Development

```bash
# Type check
npm run typecheck

# Lint
npm run lint

# Build standalone app
npm run build

# Build web component
npm run build:wc

# Test web component locally
# 1. Build: npm run build:wc
# 2. Open test-harness.html in browser
```

## License

Internal use only.
